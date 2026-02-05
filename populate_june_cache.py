#!/usr/bin/env python
"""
Populate dashboard cache using June 2025 data (when test data exists).
This will create a cache entry with the current API date range but use June 2025 data.
"""
import os
import django
from datetime import datetime, timedelta, timezone as dt_timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrics_service.settings')
django.setup()

from django.utils import timezone
from apps.tasks.utils import get_db_connection
from apps.dashboard_reports.models import DashboardReportCache

# Use June 2025 date range (when test data exists)
start_date = datetime(2025, 6, 1, tzinfo=dt_timezone.utc)
end_date = datetime(2025, 7, 1, tzinfo=dt_timezone.utc)

print(f"Fetching job data from June 2025 ({start_date.date()} to {end_date.date()})...")

db = get_db_connection('awx')
cursor = db.cursor()

# Get job data from June 2025
cursor.execute('''
    SELECT
        jt.id, jt.name,
        COUNT(uj.id) as runs,
        SUM(CASE WHEN uj.status = 'successful' THEN 1 ELSE 0 END) as successful,
        SUM(CASE WHEN uj.status = 'failed' THEN 1 ELSE 0 END) as failed,
        SUM(uj.elapsed) as elapsed
    FROM main_job mj
    JOIN main_unifiedjob uj ON mj.unifiedjob_ptr_id = uj.id
    JOIN main_unifiedjobtemplate jt ON mj.job_template_id = jt.id
    WHERE uj.finished BETWEEN %s AND %s
    GROUP BY jt.id, jt.name
''', [start_date, end_date])

job_templates = []
for row in cursor.fetchall():
    template_id, template_name, runs, successful, failed, elapsed = row
    elapsed = elapsed or 0

    # Format duration
    if elapsed < 60:
        elapsed_str = f'{int(elapsed)}s'
    elif elapsed < 3600:
        elapsed_str = f'{int(elapsed/60)}m {int(elapsed%60)}s'
    else:
        elapsed_str = f'{int(elapsed/3600)}h {int((elapsed%3600)/60)}m'

    job_templates.append({
        'name': template_name,
        'runs': runs,
        'elapsed': int(elapsed),
        'cluster': 1,
        'elapsed_str': elapsed_str,
        'num_hosts': 0,
        'time_taken_manually_execute_minutes': runs * 5,
        'time_taken_create_automation_minutes': 120,
        'successful_runs': successful or 0,
        'failed_runs': failed or 0,
        'automated_costs': round((elapsed / 60) * 0.50, 2),
        'manual_costs': round((runs * 5 / 60) * 50.00, 2),
        'savings': round(((runs * 5 / 60) * 50.00) - ((elapsed / 60) * 0.50) - ((120 / 60) * 50.00), 2),
    })

cursor.close()

print(f"Found {len(job_templates)} job templates with data")

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
print(f'  (Using June 2025 data for API compatibility)')
print(f'  Total templates: {len(job_templates)}')
if job_templates:
    print(f'  Total runs: {sum(t["runs"] for t in job_templates)}')
    print('\nSample data:')
    for t in job_templates[:5]:
        print(f'  - {t["name"]}: {t["runs"]} runs, {t["elapsed_str"]} duration, ${t["savings"]} savings')
