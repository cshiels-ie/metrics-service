"""
Background tasks for dashboard reports data collection and cleanup.

Provides five dispatcherd tasks:
- collect_dashboard_reports_initial_data: full historical backfill (default 90 days)
- collect_dashboard_reports_data: incremental sync from last known timestamp (deprecated)
- sync_dashboard_job_records: writes unified_jobs data from the hourly hook to JobData
- sync_dashboard_host_summaries: writes host summary data from the hourly hook to JobHostSummary
- cleanup_dashboard_reports_old_data: removes JobData records beyond retention period
"""

import logging
import math
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from metrics_utility.library.collectors.dashboard import (
    DashboardJobsResultType,
    dashboard_jobs,
)

from apps.dashboard_reports.models import DashboardTelemetry, JobData, JobHostSummary
from apps.tasks.utils import create_task_result, get_db_connection, log_task_execution

DEFAULT_DB_NAME = "awx"

logger = logging.getLogger(__name__)


class _PartialSyncRollbackError(Exception):
    """Sentinel raised inside a transaction.atomic() block to roll back all saves when any job fails to sync."""


def _parse_dt(value: Any) -> datetime | None:
    """Coerce value to a timezone-aware datetime.

    - None      → None
    - str       → parsed via fromisoformat; naive result is assumed UTC
    - datetime  → returned unchanged if tz-aware; naive datetime is localised to UTC
    - other     → raises TypeError so callers receive a structured error
    """
    if value is None:
        return None
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    raise TypeError(f"_parse_dt: expected str, datetime, or None; got {type(value).__name__!r}")


def _collect_jobs(
    db_connection, since: datetime, until: datetime, after_id: int | None = None, batch_size: int | None = None
) -> DashboardJobsResultType:
    """
    Collect dashboard jobs data from the database for the specified date range.

    When *after_id* and *batch_size* are both supplied the underlying query uses
    cursor-based pagination (``id > after_id ORDER BY id LIMIT batch_size``) and
    labels/host-summaries are fetched by the returned job IDs rather than the
    full date range, which is far more efficient for large backfills.
    """
    return dashboard_jobs(
        db=db_connection, since=since, until=until, after_id=after_id, batch_size=batch_size, date_field="finished"
    ).gather()


def _get_job_id_range(db_connection, since: datetime, until: datetime) -> tuple:
    """Return (min_id, max_id) for jobs matching the backfill filter, or (None, None) if empty."""
    # Lazy import: keeps metrics_utility optional at module level so unrelated tasks
    # (hello_world, cleanup_old_tasks) can be registered without the dependency installed.
    from metrics_utility.library.collectors.dashboard import get_min_max_job_id_query

    query, params = get_min_max_job_id_query(since, until, date_field="finished")
    with db_connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def _sync_jobs_atomically(job_results: list) -> list:
    """
    Persist all jobs in a single atomic transaction.

    Returns the list of job IDs that failed to sync.  If any job fails every
    save made in this call is rolled back, keeping JobData.last_timestamp()
    unchanged so the next incremental run retries from the same watermark.


    Note: retry behaviour for the outer Task is handled by the Task model's max_attempts
    mechanism (default: 3 attempts). When this function signals failure the calling task
    returns create_task_result("error"), which marks the Task as failed and allows the
    scheduler to retry it automatically up to max_attempts times via Task.can_retry().
    """
    failed_jobs: list = []
    try:
        with transaction.atomic():
            for job in job_results:
                try:
                    JobData.create_or_update_from_awx(job)
                except Exception as e:
                    logger.error(f"Error creating/updating JobData for job {job['id']}: {str(e)}")
                    failed_jobs.append(job["id"])
            if failed_jobs:
                raise _PartialSyncRollbackError()
    except _PartialSyncRollbackError:
        pass  # transaction rolled back; caller inspects failed_jobs
    return failed_jobs


def _resolve_collection_params(kwargs: dict) -> tuple[str, datetime, datetime, int]:
    """Resolve db_name, since, until, and batch_size from task kwargs with defaults applied."""
    dashboard_cfg = getattr(settings, "DASHBOARD_COLLECTION", None) or {}
    db_name = kwargs.get("database", DEFAULT_DB_NAME)
    until = _parse_dt(kwargs.get("until")) or datetime.now(tz=UTC)
    since = _parse_dt(kwargs.get("since")) or JobData.last_timestamp()
    if since is None:
        raw_backfill_days = dashboard_cfg.get("INITIAL_BACKFILL_DAYS", 90)
        try:
            backfill_days = int(raw_backfill_days)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"DASHBOARD_COLLECTION.INITIAL_BACKFILL_DAYS must be a positive integer, got {raw_backfill_days!r}"
            ) from e
        if backfill_days <= 0:
            raise ValueError("DASHBOARD_COLLECTION.INITIAL_BACKFILL_DAYS must be > 0")
        since = (
            (until - timedelta(days=backfill_days)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        )
    raw_batch_size = dashboard_cfg.get("BACKFILL_BATCH_SIZE", 5_000)
    try:
        batch_size = int(raw_batch_size)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"DASHBOARD_COLLECTION.BACKFILL_BATCH_SIZE must be a positive integer, got {raw_batch_size!r}"
        ) from e
    if batch_size <= 0:
        raise ValueError("DASHBOARD_COLLECTION.BACKFILL_BATCH_SIZE must be > 0")
    return db_name, since, until, batch_size


def _process_batches(
    db_connection, since: datetime, until: datetime, max_id: int, after_id: int, batch_size: int, task_name: str
) -> tuple[int, str | None]:
    """Collect and sync jobs in cursor-paginated batches. Returns (total_synced, error_message_or_None)."""
    total_synced = 0
    while after_id < max_id:
        try:
            batch = _collect_jobs(db_connection, since=since, until=until, after_id=after_id, batch_size=batch_size)
        except Exception as e:
            logger.exception(f"Error collecting jobs batch after id {after_id}")
            return total_synced, f"Collecting jobs failed: {str(e)}"

        if not batch["results"]:
            break

        failed_jobs = _sync_jobs_atomically(batch["results"])
        if failed_jobs:
            return total_synced, f"Failed to sync {len(failed_jobs)} job(s): {failed_jobs}"

        batch_count = batch["count"]
        total_synced += batch_count
        after_id = max(j["id"] for j in batch["results"])
        log_task_execution(
            task_name=task_name,
            operation="processing",
            details=f"Synced batch of {batch_count} jobs (total so far: {total_synced}, cursor id: {after_id})",
        )
    return total_synced, None


def _collect_data(task_name: str, **kwargs) -> dict[str, Any]:
    """
    Core data collection logic for dashboard reports.

    Fetches jobs in cursor-paginated batches (default 10 000 records each) to
    keep memory usage and DB transaction times bounded regardless of window size.
    Each batch is committed independently so progress is preserved if the task
    is interrupted and retried.
    """
    result = {
        "error": False,
        "message": "",
        "data": {"task_type": task_name, "date_range": {"start": None, "end": None}, "job_count": 0},
    }
    try:
        db_name, since, until, batch_size = _resolve_collection_params(kwargs)
    except ValueError as e:
        result["error"] = True
        result["message"] = str(e)
        return result

    if since >= until:
        msg = f"Invalid date range: since ({since.isoformat()}) must be before until ({until.isoformat()})"
        logger.error(msg)
        result["error"] = True
        result["message"] = msg
        return result

    start_str = since.isoformat()
    end_str = until.isoformat()

    log_task_execution(
        task_name=task_name, operation="processing", details=f"Collecting dashboard data for: {start_str} to {end_str}"
    )

    try:
        db_connection = get_db_connection(db_name)
        min_id, max_id = _get_job_id_range(db_connection, since, until)
    except Exception as e:
        logger.exception("Database error during collection setup")
        result["error"] = True
        result["message"] = f"Database error: {str(e)}"
        return result

    if min_id is None:
        log_task_execution(task_name=task_name, operation="completed", details="No jobs found in date range")
        result["data"] = {"task_type": task_name, "date_range": {"start": start_str, "end": end_str}, "job_count": 0}
        return result

    after_id = min_id - 1
    total_synced, error_msg = _process_batches(db_connection, since, until, max_id, after_id, batch_size, task_name)

    if error_msg:
        result["error"] = True
        result["message"] = error_msg
        return result

    log_task_execution(
        task_name=task_name,
        operation="completed",
        details=f"Collected and stored {total_synced} jobs from {start_str} to {end_str}",
    )
    result["data"] = {
        "task_type": task_name,
        "date_range": {"start": start_str, "end": end_str},
        "job_count": total_synced,
    }
    return result


def _save_telemetry_details(
    task_name: str,
    success: bool,
    collection_duration_ms: float,
    number_of_records_processed: int,
    database_query_time_ms: float | None,
    cache_hit_rate: float | None,
) -> None:
    try:
        DashboardTelemetry.objects.create(
            task_name=task_name,
            collection_run_date=datetime.now(UTC).date(),
            success=success,
            collection_duration_ms=collection_duration_ms,
            number_of_records_processed=number_of_records_processed,
            database_query_time_ms=database_query_time_ms,
            cache_hit_rate=cache_hit_rate,
        )
    except Exception:
        logger.exception("Failed to record dashboard telemetry")


def collect_dashboard_reports_initial_data(**kwargs) -> dict[str, Any]:
    """
    Collect historical AWX job data as a one-time backfill.

    The backfill window defaults to 90 days and can be overridden via
    settings.DASHBOARD_COLLECTION['INITIAL_BACKFILL_DAYS']. After this task
    Returns a task result dict with status, data, and any error details.
    """
    task_name = "collect_dashboard_reports_initial_data"
    start_time = time.monotonic()
    result = _collect_data(task_name=task_name, **kwargs)

    error = result.get("error", False)

    duration_ms = (time.monotonic() - start_time) * 1000
    records_processed = result.get("data", {}).get("job_count", 0)

    _save_telemetry_details(
        task_name=task_name,
        success=not error,
        collection_duration_ms=duration_ms,
        number_of_records_processed=records_processed,
        database_query_time_ms=None,  # DB time not tracked for batched backfill
        cache_hit_rate=None,
    )

    if error:
        return create_task_result(
            "error", error=result.get("message", "An unknown error occurred during initial data collection")
        )

    return create_task_result("success", data=result.get("data", {}))


def collect_dashboard_reports_data(**kwargs) -> dict[str, Any]:
    """
    Incrementally collect AWX job data since the last known JobData timestamp.

    .. deprecated::
        No longer registered as a scheduled system task. Ongoing incremental sync is driven
        automatically by the hourly_unified_jobs hook (see _build_dashboard_sync_hook).
        This function remains available for manual operator-triggered collection via the task API.

    Falls back to 90 days ago if no previous records exist.
    Returns a task result dict with status, date range, job count, and any error details.
    """
    task_name = "collect_dashboard_reports_data"
    result = _collect_data(task_name=task_name, **kwargs)
    error = result.get("error", False)

    if error:
        return create_task_result(
            "error", error=result.get("message", "An unknown error occurred during incremental data collection")
        )
    return create_task_result("success", data=result.get("data", {}))


def sync_dashboard_job_records(**kwargs) -> dict[str, Any]:
    """
    Write unified_jobs raw data collected during the hourly rollup to the dashboard JobData table.

    Scheduled automatically by the hourly_unified_jobs collection hook so no extra Controller
    DB queries are needed — the raw data is passed in task_data.
    """
    task_name = "sync_dashboard_job_records"
    hour_timestamp = kwargs.get("hour_timestamp", "unknown")
    raw_jobs = kwargs.get("raw_jobs", [])
    start_time = time.monotonic()

    log_task_execution(
        task_name=task_name,
        operation="processing",
        details=f"Syncing {len(raw_jobs)} dashboard job records for {hour_timestamp}",
    )

    assembled = []
    for row in raw_jobs:
        label_ids_raw = row.get("label_ids")
        if label_ids_raw is None or (isinstance(label_ids_raw, float) and math.isnan(label_ids_raw)):
            labels = []
        elif isinstance(label_ids_raw, str):
            labels = [int(x.strip()) for x in label_ids_raw.split(",") if x.strip()]
        else:
            labels = [int(label_ids_raw)]
        assembled.append(
            {
                "id": row["id"],
                "name": row["name"],
                "unified_job_template_id": row.get("unified_job_template_id"),
                "organization_id": row.get("organization_id"),
                "organization_name": row.get("organization_name"),
                "started": _parse_dt(row.get("started")),
                "finished": _parse_dt(row.get("finished")),
                "status": row["status"],
                "elapsed": row["elapsed"],
                "launched_by_id": row.get("launched_by_id"),
                "launched_by_username": row.get("launched_by_username"),
                "project_id": row.get("project_id"),
                "project_name": row.get("project_name"),
                "created": _parse_dt(row.get("created")),
                "modified": _parse_dt(row.get("modified")),
                "labels": labels,
                # host_summaries=None signals create_or_update_from_awx to leave
                # existing JobHostSummary records intact (created by initial backfill).
                "host_summaries": None,
                "num_hosts": row.get("num_hosts") or 0,
            }
        )

    failed_jobs = _sync_jobs_atomically(assembled)

    duration_ms = (time.monotonic() - start_time) * 1000
    success = not failed_jobs
    _save_telemetry_details(
        task_name=task_name,
        success=success,
        collection_duration_ms=duration_ms,
        number_of_records_processed=len(assembled) - len(failed_jobs),
        database_query_time_ms=None,
        cache_hit_rate=None,
    )

    if failed_jobs:
        return create_task_result("error", error=f"Failed to sync {len(failed_jobs)} job(s): {failed_jobs}")

    log_task_execution(
        task_name=task_name,
        operation="completed",
        details=f"Synced {len(assembled)} job records for {hour_timestamp}",
    )
    return create_task_result(
        "success", data={"task_type": task_name, "job_count": len(assembled), "hour_timestamp": hour_timestamp}
    )


def sync_dashboard_host_summaries(**kwargs) -> dict[str, Any]:
    """Write job_host_summary_service data to JobHostSummary records in the dashboard tables.

    Scheduled automatically by the hourly job_host_summary_service hook so no extra Controller
    DB queries are needed — the raw data is passed in task_data. Jobs not present in JobData
    (e.g. sync-type or non-terminal jobs filtered out by the dashboard collector) are silently
    skipped.
    """
    task_name = "sync_dashboard_host_summaries"
    hour_timestamp = kwargs.get("hour_timestamp", "unknown")
    raw_host_summaries = kwargs.get("raw_host_summaries", [])

    log_task_execution(
        task_name=task_name,
        operation="processing",
        details=f"Syncing host summaries for {len(raw_host_summaries)} records ({hour_timestamp})",
    )

    # Group by job_remote_id; the hook's serializer already maps host_remote_id → host_id.
    by_job: dict[int, list] = {}
    for row in raw_host_summaries:
        job_id = row.get("job_remote_id")
        if job_id is None:
            continue
        summary_id = row.get("id")
        if summary_id is None:
            continue
        by_job.setdefault(job_id, []).append(
            {
                "id": summary_id,
                "host_id": row.get("host_id"),
                "host_name": row.get("host_name"),
            }
        )

    # Batch-fetch all matching JobData and their existing JobHostSummary records in two queries
    # rather than 2N queries (one get + one filter per job).
    job_data_by_id: dict[int, Any] = {}
    existing_by_job_data_pk: dict[int, dict] = {}
    if by_job:
        job_data_by_id = {jd.job_id: jd for jd in JobData.objects.filter(job_id__in=by_job.keys())}
        for hs in JobHostSummary.objects.filter(job_data__in=job_data_by_id.values()):
            existing_by_job_data_pk.setdefault(hs.job_data_id, {})[hs.host_summary_id] = hs

    synced = 0
    failed = 0
    for job_remote_id, host_summaries in by_job.items():
        job_data = job_data_by_id.get(job_remote_id)
        if job_data is None:
            continue  # sync/non-terminal job — no matching JobData record
        try:
            with transaction.atomic():
                existing = existing_by_job_data_pk.get(job_data.pk, {})
                JobData._sync_host_summaries(job_data, host_summaries, existing)
            synced += 1
        except Exception:
            logger.exception("Error syncing host summaries for job %s", job_remote_id)
            failed += 1

    log_task_execution(
        task_name=task_name,
        operation="completed",
        details=f"Synced host summaries for {synced} jobs, {failed} failed ({hour_timestamp})",
    )
    if failed:
        return create_task_result(
            "error",
            data={"task_type": task_name, "job_count": synced, "failed": failed, "hour_timestamp": hour_timestamp},
        )
    return create_task_result(
        "success", data={"task_type": task_name, "job_count": synced, "hour_timestamp": hour_timestamp}
    )


def cleanup_dashboard_reports_old_data(**kwargs) -> dict[str, Any]:
    """
    Delete JobData records with a finished date older than retention_period_days.

    Defaults to settings.DASHBOARD_COLLECTION['INITIAL_BACKFILL_DAYS'] so the
    retention window always matches the backfill window, falling back to 90 days.
    Returns a task result dict with the number of deleted records, cutoff date, and any error details.
    """
    dashboard_cfg = getattr(settings, "DASHBOARD_COLLECTION", None) or {}
    raw_default_retention = dashboard_cfg.get("INITIAL_BACKFILL_DAYS", 90)
    try:
        default_retention = int(raw_default_retention)
    except (TypeError, ValueError):
        logger.warning(
            "cleanup_dashboard_reports_old_data: INITIAL_BACKFILL_DAYS=%r is not a valid integer; falling back to 90",
            raw_default_retention,
        )
        default_retention = 90
    retention_period_days = kwargs.get("retention_period_days", default_retention)
    try:
        retention_period_days = int(retention_period_days)
    except (TypeError, ValueError):
        logger.error(
            "cleanup_dashboard_reports_old_data: retention_period_days=%r is not a valid integer; aborting cleanup",
            retention_period_days,
        )
        return create_task_result("error", error=f"Invalid retention_period_days value: {retention_period_days!r}")
    if retention_period_days < 0:
        logger.warning(
            "cleanup_dashboard_reports_old_data: retention_period_days=%d is negative which would produce a future "
            "cutoff date and delete current records; clamping to 0",
            retention_period_days,
        )
        retention_period_days = 0
    cutoff_date = datetime.now(tz=UTC) - timedelta(days=retention_period_days)
    cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date_str = cutoff_date.isoformat()

    log_task_execution(
        task_name="cleanup_dashboard_reports_old_data",
        operation="processing",
        details=f"Cleaning up JobData records older than {cutoff_date_str} (retention period: {retention_period_days} days)",
    )

    start_time = time.monotonic()
    duration_db_ms = 0
    jobdata_count = 0
    task_name = "cleanup_dashboard_reports_old_data"
    try:
        start_db_time = time.monotonic()
        queryset = JobData.objects.filter(finished__lt=cutoff_date)
        # Count JobData rows before deletion — delete() returns the total across all
        # cascaded models (JobLabel, JobHostSummary, etc.) which inflates the count.
        jobdata_count = queryset.count()
        queryset.delete()
        duration_db_ms = (time.monotonic() - start_db_time) * 1000
        log_task_execution(
            task_name=task_name,
            operation="completed",
            details=f"Deleted {jobdata_count} JobData records finished before {cutoff_date_str}",
        )
        duration_ms = (time.monotonic() - start_time) * 1000

        _save_telemetry_details(
            task_name=task_name,
            success=True,
            collection_duration_ms=duration_ms,
            number_of_records_processed=jobdata_count,
            database_query_time_ms=duration_db_ms,
            cache_hit_rate=None,
        )
        return create_task_result(
            "success",
            data={
                "deleted_records": jobdata_count,
                "cutoff_date": cutoff_date_str,
                "retention_period_days": retention_period_days,
            },
        )
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(f"Error during cleanup of old JobData records: {str(e)}")
        _save_telemetry_details(
            task_name=task_name,
            success=False,
            collection_duration_ms=duration_ms,
            number_of_records_processed=jobdata_count,
            database_query_time_ms=duration_db_ms,
            cache_hit_rate=None,
        )
        return create_task_result("error", error=f"Cleanup failed: {str(e)}")


def cleanup_dashboard_telemetry(**kwargs) -> dict[str, Any]:
    """
    Delete DashboardTelemetry rows older than retention_period_days (default: 60).

    Keeps the telemetry table bounded; the API window is 30 days so rows beyond
    60 days are no longer surfaced and can safely be purged.
    Returns a task result dict with the number of deleted rows and cutoff date.
    """
    task_name = "cleanup_dashboard_telemetry"
    retention_period_days = kwargs.get("retention_period_days", 60)
    try:
        retention_period_days = int(retention_period_days)
    except (TypeError, ValueError):
        logger.error(
            "%s: retention_period_days=%r is not a valid integer; aborting cleanup",
            task_name,
            retention_period_days,
        )
        return create_task_result("error", error=f"Invalid retention_period_days value: {retention_period_days!r}")
    if retention_period_days < 0:
        logger.warning(
            "%s: retention_period_days=%d is negative; clamping to 0",
            task_name,
            retention_period_days,
        )
        retention_period_days = 0

    cutoff_date = (datetime.now(tz=UTC) - timedelta(days=retention_period_days)).date()
    log_task_execution(
        task_name=task_name,
        operation="processing",
        details=f"Deleting DashboardTelemetry rows with collection_run_date < {cutoff_date} (retention: {retention_period_days} days)",
    )

    try:
        deleted_count, _ = DashboardTelemetry.objects.filter(collection_run_date__lt=cutoff_date).delete()
        log_task_execution(
            task_name=task_name,
            operation="completed",
            details=f"Deleted {deleted_count} DashboardTelemetry rows before {cutoff_date}",
        )
        return create_task_result(
            "success",
            data={
                "deleted_records": deleted_count,
                "cutoff_date": str(cutoff_date),
                "retention_period_days": retention_period_days,
            },
        )
    except Exception as e:
        logger.exception("Error during cleanup of DashboardTelemetry rows")
        return create_task_result("error", error=f"Cleanup failed: {str(e)}")
