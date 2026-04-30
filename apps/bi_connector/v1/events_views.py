"""
BI connector events views — pre-collected AWX job event data.

Exposes JobEvent and DailyEventSummary stored by the events collection pipeline.
Data is collected incrementally by the events collector tasks — these endpoints
serve whatever has been collected so far.

Both endpoints are synchronous (data is local to the metrics-service DB) and
read-only. Use since/until query params to scope the date window — both are
required and the window is capped at BI_CONNECTOR_MAX_DAYS_DEFAULT (default: 7 days).

Enable these endpoints via: METRICS_SERVICE_FEATURE_ENABLED__BI_CONNECTOR=true

Depends on Unit 1: apps/events/models.py (JobEvent, DailyEventSummary).
"""

from rest_framework.permissions import IsAuthenticated

# Dependency: apps/events/models.py — created by Unit 1 (JobEvent model PR).
from apps.events.models import DailyEventSummary, JobEvent
from apps.tasks.v1.base_views import BaseViewSet

from .events_serializers import DailyEventSummarySerializer, JobEventSerializer
from .mixins import BiConnectorEnabledMixin, DateRangeRequiredMixin


class JobEventViewSet(BiConnectorEnabledMixin, DateRangeRequiredMixin, BaseViewSet):
    """
    Read-only endpoint for querying collected AWX job events.

    Returns JobEvent rows collected from the AWX main_jobevent table. Data is
    scoped to a mandatory date window (since/until on awx_created). Supports
    additional filtering by job_id, host_name, task_action, and failed status.

    Query params:
        since (required) — start of awx_created range, ISO 8601 datetime or date
        until (required) — end of awx_created range, ISO 8601 datetime or date
        job_id           — filter to a specific AWX job (integer)
        host_name        — filter by Ansible host name (exact match)
        task_action      — filter by Ansible module name (exact match)
        failed           — filter by failure status (true/false)

    Authentication: token auth (rest_framework.authtoken)
    Throttle: 30 req/hour per user (bi_connector scope)
    """

    queryset = JobEvent.objects.all()
    serializer_class = JobEventSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    versioning_class = None
    ordering = ["-awx_created", "id"]
    ordering_fields = ["awx_created", "job_created", "job_id", "failed", "task_action", "host_name", "duration"]

    DATE_RANGE_FIELD = "awx_created"

    def get_queryset(self):
        """Apply date range filtering then additional query param filters."""
        qs = super().get_queryset()

        job_id = self.request.query_params.get("job_id")
        host_name = self.request.query_params.get("host_name")
        task_action = self.request.query_params.get("task_action")
        failed = self.request.query_params.get("failed")

        if job_id is not None:
            qs = qs.filter(job_id=job_id)
        if host_name is not None:
            qs = qs.filter(host_name=host_name)
        if task_action is not None:
            qs = qs.filter(task_action=task_action)
        if failed is not None:
            failed_bool = failed.lower() in ("true", "1", "yes")
            qs = qs.filter(failed=failed_bool)

        return qs


class DailyEventSummaryViewSet(BiConnectorEnabledMixin, DateRangeRequiredMixin, BaseViewSet):
    """
    Read-only endpoint for daily event aggregates.

    Returns DailyEventSummary rows — one per calendar day — pre-aggregated from
    JobEvent records by the daily rollup task. Use this endpoint for trend analysis
    and high-level dashboards; use JobEventViewSet for row-level event data.

    Query params:
        since (required) — start of summary_date range, ISO 8601 date or datetime
        until (required) — end of summary_date range, ISO 8601 date or datetime

    Authentication: token auth (rest_framework.authtoken)
    Throttle: 30 req/hour per user (bi_connector scope)
    """

    queryset = DailyEventSummary.objects.all()
    serializer_class = DailyEventSummarySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    versioning_class = None
    ordering = ["-summary_date"]
    ordering_fields = ["summary_date", "total_events", "failed_events", "unique_hosts", "jobs_covered"]
    lookup_field = "summary_date"

    DATE_RANGE_FIELD = "summary_date"
