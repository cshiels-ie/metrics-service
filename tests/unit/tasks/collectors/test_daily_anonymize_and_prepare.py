"""
Unit tests for apps/tasks/collectors/daily_anonymize_and_prepare.py

Tests cover:
- Success path with payload creation
- Atomic transaction handling
- Daily summary status updates
- Missing summary error handling
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.tasks.collectors.daily_anonymize_and_prepare import daily_anonymize_and_prepare


@pytest.mark.unit
@pytest.mark.django_db
class TestDailyAnonymizeAndPrepare:
    """Test daily_anonymize_and_prepare task."""

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_success_path_creates_payload(self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory):
        """Test successful anonymization creates AnonymizedMetricsPayload."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)
        mock_salt = "test-salt-123"
        mock_generate_salt.return_value = mock_salt

        daily_summary = daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {"test": "rollup1"},
                "main_jobevent_service": {"test": "rollup2"},
                "unified_jobs": {"test": "rollup3"},
                "execution_environments": {"test": "rollup4"},
                "credentials_service": {"test": "rollup5"},
            },
            hourly_collections_count=24,
            missing_hours=[],
            aggregation_completed_at=timezone.now(),
        )

        mock_anonymized = {
            "statistics": {"total": 100},
            "jobs_by_template": [],
        }
        mock_anonymize_rollups.return_value = mock_anonymized

        # Act
        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert
        assert result["status"] == "success"
        assert result["task_type"] == "daily_anonymize_and_prepare"

        # Verify payload was created
        from apps.tasks.models import AnonymizedMetricsPayload

        payload = AnonymizedMetricsPayload.objects.get(id=result["payload_id"])
        assert payload.summary_date == summary_date
        assert payload.status == "pending"
        assert payload.daily_summary == daily_summary

        # Verify anonymized data includes required sections
        assert "statistics" in payload.anonymized_data
        assert "summary_metadata" in payload.anonymized_data

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_updates_daily_summary_status_to_anonymized(
        self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory
    ):
        """Test daily summary status is updated to 'anonymized'."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)
        daily_summary = daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
        )

        mock_anonymize_rollups.return_value = {"test": "data"}
        mock_generate_salt.return_value = "test-salt"

        # Act
        daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert
        daily_summary.refresh_from_db()
        assert daily_summary.status == "anonymized"

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_uses_atomic_transaction(self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory):
        """Test uses atomic transaction by simulating database error."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)
        daily_summary = daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
        )

        mock_anonymize_rollups.return_value = {"test": "data"}
        mock_generate_salt.return_value = "test-salt"

        # Simulate database error during payload creation
        from apps.tasks.models import AnonymizedMetricsPayload

        with patch.object(AnonymizedMetricsPayload.objects, "create", side_effect=Exception("Database error")):
            # Act
            result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert - transaction should rollback, error returned
        assert result["status"] == "error"
        assert "Database error" in result["error"]

        # Summary status should remain 'aggregated' (transaction rolled back)
        daily_summary.refresh_from_db()
        assert daily_summary.status == "aggregated"

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_adds_summary_metadata(self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory):
        """Test adds summary metadata to anonymized data."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)
        aggregation_time = timezone.now()

        daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
            hourly_collections_count=23,
            missing_hours=[5],
            aggregation_completed_at=aggregation_time,
        )

        mock_anonymize_rollups.return_value = {"statistics": {}}
        mock_generate_salt.return_value = "test-salt"

        # Act
        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert
        from apps.tasks.models import AnonymizedMetricsPayload

        payload = AnonymizedMetricsPayload.objects.get(id=result["payload_id"])
        metadata = payload.anonymized_data["summary_metadata"]

        assert metadata["summary_date"] == str(summary_date)
        assert metadata["hourly_collections_count"] == 23
        assert metadata["missing_hours"] == [5]
        assert metadata["aggregation_timestamp"] == aggregation_time.isoformat()

    def test_handles_missing_daily_summary(self):
        """Test handles DailyMetricsSummary.DoesNotExist exception."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)
        # No daily summary created

        # Act
        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert
        assert result["status"] == "error"
        assert "No daily summary found" in result["error"]
        assert summary_date.isoformat() in result["error"]

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_defaults_to_yesterday_when_no_date_provided(
        self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory
    ):
        """Test defaults to yesterday's date when no summary_date provided."""
        # Arrange
        yesterday = timezone.now().date() - timedelta(days=1)

        daily_summary_factory(
            summary_date=yesterday,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
        )

        mock_anonymize_rollups.return_value = {"statistics": {}}
        mock_generate_salt.return_value = "test-salt"

        # Act - no summary_date provided
        result = daily_anonymize_and_prepare()

        # Assert
        assert result["status"] == "success"
        assert result["summary_date"] == str(yesterday)

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_sets_custom_event_name_when_provided(
        self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory
    ):
        """Test sets custom event name when provided in kwargs."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)
        custom_event_name = "Custom Event Name"

        daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
        )

        mock_anonymize_rollups.return_value = {"statistics": {}}
        mock_generate_salt.return_value = "test-salt"

        # Act
        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat(), event_name=custom_event_name)

        # Assert
        from apps.tasks.models import AnonymizedMetricsPayload

        payload = AnonymizedMetricsPayload.objects.get(id=result["payload_id"])
        assert payload.segment_event_name == custom_event_name

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_sets_default_event_name_when_not_provided(
        self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory
    ):
        """Test sets default event name with today's date when not provided."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)

        daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
        )

        mock_anonymize_rollups.return_value = {"statistics": {}}
        mock_generate_salt.return_value = "test-salt"

        # Act
        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert
        from apps.tasks.models import AnonymizedMetricsPayload

        payload = AnonymizedMetricsPayload.objects.get(id=result["payload_id"])
        expected_event_name = "Controller Metrics Daily Rollup"
        assert payload.segment_event_name == expected_event_name

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_handles_general_exception(self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory):
        """Test handles general exceptions during anonymization."""
        # Arrange
        summary_date = timezone.now().date() - timedelta(days=1)

        daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={
                "job_host_summary_service": {},
                "unified_jobs": {},
                "execution_environments": {},
            },
        )

        mock_generate_salt.return_value = "test-salt"
        mock_anonymize_rollups.side_effect = Exception("Anonymization error")

        # Act
        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        # Assert
        assert result["status"] == "error"
        assert "Anonymization failed" in result["error"]
        assert "Anonymization error" in result["error"]

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_creates_send_task_on_success(self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory):
        """Test a one-time send_anonymized_to_segment Task is created after successful anonymization."""
        summary_date = timezone.now().date() - timedelta(days=1)
        mock_generate_salt.return_value = "test-salt"
        mock_anonymize_rollups.return_value = {"statistics": {}}

        daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={"job_host_summary_service": {}, "unified_jobs": {}, "execution_environments": {}},
        )

        now = timezone.now()
        with patch("apps.tasks.collectors.daily_anonymize_and_prepare.timezone.now", return_value=now):
            result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        from apps.tasks.models import Task

        assert result["status"] == "success"
        task = Task.objects.get(function_name="send_anonymized_to_segment")
        assert task.task_data["payload_id"] == result["payload_id"]
        assert now < task.scheduled_time <= now + timedelta(minutes=240)

    @patch("metrics_utility.anonymized_rollups.anonymize_rollups")
    @patch("apps.tasks.collectors.daily_anonymize_and_prepare.generate_salt")
    def test_send_task_not_created_when_anonymization_fails(
        self, mock_generate_salt, mock_anonymize_rollups, daily_summary_factory
    ):
        """Test no send task is created when anonymization raises an exception."""
        summary_date = timezone.now().date() - timedelta(days=1)
        mock_generate_salt.return_value = "test-salt"
        mock_anonymize_rollups.side_effect = Exception("boom")

        daily_summary_factory(
            summary_date=summary_date,
            status="aggregated",
            aggregated_metrics={"job_host_summary_service": {}, "unified_jobs": {}, "execution_environments": {}},
        )

        result = daily_anonymize_and_prepare(summary_date=summary_date.isoformat())

        from apps.tasks.models import Task

        assert result["status"] == "error"
        assert not Task.objects.filter(function_name="send_anonymized_to_segment").exists()

    @patch("uuid.UUID")
    def test_jitter_offset_is_not_deterministic(self, mock_uuid):
        """Jitter offset is random, not derived from installation UUID."""
        mock_uuid.return_value = "12345678-1234-5678-9012-123456789012"

        from apps.tasks.collectors.daily_anonymize_and_prepare import random_offset

        result = random_offset()
        assert 1 <= result <= 240
        mock_uuid.assert_not_called()
