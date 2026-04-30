"""
BI connector dashboard views — pre-collected job data from the dashboard_reports app.

Exposes JobData and TemplateMetadata stored by the DASHBOARD_COLLECTION task group.
Data is collected incrementally every 6 hours (configurable) by the dashboard collection
tasks — these endpoints serve whatever has been collected so far.

Enable data collection via: METRICS_SERVICE_FEATURE_ENABLED__DASHBOARD_COLLECTION=true
Enable these endpoints via: METRICS_SERVICE_FEATURE_ENABLED__BI_CONNECTOR=true
"""

from rest_framework.permissions import IsAuthenticated

from apps.dashboard_reports.models import JobData, TemplateMetadata
from apps.tasks.v1.base_views import BaseViewSet

from .dashboard_serializers import (
    JobDataDetailSerializer,
    JobDataListSerializer,
    TemplateMetadataSerializer,
)
from .mixins import BiConnectorEnabledMixin


class JobDataViewSet(BiConnectorEnabledMixin, BaseViewSet):
    """
    Read-only ViewSet for dashboard JobData.

    Exposes AWX job execution records collected by the DASHBOARD_COLLECTION task group.
    Filter by finished date range, status, template, organization, or project.
    Template metadata time estimates are inlined as flat columns.

    Filters: finished__gte, finished__lte, status, template_id, organization_id, project_id
    """

    queryset = JobData.objects.select_related("template_metadata").all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    versioning_class = None
    lookup_field = "job_id"
    ordering = ["-finished"]
    ordering_fields = ["finished", "started", "elapsed", "template_name", "organization_name", "status"]
    serializer_class = JobDataListSerializer

    @property
    def filterset_fields(self) -> dict:
        return {
            "finished": ["gte", "lte"],
            "started": ["gte", "lte"],
            "status": ["exact", "in"],
            "template_id": ["exact", "in"],
            "organization_id": ["exact", "in"],
            "project_id": ["exact", "in"],
        }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return JobDataDetailSerializer
        return JobDataListSerializer


class TemplateMetadataViewSet(BiConnectorEnabledMixin, BaseViewSet):
    """
    Read-only ViewSet for dashboard TemplateMetadata.

    Exposes per-template time estimates (manual execution time, automation creation time)
    used for cost and ROI calculations in the dashboard. These are user-configurable values.

    Filters: template_id, template_name
    """

    queryset = TemplateMetadata.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    versioning_class = None
    lookup_field = "template_id"
    ordering = ["template_name"]
    ordering_fields = ["template_name", "template_id", "created", "modified"]
    serializer_class = TemplateMetadataSerializer

    @property
    def filterset_fields(self) -> dict:
        return {
            "template_id": ["exact", "in"],
            "template_name": ["exact", "icontains"],
        }
