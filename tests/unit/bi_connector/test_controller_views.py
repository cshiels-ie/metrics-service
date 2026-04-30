"""
Tests for BI connector Layer 2 API endpoints (live AWX DB).

Time-series views (jobs, hosts, credentials, events) are async:
  - Valid request → 202 Accepted with task_id and results_url
  - Duplicate in-flight request → 202 with the existing task_id (no new task created)
  - Bad date params → 400 before any task is created
  - Feature flag disabled → 404

Snapshot view remains synchronous:
  - Valid request → 200 with collectors/errors/collected_at
  - AWX DB unavailable → 503
  - Partial collector failure → 200 with errors dict populated
  - Feature flag disabled → 404
"""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from tests.test_utils import get_test_password

VALID_SINCE = "2025-03-01T00:00:00Z"
VALID_UNTIL_7 = "2025-03-07T23:59:59Z"  # 6 days — within 7-day limit
VALID_UNTIL_3 = "2025-03-03T23:59:59Z"  # 2 days — within 3-day limit
OVER_7_DAYS_UNTIL = "2025-03-10T00:00:00Z"  # 9 days — exceeds 7-day limit
OVER_3_DAYS_UNTIL = "2025-03-05T00:00:00Z"  # 4 days — exceeds 3-day limit

_SNAPSHOT_PATCH = "apps.tasks.collectors.collect_snapshot_metrics._get_snapshot_collectors"
_DB_PATCH = "apps.bi_connector.v1.controller_views.get_db_connection"
_FLAG_PATCH = "apps.tasks.task_groups.get_feature_enabled_from_db"
_SUBMIT_PATCH = "apps.tasks.tasks_system.submit_task_to_dispatcher"


def _make_mock_collector(data=None):
    mock = MagicMock()
    mock.gather.return_value = data or [{"id": 1}]
    return mock


# ---------------------------------------------------------------------------
# Time-series views — shared behaviour tested via the jobs endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestControllerJobsView(APITestCase):
    """Tests for GET /api/v1/controller/jobs/ — async 202 pattern."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.url = reverse("bi_connector:controller:controller-jobs")
        flag_patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = flag_patcher.start()
        self.addCleanup(flag_patcher.stop)

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_unauthenticated_returns_401_or_403(self):
        response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    # --- Date range validation (400 before any task is created) ---

    def test_missing_since_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"until": VALID_UNTIL_7})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_until_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": VALID_SINCE})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_both_params_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_since_format_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": "not-a-date", "until": VALID_UNTIL_7})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_until_before_since_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": VALID_UNTIL_7, "until": VALID_SINCE})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_range_exceeding_7_days_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": VALID_SINCE, "until": OVER_7_DAYS_UNTIL})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "7 days" in str(response.data)

    def test_range_exactly_7_days_is_allowed(self):
        # 2025-03-01T00:00:00Z to 2025-03-08T00:00:00Z is exactly 7 days — should be accepted.
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            response = self.client.get(self.url, {"since": VALID_SINCE, "until": "2025-03-08T00:00:00Z"})
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_range_7_days_plus_1_second_returns_400(self):
        # Validates the total_seconds() check catches fractional-day overruns that delta.days would miss.
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": VALID_SINCE, "until": "2025-03-08T00:00:01Z"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # --- Async 202 response ---

    def test_valid_request_returns_202_with_task_id(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "task_id" in response.data
        assert "results_url" in response.data
        assert response.data["status"] == "pending"
        assert response.data["collector_type"] == "unified_jobs"
        assert f"/api/v1/tasks/{response.data['task_id']}/" == response.data["results_url"]

    def test_task_created_with_correct_task_data(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})

        from apps.tasks.models import Task

        task = Task.objects.get(id=response.data["task_id"])
        assert task.function_name == "collect_bi_controller_data"
        assert task.task_data["collector_key"] == "unified_jobs"
        assert "2025-03-01" in task.task_data["since"]
        assert "2025-03-07" in task.task_data["until"]

    def test_duplicate_in_flight_request_returns_existing_task_id(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            first = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})
            second = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})

        assert first.status_code == status.HTTP_202_ACCEPTED
        assert second.status_code == status.HTTP_202_ACCEPTED
        assert first.data["task_id"] == second.data["task_id"]

        from apps.tasks.models import Task

        assert Task.objects.filter(function_name="collect_bi_controller_data").count() == 1

    def test_different_date_range_creates_new_task(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            first = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})
            second = self.client.get(self.url, {"since": "2025-04-01T00:00:00Z", "until": "2025-04-06T00:00:00Z"})

        assert first.data["task_id"] != second.data["task_id"]

        from apps.tasks.models import Task

        assert Task.objects.filter(function_name="collect_bi_controller_data").count() == 2

    def test_submit_to_dispatcher_called(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH) as mock_submit:
            self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})

        mock_submit.assert_called_once()


@pytest.mark.unit
@pytest.mark.django_db
class TestControllerHostsView(APITestCase):
    """Tests for GET /api/v1/controller/hosts/ — spot-checks the async pattern."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.url = reverse("bi_connector:controller:controller-hosts")
        flag_patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = flag_patcher.start()
        self.addCleanup(flag_patcher.stop)

    def test_missing_params_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_valid_request_returns_202_with_correct_collector_type(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["collector_type"] == "job_host_summary_service"


@pytest.mark.unit
@pytest.mark.django_db
class TestControllerCredentialsView(APITestCase):
    """Tests for GET /api/v1/controller/credentials/ — spot-checks the async pattern."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.url = reverse("bi_connector:controller:controller-credentials")
        flag_patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = flag_patcher.start()
        self.addCleanup(flag_patcher.stop)

    def test_missing_params_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_valid_request_returns_202_with_correct_collector_type(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["collector_type"] == "credentials_service"


@pytest.mark.unit
@pytest.mark.django_db
class TestControllerEventsView(APITestCase):
    """Tests for GET /api/v1/controller/events/ — tighter 3-day window."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.url = reverse("bi_connector:controller:controller-events")
        flag_patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = flag_patcher.start()
        self.addCleanup(flag_patcher.stop)

    def test_range_exceeding_3_days_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": VALID_SINCE, "until": OVER_3_DAYS_UNTIL})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "3 days" in str(response.data)

    def test_range_within_7_days_but_over_3_also_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_7})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_valid_3_day_range_returns_202(self):
        self.client.force_authenticate(user=self.user)
        with patch(_SUBMIT_PATCH):
            response = self.client.get(self.url, {"since": VALID_SINCE, "until": VALID_UNTIL_3})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["collector_type"] == "main_jobevent_service"


# ---------------------------------------------------------------------------
# Snapshot view — stays synchronous
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestControllerSnapshotView(APITestCase):
    """Tests for GET /api/v1/controller/snapshot/ — synchronous, unchanged."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.url = reverse("bi_connector:controller:controller-snapshot")
        flag_patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = flag_patcher.start()
        self.addCleanup(flag_patcher.stop)

    def _make_snapshot_registry(self, collectors=None):
        if collectors is None:
            collectors = ["execution_environments", "controller_version_service", "table_metadata", "config"]

        def _make_func(collector_type):
            def collector_func(**kw):
                return _make_mock_collector(data={"type": collector_type})

            return collector_func

        return {c: {"collector_func": _make_func(c)} for c in collectors}

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_returns_401_or_403(self):
        response = self.client.get(self.url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_awx_db_unavailable_returns_503(self):
        self.client.force_authenticate(user=self.user)
        with patch(_DB_PATCH, side_effect=Exception("no conn")):
            response = self.client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_all_collectors_success_returns_200(self):
        self.client.force_authenticate(user=self.user)
        registry = self._make_snapshot_registry()

        with patch(_DB_PATCH, return_value=MagicMock()), patch(_SNAPSHOT_PATCH, return_value=registry):
            response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert "collectors" in response.data
        assert "errors" in response.data
        assert "collected_at" in response.data
        assert response.data["errors"] == {}

    def test_partial_collector_failure_returns_200_with_errors(self):
        self.client.force_authenticate(user=self.user)
        failing_mock = MagicMock()
        failing_mock.gather.side_effect = Exception("DB error")

        registry = {
            "execution_environments": {"collector_func": lambda **kw: _make_mock_collector()},
            "controller_version_service": {"collector_func": lambda **kw: failing_mock},
            "table_metadata": {"collector_func": lambda **kw: _make_mock_collector()},
            "config": {"collector_func": lambda **kw: _make_mock_collector()},
        }

        with patch(_DB_PATCH, return_value=MagicMock()), patch(_SNAPSHOT_PATCH, return_value=registry):
            response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert "controller_version_service" in response.data["errors"]
        assert "execution_environments" in response.data["collectors"]

    def test_collectors_query_param_subsets_results(self):
        self.client.force_authenticate(user=self.user)
        registry = self._make_snapshot_registry()

        with patch(_DB_PATCH, return_value=MagicMock()), patch(_SNAPSHOT_PATCH, return_value=registry):
            response = self.client.get(self.url, {"collectors": "config"})

        assert response.status_code == status.HTTP_200_OK
        assert "config" in response.data["collectors"]
        assert "execution_environments" not in response.data["collectors"]

    def test_unknown_collector_in_query_param_returns_error_entry(self):
        self.client.force_authenticate(user=self.user)
        registry = self._make_snapshot_registry(["execution_environments"])

        with patch(_DB_PATCH, return_value=MagicMock()), patch(_SNAPSHOT_PATCH, return_value=registry):
            response = self.client.get(self.url, {"collectors": "execution_environments,nonexistent"})

        assert response.status_code == status.HTTP_200_OK
        assert "nonexistent" in response.data["errors"]
