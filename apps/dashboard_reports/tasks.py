"""
Background tasks for dashboard reports data collection and cleanup.

Provides three dispatcherd tasks:
- collect_dashboard_reports_initial_data: full 90-day historical backfill
- collect_dashboard_reports_data: incremental sync from last known timestamp
- cleanup_dashboard_reports_old_data: removes JobData records beyond retention period
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from django.db import transaction
from metrics_utility.library.collectors.dashboard import DashboardJobsResultType, dashboard_jobs

from apps.dashboard_reports.models import JobData
from apps.tasks.models import Task
from apps.tasks.task_groups import DASHBOARD_COLLECTION_GROUP
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


def _collect_jobs(db_connection, since: datetime, until: datetime) -> DashboardJobsResultType:
    """
    Collect dashboard jobs data from the database for the specified date range.
    """
    return dashboard_jobs(db=db_connection, since=since, until=until).gather()


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


def _collect_data(task_name: str, **kwargs) -> dict[str, Any]:
    """
    Core data collection logic for dashboard reports.
    This function can be called by different tasks with varying parameters.
    """
    result = {
        "error": False,
        "message": "",
        "data": {"task_type": task_name, "date_range": {"start": None, "end": None}, "job_count": 0},
    }
    db_name = kwargs.get("database", DEFAULT_DB_NAME)
    until = _parse_dt(kwargs.get("until"))
    since = _parse_dt(kwargs.get("since"))

    if until is None:
        # Default to now if not provided
        until = datetime.now(tz=UTC)
    if since is None:
        # For incremental collection, we want to start from the last timestamp in the JobData table
        since = JobData.last_timestamp()
        if since is None:
            # Default to 90 days ago if no previous timestamp is found
            since = until - timedelta(days=90)
            since = since.replace(hour=0, minute=0, second=0, microsecond=0)
            since = since.astimezone(tz=UTC)

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
        jobs = _collect_jobs(db_connection, since=since, until=until)
    except Exception as e:
        logger.error(f"Error collecting jobs: {str(e)}")
        result["error"] = True
        result["message"] = f"Collecting jobs failed: {str(e)}"
        return result

    failed_jobs = _sync_jobs_atomically(jobs["results"])

    if failed_jobs:
        result["error"] = True
        result["message"] = f"Failed to sync {len(failed_jobs)} job(s): {failed_jobs}"
        return result

    job_count = jobs["count"]
    log_task_execution(
        task_name=task_name,
        operation="completed",
        details=f"Collected and stored data for {job_count} jobs from {start_str} to {end_str}",
    )
    result["data"] = {
        "task_type": task_name,
        "date_range": {"start": start_str, "end": end_str},
        "job_count": job_count,
    }
    return result


def collect_dashboard_reports_initial_data(**kwargs) -> dict[str, Any]:
    """
    Collect up to 90 days of historical AWX job data and schedule the recurring incremental task.

    On success, creates the follow-up daily_dashboard_collection system task if it does not exist.
    Returns a task result dict with status, data, and any error details.
    """
    task_name = "collect_dashboard_reports_initial_data"
    result = _collect_data(task_name=task_name, **kwargs)

    error = result.get("error", False)

    if error:
        return create_task_result(
            "error", error=result.get("message", "An unknown error occurred during initial data collection")
        )
    data = result.get("data", {})

    # TODO: Tech Preview only — the daily_dashboard_collection task is created here rather than
    # via init-system-tasks because it must only be activated after a successful initial backfill.
    # At GA this should be refactored to align with the standard task group lifecycle so that
    # init-system-tasks is the authoritative source for all system tasks (see task_groups.py).
    log_task_execution(
        task_name=task_name,
        operation="processing",
        details="Creating follow-up task for collecting dashboard reports data (every 6 hours) after initial data collection.",
    )

    dashboard_tasks = list(
        filter(lambda t: t["task_id"] == "daily_dashboard_collection", DASHBOARD_COLLECTION_GROUP.tasks)
    )

    if len(dashboard_tasks) == 0:
        error_msg = "No task with task_id 'daily_dashboard_collection' found in DASHBOARD_COLLECTION_GROUP"
        logger.error(error_msg)
        return create_task_result("error", error=error_msg)
    follow_up_task_id = dashboard_tasks[0].get("task_id")
    daily_dashboard_collection_task = dashboard_tasks[0]
    task_data = dashboard_tasks[0].get("args", {}).copy()
    if DASHBOARD_COLLECTION_GROUP.feature_flag:
        task_data["_feature_flag"] = DASHBOARD_COLLECTION_GROUP.feature_flag
    try:
        _, created = Task.objects.get_or_create(
            name=follow_up_task_id,
            is_system_task=True,
            defaults={
                "description": daily_dashboard_collection_task.get("description", ""),
                "function_name": daily_dashboard_collection_task["function"],
                "task_data": task_data,
                "cron_expression": daily_dashboard_collection_task.get("cron"),
                "status": "pending",
            },
        )
        if created:
            data["Follow-up task creation"] = "success"
        else:
            logger.info(f"Task '{follow_up_task_id}' already exists. Skipping creation of follow-up task.")
            data["Follow-up task creation"] = "skipped"
    except Exception as e:
        logger.error(f"Error creating follow-up task for collecting dashboard reports data: {str(e)}")
        return create_task_result("error", error=f"Creating follow-up task failed: {str(e)}")

    return create_task_result("success", data=data)


def collect_dashboard_reports_data(**kwargs) -> dict[str, Any]:
    """
    Incrementally collect AWX job data since the last known JobData timestamp.

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


def cleanup_dashboard_reports_old_data(**kwargs) -> dict[str, Any]:
    """
    Delete JobData records with a finished date older than retention_period_days (default: 90).

    Returns a task result dict with the number of deleted records, cutoff date, and any error details.
    """
    retention_period_days = kwargs.get("retention_period_days", 90)
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

    try:
        queryset = JobData.objects.filter(finished__lt=cutoff_date)
        # Count JobData rows before deletion — delete() returns the total across all
        # cascaded models (JobLabel, JobHostSummary, etc.) which inflates the count.
        jobdata_count = queryset.count()
        queryset.delete()
        log_task_execution(
            task_name="cleanup_dashboard_reports_old_data",
            operation="completed",
            details=f"Deleted {jobdata_count} JobData records finished before {cutoff_date_str}",
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
        logger.error(f"Error during cleanup of old JobData records: {str(e)}")
        return create_task_result("error", error=f"Cleanup failed: {str(e)}")
