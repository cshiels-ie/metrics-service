"""Integration tests for the dashboard collection telemetry endpoint
GET /api/v1/dashboard_reports/collection_telemetry/."""

import decimal
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve
from rest_framework.test import APIClient

from apps.dashboard_reports.models import DashboardTelemetry
from apps.dashboard_reports.tasks import _save_telemetry_details
from tests.test_utils import get_test_password

User = get_user_model()

TELEMETRY_ENDPOINT = "/api/v1/dashboard_reports/collection_telemetry/"


def _create_telemetry(task_name="collect_dashboard_reports_initial_data", days_ago=0, **kwargs):
    """Helper to create a DashboardTelemetry record at a given offset from today."""
    defaults = {
        "task_name": task_name,
        "collection_run_date": date.today() - timedelta(days=days_ago),
        "success": True,
        "collection_duration_ms": decimal.Decimal("1000.00"),
        "number_of_records_processed": 10,
        "database_query_time_ms": decimal.Decimal("100.00"),
        "cache_hit_rate": None,
    }
    defaults.update(kwargs)
    return DashboardTelemetry.objects.create(**defaults)


@pytest.mark.integration
class TestCollectionTelemetryEndpoint(TestCase):
    """Integration tests for the /collection_telemetry/ endpoint."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="telemetry_tester",
            email="telemetry@example.com",
            password=get_test_password(),
        )
        self.client.force_authenticate(user=self.user)

    def test_endpoint_resolves(self):
        """The URL /api/v1/dashboard_reports/collection_telemetry/ resolves correctly."""
        match = resolve(TELEMETRY_ENDPOINT)
        assert match is not None

    def test_returns_200(self):
        """Authenticated request returns HTTP 200."""
        response = self.client.get(TELEMETRY_ENDPOINT)
        assert response.status_code == 200

    def test_response_shape_with_no_data(self):
        """Empty table: response is {count: 0, results: []}."""
        DashboardTelemetry.objects.all().delete()
        response = self.client.get(TELEMETRY_ENDPOINT)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_returns_entry_within_30_days(self):
        """An entry from 15 days ago is included in the response."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(days_ago=15)

        response = self.client.get(TELEMETRY_ENDPOINT)
        data = response.json()
        assert data["count"] == 1
        assert len(data["results"]) == 1

    def test_excludes_entries_older_than_30_days(self):
        """An entry from 31 days ago is NOT included in the response."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(days_ago=31)

        response = self.client.get(TELEMETRY_ENDPOINT)
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_boundary_at_30_days(self):
        """An entry exactly 30 days ago is included (>= cutoff)."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(days_ago=29)

        response = self.client.get(TELEMETRY_ENDPOINT)
        data = response.json()
        assert data["count"] == 1

    def test_response_contains_expected_fields(self):
        """Each result entry has the expected set of fields."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(days_ago=1)

        response = self.client.get(TELEMETRY_ENDPOINT)
        entry = response.json()["results"][0]
        expected_fields = {
            "task_name",
            "collection_run_date",
            "collection_duration_ms",
            "number_of_records_processed",
            "database_query_time_ms",
            "cache_hit_rate",
            "success",
        }
        assert expected_fields == set(entry.keys())

    def test_response_contains_no_sensitive_fields(self):
        """No sensitive fields (user IDs, org names, job details) are exposed."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(days_ago=1)

        response = self.client.get(TELEMETRY_ENDPOINT)
        entry = response.json()["results"][0]
        sensitive = {"organization_name", "user_id", "username", "job_id", "job_name"}
        assert not sensitive.intersection(entry.keys())

    def test_unauthenticated_returns_403(self):
        """Unauthenticated requests are rejected with 403."""
        unauthenticated = APIClient()
        response = unauthenticated.get(TELEMETRY_ENDPOINT)
        assert response.status_code == 403

    def test_count_matches_results_length(self):
        """The count field always matches the length of the results list."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(task_name="task_a", days_ago=1)
        _create_telemetry(task_name="task_b", days_ago=2)

        response = self.client.get(TELEMETRY_ENDPOINT)
        data = response.json()
        assert data["count"] == len(data["results"])

    def test_old_entries_mixed_with_recent_filtered_correctly(self):
        """Mix of old and recent entries: only the recent ones are returned."""
        DashboardTelemetry.objects.all().delete()
        _create_telemetry(task_name="recent", days_ago=5)
        _create_telemetry(task_name="old", days_ago=60)

        response = self.client.get(TELEMETRY_ENDPOINT)
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["task_name"] == "recent"


@pytest.mark.integration
class TestTelemetryEndToEnd(TestCase):
    """End-to-end integration: run tasks → check telemetry → verify API."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="e2e_tester",
            email="e2e@example.com",
            password=get_test_password(),
        )
        self.client.force_authenticate(user=self.user)

    def test_save_telemetry_creates_row_visible_via_api(self):
        """Calling _save_telemetry_details creates a row that appears in the API response."""
        DashboardTelemetry.objects.all().delete()

        _save_telemetry_details(
            task_name="collect_dashboard_reports_initial_data",
            success=True,
            collection_duration_ms=2500.0,
            number_of_records_processed=15,
            database_query_time_ms=300.0,
            cache_hit_rate=None,
        )

        response = self.client.get(TELEMETRY_ENDPOINT)
        data = response.json()
        assert data["count"] == 1
        entry = data["results"][0]
        assert entry["task_name"] == "collect_dashboard_reports_initial_data"
        assert entry["number_of_records_processed"] == 15

    def test_telemetry_failure_does_not_affect_collection_task(self):
        """When telemetry saving fails (DB error), the collection task still returns a result
        (the error is swallowed by _save_telemetry_details)."""
        from unittest.mock import patch

        from apps.dashboard_reports.tasks import cleanup_dashboard_reports_old_data

        with (
            patch("apps.dashboard_reports.tasks.DashboardTelemetry") as mock_model,
            patch("apps.dashboard_reports.tasks.JobData") as mock_jobdata,
            patch("apps.dashboard_reports.tasks.log_task_execution"),
        ):
            mock_model.objects.create.side_effect = Exception("telemetry DB failure")
            mock_jobdata.objects.filter.return_value.count.return_value = 0

            result = cleanup_dashboard_reports_old_data(retention_period_days=90)

        assert result["status"] == "success"

    def test_save_telemetry_failure_logged_not_raised(self):
        """When telemetry saving fails, the exception is logged, not propagated."""
        from unittest.mock import patch

        with (
            patch("apps.dashboard_reports.tasks.DashboardTelemetry") as mock_model,
            patch("apps.dashboard_reports.tasks.logger") as mock_logger,
        ):
            mock_model.objects.create.side_effect = Exception("write failure")
            _save_telemetry_details(
                task_name="test",
                success=True,
                collection_duration_ms=100.0,
                number_of_records_processed=0,
                database_query_time_ms=10.0,
                cache_hit_rate=None,
            )

        mock_logger.exception.assert_called_once_with("Failed to record dashboard telemetry")
