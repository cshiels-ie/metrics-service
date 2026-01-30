"""
Dashboard data collection tasks for automation-reports integration.

This module contains tasks for collecting and caching dashboard metrics
using SQL collectors from metrics-utility.
"""

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.tasks.utils import create_task_result, log_task_execution, task, task_execution_wrapper, get_db_connection

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "awx"


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("collect_dashboard_reports")
def collect_dashboard_reports(**kwargs) -> dict[str, Any]:
    """
    Collect and cache dashboard report data for automation-reports frontend.

    This task:
    1. Calls metrics-utility dashboard collectors (SQL-based)
    2. Stores results in DashboardReportCache
    3. Updates cache via update_or_create (handles retries gracefully)

    The dashboard collectors query the AWX database directly to gather:
    - Job template summary (runs, success/failure, costs, savings)
    - Top projects by job count
    - Top users by execution count

    Args:
        **kwargs: Task data containing:
            - start_date (str): ISO datetime for range start (optional)
            - end_date (str): ISO datetime for range end (optional)
            - database (str): Database name (default: 'awx')

    Returns:
        dict: Task result with collection statistics
    """
    try:
        # Import dashboard collectors from metrics-utility
        try:
            from metrics_utility.library.collectors.dashboard import (
                dashboard_job_templates,
                dashboard_top_projects,
                dashboard_top_users,
            )
        except ImportError as e:
            logger.error(f"Failed to import dashboard collectors: {str(e)}")
            return create_task_result("error", error=f"Dashboard collectors not available: {str(e)}")

        from apps.dashboard_reports.models import DashboardReportCache

        # Parse date range
        end_param = kwargs.get('end_date')
        start_param = kwargs.get('start_date')

        end_date = timezone.datetime.fromisoformat(end_param) if end_param else timezone.now()
        start_date = (
            timezone.datetime.fromisoformat(start_param)
            if start_param
            else end_date - timedelta(days=30)
        )

        # Ensure timezone-aware datetimes
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)

        # Database connection
        db_name = kwargs.get('database', DEFAULT_DB_NAME)
        db_connection = get_db_connection(db_name)

        # Build cache key prefix
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        cache_key_prefix = f"{start_str}_{end_str}"

        log_task_execution(
            "collect_dashboard_reports",
            "processing",
            f"Collecting dashboard data for: {start_str} to {end_str}"
        )

        # Collect job templates
        log_task_execution("collect_dashboard_reports", "processing", "Collecting job templates")
        job_templates_data = dashboard_job_templates(
            db=db_connection,
            since=start_date,
            until=end_date
        )

        DashboardReportCache.objects.update_or_create(
            cache_key=f"job_templates_{cache_key_prefix}",
            defaults={
                'report_type': DashboardReportCache.REPORT_TYPE_JOB_TEMPLATES,
                'data': job_templates_data,
                'date_range_start': start_date,
                'date_range_end': end_date
            }
        )

        # Collect top projects
        log_task_execution("collect_dashboard_reports", "processing", "Collecting top projects")
        top_projects_data = dashboard_top_projects(
            db=db_connection,
            since=start_date,
            until=end_date,
            limit=10
        )

        DashboardReportCache.objects.update_or_create(
            cache_key=f"top_projects_{cache_key_prefix}",
            defaults={
                'report_type': DashboardReportCache.REPORT_TYPE_TOP_PROJECTS,
                'data': top_projects_data,
                'date_range_start': start_date,
                'date_range_end': end_date
            }
        )

        # Collect top users
        log_task_execution("collect_dashboard_reports", "processing", "Collecting top users")
        top_users_data = dashboard_top_users(
            db=db_connection,
            since=start_date,
            until=end_date,
            limit=10
        )

        DashboardReportCache.objects.update_or_create(
            cache_key=f"top_users_{cache_key_prefix}",
            defaults={
                'report_type': DashboardReportCache.REPORT_TYPE_TOP_USERS,
                'data': top_users_data,
                'date_range_start': start_date,
                'date_range_end': end_date
            }
        )

        log_task_execution(
            "collect_dashboard_reports",
            "completed",
            f"Collected 3 report types for {start_str} to {end_str}"
        )

        return create_task_result(
            'success',
            {
                'task_type': 'collect_dashboard_reports',
                'reports_collected': 3,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'job_templates_count': len(job_templates_data.get('job_templates', [])),
                'top_projects_count': len(top_projects_data.get('top_projects', [])),
                'top_users_count': len(top_users_data.get('top_users', []))
            }
        )

    except Exception as e:
        logger.error(f"Error collecting dashboard reports: {str(e)}")
        return create_task_result('error', error=f"Collection failed: {str(e)}")
