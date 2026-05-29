"""ViewSet for dashboard collection status."""

from rest_framework.request import Request
from rest_framework.response import Response

from apps.dashboard_reports.viewsets.admin_viewsets import BaseAdminViewSet
from apps.tasks.models import Task
from apps.tasks.task_groups import get_feature_enabled_from_db


class DashboardCollectionStatusViewSet(BaseAdminViewSet):
    """Returns the enabled state and task status for the dashboard reports collection pipeline."""

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return dashboard collection feature flag status and task state.

        When enabled is false, next_run and initial_collection_status are null.
        initial_collection_status reflects the status of the one-shot initial collection task:
        "pending", "running", "completed", "failed", or "cancelled".
        """
        enabled = get_feature_enabled_from_db("DASHBOARD_COLLECTION", default=False)

        next_run = None
        initial_collection_status = None

        if enabled:
            # Incremental dashboard sync is driven by the hourly_unified_jobs hook,
            # so next_run reflects when that collector will next fire.
            hourly_task = Task.objects.filter(
                name="hourly_unified_jobs",
                is_system_task=True,
            ).first()
            if hourly_task:
                next_run = hourly_task.get_next_run_time()

            initial_task = Task.objects.filter(
                function_name="collect_dashboard_reports_initial_data",
                is_system_task=True,
            ).first()
            if initial_task:
                initial_collection_status = initial_task.status

        return Response(
            {
                "enabled": enabled,
                "next_run": next_run,
                "initial_collection_status": initial_collection_status,
            }
        )
