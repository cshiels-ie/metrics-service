"""
Serializers for BI connector events endpoints.

Exposes JobEvent and DailyEventSummary in a flat columnar format suitable for
BI tool consumption (Tableau, Power BI, Grafana).

Depends on Unit 1: apps/events/models.py (JobEvent, DailyEventSummary).
"""

from rest_framework import serializers

# Dependency: apps/events/models.py — created by Unit 1 (JobEvent model PR).
from apps.events.models import DailyEventSummary, JobEvent


class JobEventSerializer(serializers.ModelSerializer):
    """
    Flat serializer for JobEvent records.

    Exposes all event fields needed for BI analysis. The collected_at field is
    excluded — it is an internal housekeeping timestamp, not meaningful for BI consumers.
    """

    class Meta:
        model = JobEvent
        fields = [
            "id",
            "awx_event_id",
            "job_id",
            "job_created",
            "event_type",
            "counter",
            "failed",
            "changed",
            "task_action",
            "task",
            "role",
            "host_name",
            "duration",
            "awx_created",
        ]


class DailyEventSummarySerializer(serializers.ModelSerializer):
    """
    Flat serializer for DailyEventSummary records.

    Exposes all pre-aggregated daily rollup fields. JSON fields (top_task_actions,
    duration_stats) are returned as-is — BI tools that cannot traverse nested JSON
    should use the JobEvent endpoint directly.
    """

    class Meta:
        model = DailyEventSummary
        fields = [
            "id",
            "summary_date",
            "total_events",
            "failed_events",
            "changed_events",
            "unique_hosts",
            "top_task_actions",
            "duration_stats",
            "jobs_covered",
            "created_at",
        ]
