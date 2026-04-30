"""
Admin configuration for events app.
"""

from django.contrib import admin

from .models import DailyEventSummary, JobEvent


@admin.register(JobEvent)
class JobEventAdmin(admin.ModelAdmin):
    """Admin interface for JobEvent model."""

    list_display = ["awx_event_id", "job_id", "event_type", "failed", "changed", "host_name", "collected_at"]
    list_filter = ["event_type", "failed", "changed"]
    search_fields = ["host_name", "task_action", "task", "role"]
    readonly_fields = ["collected_at"]


@admin.register(DailyEventSummary)
class DailyEventSummaryAdmin(admin.ModelAdmin):
    """Admin interface for DailyEventSummary model."""

    list_display = ["summary_date", "total_events", "failed_events", "changed_events", "unique_hosts", "jobs_covered"]
    search_fields = ["summary_date"]
    readonly_fields = ["created_at"]
