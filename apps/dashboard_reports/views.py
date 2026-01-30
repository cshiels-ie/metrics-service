"""
Dashboard report API views for automation-reports integration.

Provides REST API endpoints for serving pre-calculated dashboard metrics.
"""

from datetime import timedelta
from typing import Any

from django.http import HttpRequest
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.core.permissions import DeveloperModeRequired
from apps.tasks.api_utils import build_error_response

from .models import DashboardReportCache
from .serializers import DashboardDetailsSerializer, ReportResponseSerializer


class DashboardReportViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for dashboard report data endpoints.

    Provides API endpoints for automation-reports dashboard integration,
    serving pre-calculated metrics data from the DashboardReportCache model.

    Endpoints:
        GET /api/v1/report/ - List job template reports (paginated)
        GET /api/v1/report/details/ - Detailed dashboard data

    Features:
        - Serves cached data for fast response times
        - Supports date range filtering
        - Client-side pagination for efficiency
        - Matches automation-reports TypeScript interface exactly

    Query Parameters:
        - start: ISO datetime for date range start (default: 30 days ago)
        - end: ISO datetime for date range end (default: now)
        - page: Page number (default: 1)
        - page_size: Results per page (default: 20)

    Example:
        GET /api/v1/report/?start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
        GET /api/v1/report/details/
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = ReportResponseSerializer
    versioning_class = None  # Disable versioning for this viewset

    # Queryset required by DRF but we override list() to use custom data source
    def get_queryset(self):
        """Return empty queryset - we override list() method instead."""
        return DashboardReportCache.objects.none()

    def list(self, request: HttpRequest, *args, **kwargs) -> Response:
        """
        GET /api/v1/report/

        Returns paginated list of job template reports from cache.

        Query Parameters:
            start (str): ISO datetime for range start (default: 30 days ago)
            end (str): ISO datetime for range end (default: now)
            page (int): Page number (default: 1)
            page_size (int): Results per page (default: 20)

        Returns:
            Response: Paginated report data matching ReportResponse interface
        """
        # Parse date range parameters
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')

        if start_param:
            try:
                start_date = timezone.datetime.fromisoformat(start_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                error_response = build_error_response(
                    "Invalid start date format. Use ISO 8601 format.",
                    status_code=400
                )
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        if end_param:
            try:
                end_date = timezone.datetime.fromisoformat(end_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                error_response = build_error_response(
                    "Invalid end date format. Use ISO 8601 format.",
                    status_code=400
                )
                return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        # Build cache key
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        cache_key = f"job_templates_{start_str}_{end_str}"

        # Retrieve cached data
        cache_entry = DashboardReportCache.objects.filter(cache_key=cache_key).first()

        if not cache_entry:
            # No cached data - return empty response
            response_data = {
                'count': 0,
                'next': None,
                'previous': None,
                'results': []
            }
            serializer = ReportResponseSerializer(response_data)
            return Response(serializer.data)

        # Get data from cache
        data = cache_entry.data.get('job_templates', [])

        # Parse pagination parameters
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
        except (ValueError, TypeError):
            page = 1
            page_size = 20

        # Paginate results (client-side pagination)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = data[start_idx:end_idx]

        # Calculate next/previous URLs
        next_url = None
        previous_url = None

        if end_idx < len(data):
            # More data available
            next_url = f"?page={page + 1}&page_size={page_size}"
            if start_param:
                next_url += f"&start={start_param}"
            if end_param:
                next_url += f"&end={end_param}"

        if page > 1:
            # Previous page available
            previous_url = f"?page={page - 1}&page_size={page_size}"
            if start_param:
                previous_url += f"&start={start_param}"
            if end_param:
                previous_url += f"&end={end_param}"

        # Build response
        response_data = {
            'count': len(data),
            'next': next_url,
            'previous': previous_url,
            'results': paginated_data
        }

        serializer = ReportResponseSerializer(response_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def details(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/report/details/

        Returns comprehensive dashboard data including job templates,
        top projects, and top users.

        Query Parameters:
            start (str): ISO datetime for range start (default: 30 days ago)
            end (str): ISO datetime for range end (default: now)

        Returns:
            Response: Dashboard details with all report types
        """
        # Parse date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')

        if start_param:
            try:
                start_date = timezone.datetime.fromisoformat(start_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass  # Use default

        if end_param:
            try:
                end_date = timezone.datetime.fromisoformat(end_param.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass  # Use default

        # Build cache key prefix
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        cache_key_prefix = f"{start_str}_{end_str}"

        # Fetch all report types from cache
        job_templates_key = f"job_templates_{cache_key_prefix}"
        top_projects_key = f"top_projects_{cache_key_prefix}"
        top_users_key = f"top_users_{cache_key_prefix}"

        job_templates_data = DashboardReportCache.get_or_empty(job_templates_key)
        top_projects_data = DashboardReportCache.get_or_empty(top_projects_key)
        top_users_data = DashboardReportCache.get_or_empty(top_users_key)

        # Build response
        response_data = {
            'job_templates': job_templates_data,
            'top_projects': top_projects_data,
            'top_users': top_users_data,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }

        serializer = DashboardDetailsSerializer(response_data)
        return Response(serializer.data)
