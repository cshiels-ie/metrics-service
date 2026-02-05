#!/usr/bin/env python
"""
Script to populate dashboard cache with calculated metrics from AWX data.
"""
import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrics_service.settings')
django.setup()

from django.utils import timezone
from apps.tasks.utils import get_db_connection
from apps.dashboard_reports.models import DashboardReportCache
import json


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m"


def calculate_dashboard_metrics(start_date, end_date):
    """Calculate dashboard metrics from AWX database."""
    db = get_db_connection('awx')
    cursor = db.cursor()

    # Query jobs with template information
    cursor.execute('''
        SELECT
            jt.id as template_id,
            jt.name as template_name,
            COUNT(uj.id) as total_runs,
            SUM(CASE WHEN uj.status = 'successful' THEN 1 ELSE 0 END) as successful_runs,
            SUM(CASE WHEN uj.status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
            SUM(uj.elapsed) as total_elapsed,
            COUNT(DISTINCT jhs.host_id) as num_hosts
        FROM main_job mj
        JOIN main_unifiedjob uj ON mj.unifiedjob_ptr_id = uj.id
        JOIN main_unifiedjobtemplate jt ON mj.job_template_id = jt.id
        LEFT JOIN main_jobhostsummary jhs ON jhs.job_id = uj.id
        WHERE uj.finished BETWEEN %s AND %s
        GROUP BY jt.id, jt.name
        ORDER BY total_runs DESC
    ''', [start_date, end_date])

    job_templates = []
    for row in cursor.fetchall():
        template_id, template_name, total_runs, successful, failed, elapsed, num_hosts = row

        # Calculate costs (using default settings)
        automated_cost_per_minute = 0.50
        manual_cost_per_hour = 50.00

        # Time taken to execute manually (estimate: 5 minutes per run)
        time_manual_minutes = total_runs * 5

        # Time to create automation (estimate: 2 hours)
        time_create_minutes = 120

        # Calculate costs
        automated_costs = (elapsed / 60) * automated_cost_per_minute if elapsed else 0
        manual_costs = (time_manual_minutes / 60) * manual_cost_per_hour
        savings = manual_costs - automated_costs - (time_create_minutes / 60 * manual_cost_per_hour)

        job_templates.append({
            'name': template_name,
            'runs': total_runs,
            'elapsed': int(elapsed) if elapsed else 0,
            'cluster': 1,
            'elapsed_str': format_duration(elapsed) if elapsed else '0s',
            'num_hosts': num_hosts or 0,
            'time_taken_manually_execute_minutes': time_manual_minutes,
            'time_taken_create_automation_minutes': time_create_minutes,
            'successful_runs': successful or 0,
            'failed_runs': failed or 0,
            'automated_costs': round(automated_costs, 2),
            'manual_costs': round(manual_costs, 2),
            'savings': round(savings, 2),
        })

    cursor.close()
    return job_templates


def populate_cache():
    """Populate the dashboard cache."""
    print("Populating dashboard cache...")

    # Calculate for last year (to capture test data)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=365)

    print(f"Date range: {start_date.date()} to {end_date.date()}")

    # Get metrics
    job_templates = calculate_dashboard_metrics(start_date, end_date)

    print(f"Found {len(job_templates)} job templates with data")

    if len(job_templates) == 0:
        print("⚠️  No job data found in the specified date range.")
        print("   Tip: Check if there are jobs with 'finished' dates in the AWX database")
        return None

    # Build cache key
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    cache_key = f"job_templates_{start_str}_{end_str}"

    # Create cache entry
    cache_data = {
        'count': len(job_templates),
        'timestamp': timezone.now().isoformat(),
        'job_templates': job_templates
    }

    # Delete existing cache and create new
    DashboardReportCache.objects.filter(cache_key=cache_key).delete()

    cache_entry = DashboardReportCache.objects.create(
        cache_key=cache_key,
        report_type=DashboardReportCache.REPORT_TYPE_JOB_TEMPLATES,
        data=cache_data,
        date_range_start=start_date,
        date_range_end=end_date
    )

    print(f"✓ Created cache entry: {cache_key}")
    print(f"  Total templates: {len(job_templates)}")
    print(f"  Total runs: {sum(t['runs'] for t in job_templates)}")
    print(f"\nSample data:")
    for template in job_templates[:3]:
        print(f"  - {template['name']}: {template['runs']} runs, {template['elapsed_str']}")

    return cache_entry


def populate_default_30day_cache():
    """Populate cache for the default 30-day range that the API uses."""
    print("\nPopulating default 30-day cache (for API compatibility)...")

    # Use the same date range logic as the API
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)

    print(f"Date range: {start_date.date()} to {end_date.date()}")

    # Get metrics
    job_templates = calculate_dashboard_metrics(start_date, end_date)

    print(f"Found {len(job_templates)} job templates with data")

    # Build cache key (matches API format)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    cache_key = f"job_templates_{start_str}_{end_str}"

    # Create cache entry
    cache_data = {
        'count': len(job_templates),
        'timestamp': timezone.now().isoformat(),
        'job_templates': job_templates
    }

    # Delete existing cache and create new
    DashboardReportCache.objects.filter(cache_key=cache_key).delete()

    cache_entry = DashboardReportCache.objects.create(
        cache_key=cache_key,
        report_type=DashboardReportCache.REPORT_TYPE_JOB_TEMPLATES,
        data=cache_data,
        date_range_start=start_date,
        date_range_end=end_date
    )

    print(f"✓ Created 30-day cache entry: {cache_key}")
    print(f"  Total templates: {len(job_templates)}")
    if len(job_templates) > 0:
        print(f"  Total runs: {sum(t['runs'] for t in job_templates)}")
        print(f"\nSample data:")
        for template in job_templates[:3]:
            print(f"  - {template['name']}: {template['runs']} runs, {template['elapsed_str']}")

    return cache_entry


if __name__ == '__main__':
    # Populate both year-long and 30-day caches
    populate_cache()
    populate_default_30day_cache()
