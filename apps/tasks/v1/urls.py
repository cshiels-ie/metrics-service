"""
URL configuration for Task-related API endpoints.

This module provides URL routing for all task management endpoints
converted from the manage_tasks.py command functionality.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardReportViewSet,
    TaskExecutionViewSet,
    TaskViewSet,
)

app_name = "tasks_v1"

# Create DRF router for task endpoints
router = DefaultRouter()

# Main task management endpoints
# /api/v1/tasks/ - CRUD operations for tasks
# /api/v1/tasks/list/ - Custom filtered list (manage_tasks list)
# /api/v1/tasks/{id}/retry/ - Retry task (manage_tasks retry)
# /api/v1/tasks/{id}/cancel/ - Cancel task (manage_tasks cancel)
# /api/v1/tasks/cleanup/ - Cleanup old tasks (manage_tasks cleanup)
# /api/v1/tasks/available_functions/ - Get available task functions
router.register(r"", TaskViewSet, basename="task")


# Task execution monitoring endpoints
# /api/v1/tasks/executions/ - View task execution history
router.register(r"executions", TaskExecutionViewSet, basename="taskexecution")

urlpatterns = [
    # Include all task router URLs at /api/v1/tasks/
    path("", include(router.urls)),
]

# This creates the following endpoint structure:
#
# Task Management (replaces manage_tasks.py functionality):
# GET    /api/v1/tasks/                     - List all tasks (paginated, filterable)
# POST   /api/v1/tasks/                     - Create new task (manage_tasks create)
# GET    /api/v1/tasks/{id}/                - Get task details (manage_tasks show)
# PUT    /api/v1/tasks/{id}/                - Update task
# DELETE /api/v1/tasks/{id}/                - Delete task
#
# Custom Task Actions:
# GET    /api/v1/tasks/list/                - Filtered list (manage_tasks list)
# GET    /api/v1/tasks/running/             - Get running tasks
# GET    /api/v1/tasks/pending/             - Get pending tasks
# POST   /api/v1/tasks/{id}/retry/          - Retry failed task (manage_tasks retry)
# POST   /api/v1/tasks/{id}/cancel/         - Cancel task (manage_tasks cancel)
# POST   /api/v1/tasks/cleanup/             - Cleanup old tasks (manage_tasks cleanup)
# GET    /api/v1/tasks/available_functions/ - Get available task functions
#
