from datetime import UTC, datetime, timedelta
from typing import Any

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.dashboard_reports.models import DashboardTelemetry
from apps.dashboard_reports.serializers import DashboardTelemetrySerializer
from apps.dashboard_reports.viewsets.admin_viewsets import BaseAdminViewSet

_telemetry_response_serializer = inline_serializer(
    name="DashboardTelemetryResponse",
    fields={
        "count": serializers.IntegerField(),
        "results": DashboardTelemetrySerializer(many=True),
    },
)


@extend_schema_view(
    list=extend_schema(
        summary="Return the last 30 days of daily dashboard collection performance stats.",
        description=(
            "Aggregate performance metrics (duration, records processed, DB query time, cache hit rate) "
            "for each DASHBOARD_COLLECTION task execution within the last 30 days. No sensitive data is included."
        ),
        responses={200: OpenApiResponse(response=_telemetry_response_serializer)},
    )
)
class DashboardTelemetryViewSet(BaseAdminViewSet):
    """
    ViewSet for retrieving the last 30 days of dashboard collection performance telemetry
    from metrics service database.

    Provides listing last 30 days of dashboard collection performance telemetry entries.

    Endpoints:
        GET /api/v1/dashboard_reports/collection_telemetry/ - List last 30 days of dashboard collection telemetry entries (without pagination)
    """

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        cutoff = datetime.now(UTC).date() - timedelta(days=29)
        queryset = DashboardTelemetry.objects.filter(collection_run_date__gte=cutoff).order_by(
            "-collection_run_date", "task_name"
        )
        serializer = DashboardTelemetrySerializer(queryset, many=True)
        results = serializer.data
        return Response({"count": len(results), "results": results})
