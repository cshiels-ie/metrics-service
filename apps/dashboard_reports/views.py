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
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, permission_classes as permission_classes_decorator
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


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication without CSRF enforcement for development mode.

    This allows the automation-reports frontend to make POST requests
    without CSRF tokens during development. DO NOT use in production!
    """
    def enforce_csrf(self, request):
        return  # Skip CSRF check


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

    def _calculate_job_templates_from_awx(self, start_date, end_date):
        """
        Dynamically calculate job templates data from AWX database.
        Used when no cache exists for the requested date range.
        """
        from apps.tasks.utils import get_db_connection

        try:
            db = get_db_connection('awx')
            cursor = db.cursor()

            # Query jobs within date range
            cursor.execute('''
                SELECT
                    COALESCE(jt.id, 0) as template_id,
                    COALESCE(jt.name, 'Unknown Template') as template_name,
                    COUNT(uj.id) as runs,
                    SUM(CASE WHEN uj.status = 'successful' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN uj.status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(uj.elapsed) as elapsed,
                    COUNT(DISTINCT jhs.host_id) as num_hosts
                FROM main_unifiedjob uj
                LEFT JOIN main_job mj ON uj.id = mj.unifiedjob_ptr_id
                LEFT JOIN main_unifiedjobtemplate jt ON mj.job_template_id = jt.id
                LEFT JOIN main_jobhostsummary jhs ON jhs.job_id = uj.id
                WHERE uj.status IN ('successful', 'failed', 'pending', 'running')
                  AND (uj.finished IS NULL OR uj.finished BETWEEN %s AND %s)
                GROUP BY jt.id, jt.name
                ORDER BY runs DESC
            ''', [start_date, end_date])

            job_templates = []
            for row in cursor.fetchall():
                template_id, template_name, runs, successful, failed, elapsed, num_hosts = row
                elapsed = float(elapsed or 0)
                successful = int(successful or 0)
                failed = int(failed or 0)
                num_hosts = int(num_hosts or 0)

                # Format duration
                if elapsed < 60:
                    elapsed_str = f'{int(elapsed)}s'
                elif elapsed < 3600:
                    mins = int(elapsed / 60)
                    secs = int(elapsed % 60)
                    elapsed_str = f'{mins}m {secs}s'
                else:
                    hours = int(elapsed / 3600)
                    mins = int((elapsed % 3600) / 60)
                    elapsed_str = f'{hours}h {mins}m'

                # Calculate costs
                time_manual_minutes = runs * 5
                time_create_minutes = 120
                automated_costs = (elapsed / 60) * 0.50
                manual_costs = (time_manual_minutes / 60) * 50.00
                savings = manual_costs - automated_costs - (time_create_minutes / 60 * 50.00)

                job_templates.append({
                    'name': template_name,
                    'runs': runs,
                    'elapsed': int(elapsed),
                    'cluster': 1,
                    'elapsed_str': elapsed_str,
                    'num_hosts': num_hosts,
                    'time_taken_manually_execute_minutes': time_manual_minutes,
                    'time_taken_create_automation_minutes': time_create_minutes,
                    'successful_runs': successful,
                    'failed_runs': failed,
                    'automated_costs': round(automated_costs, 2),
                    'manual_costs': round(manual_costs, 2),
                    'savings': round(savings, 2),
                })

            cursor.close()
            return job_templates

        except Exception as e:
            logger.error(f"Error querying AWX database: {str(e)}")
            return []

    def _calculate_charts_from_awx(self, start_date, end_date):
        """
        Dynamically calculate chart data from AWX database.
        Returns job and host charts with time-series data.
        """
        from apps.tasks.utils import get_db_connection

        try:
            db = get_db_connection('awx')
            cursor = db.cursor()

            # Query jobs by date
            cursor.execute('''
                SELECT DATE(uj.finished) as date,
                       COUNT(uj.id) as job_count,
                       COUNT(DISTINCT jhs.host_id) as host_count
                FROM main_unifiedjob uj
                LEFT JOIN main_jobhostsummary jhs ON jhs.job_id = uj.id
                WHERE uj.status IN ('successful', 'failed', 'pending', 'running')
                  AND uj.finished IS NOT NULL
                  AND uj.finished BETWEEN %s AND %s
                GROUP BY DATE(uj.finished)
                ORDER BY date
            ''', [start_date, end_date])

            job_chart_items = []
            host_chart_items = []
            max_job_count = 0
            max_host_count = 0
            min_date = None
            max_date = None

            for row in cursor.fetchall():
                date, job_count, host_count = row
                job_count = int(job_count or 0)
                host_count = int(host_count or 0)

                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

                if job_count > max_job_count:
                    max_job_count = job_count
                if host_count > max_host_count:
                    max_host_count = host_count

                # Format for frontend (expects ISO string for x-axis)
                date_str = date.isoformat() if hasattr(date, 'isoformat') else str(date)

                job_chart_items.append({'x': date_str, 'y': job_count})
                host_chart_items.append({'x': date_str, 'y': host_count})

            cursor.close()

            return {
                'job_chart': {
                    'items': job_chart_items,
                    'range': {
                        'start': min_date.isoformat() if min_date else None,
                        'end': max_date.isoformat() if max_date else None,
                        'max_value': max_job_count
                    }
                },
                'host_chart': {
                    'items': host_chart_items,
                    'range': {
                        'start': min_date.isoformat() if min_date else None,
                        'end': max_date.isoformat() if max_date else None,
                        'max_value': max_host_count
                    }
                }
            }

        except Exception as e:
            logger.error(f"Error querying AWX charts: {str(e)}")
            return {
                'job_chart': {'items': [], 'range': {}},
                'host_chart': {'items': [], 'range': {}}
            }

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

        # Accept both 'start'/'end' and 'start_date'/'end_date' parameter names
        start_param = request.query_params.get('start') or request.query_params.get('start_date')
        end_param = request.query_params.get('end') or request.query_params.get('end_date')

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
            # No cached data - dynamically query AWX database
            logger.info(f"No cache found for {cache_key}, querying AWX database directly")
            data = self._calculate_job_templates_from_awx(start_date, end_date)
        else:
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

        # Accept both 'start'/'end' and 'start_date'/'end_date' parameter names
        start_param = request.query_params.get('start') or request.query_params.get('start_date')
        end_param = request.query_params.get('end') or request.query_params.get('end_date')

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

        # Fetch all report types from cache (or calculate dynamically)
        job_templates_key = f"job_templates_{cache_key_prefix}"
        top_projects_key = f"top_projects_{cache_key_prefix}"
        top_users_key = f"top_users_{cache_key_prefix}"

        # Check cache first, fallback to dynamic calculation
        job_templates_cache = DashboardReportCache.objects.filter(cache_key=job_templates_key).first()
        if job_templates_cache:
            job_templates_data = job_templates_cache.data
        else:
            logger.info(f"No job templates cache for {job_templates_key}, querying AWX")
            templates = self._calculate_job_templates_from_awx(start_date, end_date)
            charts = self._calculate_charts_from_awx(start_date, end_date)
            job_templates_data = {
                'count': len(templates),
                'timestamp': timezone.now().isoformat(),
                'job_templates': templates,
                'job_chart': charts['job_chart'],
                'host_chart': charts['host_chart']
            }

        top_projects_cache = DashboardReportCache.objects.filter(cache_key=top_projects_key).first()
        if top_projects_cache:
            top_projects_data = top_projects_cache.data
        else:
            logger.info(f"No top projects cache for {top_projects_key}, querying AWX")
            top_projects_data = {
                'count': 0,
                'timestamp': timezone.now().isoformat(),
                'top_projects': []
            }

        top_users_cache = DashboardReportCache.objects.filter(cache_key=top_users_key).first()
        if top_users_cache:
            top_users_data = top_users_cache.data
        else:
            logger.info(f"No top users cache for {top_users_key}, querying AWX")
            top_users_data = {
                'count': 0,
                'timestamp': timezone.now().isoformat(),
                'top_users': []
            }

        # Calculate summary totals from job templates
        templates = job_templates_data.get('job_templates', [])

        total_successful = sum(t.get('successful_runs', 0) for t in templates)
        total_failed = sum(t.get('failed_runs', 0) for t in templates)
        total_hosts = sum(t.get('num_hosts', 0) for t in templates)
        total_elapsed_seconds = sum(t.get('elapsed', 0) for t in templates)
        total_hours = round(total_elapsed_seconds / 3600, 2) if total_elapsed_seconds else 0

        # Calculate total job runs (sum of all template runs)
        total_job_runs = sum(t.get('runs', 0) for t in templates)

        # Calculate total host job runs (sum of runs * num_hosts for each template)
        total_host_job_runs = sum(t.get('runs', 0) * t.get('num_hosts', 0) for t in templates)

        # Get chart data from job_templates cache (if available)
        job_chart = job_templates_data.get('job_chart', {'items': [], 'range': {}})
        host_chart = job_templates_data.get('host_chart', {'items': [], 'range': {}})

        # Build response with summary totals
        response_data = {
            'job_templates': job_templates_data,
            'top_projects': top_projects_data,
            'top_users': top_users_data,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_number_of_successful_jobs': {'value': total_successful},
            'total_number_of_failed_jobs': {'value': total_failed},
            'total_number_of_unique_hosts': {'value': total_hosts},
            'total_hours_of_automation': {'value': total_hours},
            'total_number_of_job_runs': {'value': total_job_runs},
            'total_number_of_host_job_runs': {'value': total_host_job_runs},
            'job_chart': job_chart,
            'host_chart': host_chart
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

    authentication_classes = [CsrfExemptSessionAuthentication]
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

        Returns raw data in {id, name} format - serializer will transform to
        {key, value, cluster_id} format for frontend compatibility.

        Returns:
            dict: Filter options with keys: organizations, projects, labels, instances, clusters
                  Each option in format: {id: int, name: str}
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

    authentication_classes = [CsrfExemptSessionAuthentication]
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

    authentication_classes = [CsrfExemptSessionAuthentication]
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

    authentication_classes = [CsrfExemptSessionAuthentication]
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

    Provides real-time organization data for filter dropdowns with pagination support.

    Endpoints:
        GET /api/v1/organizations/ - List all organizations (paginated)
        GET /api/v1/organizations/{id}/ - Get specific organization

    Query Parameters:
        page (int): Page number (default: 1)
        page_size (int): Results per page (default: 10)
        search (str): Search by organization name
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer  # For get_queryset compatibility
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/organizations/

        Returns paginated list of organizations from AWX database.

        Returns:
            Response: Paginated {count, next, previous, results} with {key, value, cluster_id} format
        """
        from .awx_queries import get_organizations
        from .serializers import PaginatedFilterOptionsSerializer

        try:
            db_connection = get_db_connection('awx')
            organizations = get_organizations(db_connection)

            # Parse pagination parameters
            try:
                page = int(request.query_params.get('page', 1))
                page_size = int(request.query_params.get('page_size', 10))
            except (ValueError, TypeError):
                page = 1
                page_size = 10

            # Filter by search query if provided
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                organizations = [
                    org for org in organizations
                    if search_query.lower() in org['name'].lower()
                ]

            # Paginate results
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_orgs = organizations[start_idx:end_idx]

            # Build pagination URLs
            base_url = request.build_absolute_uri(request.path)
            next_url = None
            previous_url = None

            if end_idx < len(organizations):
                next_url = f"{base_url}?page={page + 1}&page_size={page_size}"
                if search_query:
                    next_url += f"&search={search_query}"

            if page > 1:
                previous_url = f"{base_url}?page={page - 1}&page_size={page_size}"
                if search_query:
                    previous_url += f"&search={search_query}"

            # Build response
            response_data = {
                'count': len(organizations),
                'next': next_url,
                'previous': previous_url,
                'results': paginated_orgs
            }

            serializer = PaginatedFilterOptionsSerializer(response_data)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching organizations: {str(e)}")
            error_response = build_error_response(f"Failed to fetch organizations: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request: HttpRequest, pk=None) -> Response:
        """
        GET /api/v1/organizations/{id}/

        Returns single organization by ID.

        Returns:
            Response: Single organization in {key, value, cluster_id} format
        """
        from .awx_queries import get_organizations
        from .serializers import FilterOptionWithIdSerializer

        try:
            db_connection = get_db_connection('awx')
            organizations = get_organizations(db_connection)

            # Find organization by ID
            org = next((o for o in organizations if o['id'] == int(pk)), None)

            if not org:
                error_response = build_error_response(f"Organization with id {pk} not found", status_code=404)
                return Response(error_response, status=status.HTTP_404_NOT_FOUND)

            serializer = FilterOptionWithIdSerializer(org)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching organization {pk}: {str(e)}")
            error_response = build_error_response(f"Failed to fetch organization: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectsViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving projects from AWX database.

    Provides real-time project data for filter dropdowns with pagination support.

    Endpoints:
        GET /api/v1/projects/ - List all projects (paginated)
        GET /api/v1/projects/{id}/ - Get specific project

    Query Parameters:
        page (int): Page number (default: 1)
        page_size (int): Results per page (default: 10)
        search (str): Search by project name
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/projects/

        Returns paginated list of projects from AWX database.

        Returns:
            Response: Paginated {count, next, previous, results} with {key, value, cluster_id} format
        """
        from .awx_queries import get_projects
        from .serializers import PaginatedFilterOptionsSerializer

        try:
            db_connection = get_db_connection('awx')
            projects = get_projects(db_connection)

            # Parse pagination parameters
            try:
                page = int(request.query_params.get('page', 1))
                page_size = int(request.query_params.get('page_size', 10))
            except (ValueError, TypeError):
                page = 1
                page_size = 10

            # Filter by search query if provided
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                projects = [
                    proj for proj in projects
                    if search_query.lower() in proj['name'].lower()
                ]

            # Paginate results
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_projects = projects[start_idx:end_idx]

            # Build pagination URLs
            base_url = request.build_absolute_uri(request.path)
            next_url = None
            previous_url = None

            if end_idx < len(projects):
                next_url = f"{base_url}?page={page + 1}&page_size={page_size}"
                if search_query:
                    next_url += f"&search={search_query}"

            if page > 1:
                previous_url = f"{base_url}?page={page - 1}&page_size={page_size}"
                if search_query:
                    previous_url += f"&search={search_query}"

            # Build response
            response_data = {
                'count': len(projects),
                'next': next_url,
                'previous': previous_url,
                'results': paginated_projects
            }

            serializer = PaginatedFilterOptionsSerializer(response_data)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            error_response = build_error_response(f"Failed to fetch projects: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request: HttpRequest, pk=None) -> Response:
        """
        GET /api/v1/projects/{id}/

        Returns single project by ID.

        Returns:
            Response: Single project in {key, value, cluster_id} format
        """
        from .awx_queries import get_projects
        from .serializers import FilterOptionWithIdSerializer

        try:
            db_connection = get_db_connection('awx')
            projects = get_projects(db_connection)

            # Find project by ID
            project = next((p for p in projects if p['id'] == int(pk)), None)

            if not project:
                error_response = build_error_response(f"Project with id {pk} not found", status_code=404)
                return Response(error_response, status=status.HTTP_404_NOT_FOUND)

            serializer = FilterOptionWithIdSerializer(project)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching project {pk}: {str(e)}")
            error_response = build_error_response(f"Failed to fetch project: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LabelsViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving labels from AWX database.

    Provides real-time label data for filter dropdowns with pagination support.

    Endpoints:
        GET /api/v1/labels/ - List all labels (paginated)
        GET /api/v1/labels/{id}/ - Get specific label

    Query Parameters:
        page (int): Page number (default: 1)
        page_size (int): Results per page (default: 10)
        search (str): Search by label name
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/labels/

        Returns paginated list of labels from AWX database.

        Returns:
            Response: Paginated {count, next, previous, results} with {key, value, cluster_id} format
        """
        from .awx_queries import get_labels
        from .serializers import PaginatedFilterOptionsSerializer

        try:
            db_connection = get_db_connection('awx')
            labels = get_labels(db_connection)

            # Parse pagination parameters
            try:
                page = int(request.query_params.get('page', 1))
                page_size = int(request.query_params.get('page_size', 10))
            except (ValueError, TypeError):
                page = 1
                page_size = 10

            # Filter by search query if provided
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                labels = [
                    label for label in labels
                    if search_query.lower() in label['name'].lower()
                ]

            # Paginate results
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_labels = labels[start_idx:end_idx]

            # Build pagination URLs
            base_url = request.build_absolute_uri(request.path)
            next_url = None
            previous_url = None

            if end_idx < len(labels):
                next_url = f"{base_url}?page={page + 1}&page_size={page_size}"
                if search_query:
                    next_url += f"&search={search_query}"

            if page > 1:
                previous_url = f"{base_url}?page={page - 1}&page_size={page_size}"
                if search_query:
                    previous_url += f"&search={search_query}"

            # Build response
            response_data = {
                'count': len(labels),
                'next': next_url,
                'previous': previous_url,
                'results': paginated_labels
            }

            serializer = PaginatedFilterOptionsSerializer(response_data)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching labels: {str(e)}")
            error_response = build_error_response(f"Failed to fetch labels: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request: HttpRequest, pk=None) -> Response:
        """
        GET /api/v1/labels/{id}/

        Returns single label by ID.

        Returns:
            Response: Single label in {key, value, cluster_id} format
        """
        from .awx_queries import get_labels
        from .serializers import FilterOptionWithIdSerializer

        try:
            db_connection = get_db_connection('awx')
            labels = get_labels(db_connection)

            # Find label by ID
            label = next((l for l in labels if l['id'] == int(pk)), None)

            if not label:
                error_response = build_error_response(f"Label with id {pk} not found", status_code=404)
                return Response(error_response, status=status.HTTP_404_NOT_FOUND)

            serializer = FilterOptionWithIdSerializer(label)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching label {pk}: {str(e)}")
            error_response = build_error_response(f"Failed to fetch label: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InstancesViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for retrieving instances from AWX database.

    Provides real-time instance data for filter dropdowns with pagination support.

    Endpoints:
        GET /api/v1/instances/ - List all instances (paginated)
        GET /api/v1/instances/{id}/ - Get specific instance

    Query Parameters:
        page (int): Page number (default: 1)
        page_size (int): Results per page (default: 10)
        search (str): Search by instance hostname
    """

    permission_classes = [DeveloperModeRequired]
    serializer_class = FilterSetSerializer
    versioning_class = None  # Disable versioning for this viewset

    def list(self, request: HttpRequest) -> Response:
        """
        GET /api/v1/instances/

        Returns paginated list of controller instances from AWX database.

        Returns:
            Response: Paginated {count, next, previous, results} with {key, value, cluster_id} format
        """
        from .awx_queries import get_instances
        from .serializers import PaginatedFilterOptionsSerializer

        try:
            db_connection = get_db_connection('awx')
            instances = get_instances(db_connection)

            # Parse pagination parameters
            try:
                page = int(request.query_params.get('page', 1))
                page_size = int(request.query_params.get('page_size', 10))
            except (ValueError, TypeError):
                page = 1
                page_size = 10

            # Filter by search query if provided
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                instances = [
                    inst for inst in instances
                    if search_query.lower() in inst['name'].lower()
                ]

            # Paginate results
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_instances = instances[start_idx:end_idx]

            # Build pagination URLs
            base_url = request.build_absolute_uri(request.path)
            next_url = None
            previous_url = None

            if end_idx < len(instances):
                next_url = f"{base_url}?page={page + 1}&page_size={page_size}"
                if search_query:
                    next_url += f"&search={search_query}"

            if page > 1:
                previous_url = f"{base_url}?page={page - 1}&page_size={page_size}"
                if search_query:
                    previous_url += f"&search={search_query}"

            # Build response
            response_data = {
                'count': len(instances),
                'next': next_url,
                'previous': previous_url,
                'results': paginated_instances
            }

            serializer = PaginatedFilterOptionsSerializer(response_data)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching instances: {str(e)}")
            error_response = build_error_response(f"Failed to fetch instances: {str(e)}", status_code=500)
            return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request: HttpRequest, pk=None) -> Response:
        """
        GET /api/v1/instances/{id}/

        Returns single instance by ID.

        Returns:
            Response: Single instance in {key, value, cluster_id} format
        """
        from .awx_queries import get_instances
        from .serializers import FilterOptionWithIdSerializer

        try:
            db_connection = get_db_connection('awx')
            instances = get_instances(db_connection)

            # Find instance by ID
            instance = next((i for i in instances if i['id'] == int(pk)), None)

            if not instance:
                error_response = build_error_response(f"Instance with id {pk} not found", status_code=404)
                return Response(error_response, status=status.HTTP_404_NOT_FOUND)

            serializer = FilterOptionWithIdSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching instance {pk}: {str(e)}")
            error_response = build_error_response(f"Failed to fetch instance: {str(e)}", status_code=500)
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
    filter_backends = []  # Disable automatic filtering
    pagination_class = None  # Disable pagination
    filterset_fields = []  # Disable filterset
    search_fields = []  # Disable search
    ordering_fields = []  # Disable ordering

    def get_queryset(self):
        """Return empty queryset - export methods handle data retrieval directly."""
        return DashboardReportCache.objects.none()

    def filter_queryset(self, queryset):
        """Override to prevent any filtering on export endpoints."""
        return queryset

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

            # Accept both 'start'/'end' and 'start_date'/'end_date' parameter names
            start_param = request.query_params.get('start') or request.query_params.get('start_date')
            end_param = request.query_params.get('end') or request.query_params.get('end_date')

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

            # Accept both 'start'/'end' and 'start_date'/'end_date' parameter names
            start_param = (request.data.get('start') or request.query_params.get('start') or
                          request.data.get('start_date') or request.query_params.get('start_date'))
            end_param = (request.data.get('end') or request.query_params.get('end') or
                        request.data.get('end_date') or request.query_params.get('end_date'))

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



# Function-based export views to avoid DRF filter issues

from rest_framework.decorators import api_view, permission_classes as permission_classes_decorator


@api_view(['GET'])
@permission_classes_decorator([DeveloperModeRequired])
def export_csv_view(request):
    """CSV export function-based view to avoid DRF filtering issues."""
    # Delegate to the ViewSet method
    viewset = ExportViewSet()
    viewset.request = request
    return viewset.export_csv(request)


@api_view(['POST'])
@permission_classes_decorator([DeveloperModeRequired])
def export_pdf_view(request):
    """PDF export function-based view to avoid DRF filtering issues."""
    # Delegate to the ViewSet method
    viewset = ExportViewSet()
    viewset.request = request
    return viewset.export_pdf(request)

