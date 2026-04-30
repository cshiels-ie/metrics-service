"""
Comprehensive unit tests for tasks utils module.
"""

from datetime import UTC
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.tasks import utils
from apps.tasks.collectors.send_anonymized_to_segment import send_to_segment
from apps.tasks.models import Task, TaskExecution


class TaskUtilsTestCase(TestCase):
    """Test cases for task utility functions."""

    def setUp(self):
        """Set up test data."""
        self.user = self._create_test_user()
        # Create task with signals disabled to prevent automatic submission to dispatcherd
        self.task = self._create_task_safely(
            name="Test Task", function_name="test_function", task_data={"param": "value"}, created_by=self.user
        )

    def _create_test_user(self):
        """Create a test user."""
        from apps.core.models import User

        return User.objects.create_user(username="testuser", email="test@example.com")

    def _create_task_safely(self, **kwargs):
        """Create a task without triggering signals."""
        task = Task(**kwargs)
        task.save()
        return task

    def test_handle_task_error_with_instances(self):
        """Test error handling with task and execution instances."""
        execution = TaskExecution.objects.create(task=self.task, status="running", worker_id="test-worker")

        result = utils.handle_task_error(
            task_instance=self.task, execution_instance=execution, error_message="Test error"
        )

        self.task.refresh_from_db()
        execution.refresh_from_db()

        self.assertEqual(self.task.status, "failed")
        self.assertEqual(self.task.error_message, "Test error")
        self.assertIsNotNone(self.task.completed_at)

        self.assertEqual(execution.status, "failed")
        self.assertEqual(execution.error_message, "Test error")
        self.assertIsNotNone(execution.completed_at)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "Test error")

    def test_handle_task_error_with_exception(self):
        """Test error handling with exception."""
        utils.handle_task_error(task_instance=self.task, exception=ValueError("Test exception"))

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "failed")
        self.assertIn("Test exception", self.task.error_message)

    def test_handle_task_error_with_ids(self):
        """Test error handling with task and execution IDs."""
        execution = TaskExecution.objects.create(task=self.task, status="running", worker_id="test-worker")

        utils.handle_task_error(task_id=self.task.id, execution_id=execution.id, error_message="Test error")

        self.task.refresh_from_db()
        execution.refresh_from_db()

        self.assertEqual(self.task.status, "failed")
        self.assertEqual(execution.status, "failed")

    def test_handle_task_error_invalid_ids(self):
        """Test error handling with invalid IDs."""
        result = utils.handle_task_error(task_id=99999, execution_id=99999, error_message="Test error")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "Test error")

    def test_update_task_status_completed(self):
        """Test updating task status to completed."""
        execution = TaskExecution.objects.create(task=self.task, status="running", worker_id="test-worker")

        result_data = {"result": "success"}
        utils.update_task_status(self.task, execution, "completed", result_data)

        self.task.refresh_from_db()
        execution.refresh_from_db()

        self.assertEqual(self.task.status, "completed")
        self.assertEqual(self.task.result_data, result_data)
        self.assertEqual(self.task.error_message, "")
        self.assertIsNotNone(self.task.completed_at)

        self.assertEqual(execution.status, "completed")
        self.assertEqual(execution.result_data, result_data)

    def test_update_task_status_running(self):
        """Test updating task status to running."""
        utils.update_task_status(self.task, None, "running")

        self.task.refresh_from_db()

        self.assertEqual(self.task.status, "running")
        self.assertIsNotNone(self.task.started_at)
        self.assertEqual(self.task.attempts, 1)

    def test_update_task_status_failed(self):
        """Test updating task status to failed."""
        utils.update_task_status(self.task, None, "failed", error_message="Test error")

        self.task.refresh_from_db()

        self.assertEqual(self.task.status, "failed")
        self.assertEqual(self.task.error_message, "Test error")
        self.assertIsNotNone(self.task.completed_at)

    def test_create_task_result_success(self):
        """Test creating successful task result."""
        data = {"key": "value"}
        result = utils.create_task_result("success", data)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["key"], "value")
        self.assertIn("timestamp", result)

    def test_create_task_result_error(self):
        """Test creating error task result."""
        result = utils.create_task_result("error", error="Test error")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "Test error")
        self.assertIn("timestamp", result)

    def test_create_task_result_minimal(self):
        """Test creating minimal task result."""
        result = utils.create_task_result("pending")

        self.assertEqual(result["status"], "pending")
        self.assertIn("timestamp", result)
        self.assertNotIn("error", result)

    @patch("apps.tasks.utils.logger")
    def test_log_task_execution_info(self, mock_logger):
        """Test logging task execution with info level."""
        utils.log_task_execution("test_task", "start", "Starting task", "info")

        mock_logger.info.assert_called_once_with("Task 'test_task' start: Starting task")

    @patch("apps.tasks.utils.logger")
    def test_log_task_execution_error(self, mock_logger):
        """Test logging task execution with error level."""
        utils.log_task_execution("test_task", "error", "Task failed", "error")

        mock_logger.error.assert_called_once_with("Task 'test_task' error: Task failed")

    @patch("apps.tasks.utils.logger")
    def test_log_task_execution_no_details(self, mock_logger):
        """Test logging task execution without details."""
        utils.log_task_execution("test_task", "complete")

        mock_logger.info.assert_called_once_with("Task 'test_task' complete")


class TestParseDatetimeString(TestCase):
    """Test parse_datetime_string function."""

    def test_parse_valid_iso_datetime(self):
        """Test parsing valid ISO datetime string."""
        result = utils.parse_datetime_string("2024-01-15T10:30:00+00:00")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)

    def test_parse_datetime_with_z_suffix(self):
        """Test parsing datetime with Z suffix (UTC)."""
        result = utils.parse_datetime_string("2024-06-20T15:45:00Z")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 20)

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = utils.parse_datetime_string("")

        self.assertIsNone(result)

    def test_parse_none(self):
        """Test parsing None returns None."""
        result = utils.parse_datetime_string(None)

        self.assertIsNone(result)

    def test_parse_invalid_datetime(self):
        """Test parsing invalid datetime returns None."""
        result = utils.parse_datetime_string("not-a-date")

        self.assertIsNone(result)

    def test_parse_partial_date(self):
        """Test parsing partial date returns None."""
        result = utils.parse_datetime_string("2024-01")

        self.assertIsNone(result)

    def test_parse_naive_datetime_assumes_utc(self):
        """Test parsing naive datetime (no timezone) assumes UTC."""

        result = utils.parse_datetime_string("2024-01-15T10:30:00")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)
        # Verify it's timezone-aware
        self.assertIsNotNone(result.tzinfo)
        # Verify it's UTC
        self.assertEqual(result.tzinfo, UTC)


class TestGetDbConnection(TestCase):
    """Test get_db_connection function."""

    @patch("django.db.connections")
    def test_get_db_connection_default(self, mock_connections):
        """Test getting default AWX database connection."""
        mock_raw_conn = MagicMock()
        mock_django_conn = MagicMock()
        mock_django_conn.connection = mock_raw_conn
        mock_connections.__getitem__.return_value = mock_django_conn

        result = utils.get_db_connection()

        mock_connections.__getitem__.assert_called_once_with("awx")
        mock_django_conn.ensure_connection.assert_called_once()
        self.assertEqual(result, mock_raw_conn)

    @patch("django.db.connections")
    def test_get_db_connection_custom_db(self, mock_connections):
        """Test getting custom database connection."""
        mock_raw_conn = MagicMock()
        mock_django_conn = MagicMock()
        mock_django_conn.connection = mock_raw_conn
        mock_connections.__getitem__.return_value = mock_django_conn

        result = utils.get_db_connection("custom_db")

        mock_connections.__getitem__.assert_called_once_with("custom_db")
        self.assertEqual(result, mock_raw_conn)

    @patch("django.db.close_old_connections")
    @patch("django.db.connections")
    def test_get_db_connection_does_not_call_close_old_connections(self, mock_connections, mock_close_old):
        """Test that get_db_connection does NOT call close_old_connections.

        close_old_connections() closes ALL Django connections, not just one.
        If called during task execution, it can close connections holding advisory locks,
        causing lock release failures.

        close_old_connections() should only be called at task entry points like run_with_lock().
        """
        mock_raw_conn = MagicMock()
        mock_django_conn = MagicMock()
        mock_django_conn.connection = mock_raw_conn
        mock_connections.__getitem__.return_value = mock_django_conn

        result = utils.get_db_connection()

        # Verify close_old_connections was NOT called
        mock_close_old.assert_not_called()
        # Verify ensure_connection was still called
        mock_django_conn.ensure_connection.assert_called_once()
        self.assertEqual(result, mock_raw_conn)


class TestRunWithLock(TestCase):
    """Test run_with_lock function."""

    @patch("metrics_utility.library.lock.lock")
    def test_run_with_lock_acquired(self, mock_lock_cls):
        """Test run_with_lock when lock is acquired."""
        mock_lock_cls.return_value.__enter__ = MagicMock(return_value=True)
        mock_lock_cls.return_value.__exit__ = MagicMock(return_value=False)

        fn = MagicMock(return_value={"status": "success"})
        result = utils.run_with_lock("my_lock", "my_task", fn, foo="bar")

        fn.assert_called_once_with(foo="bar")
        self.assertEqual(result["status"], "success")

    @patch("metrics_utility.library.lock.lock")
    def test_run_with_lock_not_acquired(self, mock_lock_cls):
        """Test run_with_lock when lock cannot be acquired."""
        mock_lock_cls.return_value.__enter__ = MagicMock(return_value=False)
        mock_lock_cls.return_value.__exit__ = MagicMock(return_value=False)

        fn = MagicMock()
        result = utils.run_with_lock("my_lock", "my_task", fn)

        fn.assert_not_called()
        self.assertEqual(result["status"], "error")
        self.assertIn("Could not acquire lock", result["error"])

    @patch("django.db.close_old_connections")
    @patch("metrics_utility.library.lock.lock")
    def test_run_with_lock_calls_close_old_connections(self, mock_lock_cls, mock_close_old):
        """Test that run_with_lock calls close_old_connections before acquiring lock.

        This is critical because close_old_connections() must be called BEFORE
        acquiring advisory locks to ensure stale connections are cleaned up first.
        If called during execution, it would close ALL connections including the
        one holding the lock.
        """
        mock_lock_cls.return_value.__enter__ = MagicMock(return_value=True)
        mock_lock_cls.return_value.__exit__ = MagicMock(return_value=False)

        fn = MagicMock(return_value={"status": "success"})
        utils.run_with_lock("my_lock", "my_task", fn, foo="bar")

        # Verify close_old_connections was called
        mock_close_old.assert_called_once()


class TestGenerateSalt(TestCase):
    """Test generate_salt function."""

    def test_generate_salt_returns_string(self):
        """Test generate_salt returns a string."""
        result = utils.generate_salt()

        self.assertIsInstance(result, str)

    def test_generate_salt_is_uuid_format(self):
        """Test generate_salt returns UUID4 format."""
        import uuid

        result = utils.generate_salt()

        # Should be valid UUID
        uuid.UUID(result)  # Raises ValueError if invalid

    def test_generate_salt_unique(self):
        """Test generate_salt returns unique values."""
        salt1 = utils.generate_salt()
        salt2 = utils.generate_salt()

        self.assertNotEqual(salt1, salt2)


class TestSendToSegment(TestCase):
    """Test send_to_segment function."""

    @patch("apps.tasks.collectors.send_anonymized_to_segment.logger")
    def test_send_to_segment_import_error(self, mock_logger):
        """Test send_to_segment when metrics-utility import fails."""
        with (
            patch.dict("sys.modules", {"metrics_utility.library.storage.segment": None}),
            patch("apps.tasks.collectors.send_anonymized_to_segment.logger"),
        ):
            # The function handles ImportError internally, so we need to test the fallback
            result = send_to_segment("user1", "test_event", {"data": "test"})

            # Result should indicate segment not available if metrics-utility is not installed
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["error"], "segment_not_available")

    def test_send_to_segment_no_write_key(self):
        """Test send_to_segment when SEGMENT_WRITE_KEY not configured."""
        with (
            patch("metrics_utility.library.storage.segment.SEGMENT_AVAILABLE", True),
            patch("metrics_utility.library.storage.segment.StorageSegment", MagicMock()),
            patch("django.conf.settings") as mock_settings,
        ):
            mock_settings.SEGMENT_WRITE_KEY = None

            result = send_to_segment("user1", "test_event", {"data": "test"})

            self.assertEqual(result["status"], "unavailable")
            self.assertIn("SEGMENT_WRITE_KEY not configured", result["error"])

    @patch("apps.tasks.collectors.send_anonymized_to_segment.logger")
    def test_send_to_segment_success(self, mock_logger):
        """Test send_to_segment successful transmission."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.put.return_value = ["chunk1", "chunk2"]

        with (
            patch("metrics_utility.library.storage.segment.SEGMENT_AVAILABLE", True),
            patch(
                "metrics_utility.library.storage.segment.StorageSegment", return_value=mock_storage_instance
            ) as mock_storage_class,
            patch("django.conf.settings") as mock_settings,
        ):
            mock_settings.SEGMENT_WRITE_KEY = "test-write-key"
            mock_settings.DEBUG = False

            result = send_to_segment("user1", "test_event", {"data": "test"})

            self.assertEqual(result["status"], "success")
            mock_storage_class.assert_called_once_with(
                write_key="test-write-key",
                user_id="user1",
                debug=False,
            )

    @patch("apps.tasks.collectors.send_anonymized_to_segment.logger")
    def test_send_to_segment_exception(self, mock_logger):
        """Test send_to_segment handles exceptions."""
        with (
            patch("metrics_utility.library.storage.segment.SEGMENT_AVAILABLE", True),
            patch("metrics_utility.library.storage.segment.StorageSegment") as mock_storage_class,
            patch("django.conf.settings") as mock_settings,
        ):
            mock_settings.SEGMENT_WRITE_KEY = "test-write-key"
            mock_storage_class.side_effect = Exception("Connection error")

            result = send_to_segment("user1", "test_event", {"data": "test"})

            self.assertEqual(result["status"], "error")
            self.assertIn("Connection error", result["error"])
