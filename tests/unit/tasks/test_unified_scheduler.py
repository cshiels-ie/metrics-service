"""
Comprehensive unit tests for the UnifiedTaskScheduler module.

Tests the task scheduler that combines task group scheduling and database task scheduling
without database polling, using APScheduler for optimal performance.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone

from apps.tasks.cron_scheduler import (
    UnifiedTaskScheduler,
    get_scheduler,
    start_scheduler,
    stop_scheduler,
)


@pytest.fixture
def mock_task():
    """Create a mock task object for one-time scheduled tasks."""
    task = Mock()
    task.id = 1
    task.name = "Test Task"
    task.status = "pending"
    task.function_name = "test_function"
    task.task_data = {}
    task.scheduled_time = timezone.now() + timedelta(hours=1)
    task.is_recurring = False
    task.cron_expression = None
    task.created = timezone.now()
    task.modified = timezone.now()
    task.save = Mock()
    return task


@pytest.fixture
def mock_recurring_task():
    """Create a mock recurring task object."""
    task = Mock()
    task.id = 2
    task.name = "Recurring Task"
    task.status = "pending"
    task.function_name = "recurring_function"
    task.task_data = {}
    task.scheduled_time = None
    task.is_recurring = True
    task.cron_expression = "0 * * * *"  # Every hour
    task.created = timezone.now()
    task.modified = timezone.now()
    task.save = Mock()
    return task


@pytest.fixture
def scheduler():
    """Create a UnifiedTaskScheduler instance."""
    return UnifiedTaskScheduler()


@pytest.mark.unit
class TestUnifiedTaskScheduler:
    """Test cases for UnifiedTaskScheduler class."""

    def test_init(self):
        """Test scheduler initialization."""
        scheduler = UnifiedTaskScheduler()

        assert isinstance(scheduler.scheduler, BackgroundScheduler)
        assert scheduler.running is False
        assert scheduler._db_task_jobs == {}

    @pytest.mark.django_db
    def test_start_success(self):
        """Test successful scheduler start."""
        scheduler = UnifiedTaskScheduler()
        scheduler.scheduler.start = Mock()
        scheduler._sync_database_tasks = Mock()

        scheduler.start()

        assert scheduler.running is True
        scheduler.scheduler.start.assert_called_once()

    def test_start_already_running(self):
        """Test starting scheduler when already running."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True

        scheduler.start()  # Should just return without error

    def test_start_failure(self):
        """Test scheduler start failure."""
        scheduler = UnifiedTaskScheduler()
        scheduler.scheduler.start = Mock(side_effect=Exception("Start error"))

        with pytest.raises(Exception, match="Start error"):
            scheduler.start()

    @pytest.mark.django_db
    def test_stop_success(self):
        """Test successful scheduler stop."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True
        scheduler._db_task_jobs[1] = "job_1"
        scheduler.scheduler.shutdown = Mock()

        scheduler.stop()

        assert scheduler.running is False
        assert len(scheduler._db_task_jobs) == 0
        scheduler.scheduler.shutdown.assert_called_once()

    def test_stop_not_running(self):
        """Test stopping scheduler when not running."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = False
        scheduler.scheduler.shutdown = Mock()

        scheduler.stop()

        scheduler.scheduler.shutdown.assert_not_called()

    def test_stop_failure(self):
        """Test scheduler stop failure."""
        scheduler = UnifiedTaskScheduler()
        scheduler.running = True
        scheduler.scheduler.shutdown = Mock(side_effect=Exception("Stop error"))

        scheduler.stop()  # Should catch exception

    def test_get_queue_for_function_known_functions(self):
        """Test queue mapping for known functions."""
        from apps.tasks.tasks import get_queue_for_function

        # Test specific queue mappings
        assert get_queue_for_function("cleanup_old_tasks") == "maintenance"
        assert get_queue_for_function("daily_metrics_rollup") == "metrics"

    def test_get_queue_for_function_unknown_function(self):
        """Test queue mapping for unknown function."""
        from apps.tasks.tasks import get_queue_for_function

        assert get_queue_for_function("unknown_function") == "maintenance"


@pytest.mark.unit
class TestDatabaseTaskManagement:
    """Test cases for managing database tasks."""

    def test_add_database_scheduled_task(self, scheduler, mock_task):
        """Test adding a scheduled database task."""
        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler._add_database_scheduled_task(mock_task)

            mock_add_job.assert_called_once()
            assert mock_task.id in scheduler._db_task_jobs

    def test_add_database_recurring_task(self, scheduler, mock_recurring_task):
        """Test adding a recurring database task."""
        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler._add_database_recurring_task(mock_recurring_task)

            mock_add_job.assert_called_once()
            assert mock_recurring_task.id in scheduler._db_task_jobs

    def test_add_database_recurring_task_error(self, scheduler, mock_recurring_task):
        """Test error handling when adding recurring task fails."""
        with patch.object(scheduler.scheduler, "add_job", side_effect=Exception("Scheduler error")):
            # Should not raise - error is caught and logged
            scheduler._add_database_recurring_task(mock_recurring_task)
            # Task should not be in the jobs dict since adding failed
            assert mock_recurring_task.id not in scheduler._db_task_jobs

    def test_remove_database_task(self, scheduler):
        """Test removing a database task."""
        task_id = 1
        job_id = f"db_task_{task_id}"
        scheduler._db_task_jobs[task_id] = job_id

        with patch.object(scheduler.scheduler, "remove_job") as mock_remove:
            scheduler._remove_database_task(task_id)

            mock_remove.assert_called_once_with(job_id)
            assert task_id not in scheduler._db_task_jobs

    @pytest.mark.django_db
    @patch("apps.tasks.models.Task")
    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    def test_execute_database_task(self, mock_submit, mock_task_model, scheduler):
        """Test executing a database task."""
        task_id = 1
        mock_task = Mock()
        mock_task.id = task_id
        mock_task.name = "Test"
        mock_task.cron_expression = None  # Non-recurring task
        mock_task.status = "pending"
        mock_task.task_data = {}

        mock_task_model.objects.get.return_value = mock_task

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            scheduler._execute_database_task(task_id)

            mock_submit.assert_called_once_with(mock_task)
            mock_remove.assert_called_once_with(task_id)

    @pytest.mark.django_db
    @patch("apps.tasks.models.Task")
    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    def test_execute_database_task_recurring(self, mock_submit, mock_task_model, scheduler):
        """Test executing a recurring database task."""
        task_id = 2
        mock_task = Mock()
        mock_task.id = task_id
        mock_task.name = "Recurring Test"
        mock_task.is_recurring = True
        mock_task.status = "pending"
        mock_task.function_name = "test_function"
        mock_task.task_data = {}
        mock_task.max_attempts = 3
        mock_task.created_by = None
        mock_task.is_system_task = False

        # Mock the execution task that gets created
        mock_execution_task = Mock()
        mock_execution_task.id = 999
        mock_execution_task.name = "Recurring Test (Execution 2024-01-01 12:00:00)"

        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.objects.create.return_value = mock_execution_task

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            scheduler._execute_database_task(task_id)

            # Should create execution task and submit that
            mock_task_model.objects.create.assert_called_once()
            mock_submit.assert_called_once_with(mock_execution_task)
            # Should not remove recurring tasks
            mock_remove.assert_not_called()

    @pytest.mark.django_db
    @patch("apps.tasks.models.Task")
    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    def test_execute_database_task_cancelled_status(self, mock_submit, mock_task_model, scheduler):
        """Test that a cancelled task is removed and not executed."""
        task_id = 1
        mock_task = Mock()
        mock_task.id = task_id
        mock_task.name = "Cancelled Task"
        mock_task.status = "cancelled"
        mock_task.task_data = {}

        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            scheduler._execute_database_task(task_id)

            mock_submit.assert_not_called()
            mock_remove.assert_called_once_with(task_id)

    @pytest.mark.django_db
    @patch("apps.tasks.models.Task")
    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    def test_execute_database_task_completed_status(self, mock_submit, mock_task_model, scheduler):
        """Test that a completed task is removed and not executed."""
        task_id = 1
        mock_task = Mock()
        mock_task.id = task_id
        mock_task.name = "Completed Task"
        mock_task.status = "completed"
        mock_task.task_data = {}

        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            scheduler._execute_database_task(task_id)

            mock_submit.assert_not_called()
            mock_remove.assert_called_once_with(task_id)

    @pytest.mark.django_db
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db", return_value=False)
    @patch("apps.tasks.models.Task")
    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    def test_execute_database_task_feature_flag_disabled_non_recurring(
        self, mock_submit, mock_task_model, mock_flag, scheduler
    ):
        """Test that a non-recurring task with disabled feature flag is skipped and removed from tracking."""
        task_id = 1
        mock_task = Mock()
        mock_task.id = task_id
        mock_task.name = "Flagged Task"
        mock_task.status = "pending"
        mock_task.task_data = {"_feature_flag": "ANONYMIZED_DATA_COLLECTION"}
        mock_task.cron_expression = None

        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            scheduler._execute_database_task(task_id)

            mock_submit.assert_not_called()
            # Non-recurring tasks are removed so they can be retried after flag re-enable
            mock_remove.assert_called_once_with(task_id)

    @pytest.mark.django_db
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db", return_value=False)
    @patch("apps.tasks.models.Task")
    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    def test_execute_database_task_feature_flag_disabled_recurring(
        self, mock_submit, mock_task_model, mock_flag, scheduler
    ):
        """Test that a recurring task with disabled feature flag is skipped but stays in tracking."""
        task_id = 2
        mock_task = Mock()
        mock_task.id = task_id
        mock_task.name = "Recurring Flagged Task"
        mock_task.status = "pending"
        mock_task.task_data = {"_feature_flag": "ANONYMIZED_DATA_COLLECTION"}
        mock_task.cron_expression = "0 3 * * *"

        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            scheduler._execute_database_task(task_id)

            mock_submit.assert_not_called()
            # Recurring tasks stay in tracking so they fire again on next cron tick
            mock_remove.assert_not_called()

    @pytest.mark.django_db
    @patch("apps.tasks.models.Task")
    def test_execute_database_task_not_found(self, mock_task_model, scheduler):
        """Test executing a task that doesn't exist."""
        from django.core.exceptions import ObjectDoesNotExist

        mock_task_model.objects.get.side_effect = ObjectDoesNotExist()
        mock_task_model.DoesNotExist = ObjectDoesNotExist

        with patch.object(scheduler, "_remove_database_task") as mock_remove:
            # Should not raise - error is caught and logged
            scheduler._execute_database_task(999)
            # Should remove the task from scheduler
            mock_remove.assert_called_once_with(999)


@pytest.mark.unit
class TestGlobalSchedulerFunctions:
    """Test cases for global scheduler functions."""

    @pytest.mark.django_db
    def test_get_scheduler_first_call(self):
        """Test getting scheduler instance for first time."""
        # Reset global instance
        import apps.tasks.cron_scheduler

        apps.tasks.cron_scheduler._scheduler_instance = None

        with patch("apps.tasks.cron_scheduler.UnifiedTaskScheduler") as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            scheduler = get_scheduler()

            assert scheduler == mock_instance
            mock_class.assert_called_once()

    def test_get_scheduler_subsequent_calls(self):
        """Test getting scheduler instance on subsequent calls."""
        import apps.tasks.cron_scheduler

        # Set up existing instance
        existing_instance = Mock()
        apps.tasks.cron_scheduler._scheduler_instance = existing_instance

        scheduler = get_scheduler()
        assert scheduler == existing_instance

    def test_start_scheduler(self):
        """Test starting the global scheduler."""
        with patch("apps.tasks.cron_scheduler.get_scheduler") as mock_get:
            mock_scheduler = Mock()
            mock_get.return_value = mock_scheduler

            result = start_scheduler()

            assert result == mock_scheduler
            mock_scheduler.start.assert_called_once()

    def test_stop_scheduler_with_instance(self):
        """Test stopping scheduler when instance exists."""
        import apps.tasks.cron_scheduler

        mock_instance = Mock()
        apps.tasks.cron_scheduler._scheduler_instance = mock_instance

        stop_scheduler()

        mock_instance.stop.assert_called_once()
        assert apps.tasks.cron_scheduler._scheduler_instance is None

    def test_stop_scheduler_no_instance(self):
        """Test stopping scheduler when no instance exists."""
        import apps.tasks.cron_scheduler

        apps.tasks.cron_scheduler._scheduler_instance = None

        # Should not raise any errors
        stop_scheduler()

        assert apps.tasks.cron_scheduler._scheduler_instance is None


@pytest.mark.parametrize(
    "function_name,expected_queue",
    [
        # Maintenance tasks
        ("hello_world", "maintenance"),
        ("cleanup_old_tasks", "maintenance"),
        ("cleanup_activitystream", "maintenance"),
        # Metrics tasks
        ("collect_hourly_metrics", "metrics"),
        ("collect_snapshot_metrics", "metrics"),
        ("collect_daily_metrics", "metrics"),
        ("daily_metrics_rollup", "metrics"),
        ("daily_anonymize_and_prepare", "metrics"),
        ("send_anonymized_to_segment", "metrics"),
        ("cleanup_metrics_data", "metrics"),
        # Dashboard tasks
        ("collect_dashboard_reports_initial_data", "dashboard"),
        ("collect_dashboard_reports_data", "dashboard"),
        ("cleanup_dashboard_reports_old_data", "dashboard"),
        # Unknown function (default)
        ("unknown_function", "maintenance"),
    ],
)
def test_queue_mapping_parametrized(function_name, expected_queue):
    """Test queue mapping for all known functions."""
    from apps.tasks.tasks import get_queue_for_function

    assert get_queue_for_function(function_name) == expected_queue
