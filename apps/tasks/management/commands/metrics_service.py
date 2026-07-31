"""
Fixed Django management command for the metrics service.

This version ensures dispatcherd uses the same configuration as the standalone
run_dispatcherd command, fixing the configuration inconsistency issue.
"""

import contextlib
import json
import selectors
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.tasks.models import Task
from apps.tasks.services import OutputFormatter

User = get_user_model()


class Command(BaseCommand):
    """
    Fixed management command for the metrics service.

    This command ensures dispatcherd uses the same configuration as the
    standalone run_dispatcherd command.
    """

    help = "Metrics service management - unified entry point for all service operations"

    def __init__(self, *args, **kwargs):
        """Initialize the command with service instances."""
        super().__init__(*args, **kwargs)
        self.output = OutputFormatter(self.stdout, self.style)

    def add_arguments(self, parser):
        """Add command line arguments."""
        # Main subcommands
        subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

        # Run command (main service)
        run_parser = subparsers.add_parser("run", help="Run the complete metrics service")
        self._add_run_arguments(run_parser)

        # Init commands
        init_settings_parser = subparsers.add_parser("init-default-settings", help="Initialize default settings")
        self._add_init_settings_arguments(init_settings_parser)
        remove_settings_parser = subparsers.add_parser("remove-default-settings", help="Remove default settings")
        self._add_remove_settings_arguments(remove_settings_parser)
        subparsers.add_parser("init-service-id", help="Initialize ServiceID for ansible-base")
        init_tasks_parser = subparsers.add_parser("init-system-tasks", help="Initialize system tasks")
        self._add_init_tasks_arguments(init_tasks_parser)

        # Task management
        tasks_parser = subparsers.add_parser("tasks", help="Manage database tasks")
        self._add_task_management_arguments(tasks_parser)

    def _add_run_arguments(self, parser):
        """Add arguments for the run command."""
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="Host to bind the Django server to (default: 127.0.0.1)",
        )
        parser.add_argument(
            "--port",
            default="8000",
            help="Port to bind the Django server to (default: 8000)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=4,
            help="Number of workers for both Gunicorn and dispatcher when not overridden (default: 4)",
        )
        parser.add_argument(
            "--gunicorn-workers",
            type=int,
            default=None,
            dest="gunicorn_workers",
            help="Number of Gunicorn worker processes (default: value of --workers)",
        )
        parser.add_argument(
            "--dispatcher-workers",
            type=int,
            default=None,
            dest="dispatcher_workers",
            help="Number of dispatcher worker processes (default: value of --workers)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=3600,
            help="Deprecated, no effect. Use METRICS_SERVICE_TASK_TIMEOUT env var.",
        )
        parser.add_argument(
            "--max-tasks",
            type=int,
            default=100,
            help="Maximum tasks per worker before respawn (default: 100)",
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Log level for both services (default: INFO)",
        )
        parser.add_argument(
            "--check-interval",
            type=int,
            default=60,
            help="Task scheduler check interval in seconds (default: 60)",
        )

    def _add_init_settings_arguments(self, parser):
        """Add arguments for the init-default-settings command."""

    def _add_remove_settings_arguments(self, parser):
        """Add arguments for the remove-default-settings command."""
        parser.add_argument(
            "--all-settings",
            action="store_true",
            help="Remove all settings from the database",
        )

    def _add_init_tasks_arguments(self, parser):
        """Add arguments for the init_system_tasks command."""
        parser.add_argument(
            "--list",
            action="store_true",
            help="List current system tasks",
        )

    def _add_task_management_arguments(self, parser):
        """Add arguments for task management."""
        task_subparsers = parser.add_subparsers(dest="task_action", help="Task management actions", required=True)

        # Create task
        create_parser = task_subparsers.add_parser("create", help="Create a new task")
        create_parser.add_argument("--name", required=True, help="Task name")
        create_parser.add_argument("--function", required=True, help="Function name to execute")
        create_parser.add_argument("--data", help="JSON data for the task")
        create_parser.add_argument("--description", default="", help="Task description")
        create_parser.add_argument("--scheduled-time", help="Schedule time (YYYY-MM-DD HH:MM:SS)")
        create_parser.add_argument("--cron", help="Cron expression for recurring tasks")
        create_parser.add_argument("--user", help="Username of task creator")

        # List tasks
        list_parser = task_subparsers.add_parser("list", help="List tasks")
        list_parser.add_argument("--status", help="Filter by status")
        list_parser.add_argument("--limit", type=int, default=20, help="Limit number of results")

        # Show task details
        show_parser = task_subparsers.add_parser("show", help="Show task details")
        show_parser.add_argument("task_id", type=int, help="Task ID")

        # Cancel task
        cancel_parser = task_subparsers.add_parser("cancel", help="Cancel a task")
        cancel_parser.add_argument("task_id", type=int, help="Task ID")

        # Retry task
        retry_parser = task_subparsers.add_parser("retry", help="Retry a failed task")
        retry_parser.add_argument("task_id", type=int, help="Task ID")

    def handle(self, *args, **options):
        """
        Handle the command execution.

        Routes to the appropriate subcommand handler based on the command option.
        """
        command = options.get("command")

        try:
            if command == "run":
                self._handle_run_command(options)
            elif command == "init-default-settings":
                self._handle_init_default_settings_command()
            elif command == "remove-default-settings":
                self._handle_remove_default_settings_command(options)
            elif command == "init-service-id":
                self._handle_init_service_id_command()
            elif command == "init-system-tasks":
                self._handle_init_system_tasks_command(options)
            elif command == "tasks":
                self._handle_task_management_command(options)
            else:
                self.output.error(f"Unknown command: {command}")
                sys.exit(1)
        except CommandError as e:
            self.output.error(str(e))
            sys.exit(1)
        except Exception as e:
            self.output.error(f"Unexpected error: {e}")
            sys.exit(1)

    def _handle_run_command(self, options: dict[str, Any]) -> None:
        """Handle the run command to start the metrics service (API, dispatcherd, scheduler only).

        Does not run migrations or init (init-default-settings, init-service-id, init-system-tasks).
        Those are separate steps, e.g. via entrypoint-init.sh or manual metrics-service init-* commands.
        """
        try:
            config = self._extract_config(options)
            self._start_services(config)
        except ValueError as e:
            raise CommandError(f"Configuration error: {e}") from e

    def _handle_init_default_settings_command(self) -> None:
        """Handle the init-default-settings command."""
        try:
            from apps.dynamic_settings.utils import initialize_default_settings
            from apps.tasks.apps import load_task_feature_flags, sync_flag_values_from_settings

            initialize_default_settings()
            # Seed metrics-specific AAPFlags from feature_flags.yaml. This
            # mirrors what the post_migrate signal does during `migrate`, but
            # must also run here because init-default-settings is called in
            # production without a preceding migrate (DB is pre-migrated).
            flags_seeded = load_task_feature_flags()
            # Propagate installer settings.yaml overrides (e.g. FEATURE_DASHBOARD_COLLECTION_ENABLED: True)
            # to AAPFlag values so the Gateway UI reflects the installer's intent.
            sync_flag_values_from_settings()
            if flags_seeded:
                self.output.success("Initialized default settings")
            else:
                self.output.warning(
                    "Initialized default settings in the database, but task feature flags could not be seeded; see logs.",
                )
        except Exception as e:
            raise CommandError(f"Failed to initialize default settings: {e}") from e

    def _handle_remove_default_settings_command(self, options: dict[str, Any]) -> None:
        """Handle the remove-default-settings command."""
        try:
            from apps.dynamic_settings.utils import remove_default_settings

            all_settings = options.get("all_settings", False)

            removed_count = remove_default_settings(all_settings=all_settings)
            self.output.success(f"Removed {removed_count} settings")
        except Exception as e:
            raise CommandError(f"Failed to remove default settings: {e}") from e

    def _handle_init_service_id_command(self) -> None:
        """Handle the init-service-id command."""
        try:
            from ansible_base.resource_registry.models.service_identifier import ServiceID

            service_id_count = ServiceID.objects.count()

            if service_id_count == 0:
                service_id = ServiceID.objects.create()
                message = f"Created ServiceID: {service_id.pk}"
                self.output.success(message)
            else:
                existing = ServiceID.objects.first()
                message = f"ServiceID exists: {existing.pk}"
                self.output.warning(message)
        except Exception as e:
            raise CommandError(f"Failed to initialize ServiceID: {e}") from e

    def _handle_init_system_tasks_command(self, options: dict[str, Any]) -> None:
        """Handle the init_system_tasks command."""
        # Handle --list option
        if options.get("list", False):
            self._list_system_tasks()
            return

        # Execute the initialization
        self.output.info("System Tasks Initialization")

        try:
            import time

            from apps.tasks.tasks import create_system_tasks

            start_time = time.time()
            results = create_system_tasks()
            elapsed_time = time.time() - start_time

            self._display_system_tasks_results(results, elapsed_time)
            if results.get("error"):
                raise CommandError(results["error"])
        except ImportError as e:
            raise CommandError(f"Failed to import system tasks module: {e}") from e
        except Exception as e:
            raise CommandError(f"❌ Failed to initialize system tasks: {e}") from e

    def _display_system_tasks_results(self, results, elapsed_time):
        """Display the results of system tasks initialization."""
        # Display results summary
        self.output.write("")
        self.output.write("Results:")
        if results.get("removed", 0) > 0:
            self.output.write(f"  Removed: {results['removed']} tasks")
        if results.get("created", 0) > 0:
            self.output.write(f"  Created: {results['created']} tasks")
        self.output.write("")

        # Display task details
        self._display_task_details(results)

        # Display final summary
        self.output.write_separator()
        self.output.success(f"Recreated {results.get('created', 0)} system tasks in {elapsed_time:.2f} seconds")
        self.output.write("Run 'python manage.py metrics_service init-system-tasks --list' to see current status")

    def _display_task_details(self, results):
        """Display detailed task information."""
        if not results.get("tasks", []):
            return

        self.output.write("Task Details:")
        for task_info in results["tasks"]:
            self.output.write(f"  {task_info}")
        self.output.write("")

    def _list_system_tasks(self):
        """List current system tasks."""
        try:
            from apps.tasks.models import Task
            from apps.tasks.tasks import TASK_METADATA

            system_tasks = Task.objects.filter(is_system_task=True).order_by("name")

            if not system_tasks.exists():
                self.output.write("📭 No system tasks found")
                return

            self.output.write("📋 Current System Tasks")
            self.output.write_separator()

            # Group tasks by category from TASK_METADATA
            categories: dict[str, list] = {}
            for task in system_tasks:
                metadata = TASK_METADATA.get(task.function_name, {})
                category = metadata.get("category", "Other")
                categories.setdefault(category, []).append(task)

            # Display tasks grouped by category
            for category, tasks in sorted(categories.items()):
                self.output.write(f"\n🏷️  {category} ({len(tasks)} tasks)")
                self.output.write_separator("-", 40)

                for task in tasks:
                    status_icon = {"pending": "⏳", "completed": "✅"}.get(task.status, "❌")
                    self.output.write(f"  {status_icon} {task.name}")
                    self.output.write(f"    Function: {task.function_name}")
                    if task.cron_expression:
                        self.output.write(f"    Schedule: {task.cron_expression}")
                    self.output.write(f"    Status: {task.status}")
                    self.output.write("")

            total = sum(len(t) for t in categories.values())
            self.output.write_separator()
            self.output.write(f"📊 Total: {total} system tasks")
            self.output.write(f"📂 Categories: {', '.join(c.lower() for c in sorted(categories))}")

        except Exception as e:
            self.output.error(f"❌ Failed to list system tasks: {e}")

    def _handle_task_create(self, options: dict[str, Any]) -> None:
        """Handle task creation."""
        try:
            # Parse task data if provided
            task_data = {}
            if options.get("data"):
                try:
                    task_data = json.loads(options["data"])
                except json.JSONDecodeError as e:
                    raise CommandError(f"Invalid JSON data: {e}") from e

            # Parse scheduled time if provided
            scheduled_time = None
            if options.get("scheduled_time"):
                try:
                    scheduled_time = datetime.strptime(options["scheduled_time"], "%Y-%m-%d %H:%M:%S")
                    scheduled_time = timezone.make_aware(scheduled_time)
                except ValueError as e:
                    raise CommandError(f"Invalid scheduled time format. Use YYYY-MM-DD HH:MM:SS: {e}") from e

            # Get user if specified
            created_by = None
            if options.get("user"):
                try:
                    created_by = User.objects.get(username=options["user"])
                except User.DoesNotExist as e:
                    raise CommandError(f"User '{options['user']}' not found") from e

            # Create the task
            task = Task.objects.create(
                name=options["name"],
                function_name=options["function"],
                task_data=task_data,
                description=options.get("description", ""),
                scheduled_time=scheduled_time,
                cron_expression=options.get("cron"),
                created_by=created_by,
            )

            self.output.success(f"✅ Created task: {task.name} (ID: {task.id})")

        except Exception as e:
            raise CommandError(f"Failed to create task: {e}") from e

    def _handle_task_list(self, options: dict[str, Any]) -> None:
        """Handle task listing."""
        queryset = Task.objects.all()

        # Apply status filter if provided
        if options.get("status"):
            queryset = queryset.filter(status=options["status"])

        # Apply limit
        limit = options.get("limit", 20)
        tasks = queryset.order_by("-created")[:limit]

        if not tasks:
            self.output.write("📭 No tasks found")
            return

        self.output.write(f"📋 Tasks (showing up to {limit} results)")
        self.output.write_separator()

        for task in tasks:
            status_icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌", "cancelled": "⏹️"}.get(
                task.status, "❓"
            )
            self.output.write(f"{status_icon} {task.name} (ID: {task.id})")
            self.output.write(f"    Status: {task.status} | Function: {task.function_name}")
            if task.created_by:
                self.output.write(f"    Created by: {task.created_by.username}")
            self.output.write("")

    def _handle_task_show(self, options: dict[str, Any]) -> None:
        """Handle showing task details."""
        task_id = options["task_id"]
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist as e:
            raise CommandError(f"Task with ID {task_id} not found") from e

        self.output.write(f"📋 Task Details: {task.name}")
        self.output.write_separator()
        self.output.write(f"ID: {task.id}")
        self.output.write(f"Name: {task.name}")
        self.output.write(f"Function: {task.function_name}")
        self.output.write(f"Status: {task.status}")
        if task.description:
            self.output.write(f"Description: {task.description}")
        if task.task_data:
            self.output.write(f"Data: {json.dumps(task.task_data, indent=2)}")
        if task.created_by:
            self.output.write(f"Created by: {task.created_by.username}")
        self.output.write(f"Created: {task.created}")
        if task.scheduled_time:
            self.output.write(f"Scheduled: {task.scheduled_time}")
        if task.cron_expression:
            self.output.write(f"Cron: {task.cron_expression}")

    def _handle_task_cancel(self, options: dict[str, Any]) -> None:
        """Handle task cancellation."""
        task_id = options["task_id"]
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist as e:
            raise CommandError(f"Task with ID {task_id} not found") from e

        if task.status in ["pending", "running"]:
            task.status = "cancelled"
            task.save(update_fields=["status", "modified"])
            self.output.success(f"✅ Cancelled task: {task.name}")
        else:
            self.output.warning(f"⚠️ Task {task.name} is in '{task.status}' state and cannot be cancelled")

    def _handle_task_retry(self, options: dict[str, Any]) -> None:
        """Handle task retry."""
        task_id = options["task_id"]
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist as e:
            raise CommandError(f"Task with ID {task_id} not found") from e

        if task.status == "failed":
            task.status = "pending"
            task.save(update_fields=["status", "modified"])
            self.output.success(f"✅ Retrying task: {task.name}")
        else:
            self.output.warning(f"⚠️ Task {task.name} is in '{task.status}' state and cannot be retried")

    def _start_services(self, config: dict[str, Any]) -> None:
        """
        Start all 3 services as separate processes and monitor them.

        This is the new simplified approach that directly spawns 3 processes
        (like the Procfile commands) and exits when any one exits.
        """
        processes = []
        process_names = ["Django", "Dispatcher", "Scheduler"]
        process_outputs = {}  # Map stdout file descriptor to (process, name)

        self._setup_signal_handlers_for_processes(processes)

        try:
            manage_py = sys.argv[0]
            self._display_startup_message(config)

            commands = self._build_service_commands(manage_py, config)
            for i, cmd in enumerate(commands):
                # Capture both stdout and stderr
                # Commands are built from trusted sources (manage.py and known commands)
                process = subprocess.Popen(  # noqa: S603
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Combine stderr into stdout
                    text=True,
                    bufsize=1,  # Line buffered
                )
                processes.append(process)

                # Store mapping of file descriptor to process info for select-based reading
                if process.stdout:
                    process_outputs[process.stdout.fileno()] = (process, process_names[i])

            self.output.write("All services started")
            self.output.write("Metrics service is running (Press Ctrl+C to stop)")
            self.output.write("")

            self._monitor_processes_with_select(processes, process_names, process_outputs)

        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(processes)
        except Exception as e:
            self._handle_startup_error(processes, e)

    def _display_startup_message(self, config: dict[str, Any]) -> None:
        """Display startup message with service configuration."""
        self.output.success("Starting metrics service:")
        self.output.write(f"Django server: http://{config['host']}:{config['port']}")
        self.output.write(f"Gunicorn workers: {config['gunicorn_workers']}")
        self.output.write(f"Dispatcher workers: {config['dispatcher_workers']}")
        self.output.write("Task scheduler: APScheduler with cron support")

    def _build_service_commands(self, manage_py: str | Path, config: dict[str, Any]) -> list[list[str]]:
        """Build commands for all three services (Gunicorn + Dispatcher + Scheduler)."""
        # Use Gunicorn for production-ready WSGI; logs to stdout for container-friendly output
        django_cmd = [
            sys.executable,
            "-u",
            "-m",
            "gunicorn",
            "metrics_service.wsgi:application",
            "--bind",
            f"{config['host']}:{config['port']}",
            "--workers",
            str(config["gunicorn_workers"]),
            "--capture-output",
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
            "--log-level",
            config["log_level"].lower(),
        ]

        dispatcher_cmd = [
            sys.executable,
            "-u",
            str(manage_py),
            "run_dispatcherd",
            f"--workers={config['dispatcher_workers']}",
            f"--max-tasks={config['max_tasks']}",
            f"--log-level={config['log_level']}",
        ]

        scheduler_cmd = [
            sys.executable,
            "-u",
            str(manage_py),
            "run_task_scheduler",
            f"--log-level={config['log_level']}",
            f"--check-interval={config['check_interval']}",
        ]

        return [django_cmd, dispatcher_cmd, scheduler_cmd]

    def _setup_signal_handlers_for_processes(self, processes: list[subprocess.Popen]) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            """Handle shutdown signal."""
            self.output.warning("Shutting down services...")
            self._cleanup_all_processes(processes)
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _cleanup_all_processes(self, processes: list[subprocess.Popen]) -> None:
        """Clean up all running processes."""
        for process in processes:
            if process.poll() is None:
                with contextlib.suppress(OSError, ProcessLookupError):
                    # Process may have already terminated
                    process.terminate()
        time.sleep(3)
        for process in processes:
            if process.poll() is None:
                with contextlib.suppress(OSError, ProcessLookupError):
                    # Process may have already been killed
                    process.kill()

    def _read_remaining_output(self, process: subprocess.Popen, process_name: str) -> None:
        """Read any remaining output from a process that has exited."""
        if process.stdout:
            try:
                remaining = process.stdout.read()
                if remaining:
                    self.output.write(f"\n{process_name} final output:")
                    for line in remaining.splitlines():
                        if line.strip():
                            self.output.write(f"  {line}")
            except (OSError, ValueError) as e:
                # Output stream may already be closed
                # Log only if it's an unexpected error type
                if "Bad file descriptor" not in str(e) and "I/O operation on closed file" not in str(e):
                    self.output.write(f"  (Note: Could not read remaining output: {e})")

    def _monitor_processes_with_select(
        self,
        processes: list[subprocess.Popen],
        process_names: list[str],
        process_outputs: dict[int, tuple[subprocess.Popen, str]],
    ) -> None:
        """Monitor processes using selectors for non-blocking I/O (no threading)."""
        # Create selector for cross-platform support
        selector = selectors.DefaultSelector()

        # Register all stdout file descriptors
        for _fd, (process, name) in process_outputs.items():
            selector.register(process.stdout, selectors.EVENT_READ, (process, name))

        try:
            while True:
                # Check if any process has exited
                for i, process in enumerate(processes):
                    if process.poll() is not None:
                        exit_code = process.returncode
                        self.output.write("")  # Empty line for separation
                        self.output.error(f"❌ {process_names[i]} process exited with code {exit_code}")

                        # Read any remaining output
                        self._read_remaining_output(process, process_names[i])

                        self._cleanup_all_processes(processes)
                        sys.exit(exit_code)

                # Wait for data to be available (with timeout)
                events = selector.select(timeout=0.5)

                # Read available data from all ready file descriptors
                for key, _mask in events:
                    process, name = key.data
                    if process.poll() is None:  # Process still running
                        try:
                            line = process.stdout.readline()
                            if line:
                                line = line.rstrip()
                                if line:
                                    self.output.write(f"[{name}] {line}")
                        except (OSError, ValueError) as e:
                            # Pipe may have closed
                            if process.poll() is None:
                                self.output.warning(f"[{name}] Error reading output: {e}")
        finally:
            # Clean up selector
            for key in list(selector.get_map().values()):
                selector.unregister(key.fileobj)
            selector.close()

    def _handle_keyboard_interrupt(self, processes: list[subprocess.Popen]) -> None:
        """Handle keyboard interrupt gracefully."""
        self.output.warning("Received interrupt, shutting down...")
        self._cleanup_all_processes(processes)

    def _handle_startup_error(self, processes: list[subprocess.Popen], error: Exception) -> None:
        """Handle startup errors."""
        self.output.error(f"Failed to start services: {error}")
        # Output the full traceback
        self.output.write("")
        self.output.write("Full traceback:")
        self.output.write_separator("-", 50)
        for line in traceback.format_exception(type(error), error, error.__traceback__):
            self.output.write(line.rstrip())
        self._cleanup_all_processes(processes)
        sys.exit(1)

    def _extract_config(self, options: dict[str, Any]) -> dict[str, Any]:
        """Extract configuration from command options."""
        workers = options.get("workers", 4)
        # argparse sets gunicorn_workers/dispatcher_workers to None when not passed;
        # treat None as "use workers" so options.get(..., workers) works as intended
        gunicorn_workers = options.get("gunicorn_workers")
        dispatcher_workers = options.get("dispatcher_workers")
        if gunicorn_workers is None:
            gunicorn_workers = workers
        if dispatcher_workers is None:
            dispatcher_workers = workers
        return {
            "host": options.get("host", "127.0.0.1"),
            "port": options.get("port", "8000"),
            "gunicorn_workers": gunicorn_workers,
            "dispatcher_workers": dispatcher_workers,
            "max_tasks": options.get("max_tasks", 100),
            "log_level": options.get("log_level", "INFO"),
            "check_interval": options.get("check_interval", 60),
        }

    def _handle_task_management_command(self, options: dict[str, Any]) -> None:
        """Handle task management commands."""
        action = options.get("task_action")

        try:
            if action == "create":
                self._handle_task_create(options)
            elif action == "list":
                self._handle_task_list(options)
            elif action == "show":
                self._handle_task_show(options)
            elif action == "cancel":
                self._handle_task_cancel(options)
            elif action == "retry":
                self._handle_task_retry(options)
            else:
                raise CommandError(f"Unknown task action: {action}")
        except Exception as e:
            self.output.error(f"Task management error: {e}")
            sys.exit(1)
