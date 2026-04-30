"""Daily aggregation of job event flat rows into DailyEventSummary."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.db import connection
from django.db.models import Count, Q

# NOTE: requires Unit 1 — apps/events/models.py with JobEvent and DailyEventSummary
from apps.events.models import DailyEventSummary, JobEvent

logger = logging.getLogger(__name__)


class EventDailyRollup:
    """Aggregates JobEvent rows for a given date into DailyEventSummary."""

    def compute(self, summary_date: date) -> DailyEventSummary:
        """
        Compute and upsert the daily summary for summary_date.

        Queries JobEvent rows whose awx_created date matches summary_date, computes
        aggregate counts, top task actions, and duration percentiles, then writes the
        result into DailyEventSummary via update_or_create.

        Args:
            summary_date: The calendar date to aggregate.

        Returns:
            The upserted DailyEventSummary instance.
        """
        qs = JobEvent.objects.filter(awx_created__date=summary_date)

        agg = qs.aggregate(
            total_events=Count("id"),
            failed_events=Count("id", filter=Q(failed=True)),
            changed_events=Count("id", filter=Q(changed=True)),
            unique_hosts=Count("host_name", distinct=True),
            jobs_covered=Count("job_id", distinct=True),
        )

        # Top 50 task actions by event count
        top_actions_qs = (
            qs.values("task_action")
            .annotate(count=Count("id"))
            .order_by("-count")[:50]
        )
        top_task_actions: dict[str, int] = {
            row["task_action"]: row["count"]
            for row in top_actions_qs
            if row["task_action"] is not None
        }

        # Duration percentiles via raw SQL (PERCENTILE_CONT is not available in Django ORM)
        duration_stats = self._compute_duration_stats(summary_date)

        summary, _ = DailyEventSummary.objects.update_or_create(
            summary_date=summary_date,
            defaults={
                "total_events": agg["total_events"] or 0,
                "failed_events": agg["failed_events"] or 0,
                "changed_events": agg["changed_events"] or 0,
                "unique_hosts": agg["unique_hosts"] or 0,
                "jobs_covered": agg["jobs_covered"] or 0,
                "top_task_actions": top_task_actions,
                "duration_stats": duration_stats,
            },
        )

        logger.info(
            "EventDailyRollup: upserted DailyEventSummary for %s "
            "(total=%d, failed=%d, unique_hosts=%d)",
            summary_date,
            summary.total_events,
            summary.failed_events,
            summary.unique_hosts,
        )
        return summary

    def _compute_duration_stats(self, summary_date: date) -> dict[str, Any]:
        """
        Compute duration statistics for job events on summary_date using raw SQL.

        Uses PostgreSQL PERCENTILE_CONT aggregate which is unavailable in the Django ORM.

        Args:
            summary_date: The calendar date to compute statistics for.

        Returns:
            A dict with keys avg, p50, p95, p99, max — all in seconds as floats, or an
            empty dict when no rows with a non-null duration exist for the date.
        """
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    AVG(duration),
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration),
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration),
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration),
                    MAX(duration)
                FROM events_jobevent
                WHERE duration IS NOT NULL
                  AND DATE(awx_created) = %s
                """,
                [summary_date],
            )
            row = cur.fetchone()

        if row is None or row[0] is None:
            return {}

        avg, p50, p95, p99, max_val = row
        return {
            "avg": float(avg) if avg is not None else None,
            "p50": float(p50) if p50 is not None else None,
            "p95": float(p95) if p95 is not None else None,
            "p99": float(p99) if p99 is not None else None,
            "max": float(max_val) if max_val is not None else None,
        }
