"""
BI connector Layer 2 views — live data queried directly from the AWX DB.

Time-series endpoints (jobs, hosts, credentials, events) are asynchronous:
  GET ?since=&until=  →  202 Accepted + {"task_id": N, "status_url": "/api/v1/tasks/N/"}

The collection runs inside dispatcherd so the HTTP request returns immediately.
Poll GET /api/v1/tasks/<task_id>/ until status == "completed", then read
result_data.data for the collected rows.

Deduplication: a second identical request while the first is still pending/running
returns the existing task_id rather than creating a duplicate AWX query.

The snapshot endpoint remains synchronous — it is a fast point-in-time query
with no date window, so an async round-trip would add latency for no benefit.

Collector functions are imported lazily to prevent metrics_utility import failures
from breaking the module in environments where it is not installed.
"""

import logging
from typing import Any

from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tasks.utils import get_db_connection, parse_datetime_string

from .mixins import BiConnectorEnabledMixin

logger = logging.getLogger(__name__)


class DateRangeRequiredMixin:
    """
    Mixin that enforces mandatory since/until query parameters with a maximum window.

    Protects the AWX production DB from unbounded BI queries. The default window is
    controlled by the BI_CONNECTOR_MAX_DAYS_DEFAULT Django setting (default: 7).
    Override MAX_DAYS_SETTING on the view class to point to a different setting key
    (e.g., ControllerEventsView uses BI_CONNECTOR_MAX_DAYS_EVENTS for its tighter 3-day limit).

    Configurable without code changes:
        METRICS_SERVICE_BI_CONNECTOR_MAX_DAYS_DEFAULT=14
        METRICS_SERVICE_BI_CONNECTOR_MAX_DAYS_EVENTS=5
    """

    MAX_DAYS_SETTING: str = "BI_CONNECTOR_MAX_DAYS_DEFAULT"

    def _get_max_days(self) -> int:
        from django.conf import settings

        return getattr(settings, self.MAX_DAYS_SETTING, 7)

    def validate_date_range(self, request: Any) -> tuple:
        since_str = request.query_params.get("since")
        until_str = request.query_params.get("until")

        if not since_str or not until_str:
            raise ValidationError({"detail": "Both 'since' and 'until' query parameters are required (ISO 8601)."})

        since = parse_datetime_string(since_str)
        until = parse_datetime_string(until_str)

        if since is None:
            raise ValidationError({"detail": f"Invalid 'since' datetime format: {since_str!r}. Use ISO 8601."})
        if until is None:
            raise ValidationError({"detail": f"Invalid 'until' datetime format: {until_str!r}. Use ISO 8601."})
        if until <= since:
            raise ValidationError({"detail": "'until' must be after 'since'."})

        max_days = self._get_max_days()
        delta = until - since
        if delta.total_seconds() > max_days * 86400:
            raise ValidationError({"detail": f"Date range cannot exceed {max_days} days. Requested {delta.days} days."})

        return since, until


class ControllerTimeSeriesView(BiConnectorEnabledMixin, DateRangeRequiredMixin, APIView):
    """
    Base view for async live time-series data from the AWX DB.

    Returns 202 Accepted immediately and kicks off a dispatcherd task.
    Subclasses set COLLECTOR_KEY to select which hourly collector to invoke.
    Override MAX_DAYS_SETTING to point to a different settings key for a tighter limit.
    """

    permission_classes = [IsAuthenticated]
    versioning_class = None
    COLLECTOR_KEY: str = ""

    def get(self, request: Any) -> Response:
        since, until = self.validate_date_range(request)

        from apps.tasks.models import Task
        from apps.tasks.tasks_system import submit_task_to_dispatcher

        since_iso = since.isoformat()
        until_iso = until.isoformat()

        # Return the existing task if an identical collection is already in flight.
        existing = Task.objects.filter(
            function_name="collect_bi_controller_data",
            status__in=["pending", "running"],
            task_data__collector_key=self.COLLECTOR_KEY,
            task_data__since=since_iso,
            task_data__until=until_iso,
        ).first()

        if existing:
            return Response(
                {
                    "task_id": existing.id,
                    "status": existing.status,
                    "collector_type": self.COLLECTOR_KEY,
                    "results_url": reverse("tasks:v1:task-detail", args=[existing.id]),
                },
                status=202,
            )

        task = Task.objects.create(
            name=f"bi_collect_{self.COLLECTOR_KEY}",
            function_name="collect_bi_controller_data",
            task_data={
                "collector_key": self.COLLECTOR_KEY,
                "since": since_iso,
                "until": until_iso,
            },
        )
        submit_task_to_dispatcher(task)

        return Response(
            {
                "task_id": task.id,
                "status": "pending",
                "collector_type": self.COLLECTOR_KEY,
                "results_url": reverse("tasks:v1:task-detail", args=[task.id]),
            },
            status=202,
        )


class ControllerJobsView(ControllerTimeSeriesView):
    """
    Async live unified jobs data from the AWX DB (max 7-day window).

    Query params:
        since (required) — start of range, ISO 8601 datetime
        until (required) — end of range, ISO 8601 datetime

    Returns 202 with task_id. Poll /api/v1/tasks/<task_id>/ for completion.
    """

    COLLECTOR_KEY = "unified_jobs"


class ControllerHostsView(ControllerTimeSeriesView):
    """
    Async live job host summary data from the AWX DB (max 7-day window).

    Query params:
        since (required) — start of range, ISO 8601 datetime
        until (required) — end of range, ISO 8601 datetime

    Returns 202 with task_id. Poll /api/v1/tasks/<task_id>/ for completion.
    """

    COLLECTOR_KEY = "job_host_summary_service"


class ControllerCredentialsView(ControllerTimeSeriesView):
    """
    Async live credentials usage data from the AWX DB (max 7-day window).

    Query params:
        since (required) — start of range, ISO 8601 datetime
        until (required) — end of range, ISO 8601 datetime

    Returns 202 with task_id. Poll /api/v1/tasks/<task_id>/ for completion.
    """

    COLLECTOR_KEY = "credentials_service"


class ControllerEventsView(ControllerTimeSeriesView):
    """
    Async live job events data from the AWX DB.

    Tighter 3-day max window enforced because main_jobevent is one of the
    largest tables in the AWX DB — even a 7-day query can be very heavy.

    Query params:
        since (required) — start of range, ISO 8601 datetime
        until (required) — end of range, ISO 8601 datetime

    Returns 202 with task_id. Poll /api/v1/tasks/<task_id>/ for completion.
    """

    COLLECTOR_KEY = "main_jobevent_service"
    MAX_DAYS_SETTING: str = "BI_CONNECTOR_MAX_DAYS_EVENTS"


class ControllerSnapshotView(BiConnectorEnabledMixin, APIView):
    """
    Synchronous current-state snapshot from the AWX DB.

    Queries execution environments, controller version, table metadata, and config.
    Remains synchronous — fast point-in-time query, no date window, no benefit
    to async dispatch.

    Returns partial results if individual collectors fail (200 with populated errors dict).

    Optional query param:
        collectors — comma-separated subset, e.g. ?collectors=execution_environments,config
    """

    permission_classes = [IsAuthenticated]
    versioning_class = None
    DEFAULT_COLLECTORS = ["execution_environments", "controller_version_service", "table_metadata", "config"]

    def get(self, request: Any) -> Response:
        collectors_param = request.query_params.get("collectors")
        if collectors_param:
            requested = [c.strip() for c in collectors_param.split(",") if c.strip()]
        else:
            requested = self.DEFAULT_COLLECTORS

        try:
            conn = get_db_connection()
        except Exception as e:
            logger.error("AWX DB unavailable for controller/snapshot: %s", e)
            return Response({"error": f"AWX database unavailable: {e}"}, status=503)

        try:
            from apps.tasks.collectors.collect_snapshot_metrics import _get_snapshot_collectors

            registry = _get_snapshot_collectors()
        except Exception as e:
            logger.error("Failed to load snapshot collectors: %s", e)
            return Response({"error": f"Snapshot collectors unavailable: {e}"}, status=500)

        results: dict = {}
        errors: dict = {}

        for collector_type in requested:
            if collector_type not in registry:
                errors[collector_type] = f"Unknown collector type: {collector_type!r}"
                continue
            try:
                entry = registry[collector_type]
                collector = entry["collector_func"](db=conn)
                results[collector_type] = collector.gather()
            except Exception as e:
                logger.warning("Snapshot collector %s failed: %s", collector_type, e)
                errors[collector_type] = str(e)

        return Response(
            {
                "collected_at": timezone.now().isoformat(),
                "collectors": results,
                "errors": errors,
            }
        )
