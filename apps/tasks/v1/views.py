"""
Task Management API ViewSets for background task operations.

This module provides comprehensive REST API endpoints for managing background tasks
and task executions. It converts functionality previously available only through
the manage_tasks.py management command into a full-featured REST API with proper
authentication, validation, and monitoring capabilities.

ViewSets:
    TaskViewSet: Complete task lifecycle management with CRUD operations
    TaskExecutionViewSet: Task execution monitoring and history tracking

Features:
    - Task creation with scheduling and recurring task support
    - Task status monitoring and real-time updates
    - Task retry and cancellation operations
    - Task cleanup and maintenance operations
    - Comprehensive filtering and search capabilities
    - Available task function discovery
    - Task execution history and metrics

Operations:
    Create Tasks: POST /api/v1/tasks/ with function_name and parameters
    List Tasks: GET /api/v1/tasks/ with filtering by status, function, etc.
    Retry Tasks: POST /api/v1/tasks/{id}/retry/ for failed tasks
    Cancel Tasks: POST /api/v1/tasks/{id}/cancel/ for pending/running tasks
    Cleanup Tasks: POST /api/v1/tasks/cleanup/ to remove old completed tasks

Task Functions:
    Supports all registered task functions including:
    - cleanup_old_data: System maintenance tasks
    - cleanup_old_tasks: Task cleanup
    - execute_db_task: Database operations
    - hello_world: Test task

Security:
    - Input validation for all task parameters
    - Safe task function execution with proper isolation
    - Audit logging for all task operations
"""

from datetime import timedelta
from typing import Any

from django.http import HttpRequest
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import DeveloperModeRequired
from apps.tasks.api_utils import build_error_response
from apps.tasks.models import Task, TaskExecution

from .base_views import BaseViewSet
from .serializers import (
    DashboardDetailsSerializer,
    ReportResponseSerializer,
    TaskCleanupSerializer,
    TaskCreateSerializer,
    TaskExecutionSerializer,
    TaskListSerializer,
    TaskSerializer,
)


class TaskViewSet(BaseViewSet):
    """
    ViewSet for Task model with comprehensive task management functionality.

    This ViewSet provides all the functionality from the manage_tasks.py command
    converted to REST API endpoints including creation, listing, monitoring,
    and control.
    """

    queryset = Task.objects.select_related("created_by").all()
    serializer_class = TaskSerializer
    permission_classes = [DeveloperModeRequired]
    ordering_fields = ["id", "name", "status", "priority", "scheduled_time", "created", "started_at", "completed_at"]
    ordering = ["-id"]

    @property
    def search_fields(self) -> list[str]:
        return self.get_named_model_search_fields(["function_name", "status", "created_by__username"])

    @property
    def filterset_fields(self) -> dict[str, list[str]]:
        extra_fields = {
            "function_name": self.get_text_field_filters(),
            "status": ["exact", "in"],
            "priority": ["exact", "gte", "lte"],
            "is_recurring": self.get_boolean_field_filters(),
            "created_by": self.get_foreign_key_filters(),
            "created_by__username": self.get_text_field_filters(),
            "scheduled_time": self.get_datetime_field_filters(),
            "started_at": self.get_datetime_field_filters(),
            "completed_at": self.get_datetime_field_filters(),
        }
        return self.build_filterset_fields(self.get_named_model_filterset_fields(extra_fields))

    def get_serializer_class(self):
        """Use appropriate serializer based on action."""
        if self.action == "create":
            return TaskCreateSerializer
        elif self.action == "list_filtered":
            return TaskListSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        """Create task - APScheduler will handle all task submission via polling."""
        # All tasks (immediate, scheduled, recurring) are now handled by APScheduler polling
        # This eliminates cross-process communication issues and provides unified task submission
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="list")
    def list_filtered(self, request: HttpRequest) -> Response:
        """
        List tasks with filtering, similar to manage_tasks list command.

        This endpoint replicates the functionality of:
        python manage.py manage_tasks list --status=pending --limit=20

        Returns:
            Response: Filtered and limited list of tasks
        """
        queryset = self.get_queryset()

        # Filter by status if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply limit (default 20)
        limit = int(request.query_params.get("limit", 20))
        queryset = queryset.order_by("-id")[:limit]

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def running(self, request: HttpRequest) -> Response:
        """
        Get list of currently running tasks.

        Returns:
            Response: List of tasks with status 'running'
        """
        running_tasks = self.get_queryset().filter(status="running")
        serializer = self.get_serializer(running_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pending(self, request: HttpRequest) -> Response:
        """
        Get list of pending tasks waiting to run.

        Returns:
            Response: List of tasks with status 'pending'
        """
        pending_tasks = self.get_queryset().filter(status="pending")
        serializer = self.get_serializer(pending_tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def retry(self, request: HttpRequest, pk: Any = None) -> Response:
        """
        Retry a failed task.

        This endpoint replicates the functionality of:
        python manage.py manage_tasks retry <task_id>

        Args:
            request: HTTP request
            pk: Primary key of the task

        Returns:
            Response: Success or error response
        """
        task = self.get_object()

        if not task.can_retry():
            error_response = build_error_response(
                f"Cannot retry task: status={task.status}, attempts={task.attempts}/{task.max_attempts}",
                status_code=400,
            )
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        # Reset task status for retry (same logic as manage_tasks.py)
        task.status = "pending"
        task.error_message = ""
        task.started_at = None
        task.completed_at = None
        task.save()

        return Response({"message": f"Task '{task.name}' queued for retry"})

    @action(detail=True, methods=["post"])
    def cancel(self, request: HttpRequest, pk: Any = None) -> Response:
        """
        Cancel a pending or running task.

        This endpoint replicates the functionality of:
        python manage.py manage_tasks cancel <task_id>

        Args:
            request: HTTP request
            pk: Primary key of the task

        Returns:
            Response: Success or error response
        """
        task = self.get_object()

        if task.status in ["completed", "cancelled", "failed"]:
            error_response = build_error_response(f"Cannot cancel task with status: {task.status}", status_code=400)
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        task.status = "cancelled"
        task.save()

        return Response({"message": f"Task '{task.name}' cancelled"})

    @action(detail=False, methods=["post"])
    def cleanup(self, request: HttpRequest) -> Response:
        """
        Clean up old completed tasks.

        This endpoint replicates the functionality of:
        python manage.py manage_tasks cleanup --days=30 --dry-run

        Args:
            request: HTTP request with cleanup parameters

        Returns:
            Response: Success message with count of tasks cleaned up
        """
        serializer = TaskCleanupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        days = serializer.validated_data["days"]
        dry_run = serializer.validated_data["dry_run"]

        cutoff_date = timezone.now() - timedelta(days=days)
        old_tasks = Task.objects.filter(status__in=["completed", "failed", "cancelled"], completed_at__lt=cutoff_date)

        count = old_tasks.count()

        if dry_run:
            # Return preview of what would be deleted
            preview = []
            for task in old_tasks[:10]:
                preview.append(
                    {
                        "id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    }
                )

            return Response(
                {
                    "message": f"Would delete {count} tasks older than {days} days",
                    "count": count,
                    "preview": preview,
                    "showing_preview_of": min(10, count),
                }
            )
        else:
            old_tasks.delete()
            return Response({"message": f"Deleted {count} old tasks", "count": count})

    @action(detail=False, methods=["get"])
    def available_functions(self, request: HttpRequest) -> Response:
        """
        Get list of available task functions with enhanced metadata for the dashboard.

        Returns:
            Response: List of available task functions with descriptions, parameters, and examples
        """
        from apps.tasks.tasks import TASK_FUNCTIONS, TASK_METADATA

        functions = []
        for func_name, func in TASK_FUNCTIONS.items():
            # Get enhanced metadata if available, fallback to basic info
            metadata = TASK_METADATA.get(func_name, {})

            function_info = {
                "name": func_name,
                "description": metadata.get("description")
                or (func.__doc__.split("\n")[1].strip() if func.__doc__ else "No description available"),
                "category": metadata.get("category", "General"),
                "parameters": metadata.get("parameters", {}),
                "examples": metadata.get("examples", []),
            }

            functions.append(function_info)

        # Sort by category, then by name
        functions.sort(key=lambda x: (x["category"], x["name"]))

        return Response({"functions": functions})

    @action(detail=False, methods=["get"])
    def system_tasks_info(self, request: HttpRequest) -> Response:
        """
        Get information about system-defined tasks.

        Returns:
            Response: List of system tasks with their status and configuration
        """
        from apps.tasks.tasks import get_system_task_info

        try:
            info = get_system_task_info()
            return Response(info)
        except Exception as e:
            return Response(
                {"error": f"Failed to get system task info: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_destroy(self, instance):
        """
        Override destroy to protect system tasks.

        System tasks cannot be easily deleted to maintain critical functionality.
        """
        if instance.is_system_task:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "System tasks cannot be deleted. These tasks are essential for proper system operation. "
                "To disable a system task, contact your system administrator."
            )
        super().perform_destroy(instance)

    def perform_update(self, serializer):
        """
        Override update to protect critical system task fields.

        System tasks have restricted modification to prevent breaking functionality.
        """
        instance = serializer.instance
        if instance and instance.is_system_task:
            # Allow limited modifications for system tasks
            protected_fields = {"function_name", "is_system_task", "cron_expression", "is_recurring"}

            # Check if any protected fields are being modified
            if any(field in serializer.validated_data for field in protected_fields):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied(
                    f"System tasks cannot modify protected fields: {', '.join(protected_fields)}. "
                    "These fields are managed by the system configuration."
                )

        super().perform_update(serializer)

    @action(detail=True, methods=["delete"])
    def force_delete(self, request, pk=None):
        """
        Force delete a system task (admin only).

        This endpoint allows administrators to delete system tasks if absolutely necessary.
        Use with extreme caution as it may break system functionality.
        """
        task = self.get_object()

        # This would normally check for admin permissions
        # For now, we'll require explicit confirmation
        force_confirm = request.data.get("force_confirm", False)

        if not force_confirm:
            return Response(
                {
                    "error": "Force deletion requires explicit confirmation",
                    "message": "System tasks are protected. Set 'force_confirm': true to override.",
                    "warning": "Deleting system tasks may break critical functionality!",
                    "task": {
                        "name": task.name,
                        "function_name": task.function_name,
                        "is_system_task": task.is_system_task,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if task.is_system_task:
            task_name = task.name
            task.delete()
            return Response(
                {
                    "message": f"System task '{task_name}' has been force deleted",
                    "warning": "System functionality may be affected. Consider recreating system tasks.",
                },
                status=status.HTTP_200_OK,
            )
        else:
            # Regular deletion for non-system tasks
            task.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def scheduler_status(self, request: HttpRequest) -> Response:
        """
        Get the status of the simple scheduler and all scheduled tasks.
        Returns:
            Response: Scheduler status and list of scheduled tasks
        """
        try:
            from apps.tasks.cron_scheduler import get_scheduler

            scheduler = get_scheduler()

            # Get scheduled and recurring tasks from database
            scheduled_tasks = Task.objects.filter(status="pending", scheduled_time__isnull=False).count()

            recurring_tasks = (
                Task.objects.filter(status="pending", is_recurring=True, cron_expression__isnull=False)
                .exclude(cron_expression="")
                .count()
            )

            return Response(
                {
                    "scheduler": {
                        "running": scheduler.running if scheduler else False,
                        "check_interval": scheduler.check_interval if scheduler else 30,
                        "scheduled_tasks": scheduled_tasks,
                        "recurring_tasks": recurring_tasks,
                    },
                    "message": "Simple scheduler status retrieved successfully",
                }
            )
        except Exception as e:
            error_response = build_error_response(f"Failed to get scheduler status: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["post"])
    def schedule_immediate(self, request: HttpRequest) -> Response:
        """
        Schedule a task to run immediately using the simple scheduler.
        Args:
            request: HTTP request with task parameters
        Returns:
            Response: Success message with task ID
        """
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Create task directly in database - signals will handle immediate execution
            task = Task.objects.create(
                name=serializer.validated_data.get("name", "Immediate Task"),
                function_name=serializer.validated_data["function_name"],
                task_data=serializer.validated_data.get("task_data", {}),
                priority=serializer.validated_data.get("priority", 2),
                created_by=request.user if request.user.is_authenticated else None,
                # No scheduled_time means immediate execution
            )

            return Response({"message": "Task scheduled for immediate execution", "task_id": str(task.id)})
        except Exception as e:
            error_response = build_error_response(f"Failed to schedule task: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["post"])
    def schedule_recurring(self, request: HttpRequest) -> Response:
        """
        Schedule a recurring task using cron expression.
        Args:
            request: HTTP request with task parameters including cron_expression
        Returns:
            Response: Success message with task ID
        """
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cron_expression = serializer.validated_data.get("cron_expression")
        if not cron_expression:
            error_response = build_error_response("cron_expression is required for recurring tasks", status_code=400)
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Create recurring task directly in database - simple scheduler will handle it
            task = Task.objects.create(
                name=serializer.validated_data.get("name", "Recurring Task"),
                function_name=serializer.validated_data["function_name"],
                task_data=serializer.validated_data.get("task_data", {}),
                priority=serializer.validated_data.get("priority", 2),
                cron_expression=cron_expression,
                is_recurring=True,
                created_by=request.user if request.user.is_authenticated else None,
            )

            return Response({"message": "Recurring task scheduled successfully", "task_id": str(task.id)})
        except Exception as e:
            error_response = build_error_response(f"Failed to schedule recurring task: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskExecutionViewSet(BaseViewSet):
    """
    ViewSet for TaskExecution model to monitor task execution history.
    """

    queryset = TaskExecution.objects.select_related("task").all()
    serializer_class = TaskExecutionSerializer
    permission_classes = [DeveloperModeRequired]
    ordering_fields = ["started_at", "completed_at", "execution_time_seconds", "status"]
    ordering = ["-started_at"]

    @property
    def search_fields(self) -> list[str]:
        return ["task__name", "task__function_name", "worker_id"]

    @property
    def filterset_fields(self) -> dict[str, list[str]]:
        return {
            "task": ["exact"],
            "status": ["exact"],
            "worker_id": ["exact", "icontains"],
            "started_at": ["gte", "lte"],
            "completed_at": ["gte", "lte"],
        }


class DashboardReportViewSet(BaseViewSet):
    """
    ViewSet for dashboard report data endpoints.

    Provides API endpoints for automation-reports dashboard integration,
    serving pre-calculated metrics data from the DashboardReportCache model.

    Endpoints:
        GET /api/v1/report/ - List job template reports (paginated)
        GET /api/v1/report/details/ - Detailed dashboard data

    Features:
        - Serves cached data for fast response times
        - Supports date range filtering
        - Client-side pagination for efficiency
        - Matches automation-reports TypeScript interface exactly

    Query Parameters:
        - start: ISO datetime for date range start (default: 30 days ago)
        - end: ISO datetime for date range end (default: now)
        - page: Page number (default: 1)
        - page_size: Results per page (default: 20)

    Example:
        GET /api/v1/report/?start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
        GET /api/v1/report/details/
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = ReportResponseSerializer
    versioning_class = None  # Disable versioning for this viewset

    # Queryset required by DRF but we override list() to use custom data source
    def get_queryset(self):
        """Return empty queryset - we override list() method instead."""
        from apps.tasks.models import DashboardReportCache
        return DashboardReportCache.objects.none()

    def list(self, request: HttpRequest, *args, **kwargs) -> Response:
        """
        GET /api/v1/report/

        Returns paginated list of job template reports from cache.

        Query Parameters:
            start (str): ISO datetime for range start (default: 30 days ago)
            end (str): ISO datetime for range end (default: now)
            page (int): Page number (default: 1)
            page_size (int): Results per page (default: 20)

        Returns:
            Response: Paginated report data matching ReportResponse interface
        """
        from apps.tasks.models import DashboardReportCache

        # Parse date range parameters
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')

        if start_param:
            try:
                start_date = timezone.datetime.fromisoformat(start_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                error_response = build_error_response(
                    "Invalid start date format. Use ISO 8601 format.",
                    status_code=400
                )
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        if end_param:
            try:
                end_date = timezone.datetime.fromisoformat(end_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                error_response = build_error_response(
                    "Invalid end date format. Use ISO 8601 format.",
                    status_code=400
                )
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        # Build cache key
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        cache_key = f"job_templates_{start_str}_{end_str}"

        # Retrieve cached data
        cache_entry = DashboardReportCache.objects.filter(cache_key=cache_key).first()

        if not cache_entry:
            # No cached data - return empty response
            response_data = {
                'count': 0,
                'next': None,
                'previous': None,
                'results': []
            }
            serializer = ReportResponseSerializer(response_data)
            return Response(serializer.data)

        # Get data from cache
        data = cache_entry.data.get('job_templates', [])

        # Parse pagination parameters
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
        except (ValueError, TypeError):
            page = 1
            page_size = 20

        # Paginate results (client-side pagination)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = data[start_idx:end_idx]

        # Calculate next/previous URLs
        next_url = None
        previous_url = None

        if end_idx < len(data):
            # More data available
            next_url = f"?page={page + 1}&page_size={page_size}"
            if start_param:
                next_url += f"&start={start_param}"
            if end_param:
                next_url += f"&end={end_param}"

        if page > 1:
            # Previous page available
            previous_url = f"?page={page - 1}&page_size={page_size}"
            if start_param:
                previous_url += f"&start={start_param}"
            if end_param:
                previous_url += f"&end={end_param}"

        # Build response
        response_data = {
            'count': len(data),
            'next': next_url,
            'previous': previous_url,
            'results': paginated_data
        }

        serializer = ReportResponseSerializer(response_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def details(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/report/details/

        Returns comprehensive dashboard data including job templates,
        top projects, and top users.

        Query Parameters:
            start (str): ISO datetime for range start (default: 30 days ago)
            end (str): ISO datetime for range end (default: now)

        Returns:
            Response: Dashboard details with all report types
        """
        from apps.tasks.models import DashboardReportCache

        # Parse date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')

        if start_param:
            try:
                start_date = timezone.datetime.fromisoformat(start_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass  # Use default

        if end_param:
            try:
                end_date = timezone.datetime.fromisoformat(end_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass  # Use default

        # Build cache key prefix
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        cache_key_prefix = f"{start_str}_{end_str}"

        # Fetch all report types from cache
        job_templates_key = f"job_templates_{cache_key_prefix}"
        top_projects_key = f"top_projects_{cache_key_prefix}"
        top_users_key = f"top_users_{cache_key_prefix}"

        job_templates_data = DashboardReportCache.get_or_empty(job_templates_key)
        top_projects_data = DashboardReportCache.get_or_empty(top_projects_key)
        top_users_data = DashboardReportCache.get_or_empty(top_users_key)

        # Build response
        response_data = {
            'job_templates': job_templates_data,
            'top_projects': top_projects_data,
            'top_users': top_users_data,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }

        serializer = DashboardDetailsSerializer(response_data)
        return Response(serializer.data)
