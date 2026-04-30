"""Cleanup of old JobEvent raw rows past the retention window."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings

from ..utils import create_task_result, log_task_execution

logger = logging.getLogger(__name__)

EVENTS_RAW_RETENTION_DAYS_DEFAULT = 30
_BATCH_SIZE = 10_000


def cleanup_job_events(**kwargs: Any) -> dict[str, Any]:
    """
    Delete JobEvent rows older than the configured retention window.

    Reads EVENTS_RAW_RETENTION_DAYS from Dynaconf settings (default: 30 days).
    Rows are deleted in batches of 10,000 to avoid lock contention on large tables.

    Args:
        **kwargs: Unused; accepted for compatibility with the task dispatcher interface.

    Returns:
        A dict with keys:
            - status (str): "success" or "error"
            - deleted_count (int): Total number of rows deleted
            - cutoff_date (str): ISO-format cutoff datetime used for deletion
    """
    # NOTE: requires Unit 1 — apps/events/models.py with JobEvent model
    from apps.events.models import JobEvent

    retention_days = int(
        getattr(settings, "EVENTS_RAW_RETENTION_DAYS", EVENTS_RAW_RETENTION_DAYS_DEFAULT)
    )
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)

    log_task_execution(
        "cleanup_job_events",
        "processing",
        f"Deleting JobEvent rows older than {cutoff.isoformat()} (retention={retention_days} days)",
    )

    total_deleted = 0
    try:
        while True:
            # Fetch a batch of PKs to delete — avoids long-held locks from a single large DELETE
            batch_ids = list(
                JobEvent.objects.filter(collected_at__lt=cutoff)
                .values_list("id", flat=True)[:_BATCH_SIZE]
            )
            if not batch_ids:
                break
            deleted, _ = JobEvent.objects.filter(id__in=batch_ids).delete()
            total_deleted += deleted
            logger.debug("cleanup_job_events: deleted batch of %d rows (total so far: %d)", deleted, total_deleted)

    except Exception as exc:
        error_msg = f"Cleanup failed after deleting {total_deleted} rows: {exc}"
        logger.exception("cleanup_job_events: %s", error_msg)
        return create_task_result("error", {"deleted_count": total_deleted, "cutoff_date": cutoff.isoformat()}, error=error_msg)

    log_task_execution("cleanup_job_events", "completed", f"Deleted {total_deleted} rows")
    return create_task_result(
        "success",
        {
            "deleted_count": total_deleted,
            "cutoff_date": cutoff.isoformat(),
        },
    )
