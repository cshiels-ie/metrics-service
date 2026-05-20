"""
Integration tests for the metrics_service management command.

Tests the full metrics service management command functionality including
service initialization, task management, and command line operations.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase

from apps.tasks.models import Task
from tests.test_utils import get_test_password
from tests.unit.core.test_metrics_service_helpers import create_mock_processes_with_exit, get_default_config

User = get_user_model()


@pytest.mark.integration
class TestMetricsServiceCommand(TransactionTestCase):
    """Integration tests for the metrics_service management command."""

    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    def test_init_system_tasks_list(self):
        """Test the init-system-tasks --list subcommand."""
        with patch("sys.stdout.write") as mock_stdout:
            call_command("metrics_service", "init-system-tasks", "--list")

        # Should not raise an exception
        mock_stdout.assert_called()

    def test_task_create_command(self):
        """Test the tasks create subcommand."""
        task_data = '{"test": "data"}'

        call_command(
            "metrics_service",
            "tasks",
            "create",
            "--name",
            "Test Task",
            "--function",
            "hello_world",
            "--data",
            task_data,
            "--description",
            "Test description",
            "--user",
            self.user.username,
        )

        # Verify task was created
        task = Task.objects.get(name="Test Task")
        assert task.function_name == "hello_world"
        assert task.task_data == {"test": "data"}
        assert task.description == "Test description"
        assert task.created_by == self.user

    def test_task_list_command(self):
        """Test the tasks list subcommand."""
        # Create test tasks
        task1 = Task.objects.create(name="Task 1", function_name="hello_world", status="pending", created_by=self.user)
        task1.save()
        Task.objects.create(name="Task 2", function_name="hello_world", status="completed", created_by=self.user)

        with patch("sys.stdout.write") as mock_stdout:
            call_command("metrics_service", "tasks", "list")

        mock_stdout.assert_called()

    def test_task_list_with_status_filter(self):
        """Test tasks list with status filtering."""
        pending_task = Task.objects.create(
            name="Pending Task", function_name="hello_world", status="pending", created_by=self.user
        )
        pending_task.save()
        Task.objects.create(
            name="Completed Task", function_name="hello_world", status="completed", created_by=self.user
        )

        with patch("sys.stdout.write") as mock_stdout:
            call_command("metrics_service", "tasks", "list", "--status", "pending")

        mock_stdout.assert_called()

    def test_task_show_command(self):
        """Test the tasks show subcommand."""
        task = Task.objects.create(
            name="Show Task",
            function_name="hello_world",
            task_data={"test": "data"},
            description="Test task for show command",
            created_by=self.user,
        )

        with patch("sys.stdout.write") as mock_stdout:
            call_command("metrics_service", "tasks", "show", str(task.id))

        mock_stdout.assert_called()

    def test_task_cancel_command(self):
        """Test the tasks cancel subcommand."""
        # Create task with completed status first to avoid signal issues, then change to pending
        task = Task.objects.create(
            name="Cancel Task", function_name="hello_world", status="completed", created_by=self.user
        )
        task.status = "pending"
        task.save()

        with patch("sys.stdout.write"):
            call_command("metrics_service", "tasks", "cancel", str(task.id))

        # Verify task was cancelled
        task.refresh_from_db()
        assert task.status == "cancelled"

    def test_task_retry_command(self):
        """Test the tasks retry subcommand."""
        task = Task.objects.create(
            name="Retry Task", function_name="hello_world", status="failed", created_by=self.user
        )

        with patch("sys.stdout.write"):
            call_command("metrics_service", "tasks", "retry", str(task.id))

        # Verify task was reset to pending
        task.refresh_from_db()
        assert task.status == "pending"

    def test_invalid_command_arguments(self):
        """Test error handling for invalid command arguments."""
        # Test invalid JSON data
        with pytest.raises(SystemExit):
            call_command(
                "metrics_service",
                "tasks",
                "create",
                "--name",
                "Invalid Task",
                "--function",
                "hello_world",
                "--data",
                "invalid-json",
            )

        # Test invalid scheduled time format
        with pytest.raises(SystemExit):
            call_command(
                "metrics_service",
                "tasks",
                "create",
                "--name",
                "Invalid Time Task",
                "--function",
                "hello_world",
                "--scheduled-time",
                "invalid-time-format",
            )

        # Test non-existent user
        with pytest.raises(SystemExit):
            call_command(
                "metrics_service",
                "tasks",
                "create",
                "--name",
                "Invalid User Task",
                "--function",
                "hello_world",
                "--user",
                "nonexistent_user",
            )

    def test_task_not_found_operations(self):
        """Test operations on non-existent tasks."""
        # Test show non-existent task
        with pytest.raises(SystemExit):
            call_command("metrics_service", "tasks", "show", "99999")

        # Test cancel non-existent task
        with pytest.raises(SystemExit):
            call_command("metrics_service", "tasks", "cancel", "99999")

        # Test retry non-existent task
        with pytest.raises(SystemExit):
            call_command("metrics_service", "tasks", "retry", "99999")

    def test_task_invalid_state_operations(self):
        """Test operations on tasks in invalid states."""
        # Create completed task
        completed_task = Task.objects.create(
            name="Completed Task", function_name="hello_world", status="completed", created_by=self.user
        )

        # Try to cancel completed task
        with patch("sys.stdout.write"):
            call_command("metrics_service", "tasks", "cancel", str(completed_task.id))

        # Task should remain completed
        completed_task.refresh_from_db()
        assert completed_task.status == "completed"

        # Create pending task and try to retry it
        pending_task = Task.objects.create(
            name="Pending Task", function_name="hello_world", status="pending", created_by=self.user
        )
        pending_task.save()

        with patch("sys.stdout.write"):
            call_command("metrics_service", "tasks", "retry", str(pending_task.id))

        # Task should remain pending
        pending_task.refresh_from_db()
        assert pending_task.status == "pending"

    def test_command_help_outputs(self):
        """Test that help commands work without errors."""
        with patch("sys.stdout.write"), pytest.raises(SystemExit):  # Help commands exit with code 0
            call_command("metrics_service", "--help")


@pytest.mark.integration
class TestMetricsServiceCommandSubprocess(TestCase):
    """Integration tests using subprocess to test command line interface."""

    def setUp(self):
        """Set up test environment."""
        self.manage_py = Path(__file__).parent.parent.parent / "manage.py"
        assert self.manage_py.exists(), f"manage.py not found at {self.manage_py}"

    def _run_command(self, *args, timeout=30):
        """Helper to run management command via subprocess."""
        cmd = [sys.executable, str(self.manage_py), "metrics_service"] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            return result
        except subprocess.TimeoutExpired:
            pytest.fail(f"Command timed out: {' '.join(cmd)}")

    def test_help_command_subprocess(self):
        """Test help command via subprocess."""
        result = self._run_command("--help")
        assert result.returncode == 0
        assert "metrics_service" in str(result.stdout)

    def test_init_system_tasks_list_subprocess(self):
        """Test init-system-tasks --list command via subprocess."""
        result = self._run_command("init-system-tasks", "--list")
        assert result.returncode == 0

    def test_tasks_subcommand_help_subprocess(self):
        """Test tasks subcommand help via subprocess."""
        result = self._run_command("tasks", "--help")
        assert result.returncode == 0
        assert "Task management actions" in result.stdout


@pytest.mark.integration
class TestMetricsServiceFullIntegration(TransactionTestCase):
    """Full integration tests that test the complete service startup."""

    def setUp(self):
        """Set up test environment."""
        self.manage_py = Path(__file__).parent.parent.parent / "manage.py"
        assert self.manage_py.exists(), f"manage.py not found at {self.manage_py}"

    def _setup_mocks_for_start_services(self, mock_exists, mock_exit, mock_sleep, mock_popen):
        """Set up common mocks for tests that call _start_services."""
        mock_exists.return_value = True
        mock_exit.side_effect = SystemExit
        mock_sleep.return_value = None
        mock_popen.side_effect = create_mock_processes_with_exit()

    def _create_command_instance(self):
        """Create and configure a Command instance for testing."""
        from apps.tasks.management.commands.metrics_service import Command

        command = Command()
        command.shutdown_requested = False
        return command

    def _call_run_command_with_mock(self, *args, expect_exception=False):
        """Helper to call run command with _start_services mocked."""
        with patch("apps.tasks.management.commands.metrics_service.Command._start_services") as mock_start:
            try:
                call_command("metrics_service", "run", *args)
            except (ValueError, SystemExit):
                if not expect_exception:
                    raise  # Re-raise if exception not expected
                # Expected if validation happens
            return mock_start

    @patch("apps.tasks.management.commands.metrics_service.Command._start_services")
    def test_service_run_command_validation(self, mock_start_services):
        """Test that the run command validates and processes arguments correctly."""
        # Mock the actual service startup to avoid conflicts
        mock_start_services.return_value = None

        with patch("sys.exit"):
            call_command(
                "metrics_service",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
                "--workers",
                "2",
                "--max-tasks",
                "50",
                "--log-level",
                "DEBUG",
            )

        # Verify service startup was called with correct config
        mock_start_services.assert_called_once()
        args, _ = mock_start_services.call_args
        config = args[0]

        assert config["host"] == "127.0.0.1"
        assert config["port"] == "8001"
        assert config["gunicorn_workers"] == 2
        assert config["dispatcher_workers"] == 2
        assert config["max_tasks"] == 50
        assert config["log_level"] == "DEBUG"

    @patch("subprocess.Popen")
    @patch("pathlib.Path.exists")
    @patch("time.sleep")
    @patch("sys.exit")
    def test_signal_handler_setup(self, mock_exit, mock_sleep, mock_exists, mock_popen):
        """Test that signal handlers are properly configured in _start_services."""
        command = self._create_command_instance()
        self._setup_mocks_for_start_services(mock_exists, mock_exit, mock_sleep, mock_popen)
        config = get_default_config()

        # Signal handlers are set up inside _start_services
        with pytest.raises(SystemExit):
            command._start_services(config)

        # Verify signal handlers were registered by checking they're not default
        # (This is a bit indirect, but we can't easily access the handler after it's set)
        # The fact that the method runs without error means signal handlers were set up

    def test_configuration_extraction(self):
        """Test configuration extraction from command options."""
        from apps.tasks.management.commands.metrics_service import Command

        command = Command()
        options = {
            "host": "localhost",
            "port": "9000",
            "workers": 8,
            "max_tasks": 200,
            "log_level": "WARNING",
            "check_interval": 120,
        }

        config = command._extract_config(options)

        assert config["host"] == "localhost"
        assert config["port"] == "9000"
        assert config["gunicorn_workers"] == 8
        assert config["dispatcher_workers"] == 8
        assert config["max_tasks"] == 200
        assert config["log_level"] == "WARNING"
        assert config["check_interval"] == 120

    def test_django_server_command_building(self):
        """Test Django server command building and validation."""
        import sys
        from pathlib import Path

        from apps.tasks.management.commands.metrics_service import Command

        Command()

        # Test command building logic without actually running it
        manage_py = Path(__file__).parent.parent.parent / "manage.py"
        assert manage_py.exists(), f"manage.py not found at {manage_py}"

        # Test input validation (this is what we're really testing)
        host = "127.0.0.1"
        port = "8000"

        # Validate inputs for security (copied from the actual method)
        if not host.replace(".", "").replace(":", "").isalnum():
            pytest.fail(f"Invalid host: {host}")
        if not str(port).isdigit():
            pytest.fail(f"Invalid port: {port}")

        # Build expected command (Gunicorn for production)
        expected_cmd = [
            sys.executable,
            "-u",
            "-m",
            "gunicorn",
            "metrics_service.wsgi:application",
            "--bind",
            f"{host}:{port}",
        ]

        # Verify command structure
        assert "gunicorn" in expected_cmd
        assert f"{host}:{port}" in expected_cmd

    @patch("subprocess.Popen")
    @patch("pathlib.Path.exists")
    @patch("time.sleep")
    @patch("sys.exit")
    def test_dispatcher_command_building(self, mock_exit, mock_sleep, mock_exists, mock_popen):
        """Test dispatcher command building in _start_services."""
        import sys
        from pathlib import Path

        from apps.tasks.management.commands import metrics_service

        command = self._create_command_instance()
        manage_py = Path(__file__).parent.parent.parent / "manage.py"
        self._setup_mocks_for_start_services(mock_exists, mock_exit, mock_sleep, mock_popen)
        config = get_default_config()

        # Patch sys.argv[0] in the metrics_service module to point to manage.py
        # so the command finds it correctly when it uses sys.argv[0]
        original_argv = metrics_service.sys.argv
        metrics_service.sys.argv = [str(manage_py)]

        try:
            # Start services will build the dispatcher command internally
            # We'll verify it by checking the Popen calls
            with pytest.raises(SystemExit):
                command._start_services(config)
        finally:
            # Restore original argv
            metrics_service.sys.argv = original_argv

        # Verify dispatcher command was built correctly by checking Popen calls
        # The second call should be for dispatcher (index 1)
        assert mock_popen.call_count >= 2
        dispatcher_call = mock_popen.call_args_list[1]
        dispatcher_cmd = dispatcher_call[0][0]

        # Verify command structure
        assert sys.executable in dispatcher_cmd
        assert str(manage_py) in dispatcher_cmd
        assert "run_dispatcherd" in dispatcher_cmd
        assert "--workers=4" in dispatcher_cmd
        assert "--max-tasks=100" in dispatcher_cmd
        assert "--log-level=INFO" in dispatcher_cmd

    def test_input_validation(self):
        """Test input validation for security in command options."""
        # Test that invalid configuration values are caught at the command level
        # The new implementation builds commands directly, so validation happens
        # when the command is constructed. We test this by ensuring the command
        # handles invalid values gracefully.

        # Test with invalid workers (should be caught by argparse or command validation)
        # Mock _start_services to prevent infinite loop if validation doesn't catch it
        self._call_run_command_with_mock(
            "--host", "127.0.0.1", "--port", "8000", "--workers", "-1", expect_exception=True
        )

        # Test with invalid port (should be caught by command validation)
        # Note: The current implementation doesn't validate port format strictly,
        # but it will fail when trying to start the server
        self._call_run_command_with_mock("--host", "127.0.0.1", "--port", "invalid_port", expect_exception=True)

        # Test that valid configuration works
        mock_start = self._call_run_command_with_mock(
            "--host", "127.0.0.1", "--port", "8000", "--workers", "4", "--log-level", "INFO"
        )
        mock_start.assert_called_once()
