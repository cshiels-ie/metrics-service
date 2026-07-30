"""
Shared test helpers for metrics_service command tests.

This module contains helper functions used by both unit and integration tests
to avoid code duplication.
"""

from unittest.mock import MagicMock


def create_mock_processes_with_exit():
    """Create mock processes where Django process exits after first check."""
    poll_call_count = {"django": 0}

    def django_poll_side_effect():
        """Simulate Django process that exits after first monitoring check."""
        poll_call_count["django"] += 1
        if poll_call_count["django"] == 1:
            return None  # First check: still running
        return 0  # Exited

    django_process = MagicMock()
    django_process.poll.side_effect = django_poll_side_effect
    django_process.returncode = 0
    django_process.terminate.return_value = None
    django_process.kill.return_value = None

    other_process = MagicMock()
    other_process.poll.return_value = None
    other_process.terminate.return_value = None
    other_process.kill.return_value = None

    return [django_process, other_process, other_process]


def get_default_config(log_level="INFO", gunicorn_workers=4, dispatcher_workers=4):
    """Get default test configuration."""
    return {
        "host": "127.0.0.1",
        "port": "8000",
        "gunicorn_workers": gunicorn_workers,
        "dispatcher_workers": dispatcher_workers,
        "log_level": log_level,
        "max_tasks": 100,
        "check_interval": 60,
    }
