"""Views exposing daily aggregated metrics from the anonymized collection pipeline."""

import logging

from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor
from ansible_base.rest_pagination import DefaultPaginator
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.bi_export.v1.serializers import DailyMetricsSummaryDetailSerializer, DailyMetricsSummaryListSerializer
from apps.tasks.models import DailyMetricsSummary

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        description="Paginated list of daily aggregated metrics summaries. "
        "Each entry represents one calendar day of pre-aggregated automation data "
        "(jobs by type, module usage, collection stats, host pair counts). "
        "Retrieve a specific date for the full aggregated_metrics payload.",
        parameters=[
            OpenApiParameter(
                "status", str, description="Filter by summary status (aggregated, anonymized, sent, failed)"
            ),
            OpenApiParameter("start_date", str, description="Filter summaries on or after YYYY-MM-DD"),
            OpenApiParameter("end_date", str, description="Filter summaries on or before YYYY-MM-DD"),
        ],
    ),
    retrieve=extend_schema(
        description="Full daily metrics summary including the complete aggregated_metrics JSON blob. "
        "Contains jobs_by_job_type, jobs_by_launch_type, module_stats, collection_stats, "
        "table_metadata, and other pre-aggregated analytics for the given date.",
    ),
)
class DailyMetricsSummaryViewSet(ReadOnlyModelViewSet):
    """Read-only access to daily aggregated metrics for BI tool consumption."""

    permission_classes = [IsSystemAdminOrAuditor]
    pagination_class = DefaultPaginator

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DailyMetricsSummaryDetailSerializer
        return DailyMetricsSummaryListSerializer

    def get_queryset(self):
        qs = DailyMetricsSummary.objects.exclude(status="pending").order_by("-summary_date")

        if status := self.request.query_params.get("status"):
            qs = qs.filter(status=status)
        if start_date := self.request.query_params.get("start_date"):
            qs = qs.filter(summary_date__gte=start_date)
        if end_date := self.request.query_params.get("end_date"):
            qs = qs.filter(summary_date__lte=end_date)

        return qs
