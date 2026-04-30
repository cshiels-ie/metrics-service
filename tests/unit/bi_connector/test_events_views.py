"""
Tests for BI connector events API endpoints.

Covers JobEventViewSet and DailyEventSummaryViewSet:
- Feature flag disabled → 404
- Authentication enforcement
- Required since/until query params
- Date range window enforcement
- Additional query param filters (job_id, host_name, task_action, failed)
- Read-only enforcement (write methods rejected)
- summary_date used as lookup field for daily-summary detail
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from tests.test_utils import get_test_password

_FLAG_PATCH = "apps.tasks.task_groups.get_feature_enabled_from_db"


def _make_since_until(days_back=3):
    """Return ISO 8601 since/until strings covering a valid window."""
    until = timezone.now()
    since = until - timedelta(days=days_back)
    return since.isoformat(), until.isoformat()


@pytest.mark.unit
@pytest.mark.django_db
class TestJobEventViewSet(APITestCase):
    """Tests for GET /api/v1/bi/events/ and /api/v1/bi/events/<id>/"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.since, self.until = _make_since_until()

    def _create_event(self, **kwargs):
        from apps.events.models import JobEvent

        defaults = {
            "awx_event_id": 1,
            "job_id": 100,
            "job_created": timezone.now() - timedelta(days=2),
            "event_type": "runner_on_ok",
            "counter": 1,
            "failed": False,
            "changed": False,
            "task_action": "ansible.builtin.command",
            "task": "Run command",
            "role": "",
            "host_name": "host1.example.com",
            "duration": Decimal("0.123456"),
            "awx_created": timezone.now() - timedelta(days=2),
        }
        defaults.update(kwargs)
        return JobEvent.objects.create(**defaults)

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_list_requires_authentication(self):
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK

    # --- Date range enforcement ---

    def test_missing_since_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"until": self.until})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_until_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_both_since_and_until_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_until_before_since_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        since = timezone.now().isoformat()
        until = (timezone.now() - timedelta(days=1)).isoformat()
        response = self.client.get(url, {"since": since, "until": until})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_window_exceeding_max_days_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        since = (timezone.now() - timedelta(days=30)).isoformat()
        until = timezone.now().isoformat()
        response = self.client.get(url, {"since": since, "until": until})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # --- Serializer fields ---

    def test_list_returns_expected_fields(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=42)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        expected_fields = {
            "id",
            "awx_event_id",
            "job_id",
            "job_created",
            "event_type",
            "counter",
            "failed",
            "changed",
            "task_action",
            "task",
            "role",
            "host_name",
            "duration",
            "awx_created",
        }
        assert expected_fields.issubset(set(result.keys()))

    def test_list_excludes_collected_at(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=99)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert "collected_at" not in result

    # --- Additional filters ---

    def test_filter_by_job_id(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=1, job_id=100)
        self._create_event(awx_event_id=2, job_id=200)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until, "job_id": 100})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["job_id"] == 100

    def test_filter_by_host_name(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=1, host_name="host1.example.com")
        self._create_event(awx_event_id=2, host_name="host2.example.com")
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until, "host_name": "host1.example.com"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["host_name"] == "host1.example.com"

    def test_filter_by_task_action(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=1, task_action="ansible.builtin.command")
        self._create_event(awx_event_id=2, task_action="ansible.builtin.copy")
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(
            url, {"since": self.since, "until": self.until, "task_action": "ansible.builtin.command"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_by_failed_true(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=1, failed=True)
        self._create_event(awx_event_id=2, failed=False)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until, "failed": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["failed"] is True

    def test_filter_by_failed_false(self):
        self.client.force_authenticate(user=self.user)
        self._create_event(awx_event_id=1, failed=True)
        self._create_event(awx_event_id=2, failed=False)
        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until, "failed": "false"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["failed"] is False

    # --- Date range filtering ---

    def test_events_outside_date_range_excluded(self):
        self.client.force_authenticate(user=self.user)
        # Create event with awx_created 30 days ago — outside the 7-day window
        old_ts = timezone.now() - timedelta(days=30)
        self._create_event(awx_event_id=1, awx_created=old_ts)
        # Create event within range
        recent_ts = timezone.now() - timedelta(days=2)
        self._create_event(awx_event_id=2, awx_created=recent_ts)

        url = reverse("bi_connector:events:events-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    # --- Read-only enforcement ---

    def test_post_returns_405(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-list")
        response = self.client.post(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_returns_405(self):
        self.client.force_authenticate(user=self.user)
        event = self._create_event(awx_event_id=1)
        url = reverse("bi_connector:events:events-detail", kwargs={"pk": event.pk})
        response = self.client.put(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self):
        self.client.force_authenticate(user=self.user)
        event = self._create_event(awx_event_id=1)
        url = reverse("bi_connector:events:events-detail", kwargs={"pk": event.pk})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.unit
@pytest.mark.django_db
class TestDailyEventSummaryViewSet(APITestCase):
    """Tests for GET /api/v1/bi/events/daily-summary/ and /api/v1/bi/events/daily-summary/<summary_date>/"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = patcher.start()
        self.addCleanup(patcher.stop)
        # Use date-only strings — DailyEventSummary filters on summary_date (DateField)
        self.since = (date.today() - timedelta(days=5)).isoformat()
        self.until = date.today().isoformat()

    def _create_summary(self, summary_date=None, **kwargs):
        from apps.events.models import DailyEventSummary

        if summary_date is None:
            summary_date = date.today() - timedelta(days=2)
        if isinstance(summary_date, str):
            summary_date = date.fromisoformat(summary_date)
        defaults = {
            "summary_date": summary_date,
            "total_events": 100,
            "failed_events": 5,
            "changed_events": 20,
            "unique_hosts": 3,
            "top_task_actions": {"ansible.builtin.command": 50},
            "duration_stats": {"mean": 0.5, "max": 2.0},
            "jobs_covered": 10,
        }
        defaults.update(kwargs)
        return DailyEventSummary.objects.create(**defaults)

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_list_requires_authentication(self):
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK

    # --- Date range enforcement ---

    def test_missing_since_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"until": self.until})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_until_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"since": self.since})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # --- Serializer fields ---

    def test_list_returns_expected_fields(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary()
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        expected_fields = {
            "id",
            "summary_date",
            "total_events",
            "failed_events",
            "changed_events",
            "unique_hosts",
            "top_task_actions",
            "duration_stats",
            "jobs_covered",
            "created_at",
        }
        assert expected_fields.issubset(set(result.keys()))

    # --- Date range filtering ---

    def test_summaries_outside_date_range_excluded(self):
        self.client.force_authenticate(user=self.user)
        # Create summary 30 days ago — outside the window
        old_date = date.today() - timedelta(days=30)
        self._create_summary(summary_date=old_date)
        # Create summary within range
        recent_date = date.today() - timedelta(days=2)
        self._create_summary(summary_date=recent_date)

        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.get(url, {"since": self.since, "until": self.until})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    # --- Detail endpoint (summary_date as lookup) ---

    def test_detail_uses_summary_date_as_lookup_field(self):
        self.client.force_authenticate(user=self.user)
        target_date = date.today() - timedelta(days=2)
        self._create_summary(summary_date=target_date)
        url = reverse("bi_connector:events:events-daily-summary-detail", kwargs={"summary_date": str(target_date)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["summary_date"]) == str(target_date)

    def test_detail_not_found_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-daily-summary-detail", kwargs={"summary_date": "1999-01-01"})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Read-only enforcement ---

    def test_post_returns_405(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:events:events-daily-summary-list")
        response = self.client.post(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self):
        self.client.force_authenticate(user=self.user)
        summary = self._create_summary()
        url = reverse(
            "bi_connector:events:events-daily-summary-detail",
            kwargs={"summary_date": str(summary.summary_date)},
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
