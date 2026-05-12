"""
Integration tests for apps.core.management.commands.metrics_service module.
"""

import json
from argparse import ArgumentParser
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from apps.tasks.management.commands.metrics_service import Command
from tests.unit.core.test_metrics_service_helpers import create_mock_processes_with_exit, get_default_config


class BaseCommandTestCase(TestCase):
    """Base test class with common setup/teardown for command tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = Command()
        self.out = StringIO()
        self.err = StringIO()
        self.command.shutdown_requested = False

    def tearDown(self):
        """Clean up test fixtures."""
        # Ensure shutdown is requested to stop any running processes
        self.command.shutdown_requested = True

    def setup_command_output(self):
        """Configure command to use test stdout."""
        self.command.stdout = self.out
        self.command.output.stdout = self.out

    def assert_subcommand_exists(self, parser, subcommand_name):
        """Assert that a subcommand exists in the parser."""
        actions = {action.dest: action for action in parser._actions}
        assert "command" in actions
        assert hasattr(actions["command"], "choices")
        assert subcommand_name in actions["command"].choices

    def create_test_setting(self, key, current_value, previous_value=None, last_modified_by=None):
        """Create a test Setting object with given parameters."""
        from apps.dynamic_settings.models import Setting

        return Setting.objects.create(
            setting_key=key,
            current_value=json.dumps(current_value),
            previous_value=json.dumps(previous_value) if previous_value is not None else None,
            last_modified_by=last_modified_by,
        )


class TestMetricsServiceCommand(BaseCommandTestCase):
    """Test metrics_service management command."""

    def test_command_help_text(self):
        """Test command has proper help text."""
        assert self.command.help == "Metrics service management - unified entry point for all service operations"

    def test_add_arguments(self):
        """Test add_arguments method configures parser correctly."""
        parser = ArgumentParser()
        self.command.add_arguments(parser)

        # Test that subcommands are added
        for subcommand in ["run", "init-service-id", "init-system-tasks", "tasks"]:
            self.assert_subcommand_exists(parser, subcommand)

    def test_extract_config(self):
        """Test _extract_config method."""
        options = {
            "host": "localhost",
            "port": "9000",
            "workers": 8,
            "timeout": 7200,
            "max_tasks": 200,
            "log_level": "DEBUG",
            "check_interval": 120,
        }

        config = self.command._extract_config(options)

        assert config == {
            "host": "localhost",
            "port": "9000",
            "gunicorn_workers": 8,
            "dispatcher_workers": 8,
            "timeout": 7200,
            "max_tasks": 200,
            "log_level": "DEBUG",
            "check_interval": 120,
        }

    def test_extract_config_split_workers(self):
        """Test _extract_config with explicit gunicorn_workers and dispatcher_workers."""
        options = {
            "host": "127.0.0.1",
            "port": "8000",
            "workers": 4,
            "gunicorn_workers": 2,
            "dispatcher_workers": 8,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
            "check_interval": 60,
        }

        config = self.command._extract_config(options)

        assert config["gunicorn_workers"] == 2
        assert config["dispatcher_workers"] == 8

    def _setup_start_services_mocks(self, mock_exit, mock_sleep, mock_exists, mock_popen):
        """Helper to set up common mocks for start_services tests."""
        self.setup_command_output()
        mock_exists.return_value = True
        mock_exit.side_effect = SystemExit
        mock_sleep.return_value = None
        mock_popen.side_effect = create_mock_processes_with_exit()

    @patch("signal.signal")
    @patch("subprocess.Popen")
    @patch("pathlib.Path.exists")
    @patch("time.sleep")
    @patch("sys.exit")
    def test_signal_handlers_in_start_services(self, mock_exit, mock_sleep, mock_exists, mock_popen, mock_signal):
        """Test that signal handlers are set up in _start_services."""
        self._setup_start_services_mocks(mock_exit, mock_sleep, mock_exists, mock_popen)
        config = get_default_config()

        # Signal handlers are set up inside _start_services
        # We'll verify they're called when the method runs
        with pytest.raises(SystemExit):
            self.command._start_services(config)

        # Verify signal handlers were registered (called twice for SIGINT and SIGTERM)
        assert mock_signal.call_count >= 2

    @patch("subprocess.Popen")
    @patch("signal.signal")
    @patch("pathlib.Path.exists")
    @patch("time.sleep")
    @patch("sys.exit")
    def test_start_services_success(self, mock_exit, mock_sleep, mock_exists, mock_signal, mock_popen):
        """Test _start_services method success path."""
        self._setup_start_services_mocks(mock_exit, mock_sleep, mock_exists, mock_popen)
        config = get_default_config()

        # sys.exit will raise SystemExit, which we need to catch
        with pytest.raises(SystemExit):
            self.command._start_services(config)

        # Should exit when process exits
        mock_exit.assert_called()

        # Verify processes were started (3 processes: Django, Dispatcher, Scheduler)
        assert mock_popen.call_count == 3

        # Check output contains startup message
        output = self.out.getvalue()
        assert "Starting metrics service:" in output
        assert "Django server: http://127.0.0.1:8000" in output
        assert "Gunicorn workers: 4" in output
        assert "Dispatcher workers: 4" in output

    @patch("subprocess.Popen")
    @patch("pathlib.Path.exists")
    @patch("sys.exit")
    def test_start_services_exception(self, mock_exit, mock_exists, mock_popen):
        """Test _start_services handles exceptions."""
        self.setup_command_output()

        # Mock Path.exists to raise an exception (simulating an error during startup)
        mock_exists.side_effect = Exception("Test error")
        # Make sys.exit actually raise SystemExit so execution stops
        mock_exit.side_effect = SystemExit
        # Prevent subprocess.Popen from actually creating processes
        mock_popen.side_effect = Exception("Test error")

        config = get_default_config()

        # The exception should be caught and sys.exit(1) should be called
        with pytest.raises(SystemExit):
            self.command._start_services(config)

        mock_exit.assert_called_once_with(1)

        output = self.out.getvalue()
        assert "Failed to start services: Test error" in output

    @patch.object(Command, "_handle_run_command")
    def test_handle_method(self, mock_run_command):
        """Test handle method orchestration."""
        options = {"command": "run", "host": "127.0.0.1", "port": "8000", "workers": 4}

        self.command.handle(**options)

        # Verify the run command handler was called
        mock_run_command.assert_called_once_with(options)

    @patch("subprocess.Popen")
    @patch("pathlib.Path.exists")
    @patch("time.sleep")
    @patch("sys.exit")
    def test_start_services_builds_correct_commands(self, mock_exit, mock_sleep, mock_exists, mock_popen):
        """Test that _start_services builds correct commands for all three processes."""
        import sys

        from apps.tasks.management.commands import metrics_service

        self._setup_start_services_mocks(mock_exit, mock_sleep, mock_exists, mock_popen)

        manage_py = Path(__file__).parent.parent.parent.parent / "manage.py"
        # Patch sys.argv[0] in the metrics_service module to point to manage.py
        # so the command finds it correctly when it uses sys.argv[0]
        original_argv = metrics_service.sys.argv
        metrics_service.sys.argv = [str(manage_py)]

        config = get_default_config(log_level="DEBUG")

        try:
            with pytest.raises(SystemExit):
                self.command._start_services(config)
        finally:
            # Restore original argv
            metrics_service.sys.argv = original_argv

        # Verify 3 processes were started
        assert mock_popen.call_count == 3

        # Verify Django command (Gunicorn WSGI server)
        django_call = mock_popen.call_args_list[0]
        django_cmd = django_call[0][0]
        assert sys.executable in django_cmd
        assert "gunicorn" in django_cmd
        assert "metrics_service.wsgi:application" in django_cmd
        assert "127.0.0.1:8000" in django_cmd
        assert "--workers" in django_cmd and "4" in django_cmd
        assert "--log-level" in django_cmd and "debug" in django_cmd  # DEBUG level

        # Verify Dispatcher command
        dispatcher_call = mock_popen.call_args_list[1]
        dispatcher_cmd = dispatcher_call[0][0]
        assert sys.executable in dispatcher_cmd
        assert str(manage_py) in dispatcher_cmd
        assert "run_dispatcherd" in dispatcher_cmd
        assert "--workers=4" in dispatcher_cmd
        assert "--timeout=3600" in dispatcher_cmd
        assert "--max-tasks=100" in dispatcher_cmd
        assert "--log-level=DEBUG" in dispatcher_cmd

        # Verify Scheduler command
        scheduler_call = mock_popen.call_args_list[2]
        scheduler_cmd = scheduler_call[0][0]
        assert sys.executable in scheduler_cmd
        assert str(manage_py) in scheduler_cmd
        assert "run_task_scheduler" in scheduler_cmd
        assert "--log-level=DEBUG" in scheduler_cmd
        assert "--check-interval=60" in scheduler_cmd


class TestMetricsServiceSignalHandling(BaseCommandTestCase):
    """Test signal handling functionality."""


class TestMetricsServiceEdgeCases(BaseCommandTestCase):
    """Test edge cases and error conditions."""


@pytest.mark.django_db
class TestInitDefaultSettingsCommand(BaseCommandTestCase):
    """Test the init-default-settings management command."""

    def test_import_setting_model(self):
        """Test that Setting model can be imported correctly."""
        from apps.dynamic_settings.models import Setting

        # Verify the import works and Setting is a class
        assert hasattr(Setting, "objects")

    def test_import_initialize_default_settings(self):
        """Test that initialize_default_settings function can be imported correctly."""
        from apps.dynamic_settings.utils import initialize_default_settings

        # Verify the import works and it's callable
        assert initialize_default_settings is not None
        assert callable(initialize_default_settings)

    def test_handle_init_default_settings_creates_settings(self):
        """Test that _handle_init_default_settings_command creates settings when they don't exist."""
        from apps.dynamic_settings.models import Setting

        # Ensure no settings exist
        Setting.objects.all().delete()

        # Run the command
        self.setup_command_output()
        self.command._handle_init_default_settings_command()

        # Verify settings were created
        assert Setting.objects.count() > 0
        assert Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").exists()
        assert Setting.objects.filter(setting_key="METRICS_COLLECTION").exists()

        # Check output
        output = self.out.getvalue()
        assert "Initialized default settings" in output

    @override_settings(FEATURE_ENABLED={"ANONYMIZED_DATA_COLLECTION": True, "METRICS_COLLECTION": True})
    def test_handle_init_default_settings_updates_unchanged_defaults(self):
        """Test that init updates unchanged default settings to match current config."""
        from apps.dynamic_settings.models import Setting

        # Create an unchanged default setting with non-default value
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", False, None)

        # Run the command
        self.setup_command_output()
        self.command._handle_init_default_settings_command()

        # Verify setting was updated to default value (True)
        assert Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").count() == 1
        setting = Setting.objects.get(setting_key="ANONYMIZED_DATA_COLLECTION")
        # Value should be reset to default (True)
        assert json.loads(setting.current_value) is True

        # Check output
        output = self.out.getvalue()
        assert "Initialized default settings" in output

    def test_handle_init_default_settings_skips_modified_settings(self):
        """Test that init preserves modified settings (those with previous_value)."""
        from apps.dynamic_settings.models import Setting

        # Create a modified setting (has previous_value)
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", False, True)

        # Run the command
        self.setup_command_output()
        self.command._handle_init_default_settings_command()

        # Verify no duplicate settings were created
        assert Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").count() == 1
        setting = Setting.objects.get(setting_key="ANONYMIZED_DATA_COLLECTION")
        # Modified value should remain unchanged (False)
        assert json.loads(setting.current_value) is False
        # previous_value should still be present
        assert json.loads(setting.previous_value) is True

        # Check output
        output = self.out.getvalue()
        assert "Initialized default settings" in output

    def test_handle_init_default_settings_via_handle(self):
        """Test that init-default-settings command works via handle method."""
        from apps.dynamic_settings.models import Setting

        # Ensure no settings exist
        Setting.objects.all().delete()

        # Run via handle method
        self.setup_command_output()
        options = {"command": "init-default-settings"}
        self.command.handle(**options)

        # Verify settings were created
        assert Setting.objects.count() > 0

        # Check output
        output = self.out.getvalue()
        assert "Initialized default settings" in output

    @patch("apps.tasks.apps.load_task_feature_flags")
    @patch("apps.dynamic_settings.utils.initialize_default_settings")
    def test_handle_init_default_settings_seeds_aap_flags(self, mock_initialize, mock_load_flags):
        """init-default-settings also calls load_task_feature_flags to seed AAPFlags.

        In production the DB is pre-migrated before the service starts, so the
        post_migrate signal that normally seeds AAPFlags during `migrate` never fires.
        init-default-settings must therefore call load_task_feature_flags() directly.
        """
        self.setup_command_output()
        self.command._handle_init_default_settings_command()

        mock_load_flags.assert_called_once()

    @patch("apps.dynamic_settings.utils.initialize_default_settings")
    def test_handle_init_default_settings_error_handling(self, mock_initialize):
        """Test error handling in _handle_init_default_settings_command."""
        from django.core.management.base import CommandError

        # Make initialize_default_settings raise an exception
        mock_initialize.side_effect = Exception("Database error")

        # Run the command and expect CommandError
        with pytest.raises(CommandError) as exc_info:
            self.command._handle_init_default_settings_command()

        assert "Failed to initialize default settings" in str(exc_info.value)
        assert "Database error" in str(exc_info.value)

    @override_settings(FEATURE_ENABLED={"ANONYMIZED_DATA_COLLECTION": True, "METRICS_COLLECTION": True})
    def test_handle_init_default_settings_with_overwrite(self):
        """Test that _handle_init_default_settings_command with --overwrite removes even modified settings."""
        from apps.dynamic_settings.models import Setting

        # Create a modified default setting (has previous_value)
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", False, True)

        # Run the command with --overwrite
        self.setup_command_output()
        options = {"overwrite": True}
        self.command._handle_init_default_settings_command(options)

        # Verify setting was recreated with default value
        assert Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").exists()
        setting = Setting.objects.get(setting_key="ANONYMIZED_DATA_COLLECTION")
        # Value should be reset to default (True) and previous_value should be None
        assert json.loads(setting.current_value) is True
        assert setting.previous_value is None

        # Check output
        output = self.out.getvalue()
        assert "Initialized default settings" in output

    def test_command_includes_init_default_settings(self):
        """Test that init-default-settings is registered as a subcommand."""
        parser = ArgumentParser()
        self.command.add_arguments(parser)
        self.assert_subcommand_exists(parser, "init-default-settings")

    def test_command_includes_remove_default_settings(self):
        """Test that remove-default-settings is registered as a subcommand."""
        parser = ArgumentParser()
        self.command.add_arguments(parser)
        self.assert_subcommand_exists(parser, "remove-default-settings")

    def test_handle_remove_default_settings_removes_unchanged_settings(self):
        """Test that _handle_remove_default_settings_command only removes unchanged default settings."""
        from apps.dynamic_settings.models import Setting

        # Create unchanged default setting (previous_value is None)
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", True, None)

        # Create a non-default setting
        self.create_test_setting("CUSTOM_SETTING", "test", None)

        initial_count = Setting.objects.count()
        assert initial_count == 2

        # Run the command
        self.setup_command_output()
        options = {"all_known": False, "all_settings": False}
        self.command._handle_remove_default_settings_command(options)

        # Verify only unchanged default settings were removed
        assert Setting.objects.count() == 1
        assert not Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").exists()
        # Custom setting should remain
        assert Setting.objects.filter(setting_key="CUSTOM_SETTING").exists()

        # Check output
        output = self.out.getvalue()
        assert "Removed 1 settings" in output

    def test_handle_remove_default_settings_when_none_exist(self):
        """Test that _handle_remove_default_settings_command handles no settings gracefully."""
        from apps.dynamic_settings.models import Setting

        # Ensure no settings exist
        Setting.objects.all().delete()

        # Run the command
        self.setup_command_output()
        options = {"all_known": False, "all_settings": False}
        self.command._handle_remove_default_settings_command(options)

        # Check output
        output = self.out.getvalue()
        assert "Removed 0 settings" in output

    def test_handle_remove_default_settings_via_handle(self):
        """Test that remove-default-settings command works via handle method."""
        from apps.dynamic_settings.models import Setting

        # Create a default setting
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", True, None)

        # Run via handle method
        self.setup_command_output()
        options = {"command": "remove-default-settings", "all_known": False, "all_settings": False}
        self.command.handle(**options)

        # Verify setting was removed
        assert not Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").exists()

        # Check output
        output = self.out.getvalue()
        assert "Removed" in output

    @patch("apps.dynamic_settings.utils.remove_default_settings")
    def test_handle_remove_default_settings_error_handling(self, mock_remove):
        """Test error handling in _handle_remove_default_settings_command."""
        from django.core.management.base import CommandError

        # Make remove_default_settings raise an exception
        mock_remove.side_effect = Exception("Database error")

        # Run the command and expect CommandError
        options = {"all_known": False, "all_settings": False}
        with pytest.raises(CommandError) as exc_info:
            self.command._handle_remove_default_settings_command(options)

        assert "Failed to remove default settings" in str(exc_info.value)
        assert "Database error" in str(exc_info.value)

    def test_handle_remove_default_settings_with_all_known(self):
        """Test that _handle_remove_default_settings_command with --all-known removes even modified settings."""
        from apps.dynamic_settings.models import Setting

        # Create unchanged default setting
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", True, None)

        # Create a non-default setting
        self.create_test_setting("CUSTOM_SETTING", "test", None)

        initial_count = Setting.objects.count()
        assert initial_count == 2

        # Run the command with --all-known
        self.setup_command_output()
        options = {"all_known": True, "all_settings": False}
        self.command._handle_remove_default_settings_command(options)

        # Verify default setting was removed
        assert Setting.objects.count() == 1
        assert not Setting.objects.filter(setting_key="ANONYMIZED_DATA_COLLECTION").exists()
        # Custom setting should remain
        assert Setting.objects.filter(setting_key="CUSTOM_SETTING").exists()

        # Check output
        output = self.out.getvalue()
        assert "Removed 1 settings" in output

    def test_handle_remove_default_settings_with_all_settings(self):
        """Test that _handle_remove_default_settings_command with --all-settings removes all settings."""
        from apps.dynamic_settings.models import Setting

        # Create various settings
        self.create_test_setting("ANONYMIZED_DATA_COLLECTION", False, True)
        self.create_test_setting("CUSTOM_SETTING", "test", None)

        initial_count = Setting.objects.count()
        assert initial_count == 2

        # Run the command with --all-settings
        self.setup_command_output()
        options = {"all_known": False, "all_settings": True}
        self.command._handle_remove_default_settings_command(options)

        # Verify ALL settings were removed
        assert Setting.objects.count() == 0

        # Check output
        output = self.out.getvalue()
        assert "Removed 2 settings" in output


@pytest.mark.django_db
class TestInitServiceIdCommand(BaseCommandTestCase):
    """Test the init-service-id management command."""

    def test_import_service_id_model(self):
        """Test that ServiceID model can be imported correctly."""
        from ansible_base.resource_registry.models.service_identifier import ServiceID

        # Verify the import works and ServiceID is a class
        assert ServiceID is not None
        assert hasattr(ServiceID, "objects")

    def test_import_base_command(self):
        """Test that BaseCommand can be imported correctly."""
        from django.core.management.base import BaseCommand

        # Verify the import works
        assert BaseCommand is not None
        assert hasattr(BaseCommand, "handle")

    def test_command_inherits_from_base_command(self):
        """Test that Command class properly inherits from BaseCommand."""
        from django.core.management.base import BaseCommand

        assert issubclass(Command, BaseCommand)
        assert hasattr(self.command, "handle")
        assert hasattr(self.command, "help")
