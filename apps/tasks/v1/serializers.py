"""
Task-related serializers for the API v1 endpoints.

This module provides serializers for task management functionality
converted from the manage_tasks.py command to REST API endpoints.
"""

import json

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.tasks.models import (
    Task,
    TaskExecution,
)

from .base_serializers import BaseModelSerializer, StatusFieldMixin

User = get_user_model()


class TaskSerializer(BaseModelSerializer, StatusFieldMixin):
    """
    Main serializer for Task model with comprehensive functionality.

    This serializer provides task creation, scheduling, and monitoring
    capabilities for the dashboard interface and includes all fields
    needed for task management.
    """

    # Use PrimaryKeyRelatedField instead of HyperlinkedRelatedField since user views were removed
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    executions_count = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_modify = serializers.SerializerMethodField()
    is_ready_to_run = serializers.SerializerMethodField()
    next_run_time = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = BaseModelSerializer.build_common_fields(
            [
                "name",
                "function_name",
                "task_data",
                "scheduled_time",
                "cron_expression",
                "is_recurring",
                "is_system_task",
                "status",
                "priority",
                "attempts",
                "max_attempts",
                "timeout_seconds",
                "result_data",
                "started_at",
                "completed_at",
                "error_message",
                "created_by",
            ],
            [
                "created_by_username",
                "executions_count",
                "duration",
                "can_retry",
                "can_delete",
                "can_modify",
                "is_ready_to_run",
                "next_run_time",
            ],
        )
        read_only_fields = [
            "created_by_username",
            "executions_count",
            "duration",
            "can_retry",
            "can_delete",
            "can_modify",
            "is_ready_to_run",
            "next_run_time",
            "is_system_task",
            "status",
            "attempts",
            "result_data",
            "started_at",
            "completed_at",
            "error_message",
        ]
        extra_kwargs = BaseModelSerializer.build_extra_kwargs(
            "tasks:v1:task-detail",
            {
                "scheduled_time": {"help_text": "ISO 8601 format datetime when task should run"},
                "task_data": {"help_text": "JSON data to pass to the task function"},
            },
        )

    def get_executions_count(self, obj) -> int:
        """Get count of task executions."""
        return obj.executions.count()

    def get_duration(self, obj) -> float | None:
        """Get task duration in seconds."""
        if hasattr(obj, "get_duration"):
            return obj.get_duration()
        return None

    def get_can_retry(self, obj) -> bool:
        """Check if task can be retried."""
        return obj.can_retry()

    def get_can_delete(self, obj) -> bool:
        """Check if task can be deleted."""
        return obj.can_delete()

    def get_can_modify(self, obj) -> bool:
        """Check if task can be modified."""
        return obj.can_modify()

    def get_is_ready_to_run(self, obj) -> bool:
        """Check if task is ready to run."""
        return obj.is_ready_to_run()

    def get_next_run_time(self, obj):
        """Get next run time for recurring tasks."""
        next_time = obj.get_next_run_time()
        return next_time.isoformat() if next_time else None


class TaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating tasks via the API.

    This serializer handles task creation similar to the manage_tasks.py create
    command with validation and proper data handling.
    """

    user = serializers.CharField(required=False, help_text="Username of task creator (optional)")

    class Meta:
        model = Task
        fields = [
            "name",
            "function_name",
            "task_data",
            "scheduled_time",
            "cron_expression",
            "is_recurring",
            "priority",
            "max_attempts",
            "timeout_seconds",
            "user",
        ]
        extra_kwargs = {
            "scheduled_time": {
                "required": False,
                "help_text": "ISO 8601 format datetime. Leave empty for immediate execution.",
            },
            "task_data": {"required": False, "help_text": "JSON object with task parameters"},
            "cron_expression": {"required": False, "help_text": "Cron expression for recurring tasks"},
            "is_recurring": {"default": False},
            "priority": {"default": 2},
            "max_attempts": {"default": 3},
            "timeout_seconds": {"default": 3600},
        }

    def validate_function_name(self, value):
        """Validate that the function name exists in available task functions."""
        from apps.tasks.tasks import TASK_FUNCTIONS

        if value not in TASK_FUNCTIONS:
            available_functions = list(TASK_FUNCTIONS.keys())
            raise serializers.ValidationError(f"Invalid function name. Available functions: {available_functions}")
        return value

    def validate_cron_expression(self, value):
        """Validate cron expression format."""
        if value:
            try:
                from croniter import croniter

                croniter(value)
            except (ValueError, TypeError) as e:
                raise serializers.ValidationError(f"Invalid cron expression: {e}") from e
        return value

    def validate_task_data(self, value):
        """Validate task data is proper JSON if provided as string."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise serializers.ValidationError(f"Invalid JSON data: {e}") from e
        return value

    def validate_user(self, value):
        """Validate user exists if provided."""
        if value:
            try:
                return User.objects.get(username=value)
            except User.DoesNotExist as e:
                raise serializers.ValidationError(f"User '{value}' not found") from e
        return None

    def create(self, validated_data):
        """Create task with proper user assignment."""
        user = validated_data.pop("user", None)

        # Use provided user or request user
        if user:
            validated_data["created_by"] = user
        elif (
            hasattr(self.context.get("request"), "user")
            and self.context["request"].user
            and self.context["request"].user.is_authenticated
        ):
            validated_data["created_by"] = self.context["request"].user

        return super().create(validated_data)


class TaskListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for task list endpoints.

    This serializer provides essential task information for list views,
    similar to the manage_tasks.py list command output.
    """

    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "function_name",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "created",
            "scheduled_time",
            "created_by_username",
        ]


class TaskCleanupSerializer(serializers.Serializer):
    """
    Serializer for task cleanup operations.

    This serializer handles the cleanup functionality from manage_tasks.py.
    """

    days = serializers.IntegerField(default=30, min_value=1, help_text="Number of days to keep completed tasks")
    dry_run = serializers.BooleanField(default=False, help_text="Show what would be deleted without actually deleting")


class TaskExecutionSerializer(BaseModelSerializer):
    """
    Serializer for TaskExecution model for execution tracking and monitoring.
    """

    task_name = serializers.CharField(source="task.name", read_only=True)
    task_function = serializers.CharField(source="task.function_name", read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = TaskExecution
        fields = BaseModelSerializer.build_common_fields(
            [
                "task",
                "status",
                "started_at",
                "completed_at",
                "worker_id",
                "result_data",
                "error_message",
                "execution_time_seconds",
            ],
            ["task_name", "task_function", "duration"],
        )
        read_only_fields = [
            "task_name",
            "task_function",
            "duration",
            "started_at",
            "completed_at",
            "execution_time_seconds",
        ]
        extra_kwargs = BaseModelSerializer.build_extra_kwargs(
            "tasks:v1:taskexecution-detail",
            {
                "task": {"view_name": "tasks:v1:task-detail"},
            },
        )

    def get_duration(self, obj) -> float | None:
        """Get execution duration in seconds."""
        if obj.started_at and obj.completed_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        return None


# Dashboard Report Serializers for automation-reports integration


class ReportSerializer(serializers.Serializer):
    """
    Serializer for dashboard report data.

    This serializer matches the automation-reports Report TypeScript interface exactly,
    ensuring API contract compatibility with the React frontend.

    TypeScript interface (from automation-reports):
        interface Report {
            name: string;
            runs: number;
            elapsed: string;
            cluster: number;
            elapsed_str: string;
            num_hosts: number;
            time_taken_manually_execute_minutes: number;
            time_taken_create_automation_minutes: number;
            successful_runs: number;
            failed_runs: number;
            automated_costs: string;
            manual_costs: string;
            savings: string;
        }
    """

    name = serializers.CharField(help_text="Job template name")
    runs = serializers.IntegerField(help_text="Total number of runs")
    elapsed = serializers.IntegerField(help_text="Total elapsed time in seconds")
    cluster = serializers.IntegerField(help_text="Cluster identifier")
    elapsed_str = serializers.CharField(help_text="Human-readable elapsed time (e.g., '2h 15m')")
    num_hosts = serializers.IntegerField(help_text="Number of unique hosts")
    time_taken_manually_execute_minutes = serializers.IntegerField(
        help_text="Estimated time to execute manually (minutes)"
    )
    time_taken_create_automation_minutes = serializers.IntegerField(
        help_text="Time taken to create automation (minutes)"
    )
    successful_runs = serializers.IntegerField(help_text="Number of successful runs")
    failed_runs = serializers.IntegerField(help_text="Number of failed runs")
    automated_costs = serializers.CharField(help_text="Automation costs (formatted currency)")
    manual_costs = serializers.CharField(help_text="Manual execution costs (formatted currency)")
    savings = serializers.CharField(help_text="Cost savings from automation (formatted currency)")


class ReportResponseSerializer(serializers.Serializer):
    """
    Paginated response serializer for dashboard reports.

    Matches the automation-reports ReportResponse TypeScript interface:
        interface ReportResponse {
            count: number;
            next: string;
            previous: string;
            results: Report[];
        }
    """

    count = serializers.IntegerField(help_text="Total number of reports")
    next = serializers.CharField(allow_null=True, help_text="URL to next page (null if last page)")
    previous = serializers.CharField(allow_null=True, help_text="URL to previous page (null if first page)")
    results = ReportSerializer(many=True, help_text="Array of report data")


class ProjectSummarySerializer(serializers.Serializer):
    """
    Serializer for top projects summary.

    Used by the dashboard details endpoint to show top projects by job count.
    """

    project_id = serializers.IntegerField(help_text="Project ID")
    project_name = serializers.CharField(help_text="Project name")
    job_count = serializers.IntegerField(help_text="Number of jobs executed")


class UserSummarySerializer(serializers.Serializer):
    """
    Serializer for top users summary.

    Used by the dashboard details endpoint to show top users by execution count.
    """

    user_id = serializers.IntegerField(help_text="User ID")
    username = serializers.CharField(help_text="Username")
    job_count = serializers.IntegerField(help_text="Number of jobs executed")


class DashboardDetailsSerializer(serializers.Serializer):
    """
    Comprehensive dashboard details serializer.

    Returns all dashboard data including job templates, top projects, and top users.
    Used by the /api/v1/report/details/ endpoint.
    """

    job_templates = serializers.DictField(
        help_text="Job template data with array of Report objects"
    )
    top_projects = serializers.DictField(
        help_text="Top projects data with array of project summaries"
    )
    top_users = serializers.DictField(
        help_text="Top users data with array of user summaries"
    )
    date_range = serializers.DictField(
        help_text="Date range of the data (start and end ISO timestamps)"
    )
