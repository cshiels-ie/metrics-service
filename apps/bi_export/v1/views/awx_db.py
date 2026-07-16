"""Views that query the AWX database directly for BI-ready Controller data.

Uses the same read-only `awx` DB connection as `dashboard_reports` — no HTTP
passthrough, no WIT token, no Gateway routing concerns.

Tables queried:
  main_hostmetric               → host_metrics
  main_hostmetricsummarymonthly → host_metric_summary
  main_instance                 → instances
  main_instancegroup            → instance_groups
"""

import logging
from typing import Any

from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor
from ansible_base.rest_pagination import DefaultPaginator
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.dashboard_reports.models import JobData
from apps.tasks.api_utils import build_error_response
from apps.tasks.utils import get_db_connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

_HOST_METRICS_SQL = """
    SELECT
        id,
        hostname,
        first_automation,
        last_automation,
        last_deleted,
        deleted,
        automated_counter,
        deleted_counter,
        used_in_inventories
    FROM main_hostmetric
"""

_HOST_METRIC_SUMMARY_MONTHLY_SQL = """
    SELECT
        id,
        date,
        license_capacity,
        license_consumed,
        hosts_added,
        hosts_deleted,
        indirectly_managed_hosts
    FROM main_hostmetricsummarymonthly
"""

_INSTANCES_SQL = """
    SELECT
        id,
        hostname,
        uuid,
        node_type,
        enabled,
        managed_by_policy,
        capacity,
        consumed_capacity,
        remaining_capacity,
        cpu,
        memory,
        version,
        node_state
    FROM main_instance
"""

_INSTANCE_GROUPS_SQL = """
    SELECT
        id,
        name,
        capacity,
        consumed_capacity
    FROM main_instancegroup
"""

_HOST_METRICS_COLS = [
    "id",
    "hostname",
    "first_automation",
    "last_automation",
    "last_deleted",
    "deleted",
    "automated_counter",
    "deleted_counter",
    "used_in_inventories",
]
_HOST_METRIC_SUMMARY_COLS = [
    "id",
    "date",
    "license_capacity",
    "license_consumed",
    "hosts_added",
    "hosts_deleted",
    "indirectly_managed_hosts",
]
_INSTANCES_COLS = [
    "id",
    "hostname",
    "uuid",
    "node_type",
    "enabled",
    "managed_by_policy",
    "capacity",
    "consumed_capacity",
    "remaining_capacity",
    "cpu",
    "memory",
    "version",
    "node_state",
]
_INSTANCE_GROUPS_COLS = ["id", "name", "capacity", "consumed_capacity"]


def _rows_to_dicts(rows: list[tuple], columns: list[str]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _fetch_paged(sql: str, columns: list[str], order_by: str, limit: int, offset: int) -> tuple[list[dict], int]:
    """Run a paginated SELECT + COUNT against the AWX DB and return (rows, total)."""
    conn = get_db_connection("awx")
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM ({sql}) AS _c")  # noqa: S608
        total = cur.fetchone()[0]
        cur.execute(f"{sql} ORDER BY {order_by} LIMIT %s OFFSET %s", [limit, offset])  # noqa: S608
        rows = cur.fetchall()
    return _rows_to_dicts(rows, columns), total


def _fetch_one(sql: str, columns: list[str], pk: int) -> dict[str, Any] | None:
    conn = get_db_connection("awx")
    with conn.cursor() as cur:
        cur.execute(f"{sql} WHERE id = %s", [pk])  # noqa: S608
        row = cur.fetchone()
    return dict(zip(columns, row, strict=True)) if row else None


# ---------------------------------------------------------------------------
# Base ViewSet
# ---------------------------------------------------------------------------


class AWXDBViewSet(GenericViewSet):
    """Base class for read-only AWX DB viewsets — no Django model queryset needed."""

    permission_classes = [IsSystemAdminOrAuditor]
    pagination_class = DefaultPaginator
    versioning_class = None

    _sql: str = ""
    _columns: list[str] = []
    _order_by: str = "id"
    _list_error_msg: str = "Failed to fetch records from AWX database"
    _retrieve_error_msg: str = "Failed to fetch record from AWX database"

    def get_queryset(self):
        return JobData.objects.none()

    def list(self, request: Request, **kwargs) -> Response:
        page_size = self.paginator.get_page_size(request)
        try:
            page_num = int(request.query_params.get(self.paginator.page_query_param, 1))
        except (ValueError, TypeError):
            page_num = 1
        offset = (page_num - 1) * (page_size or 0)

        try:
            items, total = _fetch_paged(self._sql, self._columns, self._order_by, page_size, offset)
        except Exception:
            logger.exception(self._list_error_msg)
            return Response(build_error_response(self._list_error_msg, status_code=500), status=500)

        self.paginate_queryset(range(total))
        return self.get_paginated_response(items)

    def retrieve(self, request: Request, pk=None, **kwargs) -> Response:
        try:
            pk_int = int(pk)
        except (TypeError, ValueError):
            return Response(build_error_response("Invalid ID", status_code=400), status=status.HTTP_400_BAD_REQUEST)

        try:
            item = _fetch_one(self._sql, self._columns, pk_int)
        except Exception:
            logger.exception(self._retrieve_error_msg)
            return Response(build_error_response(self._retrieve_error_msg, status_code=500), status=500)

        if item is None:
            return Response(
                build_error_response(f"Record with id {pk_int} not found", status_code=404),
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(item)


# ---------------------------------------------------------------------------
# Concrete viewsets
# ---------------------------------------------------------------------------


class HostMetricsViewSet(AWXDBViewSet):
    """Per-host lifetime automation tracking from main_hostmetric.

    Returns hostname, first/last automation timestamps, automated_counter,
    deleted_counter, and used_in_inventories — the same data the metrics-utility
    billing extractor uses for managed host reconciliation.
    """

    _sql = _HOST_METRICS_SQL
    _columns = _HOST_METRICS_COLS
    _order_by = "hostname"
    _list_error_msg = "Failed to fetch host metrics from AWX database"
    _retrieve_error_msg = "Failed to fetch host metric from AWX database"

    @extend_schema(
        description="Per-host lifetime automation tracking. Sourced directly from the AWX "
        "`main_hostmetric` table. Useful for managed host reconciliation, billing audits, "
        "and identifying stale or ephemeral hosts.",
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
    )
    def list(self, request, **kwargs):
        return super().list(request, **kwargs)

    @extend_schema(description="Single host metric record by ID.")
    def retrieve(self, request, pk=None, **kwargs):
        return super().retrieve(request, pk=pk, **kwargs)


class HostMetricSummaryMonthlyViewSet(AWXDBViewSet):
    """Monthly license consumption summary from main_hostmetricsummarymonthly.

    Returns one row per calendar month with license_capacity, license_consumed,
    hosts_added, hosts_deleted, and indirectly_managed_hosts. Useful for
    subscription trend analysis and renewal planning.
    """

    _sql = _HOST_METRIC_SUMMARY_MONTHLY_SQL
    _columns = _HOST_METRIC_SUMMARY_COLS
    _order_by = "date DESC"
    _list_error_msg = "Failed to fetch host metric summary from AWX database"
    _retrieve_error_msg = "Failed to fetch host metric summary from AWX database"

    @extend_schema(
        description="Monthly license consumption summary. Sourced from the AWX "
        "`main_hostmetricsummarymonthly` table. Useful for subscription trend analysis "
        "and renewal planning. Ordered newest-first.",
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
    )
    def list(self, request, **kwargs):
        return super().list(request, **kwargs)

    @extend_schema(description="Single monthly summary record by ID.")
    def retrieve(self, request, pk=None, **kwargs):
        return super().retrieve(request, pk=pk, **kwargs)


class InstancesViewSet(AWXDBViewSet):
    """Controller node topology and capacity from main_instance.

    Returns per-node hostname, uuid, node_type, capacity, consumed_capacity,
    remaining_capacity, cpu, memory, version, and node_state. Useful for
    infrastructure capacity planning and utilisation reporting.
    """

    _sql = _INSTANCES_SQL
    _columns = _INSTANCES_COLS
    _order_by = "hostname"
    _list_error_msg = "Failed to fetch instances from AWX database"
    _retrieve_error_msg = "Failed to fetch instance from AWX database"

    @extend_schema(
        description="Controller node topology and capacity. Sourced from the AWX "
        "`main_instance` table. Useful for capacity planning and node utilisation reporting.",
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
    )
    def list(self, request, **kwargs):
        return super().list(request, **kwargs)

    @extend_schema(description="Single instance record by ID.")
    def retrieve(self, request, pk=None, **kwargs):
        return super().retrieve(request, pk=pk, **kwargs)


class InstanceGroupsViewSet(AWXDBViewSet):
    """Instance group capacity summary from main_instancegroup.

    Returns name, capacity, and consumed_capacity per instance group.
    Useful for understanding execution capacity distribution across groups.
    """

    _sql = _INSTANCE_GROUPS_SQL
    _columns = _INSTANCE_GROUPS_COLS
    _order_by = "name"
    _list_error_msg = "Failed to fetch instance groups from AWX database"
    _retrieve_error_msg = "Failed to fetch instance group from AWX database"

    @extend_schema(
        description="Instance group capacity summary. Sourced from the AWX `main_instancegroup` table.",
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
    )
    def list(self, request, **kwargs):
        return super().list(request, **kwargs)

    @extend_schema(description="Single instance group record by ID.")
    def retrieve(self, request, pk=None, **kwargs):
        return super().retrieve(request, pk=pk, **kwargs)
