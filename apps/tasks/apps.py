"""
Django app configuration for tasks app.
"""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Configuration for the tasks app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Task Management"
