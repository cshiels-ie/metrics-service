"""
Console script entry point for metrics-service (like aap-eda-manage).

Provides a single command that works regardless of Python interpreter (python vs python3.12).
When installed via pip/uv, the generated script uses the environment's Python.

Usage:
  metrics-service run
  metrics-service dispatcherd [--workers N] ...
  metrics-service scheduler [--check-interval N] [--log-level LEVEL] ...
  metrics-service init-default-settings
  metrics-service init-service-id
  metrics-service init-system-tasks [--list]
  metrics-service tasks create|list|show|cancel|retry ...
"""

import os
import sys

# Subcommands that map to Django management commands (argv[1] for execute_from_command_line).
# One-to-one: metrics-service <key> [args] -> Django argv = [prog, <value>, ...args]
# Include both short names (dispatcherd, scheduler) and full names (run_dispatcherd, run_task_scheduler)
# so that "metrics-service run" can spawn children as metrics-service run_dispatcherd / run_task_scheduler.
_DJANGO_COMMAND_MAP = {
    "dispatcherd": "run_dispatcherd",
    "scheduler": "run_task_scheduler",
    "run_dispatcherd": "run_dispatcherd",
    "run_task_scheduler": "run_task_scheduler",
}

# Subcommands that go to the metrics_service management command.
# metrics-service <key> [args] -> Django argv = [prog, "metrics_service", <value>, ...args]
_METRICS_SERVICE_SUBCOMMANDS = frozenset(
    {
        "run",
        "init-default-settings",
        "remove-default-settings",
        "init-service-id",
        "init-system-tasks",
        "tasks",
    }
)


def main() -> int:
    """Run metrics-service subcommand via Django management."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "metrics_service.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        sys.stderr.write("Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH?\n")
        raise SystemExit(1) from exc

    argv = list(sys.argv)
    prog = argv[0]
    rest = argv[1:]

    if not rest or rest[0] in ("-h", "--help"):
        # No subcommand or --help: show metrics_service help
        execute_from_command_line([prog, "metrics_service", "--help"])
        # Django execute_from_command_line calls sys.exit() on success
        # If we reach here, it means command succeeded
        return 0

    subcommand = rest[0]
    args = rest[1:]

    if subcommand in _DJANGO_COMMAND_MAP:
        # e.g. metrics-service dispatcherd --workers 4 -> run_dispatcherd --workers 4
        django_argv = [prog, _DJANGO_COMMAND_MAP[subcommand], *args]
        execute_from_command_line(django_argv)
        # Django execute_from_command_line calls sys.exit() on success
        # If we reach here, command succeeded
        return 0

    if subcommand in _METRICS_SERVICE_SUBCOMMANDS:
        # e.g. metrics-service run -> metrics_service run
        django_argv = [prog, "metrics_service", subcommand, *args]
        execute_from_command_line(django_argv)
        # Django execute_from_command_line calls sys.exit() on success
        # If we reach here, command succeeded
        return 0

    # Unknown subcommand: pass through to metrics_service so it can error with usage
    django_argv = [prog, "metrics_service", subcommand, *args]
    execute_from_command_line(django_argv)
    # Django execute_from_command_line calls sys.exit() on errors
    # If we reach here, command succeeded
    return 0


if __name__ == "__main__":
    sys.exit(main())
