"""
Enhanced unit tests for cron_scheduler.py to improve coverage.

Tests cover:
- _periodic_database_sync task discovery and routing
- Error handling in _add_database_scheduled_task
- Error handling in _add_database_recurring_task
- Error handling in _execute_database_task
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.tasks.cron_scheduler import UnifiedTaskScheduler, _inject_dispatch_timestamps


@pytest.mark.unit
@pytest.mark.django_db
class TestPeriodicDatabaseSync:
    """Test _periodic_database_sync task discovery and routing."""

    @patch("apps.tasks.models.Task")
    @patch.object(UnifiedTaskScheduler, "_execute_database_task")
    def test_discovers_and_executes_immediate_tasks(self, mock_execute, mock_task_model):
        """Test periodic sync discovers new immediate tasks and executes them."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_immediate_task = MagicMock()
        mock_immediate_task.id = 1
        mock_immediate_task.name = "Immediate Task"
        mock_immediate_task.is_ready_to_run.return_value = True
        mock_immediate_task.task_data = {}

        mock_task_model.immediate_tasks.return_value = [mock_immediate_task]
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = []

        # Act
        scheduler._periodic_database_sync()

        # Assert
        mock_execute.assert_called_once_with(1)
        assert 1 in scheduler._db_task_jobs
        assert scheduler._db_task_jobs[1] == "db_immediate_1"

    @patch("apps.tasks.models.Task")
    @patch.object(UnifiedTaskScheduler, "_add_database_scheduled_task")
    def test_discovers_and_adds_scheduled_tasks(self, mock_add_scheduled, mock_task_model):
        """Test periodic sync discovers new scheduled tasks."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_scheduled_task = MagicMock()
        mock_scheduled_task.id = 2
        mock_scheduled_task.name = "Scheduled Task"
        mock_scheduled_task.task_data = {}

        mock_task_model.immediate_tasks.return_value = []
        mock_task_model.scheduled_tasks.return_value = [mock_scheduled_task]
        mock_task_model.recurring_tasks.return_value = []

        # Act
        scheduler._periodic_database_sync()

        # Assert
        mock_add_scheduled.assert_called_once_with(mock_scheduled_task)

    @patch("apps.tasks.models.Task")
    @patch.object(UnifiedTaskScheduler, "_add_database_recurring_task")
    def test_discovers_and_adds_recurring_tasks(self, mock_add_recurring, mock_task_model):
        """Test periodic sync discovers new recurring tasks."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_recurring_task = MagicMock()
        mock_recurring_task.id = 3
        mock_recurring_task.name = "Recurring Task"
        mock_recurring_task.task_data = {}

        mock_task_model.immediate_tasks.return_value = []
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = [mock_recurring_task]

        # Act
        scheduler._periodic_database_sync()

        # Assert
        mock_add_recurring.assert_called_once_with(mock_recurring_task)

    @patch("apps.tasks.models.Task")
    def test_skips_already_tracked_tasks(self, mock_task_model):
        """Test periodic sync skips tasks already in tracking."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True
        scheduler._db_task_jobs[2] = "db_task_2"  # Already tracked

        mock_scheduled_task = MagicMock()
        mock_scheduled_task.id = 2
        mock_scheduled_task.name = "Already Tracked Task"

        mock_task_model.immediate_tasks.return_value = []
        mock_task_model.scheduled_tasks.return_value = [mock_scheduled_task]
        mock_task_model.recurring_tasks.return_value = []

        # Act
        with patch.object(scheduler, "_add_database_scheduled_task") as mock_add:
            scheduler._periodic_database_sync()

        # Assert
        mock_add.assert_not_called()

    @patch("apps.tasks.models.Task")
    def test_skips_immediate_task_not_ready_to_run(self, mock_task_model):
        """Test periodic sync skips immediate tasks not ready to run."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_immediate_task = MagicMock()
        mock_immediate_task.id = 1
        mock_immediate_task.name = "Not Ready Task"
        mock_immediate_task.is_ready_to_run.return_value = False

        mock_task_model.immediate_tasks.return_value = [mock_immediate_task]
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = []

        # Act
        with patch.object(scheduler, "_execute_database_task") as mock_execute:
            scheduler._periodic_database_sync()

        # Assert
        mock_execute.assert_not_called()

    @patch("apps.tasks.task_groups.get_feature_enabled_from_db", return_value=False)
    @patch("apps.tasks.models.Task")
    def test_skips_immediate_task_with_disabled_feature_flag(self, mock_task_model, mock_flag):
        """Immediate tasks whose feature flag is off are silently skipped."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.name = "Flagged Task"
        mock_task.is_ready_to_run.return_value = True
        mock_task.task_data = {"_feature_flag": "DASHBOARD_COLLECTION"}

        mock_task_model.immediate_tasks.return_value = [mock_task]
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = []

        with patch.object(scheduler, "_execute_database_task") as mock_execute:
            scheduler._periodic_database_sync()

        mock_execute.assert_not_called()
        assert 1 not in scheduler._db_task_jobs

    @patch("apps.tasks.task_groups.get_feature_enabled_from_db", return_value=False)
    @patch("apps.tasks.models.Task")
    def test_skips_recurring_task_with_disabled_feature_flag(self, mock_task_model, mock_flag):
        """Recurring tasks whose feature flag is off are not added to the scheduler."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_task = MagicMock()
        mock_task.id = 2
        mock_task.name = "Flagged Recurring"
        mock_task.task_data = {"_feature_flag": "DASHBOARD_COLLECTION"}

        mock_task_model.immediate_tasks.return_value = []
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = [mock_task]

        with patch.object(scheduler, "_add_database_recurring_task") as mock_add:
            scheduler._periodic_database_sync()

        mock_add.assert_not_called()

    @patch("apps.tasks.task_groups.get_feature_enabled_from_db", return_value=True)
    @patch("apps.tasks.models.Task")
    @patch.object(UnifiedTaskScheduler, "_add_database_recurring_task")
    def test_adds_recurring_task_when_flag_is_enabled(self, mock_add, mock_task_model, mock_flag):
        """Recurring tasks are added once their feature flag is re-enabled."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        mock_task = MagicMock()
        mock_task.id = 3
        mock_task.name = "Re-enabled Task"
        mock_task.task_data = {"_feature_flag": "DASHBOARD_COLLECTION"}

        mock_task_model.immediate_tasks.return_value = []
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = [mock_task]

        scheduler._periodic_database_sync()

        mock_add.assert_called_once_with(mock_task)

    @patch("apps.tasks.cron_scheduler.close_old_connections")
    @patch("apps.tasks.models.Task")
    def test_closes_old_connections_before_querying(self, mock_task_model, mock_close):
        """close_old_connections must be called before any ORM access."""
        call_order = []
        mock_close.side_effect = lambda: call_order.append("close")
        mock_task_model.immediate_tasks.side_effect = lambda: call_order.append("query") or []
        mock_task_model.scheduled_tasks.return_value = []
        mock_task_model.recurring_tasks.return_value = []

        scheduler = UnifiedTaskScheduler()
        scheduler._periodic_database_sync()

        mock_close.assert_called_once()
        assert call_order[0] == "close"

    @patch("apps.tasks.cron_scheduler.close_old_connections")
    @patch("apps.tasks.models.Task")
    def test_closes_old_connections_even_on_error(self, mock_task_model, mock_close):
        """close_old_connections is called even when the sync body raises."""
        mock_task_model.immediate_tasks.side_effect = Exception("db gone")

        scheduler = UnifiedTaskScheduler()
        scheduler._periodic_database_sync()

        mock_close.assert_called_once()


@pytest.mark.unit
@pytest.mark.django_db
class TestAddDatabaseScheduledTaskErrors:
    """Test error handling in _add_database_scheduled_task."""

    def test_skips_if_already_in_tracking(self, pending_task):
        """Test returns early if task is already in tracking."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler._db_task_jobs[pending_task.id] = f"db_task_{pending_task.id}"

        # Act
        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler._add_database_scheduled_task(pending_task)

        # Assert
        mock_add_job.assert_not_called()

    @patch.object(UnifiedTaskScheduler, "_execute_database_task")
    def test_executes_immediately_if_past_due(self, mock_execute, pending_task):
        """Test executes task immediately if scheduled time is in the past."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        pending_task.scheduled_time = timezone.now() - timedelta(hours=1)

        # Act
        scheduler._add_database_scheduled_task(pending_task)

        # Assert
        mock_execute.assert_called_once_with(pending_task.id)

    def test_handles_exception_during_add(self, pending_task):
        """Test handles exception during job addition."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        pending_task.scheduled_time = timezone.now() + timedelta(hours=1)

        # Act - should not raise
        with patch.object(scheduler.scheduler, "add_job", side_effect=Exception("Scheduler error")):
            scheduler._add_database_scheduled_task(pending_task)

        # Task should not be in tracking after error
        assert pending_task.id not in scheduler._db_task_jobs


@pytest.mark.unit
@pytest.mark.django_db
class TestAddDatabaseRecurringTaskErrors:
    """Test error handling in _add_database_recurring_task."""

    def test_skips_if_already_in_tracking(self, recurring_task):
        """Test returns early if task is already in tracking."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler._db_task_jobs[recurring_task.id] = f"db_recurring_{recurring_task.id}"

        # Act
        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler._add_database_recurring_task(recurring_task)

        # Assert
        mock_add_job.assert_not_called()

    def test_handles_exception_during_add(self, recurring_task):
        """Test handles exception during job addition."""
        # Arrange
        scheduler = UnifiedTaskScheduler()

        # Act - should not raise
        with patch.object(scheduler.scheduler, "add_job", side_effect=Exception("Scheduler error")):
            scheduler._add_database_recurring_task(recurring_task)

        # Task should not be in tracking after error
        assert recurring_task.id not in scheduler._db_task_jobs


@pytest.mark.unit
@pytest.mark.django_db
class TestExecuteDatabaseTaskErrors:
    """Test error handling in _execute_database_task."""

    @patch.object(UnifiedTaskScheduler, "_remove_database_task")
    def test_handles_task_not_found(self, mock_remove):
        """Test handles Task.DoesNotExist exception."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        from apps.tasks.models import Task

        with patch("apps.tasks.models.Task.objects.get", side_effect=Task.DoesNotExist):
            # Act
            scheduler._execute_database_task(999)

        # Assert
        mock_remove.assert_called_once_with(999)

    @patch("apps.tasks.models.Task")
    @patch.object(UnifiedTaskScheduler, "_remove_database_task")
    def test_handles_non_pending_task(self, mock_remove, mock_task_model):
        """Test handles task in non-pending status."""
        # Arrange
        scheduler = UnifiedTaskScheduler()

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.name = "test_task"
        mock_task.status = "running"
        mock_task.task_data = {}
        mock_task.cron_expression = None
        mock_task_model.objects.get.return_value = mock_task

        # Act
        scheduler._execute_database_task(1)

        # Assert
        mock_remove.assert_called_once_with(1)

    @patch("apps.tasks.cron_scheduler.close_old_connections")
    @patch("apps.tasks.models.Task")
    def test_closes_old_connections_before_querying(self, mock_task_model, mock_close):
        """close_old_connections is called before any ORM access in _execute_database_task."""
        call_order = []
        mock_close.side_effect = lambda: call_order.append("close")

        def get_side_effect(**kwargs):
            call_order.append("query")
            raise Exception("db gone")

        mock_task_model.objects.get.side_effect = get_side_effect

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(999)

        mock_close.assert_called_once()
        assert call_order[0] == "close"

    @patch("apps.tasks.cron_scheduler.close_old_connections")
    @patch("apps.tasks.models.Task")
    def test_closes_old_connections_even_on_error(self, mock_task_model, mock_close):
        """close_old_connections is called even when the task body raises."""
        mock_task_model.objects.get.side_effect = Exception("db gone")

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(999)

        mock_close.assert_called_once()


@pytest.mark.unit
@pytest.mark.django_db
class TestSyncDatabaseTasks:
    """Test _sync_database_tasks functionality."""

    @patch("apps.tasks.models.Task")
    @patch.object(UnifiedTaskScheduler, "_add_database_scheduled_task")
    @patch.object(UnifiedTaskScheduler, "_add_database_recurring_task")
    def test_syncs_scheduled_and_recurring_tasks(self, mock_add_recurring, mock_add_scheduled, mock_task_model):
        """Test syncs both scheduled and recurring tasks."""
        # Arrange
        scheduler = UnifiedTaskScheduler()

        mock_scheduled_task = MagicMock()
        mock_scheduled_task.task_data = {}
        mock_recurring_task = MagicMock()
        mock_recurring_task.task_data = {}

        mock_task_model.scheduled_tasks.return_value = [mock_scheduled_task]
        mock_task_model.recurring_tasks.return_value = [mock_recurring_task]

        # Act
        scheduler._sync_database_tasks()

        # Assert
        mock_add_scheduled.assert_called_once_with(mock_scheduled_task)
        mock_add_recurring.assert_called_once_with(mock_recurring_task)


@pytest.mark.unit
@pytest.mark.django_db
class TestRemoveDatabaseTask:
    """Test _remove_database_task functionality."""

    def test_removes_job_from_scheduler_and_tracking(self):
        """Test removes job from both scheduler and tracking dict."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler._db_task_jobs[1] = "db_task_1"

        mock_remove_job = MagicMock()
        scheduler.scheduler.remove_job = mock_remove_job

        # Act
        scheduler._remove_database_task(1)

        # Assert
        mock_remove_job.assert_called_once_with("db_task_1")
        assert 1 not in scheduler._db_task_jobs

    def test_handles_exception_during_remove(self):
        """Test handles exception when removing job from scheduler."""
        # Arrange
        scheduler = UnifiedTaskScheduler()
        scheduler._db_task_jobs[1] = "db_task_1"

        scheduler.scheduler.remove_job = MagicMock(side_effect=Exception("Job not found"))

        # Act - should not raise
        scheduler._remove_database_task(1)

        # Assert - still removed from tracking
        assert 1 not in scheduler._db_task_jobs


@pytest.mark.unit
class TestInjectDispatchTimestamps:
    """
    Test that _inject_dispatch_timestamps pins the correct time-window key into
    task_data at dispatch time so retries always collect the originally intended window.
    """

    def test_injects_hour_timestamp_for_hourly_collector(self):
        """collect_hourly_metrics tasks get hour_timestamp set to the previous full hour."""
        fixed_now = timezone.now().replace(minute=30, second=0, microsecond=0)
        expected = (fixed_now.replace(minute=0) - timedelta(hours=1)).isoformat()

        with patch("apps.tasks.cron_scheduler.timezone") as mock_tz:
            mock_tz.now.return_value = fixed_now
            result = _inject_dispatch_timestamps("collect_hourly_metrics", {"collector_type": "unified_jobs"})

        assert result["hour_timestamp"] == expected

    def test_injects_collection_timestamp_for_snapshot_collector(self):
        """collect_snapshot_metrics tasks get collection_timestamp set to yesterday at 23:00."""
        fixed_now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        expected = (fixed_now.replace(hour=23) - timedelta(days=1)).isoformat()

        with patch("apps.tasks.cron_scheduler.timezone") as mock_tz:
            mock_tz.now.return_value = fixed_now
            result = _inject_dispatch_timestamps("collect_snapshot_metrics", {"collector_type": "config"})

        assert result["collection_timestamp"] == expected

    def test_does_not_overwrite_existing_hour_timestamp(self):
        """An explicit hour_timestamp already in task_data must not be replaced."""
        fixed_ts = "2024-01-15T10:00:00+00:00"
        result = _inject_dispatch_timestamps(
            "collect_hourly_metrics", {"collector_type": "unified_jobs", "hour_timestamp": fixed_ts}
        )
        assert result["hour_timestamp"] == fixed_ts

    def test_does_not_modify_unrelated_functions(self):
        """Functions not in the injection map are returned unchanged."""
        original = {"some_key": "some_value"}
        result = _inject_dispatch_timestamps("hello_world", original)
        assert result == original

    def test_returns_a_copy_not_the_original_dict(self):
        """The original task_data dict must not be mutated."""
        original = {"collector_type": "unified_jobs"}
        result = _inject_dispatch_timestamps("collect_hourly_metrics", original)
        assert "hour_timestamp" not in original
        assert "hour_timestamp" in result

    def test_injects_hour_timestamp_for_daily_collector(self):
        """collect_daily_metrics tasks get hour_timestamp set to today's midnight (UTC)."""
        fixed_now = timezone.now().replace(hour=14, minute=30, second=0, microsecond=0)
        expected = fixed_now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        with patch("apps.tasks.cron_scheduler.timezone") as mock_tz:
            mock_tz.now.return_value = fixed_now
            result = _inject_dispatch_timestamps("collect_daily_metrics", {"collector_type": "task_executions_service"})

        assert result["hour_timestamp"] == expected

    def test_does_not_overwrite_existing_hour_timestamp_for_daily_collector(self):
        """An explicit hour_timestamp already in daily task_data must not be replaced."""
        fixed_ts = "2024-01-15T00:00:00+00:00"
        result = _inject_dispatch_timestamps(
            "collect_daily_metrics",
            {"collector_type": "task_executions_service", "hour_timestamp": fixed_ts},
        )
        assert result["hour_timestamp"] == fixed_ts
