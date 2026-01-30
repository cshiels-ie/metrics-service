"""
Dashboard report API views for automation-reports integration.

Provides REST API endpoints for serving pre-calculated dashboard metrics.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.http import HttpRequest
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet, ViewSet

from apps.core.permissions import DeveloperModeRequired
from apps.tasks.api_utils import build_error_response
from apps.tasks.utils import get_db_connection

from .models import Currency, DashboardReportCache, FilterSet, TemplateMetadata, UserPreference
from .serializers import (
    CurrencySerializer,
    DashboardDetailsSerializer,
    FilterOptionResponseSerializer,
    FilterSetSerializer,
    ReportResponseSerializer,
    TemplateMetadataSerializer,
    UserPreferenceSerializer,
)

logger = logging.getLogger(__name__)


class AapAuthSettingsViewSet(ViewSet):
    """
    Stub ViewSet for AAP OAuth settings.

    Returns mock OAuth2 configuration for development/testing.
    In production, this would return actual AAP OAuth settings.

    Endpoints:
        GET /api/v1/aap_auth/settings/ - Get OAuth configuration
    """

    permission_classes = []  # No authentication required to get auth settings
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/aap_auth/settings/

        Returns OAuth2 configuration for AAP authentication.

        Returns:
            Response: OAuth settings matching AppSettings interface
        """
        # Return stub OAuth settings for development
        settings_data = {
            'name': 'Automation Platform',
            'url': 'http://localhost:8000',
            'client_id': 'metrics-service-dev',
            'scope': 'read write',
            'approval_prompt': 'auto',
            'response_type': 'code'
        }

        return Response(settings_data, status=status.HTTP_200_OK)


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


class CostsViewSet(ViewSet):
    """
    ViewSet for updating global cost settings.

    Allows administrators to update dashboard cost calculation settings.

    Endpoints:
        POST /api/v1/costs/ - Update cost settings
    """

    permission_classes = [DeveloperModeRequired]
    versioning_class = None  # Disable versioning for this viewset

    def create(self, request: HttpRequest) -> Response:
        """
        POST /api/v1/costs/

        Update global cost settings for dashboard calculations.

        Request Body:
            {
                "automated_process_cost_per_minute": "0.75",
                "manual_cost_automation_per_hour": "60.00",
                "enable_template_creation_time": true,
                "max_pdf_job_templates": 150
            }

        Returns:
            Response: Success confirmation with updated settings
        """
        from apps.dynamic_settings.models import Setting

        try:
            updated_settings = {}

            # Update automated process cost per minute
            if 'automated_process_cost_per_minute' in request.data:
                value = str(request.data['automated_process_cost_per_minute'])
                Setting.set_value('automated_process_cost_per_minute', value)
                updated_settings['automated_process_cost_per_minute'] = value

            # Update manual cost per hour
            if 'manual_cost_automation_per_hour' in request.data:
                value = str(request.data['manual_cost_automation_per_hour'])
                Setting.set_value('manual_cost_automation_per_hour', value)
                updated_settings['manual_cost_automation_per_hour'] = value

            # Update enable template creation time
            if 'enable_template_creation_time' in request.data:
                value = 'true' if request.data['enable_template_creation_time'] else 'false'
                Setting.set_value('enable_template_creation_time', value)
                updated_settings['enable_template_creation_time'] = request.data['enable_template_creation_time']

            # Update max PDF job templates
            if 'max_pdf_job_templates' in request.data:
                value = str(int(request.data['max_pdf_job_templates']))
                Setting.set_value('max_pdf_job_templates', value)
                updated_settings['max_pdf_job_templates'] = int(value)

            logger.info(f"User {request.user.username} updated cost settings: {updated_settings}")

            return Response(
                {'success': True, 'message': 'Cost settings updated successfully', 'updated': updated_settings},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error updating cost settings: {str(e)}")
            error_response = build_error_response(f"Failed to update cost settings: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TemplateOptionsViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for template options and filter configuration endpoint.

    Provides the CRITICAL endpoint that aggregates all filter options,
    settings, currencies, and saved views needed by the dashboard.

    Endpoints:
        GET /api/v1/template_options/ - Get all filter options and settings

    This is the master endpoint that the dashboard calls on load to populate:
    - Filter dropdowns (organizations, projects, labels, instances, clusters)
    - Global cost settings
    - Available currencies
    - User's saved filter sets
    - User's current currency preference
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterOptionResponseSerializer
    versioning_class = None  # Disable versioning for this viewset

    def get_queryset(self):
        """Return empty queryset - we override list() method instead."""
        return Currency.objects.none()

    def list(self, request: HttpRequest, *args, **kwargs) -> Response:
        """
        GET /api/v1/template_options/

        Returns aggregated filter options, settings, and user preferences.

        This endpoint combines:
        - Global dashboard settings (from Setting model)
        - User preferences (currency selection)
        - Available currencies
        - User's saved filter sets
        - Real-time AWX filter options (orgs, projects, labels, instances, clusters)
        - Predefined date range options

        Returns:
            Response: Complete filter options matching FilterOptionResponse interface
        """
        try:
            # Get global settings
            settings_data = self._get_global_settings()

            # Get user preferences
            user_pref = UserPreference.objects.filter(user=request.user).first()
            current_currency_id = user_pref.currency_id if (user_pref and user_pref.currency_id) else 1

            # Get currencies from Currency model
            currencies = Currency.objects.filter(is_active=True)

            # Get user's saved filter sets
            filter_sets = FilterSet.objects.filter(user=request.user)

            # Query AWX database for real-time filter options
            awx_data = self._get_awx_filter_options()

            # Aggregate response
            response_data = {
                **settings_data,
                'currency': current_currency_id,
                'currencies': CurrencySerializer(currencies, many=True).data,
                'filter_sets': FilterSetSerializer(filter_sets, many=True).data,
                **awx_data,
                'date_ranges': self._get_date_range_options(),
            }

            serializer = FilterOptionResponseSerializer(response_data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error retrieving template options: {str(e)}")
            error_response = build_error_response(
                f"Failed to retrieve template options: {str(e)}", status_code=500
            )
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_global_settings(self) -> dict[str, Any]:
        """
        Retrieve global dashboard settings from Setting model.

        Returns:
            dict: Global settings for cost calculations and features
        """
        from apps.dynamic_settings.models import Setting

        try:
            return {
                'automated_process_cost_per_minute': Setting.get_value(
                    'automated_process_cost_per_minute', '0.50'
                ),
                'manual_cost_automation_per_hour': Setting.get_value('manual_cost_automation_per_hour', '50.00'),
                'enable_template_creation_time': Setting.get_value('enable_template_creation_time', 'true')
                == 'true',
                'max_pdf_job_templates': int(Setting.get_value('max_pdf_job_templates', '100')),
            }
        except Exception as e:
            logger.warning(f"Error retrieving global settings, using defaults: {str(e)}")
            # Return safe defaults
            return {
                'automated_process_cost_per_minute': '0.50',
                'manual_cost_automation_per_hour': '50.00',
                'enable_template_creation_time': True,
                'max_pdf_job_templates': 100,
            }

    def _get_awx_filter_options(self) -> dict[str, list[dict[str, Any]]]:
        """
        Query AWX database for real-time filter options.

        Uses direct SQL queries to AWX database for current organizations,
        projects, labels, instances, and clusters.

        Returns:
            dict: Filter options with keys: organizations, projects, labels, instances, clusters
        """
        from .awx_queries import get_all_filter_options

        try:
            db_connection = get_db_connection('awx')
            return get_all_filter_options(db_connection)
        except Exception as e:
            logger.error(f"Error querying AWX database for filter options: {str(e)}")
            # Return empty arrays on error so dashboard can still load
            return {
                'organizations': [],
                'projects': [],
                'labels': [],
                'instances': [],
                'clusters': [],
            }

    def _get_date_range_options(self) -> list[dict[str, Any]]:
        """
        Get predefined date range options.

        Returns:
            list: Static date range options for dropdown
        """
        return [
            {'id': 1, 'key': 'last_7_days', 'name': 'Last 7 days'},
            {'id': 2, 'key': 'month_to_date', 'name': 'Last 30 days'},
            {'id': 3, 'key': 'last_90_days', 'name': 'Last 90 days'},
            {'id': 4, 'key': 'custom', 'name': 'Custom range'},
        ]

    @action(detail=False, methods=['post'], url_path='restore_user_inputs')
    def restore_user_inputs(self, request: HttpRequest) -> Response:
        """
        POST /api/v1/template_options/restore_user_inputs/

        Reset all template metadata overrides to defaults.

        This endpoint deletes all custom template metadata, allowing the system
        to use auto-calculated values for time estimates and costs.

        Request Body (optional):
            {
                "template_ids": [1, 2, 3]  // Specific templates to reset, or omit for all
            }

        Returns:
            Response: Success confirmation with count of reset templates
        """
        try:
            template_ids = request.data.get('template_ids')

            if template_ids:
                # Reset specific templates
                deleted_count, _ = TemplateMetadata.objects.filter(template_id__in=template_ids).delete()
                logger.info(f"User {request.user.username} reset {deleted_count} template metadata entries")
            else:
                # Reset all templates
                deleted_count, _ = TemplateMetadata.objects.all().delete()
                logger.info(f"User {request.user.username} reset ALL template metadata ({deleted_count} entries)")

            return Response(
                {
                    'success': True,
                    'message': f'Successfully reset {deleted_count} template(s) to defaults',
                    'reset_count': deleted_count,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error resetting template metadata: {str(e)}")
            error_response = build_error_response(
                f"Failed to reset template metadata: {str(e)}", status_code=500
            )
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CommonSettingsViewSet(ViewSet):
    """
    ViewSet for user preference management.

    Provides endpoints for saving and retrieving user-specific settings
    like currency preference and other dashboard preferences.

    Endpoints:
        POST /api/v1/common/settings/ - Save user preferences
    """

    permission_classes = [DeveloperModeRequired]
    versioning_class = None  # Disable versioning for this viewset

    def create(self, request: HttpRequest) -> Response:
        """
        POST /api/v1/common/settings/

        Save user dashboard preferences including currency selection.

        Request Body:
            {
                "currency": 1,  // Currency ID
                "preferences_data": {...}  // Optional additional preferences
            }

        Returns:
            Response: Success confirmation with saved currency ID
        """
        try:
            currency_id = request.data.get('currency')
            preferences_data = request.data.get('preferences_data', {})

            # Validate currency exists if provided
            if currency_id:
                try:
                    Currency.objects.get(id=currency_id, is_active=True)
                except Currency.DoesNotExist:
                    error_response = build_error_response("Invalid currency ID", status_code=400)
                    return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

            # Update or create user preference
            user_pref, created = UserPreference.objects.update_or_create(
                user=request.user,
                defaults={'currency_id': currency_id, 'preferences_data': preferences_data},
            )

            logger.info(
                f"User {request.user.username} {'created' if created else 'updated'} preferences: currency={currency_id}"
            )

            return Response(
                {'success': True, 'message': 'Settings saved successfully', 'currency': currency_id},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error saving user preferences: {str(e)}")
            error_response = build_error_response(f"Failed to save settings: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TemplateMetadataViewSet(ModelViewSet):
    """
    ViewSet for managing job template metadata overrides.

    Allows users to override auto-calculated time estimates and costs
    for specific job templates.

    Endpoints:
        GET /api/v1/templates/ - List all template metadata
        GET /api/v1/templates/{template_id}/ - Get metadata for specific template
        PUT /api/v1/templates/{template_id}/ - Update template metadata
        POST /api/v1/templates/ - Create new template metadata
        DELETE /api/v1/templates/{template_id}/ - Delete template metadata
    """

    permission_classes = [DeveloperModeRequired]
    queryset = TemplateMetadata.objects.all()
    serializer_class = TemplateMetadataSerializer
    lookup_field = 'template_id'  # Use template_id instead of pk
    versioning_class = None  # Disable versioning for this viewset

    def get_queryset(self):
        """Return all template metadata ordered by name."""
        return TemplateMetadata.objects.all().order_by('template_name')


class FilterSetViewSet(ModelViewSet):
    """
    ViewSet for managing saved filter sets (saved views).

    Allows users to save, retrieve, update, and delete filter configurations.

    Endpoints:
        GET /api/v1/common/filter_set/ - List user's saved filter sets
        GET /api/v1/common/filter_set/{id}/ - Get specific filter set
        POST /api/v1/common/filter_set/ - Create new filter set
        PUT /api/v1/common/filter_set/{id}/ - Update filter set
        DELETE /api/v1/common/filter_set/{id}/ - Delete filter set
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def get_queryset(self):
        """Filter to current user's filter sets only."""
        return FilterSet.objects.filter(user=self.request.user).order_by('-modified')

    def perform_create(self, serializer):
        """Auto-assign current user when creating filter set."""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """
        Handle default filter set constraint.

        If setting a filter set as default, unset any existing default
        for this user.
        """
        if serializer.validated_data.get('is_default'):
            # Unset any existing default filter sets for this user
            FilterSet.objects.filter(user=self.request.user, is_default=True).exclude(
                id=self.get_object().id
            ).update(is_default=False)

        serializer.save()


class OrganizationsViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving organizations from AWX database.

    Provides real-time organization data for filter dropdowns.

    Endpoints:
        GET /api/v1/template_options/organizations/ - List all organizations
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer  # Uses generic serializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/template_options/organizations/

        Returns list of active organizations from AWX database.

        Returns:
            Response: Array of {id, name} objects
        """
        from .awx_queries import get_organizations

        try:
            db_connection = get_db_connection('awx')
            organizations = get_organizations(db_connection)
            return Response(organizations, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching organizations: {str(e)}")
            error_response = build_error_response(f"Failed to fetch organizations: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectsViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving projects from AWX database.

    Provides real-time project data for filter dropdowns.

    Endpoints:
        GET /api/v1/template_options/projects/ - List all projects
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/template_options/projects/

        Returns list of projects from AWX database.

        Returns:
            Response: Array of {id, name} objects
        """
        from .awx_queries import get_projects

        try:
            db_connection = get_db_connection('awx')
            projects = get_projects(db_connection)
            return Response(projects, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            error_response = build_error_response(f"Failed to fetch projects: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LabelsViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving labels from AWX database.

    Provides real-time label data for filter dropdowns.

    Endpoints:
        GET /api/v1/template_options/labels/ - List all labels
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/template_options/labels/

        Returns list of labels from AWX database.

        Returns:
            Response: Array of {id, name} objects
        """
        from .awx_queries import get_labels

        try:
            db_connection = get_db_connection('awx')
            labels = get_labels(db_connection)
            return Response(labels, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching labels: {str(e)}")
            error_response = build_error_response(f"Failed to fetch labels: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InstancesViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving instances from AWX database.

    Provides real-time instance data for filter dropdowns.

    Endpoints:
        GET /api/v1/template_options/instances/ - List all instances
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/template_options/instances/

        Returns list of controller instances from AWX database.

        Returns:
            Response: Array of {id, name} objects (hostname as name)
        """
        from .awx_queries import get_instances

        try:
            db_connection = get_db_connection('awx')
            instances = get_instances(db_connection)
            return Response(instances, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching instances: {str(e)}")
            error_response = build_error_response(f"Failed to fetch instances: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportViewSet(ViewSet):
    """
    ViewSet for CSV and PDF export endpoints.

    Provides data export functionality for dashboard reports.

    Endpoints:
        GET /api/v1/report/csv/ - Export reports to CSV
        POST /api/v1/report/pdf/ - Export reports to PDF
    """

    permission_classes = [DeveloperModeRequired]
    versioning_class = None  # Disable versioning for this viewset

    @action(detail=False, methods=['get'], url_path='csv')
    def export_csv(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/report/csv/

        Export dashboard report data to CSV format.

        Query Parameters:
            start (str): ISO datetime for range start (default: 30 days ago)
            end (str): ISO datetime for range end (default: now)

        Returns:
            Response: CSV file download
        """
        import csv

        from django.http import HttpResponse

        try:
            # Parse date range parameters
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

            # Build cache key
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            cache_key = f"job_templates_{start_str}_{end_str}"

            # Retrieve cached data
            cache_entry = DashboardReportCache.objects.filter(cache_key=cache_key).first()

            if not cache_entry:
                error_response = build_error_response("No data available for export", status_code=404)
                return Response(error_response, status=status.HTTP_404_NOT_FOUND)

            # Generate CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = (
                f'attachment; filename="dashboard_report_{start_str}_to_{end_str}.csv"'
            )

            data = cache_entry.data.get('job_templates', [])

            if data:
                writer = csv.DictWriter(response, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            else:
                # Empty CSV with headers
                writer = csv.writer(response)
                writer.writerow(['No data available'])

            logger.info(f"User {request.user.username} exported {len(data)} records to CSV")
            return response

        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
            error_response = build_error_response(f"Failed to export CSV: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='pdf')
    def export_pdf(self, request: HttpRequest) -> Response:
        """
        POST /api/v1/report/pdf/

        Export dashboard report data to PDF format.

        Request Body:
            {
                "start": "2025-01-01T00:00:00Z",  // Optional
                "end": "2025-01-31T23:59:59Z"     // Optional
            }

        Returns:
            Response: PDF file download

        Note: Limited to max_pdf_job_templates setting (default 100 rows)
        """
        try:
            # Import PDF libraries
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.lib.units import inch
                from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
                from reportlab.lib.styles import getSampleStyleSheet
            except ImportError:
                error_response = build_error_response(
                    "PDF export requires reportlab library. Please install: pip install reportlab", status_code=500
                )
                return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            from io import BytesIO

            from django.http import HttpResponse

            # Get max rows limit from settings
            from apps.dynamic_settings.models import Setting

            max_rows = int(Setting.get_value('max_pdf_job_templates', '100'))

            # Parse date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)

            start_param = request.data.get('start') or request.query_params.get('start')
            end_param = request.data.get('end') or request.query_params.get('end')

            if start_param:
                try:
                    start_date = timezone.datetime.fromisoformat(start_param.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass

            if end_param:
                try:
                    end_date = timezone.datetime.fromisoformat(end_param.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass

            # Build cache key
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            cache_key = f"job_templates_{start_str}_{end_str}"

            # Retrieve cached data
            cache_entry = DashboardReportCache.objects.filter(cache_key=cache_key).first()

            if not cache_entry:
                error_response = build_error_response("No data available for export", status_code=404)
                return Response(error_response, status=status.HTTP_404_NOT_FOUND)

            data = cache_entry.data.get('job_templates', [])[:max_rows]

            # Generate PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5 * inch, bottomMargin=0.5 * inch)

            elements = []
            styles = getSampleStyleSheet()

            # Title
            title = Paragraph(f"Dashboard Report ({start_str} to {end_str})", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 0.2 * inch))

            if data:
                # Build table with limited columns for readability
                table_data = [['Template Name', 'Runs', 'Success', 'Failed', 'Savings']]
                for row in data:
                    table_data.append(
                        [
                            str(row.get('name', ''))[:30],  # Truncate long names
                            str(row.get('runs', 0)),
                            str(row.get('successful_runs', 0)),
                            str(row.get('failed_runs', 0)),
                            str(row.get('savings', '$0.00')),
                        ]
                    )

                table = Table(table_data)
                table.setStyle(
                    TableStyle(
                        [
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ]
                    )
                )
                elements.append(table)

                # Add note if data was truncated
                if len(cache_entry.data.get('job_templates', [])) > max_rows:
                    elements.append(Spacer(1, 0.2 * inch))
                    note = Paragraph(
                        f"Note: Report limited to {max_rows} templates. "
                        f"Total templates: {len(cache_entry.data.get('job_templates', []))}",
                        styles['Normal'],
                    )
                    elements.append(note)
            else:
                elements.append(Paragraph("No data available for this date range.", styles['Normal']))

            doc.build(elements)

            # Return response
            buffer.seek(0)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="dashboard_report_{start_str}_to_{end_str}.pdf"'

            logger.info(
                f"User {request.user.username} exported {len(data)} records to PDF (max: {max_rows})"
            )
            return response

        except Exception as e:
            logger.error(f"Error exporting to PDF: {str(e)}")
            error_response = build_error_response(f"Failed to export PDF: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
