"""
Models for the events app.

Stores AWX job event records collected from the AWX database, along with
pre-aggregated daily summaries used for reporting and trend analysis.
"""

from django.db import models


class JobEvent(models.Model):
    """
    Stores individual AWX job event records collected from the AWX main_jobevent table.

    Each row corresponds to a single Ansible task execution event emitted during an AWX job run.
    The awx_event_id is unique and used to deduplicate records on re-collection. The job_created
    field mirrors the AWX partition key to support efficient time-range queries.
    """

    awx_event_id = models.BigIntegerField(unique=True)
    job_id = models.IntegerField(db_index=True)
    job_created = models.DateTimeField(db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    counter = models.PositiveIntegerField(default=0)
    failed = models.BooleanField(default=False, db_index=True)
    changed = models.BooleanField(default=False)
    task_action = models.CharField(max_length=1024, blank=True, default="")
    task = models.CharField(max_length=1024, blank=True, default="")
    role = models.CharField(max_length=1024, blank=True, default="")
    host_name = models.CharField(max_length=1024, blank=True, default="", db_index=True)
    duration = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    awx_created = models.DateTimeField(null=True, blank=True, db_index=True)
    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Database and index configuration for JobEvent."""

        db_table = "events_jobevent"
        indexes = [
            models.Index(fields=["job_id", "job_created"]),
            models.Index(fields=["task_action", "awx_created"]),
            models.Index(fields=["failed", "awx_created"]),
            models.Index(fields=["host_name", "awx_created"]),
        ]


class DailyEventSummary(models.Model):
    """
    Pre-aggregated daily rollup of JobEvent data.

    One row per calendar day. Populated by a scheduled rollup task that aggregates
    JobEvent records for the previous day. Stores top task actions, duration statistics,
    and host/failure counts to support fast reporting without scanning the raw events table.
    """

    summary_date = models.DateField(unique=True)
    total_events = models.BigIntegerField(default=0)
    failed_events = models.BigIntegerField(default=0)
    changed_events = models.BigIntegerField(default=0)
    unique_hosts = models.IntegerField(default=0)
    top_task_actions = models.JSONField(default=dict)
    duration_stats = models.JSONField(default=dict)
    jobs_covered = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Database configuration for DailyEventSummary."""

        db_table = "events_dailyeventsummary"
