"""
Task groups configuration for organized task management.

This module defines task groups with feature flag controls and provides
a centralized way to manage different categories of tasks.
"""

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class TaskGroup:
    """
    Represents a group of related tasks with feature flag control.
    """

    def __init__(
        self,
        name: str,
        description: str,
        enabled_flag: str = None,
        default_enabled: bool = True,
        tasks: list[dict[str, Any]] = None,
    ):
        """
        Initialize a task group.

        Args:
            name: Unique name for the task group
            description: Human-readable description
            enabled_flag: Feature flag name to control this group
            default_enabled: Default state if feature flag not set
            tasks: List of task configurations in this group
        """
        self.name = name
        self.description = description
        self.enabled_flag = enabled_flag
        self.default_enabled = default_enabled
        self.tasks = tasks or []

    def is_enabled(self) -> bool:
        """
        Check if this task group is enabled based on feature flags.

        Returns:
            bool: True if group is enabled, False otherwise
        """
        if not self.enabled_flag:
            return self.default_enabled

        feature_flags = getattr(settings, "FEATURE_FLAGS", {})
        return feature_flags.get(self.enabled_flag, self.default_enabled)

    def get_enabled_tasks(self) -> list[dict[str, Any]]:
        """
        Get all tasks in this group that should be active.

        Returns:
            List of task configurations if group is enabled, empty list otherwise
        """
        if not self.is_enabled():
            return []

        return [task for task in self.tasks if task.get("enabled", True)]


# System Tasks Group - Always enabled, core system maintenance
SYSTEM_TASKS_GROUP = TaskGroup(
    name="system_tasks",
    description="Core system maintenance tasks that are always enabled",
    enabled_flag=None,  # Always enabled
    default_enabled=True,
    tasks=[
        {
            "task_id": "daily_task_cleanup",
            "function": "cleanup_old_tasks",
            "cron": "0 2 * * *",  # Daily at 2 AM
            "args": {
                "days_old": 5,
                "dry_run": False,
                "include_executions": True,
                "preserve_recurring": True,
            },
            "enabled": True,
            "description": "Daily cleanup of old completed/failed tasks (preserves recurring tasks)",
            "category": "maintenance",
        },
        {
            "task_id": "weekly_data_cleanup",
            "function": "cleanup_old_data",
            "cron": "0 3 * * 0",  # Weekly on Sunday at 3 AM
            "args": {"days_old": 30, "data_types": ["logs", "temp_files", "cache"]},
            "enabled": True,
            "description": "Weekly cleanup of old system data and temporary files",
            "category": "maintenance",
        },
        {
            "task_id": "hourly_health_check",
            "function": "hello_world",
            "cron": "0 * * * *",  # Every hour
            "args": {},
            "enabled": True,
            "description": "Hourly system health check",
            "category": "monitoring",
        },
    ],
)

# Anonymized Data Collection Group - Controlled by feature flag
ANONYMIZED_DATA_GROUP = TaskGroup(
    name="anonymized_data",
    description="Anonymized data collection tasks",
    enabled_flag="ANONYMIZED_DATA_COLLECTION",
    default_enabled=True,  # Default enabled but can be controlled
    tasks=[
        {
            "task_id": "collect_anonymous_metrics",
            "function": "collect_anonymous_metrics",
            "cron": "0 */6 * * *",  # Every 6 hours
            "args": {},
            "enabled": True,
            "description": "Collect anonymous system metrics for monitoring",
            "category": "anonymous_metrics",
        },
        {
            "task_id": "collect_config_metrics",
            "function": "collect_config_metrics",
            "cron": "0 4 * * 0",  # Weekly on Sunday at 4 AM
            "args": {},
            "enabled": True,
            "description": "Collect system configuration information anonymously",
            "category": "anonymous_metrics",
        },
    ],
)

# Metrics Collection Group - Customer controlled
METRICS_COLLECTION_GROUP = TaskGroup(
    name="metrics_collection",
    description="Customer-controlled metrics collection tasks",
    enabled_flag="METRICS_COLLECTION_ENABLED",
    default_enabled=False,  # Customers must explicitly enable
    tasks=[
        {
            "task_id": "collect_host_metrics",
            "function": "collect_host_metrics",
            "cron": "0 */4 * * *",  # Every 4 hours
            "args": {},
            "enabled": True,
            "description": "Collect host performance and system metrics",
            "category": "metrics_collection",
        },
        {
            "task_id": "collect_job_host_summary",
            "function": "collect_job_host_summary",
            "cron": "0 */8 * * *",  # Every 8 hours
            "args": {},
            "enabled": True,
            "description": "Collect job execution statistics and host performance data",
            "category": "metrics_collection",
        },
        {
            "task_id": "collect_all_metrics_daily",
            "function": "collect_all_metrics",
            "cron": "0 1 * * *",  # Daily at 1 AM
            "args": {"collectors": ["anonymous", "config", "host_metric", "job_host_summary"]},
            "enabled": True,
            "description": "Daily comprehensive metrics collection",
            "category": "metrics_collection",
        },
    ],
)

# Registry of all task groups
TASK_GROUPS = [
    SYSTEM_TASKS_GROUP,
    ANONYMIZED_DATA_GROUP,
    METRICS_COLLECTION_GROUP,
]


def get_all_enabled_tasks() -> dict[str, dict[str, Any]]:
    """
    Get all enabled tasks from all groups.

    Returns:
        Dictionary mapping task_id to task configuration for all enabled tasks
    """
    all_tasks = {}

    for group in TASK_GROUPS:
        enabled_tasks = group.get_enabled_tasks()
        for task in enabled_tasks:
            task_id = task["task_id"]
            task_config = task.copy()
            task_config["group"] = group.name
            task_config["group_description"] = group.description
            all_tasks[task_id] = task_config

    return all_tasks


def get_task_group_status() -> dict[str, Any]:
    """
    Get status of all task groups.

    Returns:
        Dictionary with status information for each group
    """
    status = {}

    for group in TASK_GROUPS:
        group_status = {
            "name": group.name,
            "description": group.description,
            "enabled": group.is_enabled(),
            "enabled_flag": group.enabled_flag,
            "total_tasks": len(group.tasks),
            "enabled_tasks": len(group.get_enabled_tasks()),
            "tasks": group.get_enabled_tasks() if group.is_enabled() else [],
        }
        status[group.name] = group_status

    return status


def enable_task_group(group_name: str) -> bool:
    """
    Enable a task group by updating its feature flag.

    Note: This function shows the concept but actual implementation
    would require runtime feature flag management.

    Args:
        group_name: Name of the group to enable

    Returns:
        bool: True if group was found and can be enabled
    """
    group = next((g for g in TASK_GROUPS if g.name == group_name), None)
    if not group or not group.enabled_flag:
        return False

    # In a real implementation, this would update the feature flag
    # For now, it's a placeholder showing the pattern
    logger.info(f"Would enable task group: {group_name} via flag: {group.enabled_flag}")
    return True


def disable_task_group(group_name: str) -> bool:
    """
    Disable a task group by updating its feature flag.

    Args:
        group_name: Name of the group to disable

    Returns:
        bool: True if group was found and can be disabled
    """
    group = next((g for g in TASK_GROUPS if g.name == group_name), None)
    if not group or not group.enabled_flag:
        return False

    # System tasks cannot be disabled
    if group.name == "system_tasks":
        logger.warning("Cannot disable system tasks group")
        return False

    logger.info(f"Would disable task group: {group_name} via flag: {group.enabled_flag}")
    return True


def get_tasks_by_category(category: str) -> list[dict[str, Any]]:
    """
    Get all enabled tasks in a specific category.

    Args:
        category: Category name to filter by

    Returns:
        List of task configurations in the specified category
    """
    all_tasks = get_all_enabled_tasks()
    return [task for task in all_tasks.values() if task.get("category") == category]


def _validate_task_id(task_id: str | None, group_name: str, all_task_ids: list[str]) -> list[str]:
    """Validate a single task ID."""
    errors = []
    if not task_id:
        errors.append(f"Task in group {group_name} missing task_id")
        return errors

    if task_id in all_task_ids:
        errors.append(f"Duplicate task_id: {task_id}")

    return errors


def _validate_required_fields(task: dict, task_id: str) -> list[str]:
    """Validate required fields for a task."""
    errors = []
    required_fields = ["function", "cron", "description"]
    for field in required_fields:
        if not task.get(field):
            errors.append(f"Task {task_id} missing required field: {field}")
    return errors


def validate_task_groups() -> list[str]:
    """
    Validate all task groups and return any errors found.

    Returns:
        List of error messages, empty if no errors
    """
    errors = []
    all_task_ids = []

    for group in TASK_GROUPS:
        for task in group.tasks:
            task_id = task.get("task_id")

            # Validate task ID
            id_errors = _validate_task_id(task_id, group.name, all_task_ids)
            errors.extend(id_errors)

            if task_id and task_id not in all_task_ids:
                all_task_ids.append(task_id)

            # Validate required fields
            if task_id:
                errors.extend(_validate_required_fields(task, task_id))

    return errors
