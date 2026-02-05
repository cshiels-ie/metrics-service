#!/usr/bin/env python
"""
Populate complete dashboard cache including job templates, top projects, top users, and charts.
"""
import os
import django
from datetime import datetime, timedelta, timezone as dt_timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrics_service.settings')
django.setup()

from django.utils import timezone
from apps.tasks.utils import get_db_connection
from apps.dashboard_reports.models import DashboardReportCache

print("Populating complete dashboard cache...")

# Use current date range for API compatibility
end_date_now = timezone.now()
start_date_now = end_date_now - timedelta(days=30)
start_str = start_date_now.strftime('%Y-%m-%d')
end_str = end_date_now.strftime('%Y-%m-%d')

db = get_db_connection('awx')
cursor = db.cursor()

# ============================================================================
# 1. TOP PROJECTS
# ============================================================================
print("\nFetching top projects...")

cursor.execute('''
    SELECT jt.id, jt.name, COUNT(uj.id) as job_count
    FROM main_job mj
    JOIN main_unifiedjob uj ON mj.unifiedjob_ptr_id = uj.id
    JOIN main_unifiedjobtemplate jt ON mj.job_template_id = jt.id
    WHERE uj.status IN ('successful', 'failed', 'pending', 'running')
    GROUP BY jt.id, jt.name
    ORDER BY job_count DESC
    LIMIT 5
''')

top_projects = []
for row in cursor.fetchall():
    project_id, project_name, job_count = row
    top_projects.append({
        'project_id': project_id,
        'project_name': project_name,
        'count': str(job_count)  # Frontend expects count as string
    })

print(f"Found {len(top_projects)} top projects")

# Create top projects cache
projects_cache_key = f"top_projects_{start_str}_{end_str}"
projects_cache_data = {
    'count': len(top_projects),
    'timestamp': timezone.now().isoformat(),
    'top_projects': top_projects
}

DashboardReportCache.objects.filter(cache_key=projects_cache_key).delete()
DashboardReportCache.objects.create(
    cache_key=projects_cache_key,
    report_type=DashboardReportCache.REPORT_TYPE_TOP_PROJECTS,
    data=projects_cache_data,
    date_range_start=start_date_now,
    date_range_end=end_date_now
)
print(f"✓ Created cache entry: {projects_cache_key}")

# ============================================================================
# 2. TOP USERS
# ============================================================================
print("\nFetching top users...")

cursor.execute('''
    SELECT COALESCE(u.id, 0) as user_id,
           COALESCE(u.username, 'System') as username,
           COUNT(uj.id) as job_count
    FROM main_unifiedjob uj
    LEFT JOIN auth_user u ON uj.created_by_id = u.id
    WHERE uj.status IN ('successful', 'failed', 'pending', 'running')
    GROUP BY u.id, u.username
    ORDER BY job_count DESC
    LIMIT 5
''')

top_users = []
for row in cursor.fetchall():
    user_id, username, job_count = row
    top_users.append({
        'user_id': user_id,
        'user_name': username,  # Frontend expects user_name
        'count': str(job_count)  # Frontend expects count as string
    })

print(f"Found {len(top_users)} top users")

# Create top users cache
users_cache_key = f"top_users_{start_str}_{end_str}"
users_cache_data = {
    'count': len(top_users),
    'timestamp': timezone.now().isoformat(),
    'top_users': top_users
}

DashboardReportCache.objects.filter(cache_key=users_cache_key).delete()
DashboardReportCache.objects.create(
    cache_key=users_cache_key,
    report_type=DashboardReportCache.REPORT_TYPE_TOP_USERS,
    data=users_cache_data,
    date_range_start=start_date_now,
    date_range_end=end_date_now
)
print(f"✓ Created cache entry: {users_cache_key}")

# ============================================================================
# 3. CHART DATA (Jobs and Hosts by Date)
# ============================================================================
print("\nFetching chart data...")

cursor.execute('''
    SELECT DATE(uj.finished) as date,
           COUNT(uj.id) as job_count,
           COUNT(DISTINCT jhs.host_id) as host_count
    FROM main_unifiedjob uj
    LEFT JOIN main_jobhostsummary jhs ON jhs.job_id = uj.id
    WHERE uj.status IN ('successful', 'failed', 'pending', 'running')
      AND uj.finished IS NOT NULL
    GROUP BY DATE(uj.finished)
    ORDER BY date
''')

job_chart_items = []
host_chart_items = []
max_job_count = 0
max_host_count = 0
min_date = None
max_date = None

for row in cursor.fetchall():
    date, job_count, host_count = row

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

print(f"Found {len(job_chart_items)} data points for charts")

# Update the existing job_templates cache to include chart data
job_templates_cache_key = f"job_templates_{start_str}_{end_str}"
cache_entry = DashboardReportCache.objects.filter(cache_key=job_templates_cache_key).first()

if cache_entry:
    # Add chart data to existing cache
    cache_entry.data['job_chart'] = {
        'items': job_chart_items,
        'range': {
            'start': min_date.isoformat() if min_date else None,
            'end': max_date.isoformat() if max_date else None,
            'max_value': max_job_count
        }
    }
    cache_entry.data['host_chart'] = {
        'items': host_chart_items,
        'range': {
            'start': min_date.isoformat() if min_date else None,
            'end': max_date.isoformat() if max_date else None,
            'max_value': max_host_count
        }
    }
    cache_entry.save()
    print(f"✓ Updated cache entry with chart data: {job_templates_cache_key}")
else:
    print(f"⚠️  Warning: job_templates cache not found. Run populate_cache_all_data.py first.")

cursor.close()

print("\n" + "="*60)
print("Dashboard cache population complete!")
print("="*60)
print(f"\nCache entries created for date range: {start_str} to {end_str}")
print(f"  - Top projects: {len(top_projects)} entries")
print(f"  - Top users: {len(top_users)} entries")
print(f"  - Chart data: {len(job_chart_items)} data points")
print("\nSummary:")
for project in top_projects[:3]:
    print(f"  - Project: {project['project_name']} ({project['count']} jobs)")
for user in top_users[:3]:
    print(f"  - User: {user['user_name']} ({user['count']} jobs)")
