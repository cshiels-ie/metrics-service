#!/usr/bin/env python
"""
Populate dashboard cache using ALL test data from the AWX database.
This will aggregate all jobs regardless of date.
"""
import os
import django
from datetime import datetime, timedelta, timezone as dt_timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrics_service.settings')
django.setup()

from django.utils import timezone
from apps.tasks.utils import get_db_connection
from apps.dashboard_reports.models import DashboardReportCache

print("Fetching ALL job data from AWX database...")

db = get_db_connection('awx')
cursor = db.cursor()

# Get ALL job data (no date filter)
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
    GROUP BY jt.id, jt.name
    ORDER BY runs DESC
''')

job_templates = []
total_successful = 0
total_failed = 0
total_hosts = 0
total_elapsed = 0

for row in cursor.fetchall():
    template_id, template_name, runs, successful, failed, elapsed, num_hosts = row
    elapsed = float(elapsed or 0)
    successful = int(successful or 0)
    failed = int(failed or 0)
    num_hosts = int(num_hosts or 0)

    total_successful += successful
    total_failed += failed
    total_hosts += num_hosts
    total_elapsed += elapsed

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

print(f"Found {len(job_templates)} job templates")
print(f"  Total successful jobs: {total_successful}")
print(f"  Total failed jobs: {total_failed}")
print(f"  Total unique hosts: {total_hosts}")
print(f"  Total elapsed time: {total_elapsed / 3600:.2f} hours")

# Create cache with today's date range (so API will find it)
end_date_now = timezone.now()
start_date_now = end_date_now - timedelta(days=30)
start_str = start_date_now.strftime('%Y-%m-%d')
end_str = end_date_now.strftime('%Y-%m-%d')
cache_key = f'job_templates_{start_str}_{end_str}'

cache_data = {
    'count': len(job_templates),
    'timestamp': timezone.now().isoformat(),
    'job_templates': job_templates
}

# Delete existing and create new
DashboardReportCache.objects.filter(cache_key=cache_key).delete()
cache_entry = DashboardReportCache.objects.create(
    cache_key=cache_key,
    report_type=DashboardReportCache.REPORT_TYPE_JOB_TEMPLATES,
    data=cache_data,
    date_range_start=start_date_now,
    date_range_end=end_date_now
)

print(f'\n✓ Created cache entry: {cache_key}')
print(f'  Total templates: {len(job_templates)}')
if job_templates:
    print(f'  Total runs: {sum(t["runs"] for t in job_templates)}')
    print('\nTop 5 templates by runs:')
    for t in job_templates[:5]:
        print(f'  - {t["name"]}: {t["runs"]} runs ({t["successful_runs"]} successful, {t["failed_runs"]} failed), {t["elapsed_str"]}, {t["num_hosts"]} hosts')
