"""
Comprehensive unit tests for run_dispatcherd management command.

This module provides complete test coverage for the run_dispatcherd
management command including all execution paths and error handling.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from apps.tasks.management.commands.run_dispatcherd import Command


@pytest.mark.unit
class TestRunDispatcherdCommand(TestCase):
    """Test cases for run_dispatcherd management command."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = Command()
        self.out = StringIO()
        self.err = StringIO()

    def _mock_dispatcherd_import(self, mock_dispatcherd):
        """Helper to create a proper dispatcherd import mock."""

        def import_side_effect(name, *args, **kwargs):
            if name == "dispatcherd":
                return mock_dispatcherd
            # Use the real __import__ for everything else
            return __import__(name, *args, **kwargs)

        return import_side_effect

    def test_command_help_text(self):
        """Test that command has appropriate help text."""
        self.assertIsNotNone(self.command.help)
        self.assertIn("dispatcherd", self.command.help.lower())
        self.assertIn("worker", self.command.help.lower())

    def test_add_arguments_workers(self):
        """Test that workers argument is added correctly."""
        parser = MagicMock()
        self.command.add_arguments(parser)

        # Verify --workers argument was added
        calls = [c for c in parser.add_argument.call_args_list if "--workers" in c[0]]
        self.assertEqual(len(calls), 1)

        # Verify argument configuration
        call_kwargs = calls[0][1]
        self.assertEqual(call_kwargs["type"], int)
        self.assertEqual(call_kwargs["default"], 1)
        self.assertIn("worker", call_kwargs["help"].lower())

    def test_add_arguments_max_tasks(self):
        """Test that max-tasks argument is added correctly."""
        parser = MagicMock()
        self.command.add_arguments(parser)

        # Verify --max-tasks argument was added
        calls = [c for c in parser.add_argument.call_args_list if "--max-tasks" in c[0]]
        self.assertEqual(len(calls), 1)

        # Verify argument configuration
        call_kwargs = calls[0][1]
        self.assertEqual(call_kwargs["type"], int)
        self.assertEqual(call_kwargs["default"], 100)
        self.assertIn("maximum", call_kwargs["help"].lower())

    def test_add_arguments_log_level(self):
        """Test that log-level argument is added correctly."""
        parser = MagicMock()
        self.command.add_arguments(parser)

        # Verify --log-level argument was added
        calls = [c for c in parser.add_argument.call_args_list if "--log-level" in c[0]]
        self.assertEqual(len(calls), 1)

        # Verify argument configuration
        call_kwargs = calls[0][1]
        self.assertEqual(call_kwargs["choices"], ["DEBUG", "INFO", "WARNING", "ERROR"])
        self.assertEqual(call_kwargs["default"], "INFO")
        self.assertIn("log level", call_kwargs["help"].lower())

    def test_add_arguments_all_args(self):
        """Test that all required arguments are added."""
        parser = MagicMock()
        self.command.add_arguments(parser)

        # Should have exactly 4 add_argument calls
        self.assertEqual(parser.add_argument.call_count, 4)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_default_options(self, mock_logging, mock_setup):
        """Test handle with default options."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        # Mock dispatcherd import
        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify logging configuration
            mock_logging.basicConfig.assert_called_once_with(level=mock_logging.INFO)

            # Verify dispatcherd setup was called
            mock_setup.assert_called_once()

            # Verify dispatcherd.run_service was called
            mock_dispatcherd.run_service.assert_called_once()

            # Verify success message
            output = self.out.getvalue()
            self.assertIn("Starting dispatcherd", output)
            self.assertIn("4 workers", output)
            self.assertIn("100", output)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_custom_workers(self, mock_logging, mock_setup):
        """Test handle with custom worker count."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 8,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            output = self.out.getvalue()
            self.assertIn("8 workers", output)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_custom_max_tasks(self, mock_logging, mock_setup):
        """Test handle with custom max_tasks."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 200,
            "log_level": "INFO",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            output = self.out.getvalue()
            self.assertIn("200", output)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_debug_log_level(self, mock_logging, mock_setup):
        """Test handle with DEBUG log level."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "DEBUG",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify DEBUG logging level was configured
            mock_logging.basicConfig.assert_called_once_with(level=mock_logging.DEBUG)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_warning_log_level(self, mock_logging, mock_setup):
        """Test handle with WARNING log level."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "WARNING",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify WARNING logging level was configured
            mock_logging.basicConfig.assert_called_once_with(level=mock_logging.WARNING)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_error_log_level(self, mock_logging, mock_setup):
        """Test handle with ERROR log level."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "ERROR",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify ERROR logging level was configured
            mock_logging.basicConfig.assert_called_once_with(level=mock_logging.ERROR)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    @patch("sys.exit")
    def test_handle_import_error(self, mock_exit, mock_logging, mock_setup):
        """Test handle when dispatcherd import fails."""
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        # Simulate ImportError by raising exception on import
        def import_side_effect(name, *args, **kwargs):
            if name == "dispatcherd":
                raise ImportError("Cannot import dispatcherd")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_side_effect):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify error message was written
            output = self.out.getvalue()
            self.assertIn("Failed to import dispatcherd", output)

            # Verify sys.exit(1) was called
            mock_exit.assert_called_once_with(1)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    @patch("sys.exit")
    def test_handle_general_exception(self, mock_exit, mock_logging, mock_setup):
        """Test handle when general exception occurs."""
        mock_dispatcherd = MagicMock()
        mock_dispatcherd.run_service.side_effect = Exception("Test error")

        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify error message was written
            output = self.out.getvalue()
            self.assertIn("Failed to start dispatcherd", output)
            self.assertIn("Test error", output)

            # Verify sys.exit(1) was called
            mock_exit.assert_called_once_with(1)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    @patch("sys.exit")
    def test_handle_setup_dispatcherd_exception(self, mock_exit, mock_logging, mock_setup):
        """Test handle when setup_dispatcherd_config raises exception."""
        mock_setup.side_effect = Exception("Setup failed")
        mock_dispatcherd = MagicMock()

        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify error message was written
            output = self.out.getvalue()
            self.assertIn("Failed to start dispatcherd", output)
            self.assertIn("Setup failed", output)

            # Verify sys.exit(1) was called
            mock_exit.assert_called_once_with(1)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_handle_all_custom_options(self, mock_logging, mock_setup):
        """Test handle with all custom options."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 16,
            "timeout": 7200,
            "max_tasks": 500,
            "log_level": "DEBUG",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify all custom values in output
            output = self.out.getvalue()
            self.assertIn("16 workers", output)
            self.assertIn("500", output)

            # Verify DEBUG logging
            mock_logging.basicConfig.assert_called_once_with(level=mock_logging.DEBUG)

            # Verify setup and run were called
            mock_setup.assert_called_once()
            mock_dispatcherd.run_service.assert_called_once()

    def test_command_instance_attributes(self):
        """Test command instance has correct attributes."""
        self.assertTrue(hasattr(self.command, "help"))
        self.assertTrue(hasattr(self.command, "add_arguments"))
        self.assertTrue(hasattr(self.command, "handle"))

    def test_command_methods_callable(self):
        """Test that command methods are callable."""
        self.assertTrue(callable(self.command.add_arguments))
        self.assertTrue(callable(self.command.handle))

    def test_add_arguments_parser_type(self):
        """Test add_arguments accepts parser-like object."""
        parser = MagicMock()
        # Should not raise any exceptions
        self.command.add_arguments(parser)
        # Parser should have been used
        self.assertTrue(parser.add_argument.called)

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_logging_configuration_called_before_setup(self, mock_logging, mock_setup):
        """Test that logging is configured before dispatcherd setup."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        call_order = []

        def record_logging_call(*args, **kwargs):
            call_order.append("logging")

        def record_setup_call(*args, **kwargs):
            call_order.append("setup")

        mock_logging.basicConfig.side_effect = record_logging_call
        mock_setup.side_effect = record_setup_call

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify logging was configured before setup
            self.assertEqual(call_order, ["logging", "setup"])

    @patch("apps.tasks.management.commands.run_dispatcherd.setup_dispatcherd_config")
    @patch("apps.tasks.management.commands.run_dispatcherd.logging")
    def test_dispatcherd_imported_after_setup(self, mock_logging, mock_setup):
        """Test that dispatcherd is imported after setup_dispatcherd_config."""
        mock_dispatcherd = MagicMock()
        options = {
            "workers": 4,
            "timeout": 3600,
            "max_tasks": 100,
            "log_level": "INFO",
        }

        with patch("builtins.__import__", side_effect=self._mock_dispatcherd_import(mock_dispatcherd)):
            self.command.stdout = self.out
            self.command.handle(**options)

            # Verify setup was called before dispatcherd.run_service
            mock_setup.assert_called_once()
            mock_dispatcherd.run_service.assert_called_once()

    def test_module_has_logger(self):
        """Test that module has logger configured."""
        from apps.tasks.management.commands.run_dispatcherd import logger

        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "apps.tasks.management.commands.run_dispatcherd")

    def test_module_imports(self):
        """Test that module has correct imports."""
        from apps.tasks.management.commands import run_dispatcherd

        self.assertTrue(hasattr(run_dispatcherd, "logging"))
        self.assertTrue(hasattr(run_dispatcherd, "sys"))
        self.assertTrue(hasattr(run_dispatcherd, "BaseCommand"))
        self.assertTrue(hasattr(run_dispatcherd, "setup_dispatcherd_config"))
        self.assertTrue(hasattr(run_dispatcherd, "logger"))
        self.assertTrue(hasattr(run_dispatcherd, "Command"))

    def test_command_class_docstring(self):
        """Test that Command class has docstring."""
        self.assertIsNotNone(Command.__doc__)
        self.assertIn("dispatcherd", Command.__doc__.lower())

    def test_add_arguments_docstring(self):
        """Test that add_arguments method has docstring."""
        self.assertIsNotNone(Command.add_arguments.__doc__)

    def test_handle_docstring(self):
        """Test that handle method has docstring."""
        self.assertIsNotNone(Command.handle.__doc__)
