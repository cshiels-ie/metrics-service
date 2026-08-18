"""
Advanced tests for tasks_collector.py to improve code coverage.

This test file focuses on covering helper functions and advanced workflows
that aren't covered by the basic comprehensive tests.
"""

from datetime import UTC, date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.tasks.collectors.daily_metrics_rollup import daily_metrics_rollup
from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment


def _make_mock_collector_registry(collector_type: str):
    """Return a minimal collector registry that never touches a real DB."""
    mock_collector = MagicMock()
    mock_collector.gather.return_value = {}
    return {
        collector_type: {
            "collector_func": lambda **kw: mock_collector,
            "rollup_processor": None,
            "description": "test",
        }
    }


@pytest.mark.unit
@pytest.mark.django_db
class TestHourlyCollectionTasks:
    """Test that collect_hourly_metrics uses a scheduler-injected hour_timestamp correctly."""

    def test_uses_provided_hour_timestamp(self):
        """When hour_timestamp is supplied (as injected by the scheduler), it must be used as-is."""
        fixed_ts = "2024-01-15T13:00:00+00:00"

        with (
            patch(
                "apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors",
                return_value=_make_mock_collector_registry("unified_jobs"),
            ),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            from apps.tasks.collectors.collect_hourly_metrics import collect_hourly_metrics

            result = collect_hourly_metrics(collector_type="unified_jobs", hour_timestamp=fixed_ts)

        assert result["status"] == "success"
        assert result["timestamp"] == fixed_ts

    def test_retry_with_injected_timestamp_ignores_wall_clock(self):
        """A retry that supplies the original hour_timestamp must collect the same window even if wall clock has advanced."""
        pinned_ts = "2024-01-15T13:00:00+00:00"
        later_now = timezone.now() + timedelta(hours=3)

        with (
            patch(
                "apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors",
                return_value=_make_mock_collector_registry("unified_jobs"),
            ),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
            patch("apps.tasks.collectors.collect_hourly_metrics.timezone") as mock_tz,
        ):
            mock_tz.now.return_value = later_now
            from apps.tasks.collectors.collect_hourly_metrics import collect_hourly_metrics

            result = collect_hourly_metrics(collector_type="unified_jobs", hour_timestamp=pinned_ts)

        assert result["status"] == "success"
        assert result["timestamp"] == pinned_ts


@pytest.mark.unit
@pytest.mark.django_db
class TestSnapshotCollectionTasks:
    """Test that collect_snapshot_metrics uses a scheduler-injected collection_timestamp correctly."""

    def test_uses_provided_collection_timestamp(self):
        """When collection_timestamp is supplied (as injected by the scheduler), it must be used as-is."""
        fixed_ts = "2024-01-14T23:00:00+00:00"

        with (
            patch(
                "apps.tasks.collectors.collect_snapshot_metrics._get_snapshot_collectors",
                return_value=_make_mock_collector_registry("config"),
            ),
            patch("apps.tasks.collectors.collect_snapshot_metrics.get_db_connection", return_value=MagicMock()),
        ):
            from apps.tasks.collectors.collect_snapshot_metrics import collect_snapshot_metrics

            result = collect_snapshot_metrics(collector_type="config", collection_timestamp=fixed_ts)

        assert result["status"] == "success"

    def test_retry_with_injected_timestamp_ignores_wall_clock(self):
        """A retry that supplies the original collection_timestamp must collect the same window even if wall clock has advanced."""
        pinned_ts = "2024-01-14T23:00:00+00:00"
        later_now = timezone.now() + timedelta(days=2)

        with (
            patch(
                "apps.tasks.collectors.collect_snapshot_metrics._get_snapshot_collectors",
                return_value=_make_mock_collector_registry("config"),
            ),
            patch("apps.tasks.collectors.collect_snapshot_metrics.get_db_connection", return_value=MagicMock()),
            patch("apps.tasks.collectors.collect_snapshot_metrics.timezone") as mock_tz,
        ):
            mock_tz.now.return_value = later_now
            from apps.tasks.collectors.collect_snapshot_metrics import collect_snapshot_metrics

            result = collect_snapshot_metrics(collector_type="config", collection_timestamp=pinned_ts)

        assert result["status"] == "success"


@pytest.mark.unit
@pytest.mark.django_db
class TestDailyRollupTask(TestCase):
    """Test daily metrics rollup task."""

    def test_daily_metrics_rollup_no_collections(self):
        """Test daily rollup skips when no hourly collections exist."""

        summary_date = date(2024, 1, 15)
        result = daily_metrics_rollup(summary_date=summary_date.isoformat())

        assert result["status"] == "error"
        assert "upstream dependency not met" in result["error"]

    def test_daily_metrics_rollup_default_date(self):
        """Test daily rollup skips when no collections for yesterday."""
        result = daily_metrics_rollup()

        assert result["status"] == "error"
        assert "upstream dependency not met" in result["error"]


@pytest.mark.unit
@pytest.mark.django_db
class TestAnonymizationTask(TestCase):
    """Test daily anonymization and preparation task."""


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(FEATURE={"ANONYMIZED_DATA_COLLECTION": True})
class TestSegmentSendingTask(TestCase):
    """Test sending anonymized data to Segment."""

    def test_send_to_segment_no_payloads(self):
        """Test sending when no payloads exist."""
        result = send_anonymized_to_segment()

        assert result["status"] == "success"
        assert result["results"]["sent"] == 0
        assert result["total_processed"] == 0

    @patch("apps.tasks.collectors.send_anonymized_to_segment.send_to_segment")
    def test_send_to_segment_success(self, mock_send_to_segment):
        """Test successful sending to Segment."""

        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        # Create daily summary and payload
        summary = DailyMetricsSummary.objects.create(
            summary_date=date(2024, 1, 22),
            aggregated_metrics={},
            config_data={},
            status="anonymized",
        )

        payload = AnonymizedMetricsPayload.objects.create(
            summary_date=date(2024, 1, 22),
            anonymized_data={"test": "data"},
            status="pending",
            daily_summary=summary,
        )

        mock_send_to_segment.return_value = {"status": "success"}

        result = send_anonymized_to_segment()

        assert result["status"] == "success"
        assert result["results"]["sent"] == 1

        # Verify payload status updated
        payload.refresh_from_db()
        assert payload.status == "sent"

    @patch("apps.tasks.collectors.send_anonymized_to_segment.send_to_segment")
    def test_send_to_segment_specific_payload(self, mock_send_to_segment):
        """Test sending specific payload by ID."""

        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        summary = DailyMetricsSummary.objects.create(
            summary_date=date(2024, 1, 23), aggregated_metrics={}, config_data={}, status="anonymized"
        )

        payload = AnonymizedMetricsPayload.objects.create(
            summary_date=date(2024, 1, 23), anonymized_data={}, status="pending", daily_summary=summary
        )

        mock_send_to_segment.return_value = {"status": "success"}

        result = send_anonymized_to_segment(payload_id=payload.id)

        assert result["status"] == "success"
        assert result["results"]["sent"] == 1

    @patch("apps.tasks.collectors.send_anonymized_to_segment.send_to_segment")
    def test_send_to_segment_retry_logic(self, mock_send_to_segment):
        """Test retry logic for failed sends."""

        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        summary = DailyMetricsSummary.objects.create(
            summary_date=date(2024, 1, 24), aggregated_metrics={}, config_data={}, status="anonymized"
        )

        # Create payload with retry status
        payload = AnonymizedMetricsPayload.objects.create(
            summary_date=date(2024, 1, 24),
            anonymized_data={},
            status="retry",
            daily_summary=summary,
            retry_count=3,
            max_retries=5,  # Still can retry
        )

        mock_send_to_segment.return_value = {"status": "success"}

        result = send_anonymized_to_segment()

        assert result["results"]["sent"] == 1
        payload.refresh_from_db()
        assert payload.status == "sent"

    def test_send_to_segment_max_retries_exceeded(self):
        """Test handling when max retries exceeded."""

        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        summary = DailyMetricsSummary.objects.create(
            summary_date=date(2024, 1, 25), aggregated_metrics={}, config_data={}, status="anonymized"
        )

        # Create payload that exceeded retries
        payload = AnonymizedMetricsPayload.objects.create(
            summary_date=date(2024, 1, 25),
            anonymized_data={},
            status="retry",
            daily_summary=summary,
            retry_count=5,
            max_retries=3,  # Already exceeded
        )

        result = send_anonymized_to_segment()

        assert result["results"]["skipped"] == 1
        payload.refresh_from_db()
        assert payload.status == "failed"
        assert "Max retries exceeded" in payload.error_message

    @patch("apps.tasks.collectors.send_anonymized_to_segment.send_to_segment")
    def test_send_to_segment_not_available(self, mock_send_to_segment):
        """Test sending when Segment not available."""

        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        # Mock send_to_segment to return segment_not_available
        mock_send_to_segment.return_value = {"status": "unavailable", "error": "segment_not_available"}

        summary = DailyMetricsSummary.objects.create(
            summary_date=date(2024, 1, 26), aggregated_metrics={}, config_data={}, status="anonymized"
        )

        payload = AnonymizedMetricsPayload.objects.create(
            summary_date=date(2024, 1, 26), anonymized_data={}, status="pending", daily_summary=summary
        )

        result = send_anonymized_to_segment()

        assert result["results"]["skipped"] == 1
        assert result["results"]["failed"] == 0
        payload.refresh_from_db()
        assert payload.status == "unavailable"
        assert "segment_not_available" in payload.error_message


@pytest.mark.unit
@pytest.mark.django_db
class TestPRFixes(TestCase):
    """Test fixes for PR #79 code review issues."""

    def test_duplicate_payload_prevention(self):
        """Test unique constraint prevents duplicate active payloads (Issue #8)."""

        from django.db import IntegrityError, transaction

        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        summary = DailyMetricsSummary.objects.create(
            summary_date=date(2024, 1, 30), aggregated_metrics={}, config_data={}, status="aggregated"
        )

        # Create first payload with pending status
        AnonymizedMetricsPayload.objects.create(
            summary_date=date(2024, 1, 30),
            anonymized_data={"test": "data1"},
            status="pending",
            daily_summary=summary,
        )

        # Try to create second payload with pending status for same summary
        # Should raise IntegrityError due to unique constraint
        # Use transaction.atomic to prevent transaction errors in tests
        with transaction.atomic(), pytest.raises(IntegrityError):
            AnonymizedMetricsPayload.objects.create(
                summary_date=date(2024, 1, 30),
                anonymized_data={"test": "data2"},
                status="pending",
                daily_summary=summary,
            )

        # Verify only one payload exists
        assert AnonymizedMetricsPayload.objects.filter(daily_summary=summary).count() == 1

    def test_cleanup_all_payload_statuses(self):
        """Test cleanup includes all payload statuses, not just failed (Issue #7)."""

        from apps.tasks.cleanup.cleanup_metrics_data import cleanup_metrics_data
        from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

        # Create old payloads with different statuses
        old_time = timezone.now() - timedelta(days=35)

        # Create payloads with various statuses (all old enough to be cleaned up)
        # Use separate summaries to avoid unique constraint conflicts
        statuses_to_test = ["failed", "pending", "sending", "retry"]
        for idx, status in enumerate(statuses_to_test):
            # Create a separate summary for each payload
            summary = DailyMetricsSummary.objects.create(
                summary_date=date(2024, 1, 15 + idx), aggregated_metrics={}, config_data={}, status="aggregated"
            )

            payload = AnonymizedMetricsPayload.objects.create(
                summary_date=date(2024, 1, 15 + idx),
                anonymized_data={"test": f"data_{status}"},
                status=status,
                daily_summary=summary,
            )
            # Manually set created time to be old
            payload.created = old_time
            payload.save()

        # Verify 4 payloads exist
        assert AnonymizedMetricsPayload.objects.count() == 4

        # Run cleanup with short retention period to clean up all old payloads
        result = cleanup_metrics_data(
            hourly_retention_days=7, daily_retention_days=30, payload_retention_days=7, dry_run=False
        )

        assert result["status"] == "success"

        # Verify all 4 old payloads were cleaned up (not just "failed")
        # The cleanup should have deleted all statuses
        remaining = AnonymizedMetricsPayload.objects.count()
        assert remaining == 0, f"Expected 0 remaining payloads, got {remaining}"


@pytest.mark.unit
@pytest.mark.django_db
class TestHourlyCollectionRetryBehavior(TestCase):
    """
    Test that hourly collection properly handles retries and duplicate triggers.

    The generic_collect_metrics function uses update_or_create to handle cases where:
    1. A failed task is retried and now succeeds
    2. Scheduler double-triggers the same hour
    3. Multiple attempts for the same collection period
    4. Re-collection after a record was already processed by daily rollup
    """

    def test_resets_processed_status_on_update(self):
        """
        Verify that re-collecting a processed record resets its status to 'collected'.

        Scenario: A collection was already processed by daily rollup (status='processed')
        and the collector runs again for the same timestamp (e.g., manual re-run or retry).
        The update should reset status to 'collected' so the new data is picked up by
        the next daily rollup.
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from apps.tasks.models import HourlyMetricsCollection
        from apps.tasks.utils import generic_collect_metrics

        # Create initial collection that was already processed by rollup
        collection_timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        HourlyMetricsCollection.objects.create(
            collector_type="unified_jobs",
            collection_timestamp=collection_timestamp,
            raw_data={"old": "data"},
            status="processed",  # Already processed by previous rollup
            error_message="",
        )

        # Mock the collector and database connection
        mock_collector = MagicMock()
        mock_collector.gather.return_value = {"new": "data"}
        mock_db = MagicMock()

        # Mock collector registry with a simple collector
        collector_registry = {
            "unified_jobs": {
                "collector_func": lambda db: mock_collector,
                "rollup_processor": None,  # No processor for this test
            }
        }

        # Re-collect the same timestamp
        with patch("apps.tasks.utils.get_db_connection", return_value=mock_db):
            result = generic_collect_metrics(
                collector_type="unified_jobs",
                collector_registry=collector_registry,
                collection_mode="hourly",
                timestamp=collection_timestamp,
                db_connection=mock_db,
            )

        # Verify the result indicates update
        assert result["status"] == "success"
        assert "Updated" in result["message"]

        # Verify the collection was updated and status was reset to 'collected'
        collection = HourlyMetricsCollection.objects.get(
            collector_type="unified_jobs", collection_timestamp=collection_timestamp
        )
        assert collection.status == "collected", "Status should be reset to 'collected' after re-collection"
        assert collection.error_message == "", "Error message should be cleared"
        assert collection.raw_data == {"new": "data"}, "Data should be updated"

    def test_creates_with_collected_status_on_first_run(self):
        """
        Verify that first-time collection creates record with status='collected'.
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from apps.tasks.models import HourlyMetricsCollection
        from apps.tasks.utils import generic_collect_metrics

        collection_timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Mock the collector and database connection
        mock_collector = MagicMock()
        mock_collector.gather.return_value = {"new": "data"}
        mock_db = MagicMock()

        # Mock collector registry
        collector_registry = {
            "unified_jobs": {
                "collector_func": lambda db: mock_collector,
                "rollup_processor": None,
            }
        }

        # Collect for the first time
        with patch("apps.tasks.utils.get_db_connection", return_value=mock_db):
            result = generic_collect_metrics(
                collector_type="unified_jobs",
                collector_registry=collector_registry,
                collection_mode="hourly",
                timestamp=collection_timestamp,
                db_connection=mock_db,
            )

        # Verify the result indicates creation
        assert result["status"] == "success"
        assert "Created" in result["message"]

        # Verify the collection was created with correct status
        collection = HourlyMetricsCollection.objects.get(
            collector_type="unified_jobs", collection_timestamp=collection_timestamp
        )
        assert collection.status == "collected", "New collection should have status='collected'"
        assert collection.error_message == ""
        assert collection.raw_data == {"new": "data"}

    def test_integrity_error_treated_as_success(self):
        """
        Verify that an IntegrityError from a concurrent write is treated as success.

        If two executions race to write the same (collector_type, collection_timestamp),
        the unique_together constraint raises IntegrityError on the loser. Since the data
        already exists, the task has nothing left to do and should return success rather
        than failing and triggering a retry.
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from django.db import IntegrityError

        from apps.tasks.utils import generic_collect_metrics

        collection_timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        mock_collector = MagicMock()
        mock_collector.gather.return_value = {"data": "value"}
        mock_db = MagicMock()

        collector_registry = {
            "unified_jobs": {
                "collector_func": lambda db: mock_collector,
                "rollup_processor": None,
            }
        }

        with patch("apps.tasks.models.HourlyMetricsCollection.objects") as mock_objects:
            mock_objects.update_or_create.side_effect = IntegrityError("duplicate key value")

            result = generic_collect_metrics(
                collector_type="unified_jobs",
                collector_registry=collector_registry,
                collection_mode="hourly",
                timestamp=collection_timestamp,
                db_connection=mock_db,
            )

        assert result["status"] == "success"
        assert "duplicate" in result["message"].lower()
