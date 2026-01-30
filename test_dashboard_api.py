#!/usr/bin/env python
"""Test script to verify dashboard API setup."""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrics_service.settings')
django.setup()

from apps.tasks.models import DashboardReportCache
from django.db import connection

print("=" * 60)
print("Dashboard API Setup Verification")
print("=" * 60)

# Check if table exists
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE tablename='dashboard_report_cache'
    """)
    result = cursor.fetchone()
    if result:
        print("✓ DashboardReportCache table exists")

        # Check table structure
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name='dashboard_report_cache'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print(f"\n  Columns ({len(columns)}):")
        for col_name, col_type in columns:
            print(f"    - {col_name}: {col_type}")
    else:
        print("✗ DashboardReportCache table does NOT exist")

# Check if model works
try:
    count = DashboardReportCache.objects.count()
    print(f"\n✓ DashboardReportCache model works (current count: {count})")
except Exception as e:
    print(f"\n✗ DashboardReportCache model error: {e}")

# Check URL configuration
print("\n" + "=" * 60)
print("URL Configuration Check")
print("=" * 60)

from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

def print_urls(urlpatterns, prefix=''):
    """Recursively print all URL patterns."""
    for pattern in urlpatterns:
        if isinstance(pattern, URLResolver):
            print_urls(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            full_pattern = prefix + str(pattern.pattern)
            if 'report' in full_pattern and 'api/v1' in full_pattern:
                print(f"✓ Found: {full_pattern}")

resolver = get_resolver()
print("\nSearching for /api/v1/report/ endpoints...")
print_urls(resolver.url_patterns)

print("\n" + "=" * 60)
print("Task Configuration Check")
print("=" * 60)

from apps.tasks.tasks import TASK_FUNCTIONS, TASK_METADATA

if 'collect_dashboard_reports' in TASK_FUNCTIONS:
    print("✓ collect_dashboard_reports is registered in TASK_FUNCTIONS")
else:
    print("✗ collect_dashboard_reports is NOT in TASK_FUNCTIONS")

if 'collect_dashboard_reports' in TASK_METADATA:
    print("✓ collect_dashboard_reports has metadata")
    metadata = TASK_METADATA['collect_dashboard_reports']
    print(f"  Category: {metadata.get('category')}")
    print(f"  Description: {metadata.get('description')[:50]}...")
else:
    print("✗ collect_dashboard_reports has NO metadata")

print("\n" + "=" * 60)
print("Task Group Check")
print("=" * 60)

from apps.tasks.task_groups import TASK_GROUPS, DASHBOARD_COLLECTION_GROUP

dashboard_group = None
for group in TASK_GROUPS:
    if group.name == 'dashboard_collection':
        dashboard_group = group
        break

if dashboard_group:
    print(f"✓ DASHBOARD_COLLECTION_GROUP exists")
    print(f"  Enabled setting: {dashboard_group.enabled_setting}")
    print(f"  Default enabled: {dashboard_group.default_enabled}")
    print(f"  Is enabled: {dashboard_group.is_enabled()}")
    print(f"  Tasks: {len(dashboard_group.tasks)}")
    for task in dashboard_group.tasks:
        print(f"    - {task['task_id']}: {task['function']} ({task['cron']})")
else:
    print("✗ DASHBOARD_COLLECTION_GROUP not found")

print("\n" + "=" * 60)
print("Setup Complete!")
print("=" * 60)
print("\nNext steps:")
print("1. Start server: .venv/bin/python manage.py runserver")
print("2. Test endpoint: curl http://localhost:8000/api/v1/report/")
print("3. Or test with data: First run collect_dashboard_reports task")
