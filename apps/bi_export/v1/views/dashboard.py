"""Views exposing dashboard collection data (JobData, JobHostSummary) for BI consumption."""

import logging
from datetime import UTC, datetime

from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor
from ansible_base.rest_pagination import DefaultPaginator
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.bi_export.v1.serializers import JobDataSerializer, JobHostSummarySerializer
from apps.dashboard_reports.models import JobData, JobHostSummary

logger = logging.getLogger(__name__)


def _parse_date(value: str | None) -> datetime | None:
    """Parse a YYYY-MM-DD query param into a timezone-aware datetime at midnight UTC."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None


@extend_schema_view(
    list=extend_schema(
        description="Paginated list of job execution records from the dashboard collection. "
        "Supports filtering by date range, organization, template, project, and status.",
        parameters=[
            OpenApiParameter("start_date", str, description="Filter jobs finished on or after YYYY-MM-DD"),
            OpenApiParameter("end_date", str, description="Filter jobs finished on or before YYYY-MM-DD"),
            OpenApiParameter("organization_id", int, description="Filter by AWX organization ID"),
            OpenApiParameter("template_id", int, description="Filter by AWX template ID"),
            OpenApiParameter("project_id", int, description="Filter by AWX project ID"),
            OpenApiParameter("status", str, description="Filter by job status (successful, failed, etc.)"),
        ],
    ),
    retrieve=extend_schema(description="Single job execution record by internal ID."),
)
class JobDataViewSet(ReadOnlyModelViewSet):
    """Read-only access to dashboard job records for BI tool consumption."""

    serializer_class = JobDataSerializer
    permission_classes = [IsSystemAdminOrAuditor]
    pagination_class = DefaultPaginator
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["finished", "started", "elapsed", "num_hosts"]
    ordering = ["-finished"]

    def get_queryset(self):
        qs = JobData.objects.prefetch_related("labels")

        start_date = _parse_date(self.request.query_params.get("start_date"))
        end_date = _parse_date(self.request.query_params.get("end_date"))
        qs = qs.after_date(start_date).before_date(end_date)

        if org := self.request.query_params.get("organization_id"):
            qs = qs.filter(organization_id=org)
        if template := self.request.query_params.get("template_id"):
            qs = qs.filter(template_id=template)
        if project := self.request.query_params.get("project_id"):
            qs = qs.filter(project_id=project)
        if status := self.request.query_params.get("status"):
            qs = qs.filter(status=status)

        return qs


@extend_schema_view(
    list=extend_schema(
        description="Paginated list of job host summaries from the dashboard collection. "
        "Returns per-host records for each collected job.",
        parameters=[
            OpenApiParameter("job_data_id", int, description="Filter by internal JobData ID"),
            OpenApiParameter("job_id", int, description="Filter by AWX job ID"),
            OpenApiParameter("host_name", str, description="Filter by host name (exact match)"),
        ],
    ),
    retrieve=extend_schema(description="Single job host summary record by internal ID."),
)
class JobHostSummaryViewSet(ReadOnlyModelViewSet):
    """Read-only access to per-host job results for BI tool consumption."""

    serializer_class = JobHostSummarySerializer
    permission_classes = [IsSystemAdminOrAuditor]
    pagination_class = DefaultPaginator
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["id", "host_name"]
    ordering = ["id"]

    def get_queryset(self):
        qs = JobHostSummary.objects.select_related("job_data")

        if job_data_id := self.request.query_params.get("job_data_id"):
            qs = qs.filter(job_data_id=job_data_id)
        if job_id := self.request.query_params.get("job_id"):
            qs = qs.filter(job_data__job_id=job_id)
        if host_name := self.request.query_params.get("host_name"):
            qs = qs.filter(host_name=host_name)

        return qs
