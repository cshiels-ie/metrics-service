"""Collector for AWX job event data using keyset pagination."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.tasks.utils import create_task_result, get_db_connection, log_task_execution, parse_datetime_string

# NOTE: requires Unit 1 PR (JobEvent model) to be merged before this import resolves.
# The try/except below handles the missing model gracefully during development.
try:
    from apps.events.models import JobEvent
except ImportError:
    JobEvent = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

COLLECTOR_TYPE = "job_events"
DEFAULT_LOOKBACK_DAYS = 7


def _get_last_watermark() -> tuple[datetime | None, int | None]:
    """
    Return (last_job_created, last_awx_event_id) from the most recent successful collection.

    Reads the ``collection_parameters`` JSON field of the most recent
    ``HourlyMetricsCollection`` record with ``collector_type="job_events"`` and
    ``status="collected"``.  Returns (None, None) when no prior collection exists.
    """
    from apps.tasks.models import HourlyMetricsCollection

    last = (
        HourlyMetricsCollection.objects.filter(collector_type=COLLECTOR_TYPE, status="collected")
        .order_by("-collection_timestamp")
        .first()
    )
    if last is None:
        return None, None

    params = last.collection_parameters or {}
    raw_ts = params.get("last_job_created")
    last_id = params.get("last_awx_event_id")

    if not raw_ts:
        return None, None

    dt = parse_datetime_string(raw_ts)
    if dt is None:
        logger.warning("collect_job_events: could not parse last_job_created=%r; starting from scratch", raw_ts)
        return None, None
    return dt, last_id


def _save_window_record(
    window_start: datetime,
    status: str,
    events_in_window: int,
    last_job_created: datetime | None,
    last_awx_event_id: int | None,
    error_message: str = "",
) -> None:
    """Persist a HourlyMetricsCollection record for the completed time window."""
    from apps.tasks.models import HourlyMetricsCollection

    collection_params: dict[str, Any] = {
        "events_in_window": events_in_window,
    }
    if last_job_created is not None:
        collection_params["last_job_created"] = last_job_created.isoformat()
    if last_awx_event_id is not None:
        collection_params["last_awx_event_id"] = last_awx_event_id

    HourlyMetricsCollection.objects.update_or_create(
        collector_type=COLLECTOR_TYPE,
        collection_timestamp=window_start,
        defaults={
            "raw_data": {},
            "status": status,
            "error_message": error_message,
            "collection_parameters": collection_params,
        },
    )


def collect_job_events(**kwargs: Any) -> dict[str, Any]:
    """Collect AWX job events into metrics-service using keyset pagination.

    Iterates hourly time windows aligned to AWX's ``main_jobevent`` partitions.
    The high-water mark (``last_job_created`` + ``last_awx_event_id``) is read
    from the most recent successful ``HourlyMetricsCollection`` with
    ``collector_type="job_events"``.  If no prior collection exists the function
    defaults to ``DEFAULT_LOOKBACK_DAYS`` days ago.

    For each hourly window the function calls ``JobEventExtractor`` from
    ``metrics_utility`` (Unit 5 PR) and bulk-inserts batches into the local
    ``JobEvent`` table using ``update_conflicts`` so re-runs are idempotent.

    Args:
        **kwargs: Optional task data.  Not currently used but kept for
            consistency with other collector functions.

    Returns:
        dict: Standard task result with ``status``, ``events_collected``, and
            ``windows_processed`` keys.
    """
    if JobEvent is None:
        msg = (
            "collect_job_events: apps.events.models.JobEvent is not importable. "
            "Ensure the Unit 1 PR (JobEvent model) has been merged and migrations applied."
        )
        logger.error(msg)
        return create_task_result("error", error=msg)

    try:
        from metrics_utility.library.collectors.controller.main_jobevent_events import JobEventExtractor
    except ImportError:
        msg = (
            "collect_job_events: metrics_utility.library.collectors.controller.main_jobevent_events "
            "is not importable. Ensure the Unit 5 PR (JobEventExtractor) has been merged and "
            "metrics-utility has been updated."
        )
        logger.error(msg)
        return create_task_result("error", error=msg)

    log_task_execution("collect_job_events", "start")

    now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    last_job_created, last_awx_event_id = _get_last_watermark()

    if last_job_created is not None:
        # Re-open the watermark hour: events written at hh:59 may arrive after hh+1 starts.
        window_start = last_job_created.replace(minute=0, second=0, microsecond=0)
    else:
        window_start = now - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    if window_start >= now:
        log_task_execution("collect_job_events", "skipped", "watermark is already at current hour")
        return create_task_result(
            "success",
            data={"events_collected": 0, "windows_processed": 0, "message": "No new windows to process"},
        )

    db_connection = get_db_connection("awx")

    total_events = 0
    windows_processed = 0
    cursor_job_created = last_job_created
    cursor_event_id = last_awx_event_id

    current_window = window_start
    while current_window < now:
        window_end = current_window + timedelta(hours=1)
        events_in_window = 0

        try:
            extractor = JobEventExtractor(db=db_connection, since=current_window, until=window_end)
            for batch in extractor:
                if not batch:
                    continue
                JobEvent.objects.bulk_create(
                    [JobEvent(**row) for row in batch],
                    update_conflicts=True,
                    update_fields=["failed", "changed", "duration", "collected_at"],
                    unique_fields=["awx_event_id"],
                )
                events_in_window += len(batch)

                for row in batch:
                    row_created = row.get("job_created")
                    row_id = row.get("awx_event_id")
                    if row_created is not None:
                        if cursor_job_created is None or row_created > cursor_job_created:
                            cursor_job_created = row_created
                            cursor_event_id = row_id
                        elif row_created == cursor_job_created and row_id is not None:
                            if cursor_event_id is None or row_id > cursor_event_id:
                                cursor_event_id = row_id

            _save_window_record(
                window_start=current_window,
                status="collected",
                events_in_window=events_in_window,
                last_job_created=cursor_job_created,
                last_awx_event_id=cursor_event_id,
            )
            total_events += events_in_window
            windows_processed += 1

        except Exception as exc:
            logger.exception(
                "collect_job_events: error processing window %s–%s: %s",
                current_window.isoformat(),
                window_end.isoformat(),
                exc,
            )
            _save_window_record(
                window_start=current_window,
                status="failed",
                events_in_window=events_in_window,
                last_job_created=cursor_job_created,
                last_awx_event_id=cursor_event_id,
                error_message=str(exc),
            )
            return create_task_result(
                "error",
                data={"events_collected": total_events, "windows_processed": windows_processed},
                error=f"Collection failed at window {current_window.isoformat()}: {exc}",
            )

        current_window = window_end

    log_task_execution(
        "collect_job_events",
        "completed",
        f"Collected {total_events} events across {windows_processed} windows",
    )
    return create_task_result(
        "success",
        data={"events_collected": total_events, "windows_processed": windows_processed},
    )
