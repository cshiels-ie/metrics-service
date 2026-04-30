"""
BI connector Layer 1 ViewSets — pre-aggregated metrics from the metrics-service DB.

These endpoints expose HourlyMetricsCollection and DailyMetricsSummary in a format
suitable for BI tools (flat columns, filterable by date range, read-only).
Permission is IsAuthenticated (not DeveloperModeRequired) so they are available in production.
"""

from rest_framework.permissions import IsAuthenticated

from apps.tasks.models import DailyMetricsSummary, HourlyMetricsCollection
from apps.tasks.v1.base_views import BaseViewSet

from .mixins import BiConnectorEnabledMixin
from .serializers import (
    DailyMetricsSummaryDetailSerializer,
    DailyMetricsSummaryListSerializer,
    HourlyMetricsCollectionDetailSerializer,
    HourlyMetricsCollectionListSerializer,
)


class DailyMetricsSummaryViewSet(BiConnectorEnabledMixin, BaseViewSet):
    """
    Read-only ViewSet for DailyMetricsSummary.

    Exposes pre-aggregated daily metrics with per-collector-type flat columns
    suitable for BI tool consumption. Use summary_date as the lookup field.

    Filters: summary_date, summary_date__gte, summary_date__lte, status, status__in
    """

    queryset = DailyMetricsSummary.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    versioning_class = None
    lookup_field = "summary_date"
    ordering = ["-summary_date"]
    ordering_fields = ["summary_date", "created", "modified"]
    serializer_class = DailyMetricsSummaryListSerializer

    @property
    def filterset_fields(self) -> dict:
        return {
            "summary_date": ["exact", "gte", "lte"],
            "status": ["exact", "in"],
        }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DailyMetricsSummaryDetailSerializer
        return DailyMetricsSummaryListSerializer


class HourlyMetricsCollectionViewSet(BiConnectorEnabledMixin, BaseViewSet):
    """
    Read-only ViewSet for HourlyMetricsCollection.

    Exposes hourly rollup data per collector type. Filter by collector_type
    and collection_timestamp range for time-series analysis.

    Filters: collector_type, collector_type__in, collection_timestamp__gte,
             collection_timestamp__lte, status
    """

    queryset = HourlyMetricsCollection.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    versioning_class = None
    ordering = ["-collection_timestamp"]
    ordering_fields = ["collection_timestamp", "collector_type", "created"]
    serializer_class = HourlyMetricsCollectionListSerializer

    @property
    def filterset_fields(self) -> dict:
        return {
            "collector_type": ["exact", "in"],
            "collection_timestamp": ["gte", "lte"],
            "status": ["exact"],
        }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return HourlyMetricsCollectionDetailSerializer
        return HourlyMetricsCollectionListSerializer
