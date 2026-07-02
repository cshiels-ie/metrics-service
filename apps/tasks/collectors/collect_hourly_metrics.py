"""
Hourly metrics collector for time-series data.

Collects metrics for a specific hour, computes rollup statistics,
and stores in HourlyMetricsCollection.
"""

import logging
import math
from datetime import timedelta
from typing import Any

from django.utils import timezone

from ..utils import create_task_result, generic_collect_metrics, get_db_connection, parse_datetime_string

logger = logging.getLogger(__name__)


def _get_hourly_collectors():
    """
    Get hourly collectors registry with lazy imports.

    Lazy imports prevent metrics_utility dependency from breaking
    unrelated task registration (e.g., hello_world, cleanup_old_tasks).
    """
    from metrics_utility.anonymized_rollups import (
        CredentialsAnonymizedRollup,
        EventModulesAnonymizedRollup,
        JobHostSummaryAnonymizedRollup,
        JobsAnonymizedRollup,
    )
    from metrics_utility.library.collectors.controller import (
        credentials_service,
        job_host_summary_service,
        main_jobevent_service,
        unified_jobs_dashboard,
    )

    # Registry mapping collector_type to (collector_func, rollup_processor_class)
    return {
        "job_host_summary_service": {
            "collector_func": job_host_summary_service,
            "rollup_processor": JobHostSummaryAnonymizedRollup,
            "description": "Job host summary metrics (partition-optimized)",
        },
        "unified_jobs": {
            # unified_jobs_dashboard extends the base unified_jobs query with dashboard-specific
            # fields (project_id/name, launched_by, label_ids, num_hosts); the registry key is
            # kept as "unified_jobs" for backwards-compat with task scheduling and API references.
            "collector_func": unified_jobs_dashboard,
            "rollup_processor": JobsAnonymizedRollup,
            "description": "Unified jobs metrics",
            "post_collect_hook_factory": _build_dashboard_sync_hook,
        },
        "credentials_service": {
            "collector_func": credentials_service,
            "rollup_processor": CredentialsAnonymizedRollup,
            "description": "Credentials usage metrics",
        },
        "main_jobevent_service": {
            "collector_func": main_jobevent_service,
            "rollup_processor": EventModulesAnonymizedRollup,
            "description": "Job events (event modules) metrics",
        },
    }


def collect_hourly_metrics(**kwargs) -> dict[str, Any]:
    """
    Collect hourly metrics for a specific collector type.

    This function handles all time-series collectors that gather data
    for a specific hour window. It collects raw data, computes rollup
    statistics, and stores only the rollup in HourlyMetricsCollection.

    Args:
        **kwargs: Task data containing:
            - collector_type (str): Type of collector (required)
            - hour_timestamp (str): ISO timestamp for the hour to collect (optional, defaults to previous hour)
            - database (str): Database name (default: 'awx')

    Returns:
        dict: Task result with collection status and record ID
    """
    collector_type = kwargs.pop("collector_type", None)
    if not collector_type:
        return create_task_result("error", error="collector_type parameter is required")

    # Extract optional execution_id for linking to TaskExecution
    execution_id = kwargs.get("execution_id")  # Available when called via execute_db_task

    # Determine hour to collect (default to previous full hour)
    hour_timestamp_str = kwargs.get("hour_timestamp")
    if hour_timestamp_str:
        hour_timestamp = parse_datetime_string(hour_timestamp_str)
        if hour_timestamp is None:
            return create_task_result("error", error=f"Invalid hour_timestamp format: {hour_timestamp_str}")
    else:
        # Fallback only — the cron scheduler pins hour_timestamp into task_data
        # at dispatch time via _inject_dispatch_timestamps(), so retries reuse
        # the original window instead of recomputing from now.
        now = timezone.now()
        hour_timestamp = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    start_datetime = hour_timestamp
    end_datetime = start_datetime + timedelta(hours=1)

    # Get database connection
    db_connection = get_db_connection()

    collector_registry = _get_hourly_collectors()
    hook_factory = collector_registry.get(collector_type, {}).get("post_collect_hook_factory")
    post_collect_hook = hook_factory(start_datetime) if hook_factory else None

    # Use generic collector with hourly-specific time window
    return generic_collect_metrics(
        collector_type=collector_type,
        collector_registry=collector_registry,
        collection_mode="hourly",
        timestamp=start_datetime,
        db_connection=db_connection,
        collector_kwargs={"since": start_datetime, "until": end_datetime},
        task_execution_id=execution_id,
        post_collect_hook=post_collect_hook,
    )


_SYNC_TASK_CHUNK_SIZE = 500  # max records per sync_dashboard_job_records task

_DASHBOARD_COLUMNS = [
    "id",
    "name",
    "unified_job_template_id",
    "organization_id",
    "organization_name",
    "started",
    "finished",
    "status",
    "elapsed",
    "launched_by_id",
    "launched_by_username",
    "project_id",
    "project_name",
    "created",
    "modified",
    "label_ids",
    "num_hosts",
]


_INT_FIELDS = ("id", "organization_id", "unified_job_template_id", "launched_by_id", "project_id", "num_hosts")


def _serialize_dashboard_record(row: dict) -> None:
    """Coerce all non-serializable numpy/pandas types to Python natives in-place.

    pandas .to_dict("records") preserves numpy dtypes (numpy.int64, numpy.float64) for
    columns with no NaN values. DjangoJSONEncoder does not handle these, so storing raw
    records in Task.task_data would raise TypeError. This function converts every field
    that could carry a numpy type before the record is written to the JSONField.

    Nullable FK columns (organization_id, project_id, etc.) are upcast to float64 by pandas
    when NaN coexists with integers; .where(notna(), other=None) leaves NaN as float nan
    rather than None, so int(nan) would raise ValueError without the explicit nan guard here.
    """
    for field in ("started", "finished", "created", "modified"):
        val = row.get(field)
        if val is not None and hasattr(val, "isoformat"):
            row[field] = val.isoformat()
    for field in _INT_FIELDS:
        val = row.get(field)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            row[field] = None
        else:
            row[field] = int(val)
    val = row.get("elapsed")
    if val is None or (isinstance(val, float) and math.isnan(val)):
        row["elapsed"] = None
    else:
        row["elapsed"] = float(val)


def _build_dashboard_sync_hook(hour_timestamp):
    """
    Return a post_collect_hook that schedules a sync_dashboard_job_records task.

    The hook serialises the filtered raw unified_jobs DataFrame into task_data so the
    follow-up task can write to JobData without re-querying the Controller DB.
    Only schedules the task when the DASHBOARD_COLLECTION feature flag is enabled.
    """
    # Lazy import: circular dependency (collect_hourly_metrics → task_groups → tasks → collect_hourly_metrics).
    from apps.tasks.task_groups import get_feature_enabled_from_db

    # The flag is intentionally evaluated at hook-build time (when the hourly task starts),
    # not when the hook executes after gather(). A flag change mid-task takes effect on the
    # next collection cycle. This is acceptable — the window is the duration of one gather() call.
    if not get_feature_enabled_from_db("DASHBOARD_COLLECTION"):
        return None

    def hook(raw_data):
        if raw_data is None or raw_data.empty:
            return

        mask = raw_data["status"].isin(["failed", "successful"]) & (raw_data["launch_type"] != "sync")
        filtered = raw_data[mask]
        if filtered.empty:
            return

        # unified_jobs_dashboard guarantees these columns; guard with available
        # in case a future schema change temporarily drops one.
        available = [c for c in _DASHBOARD_COLUMNS if c in filtered.columns]
        missing = set(_DASHBOARD_COLUMNS) - set(available)
        if missing:
            logger.warning(
                "unified_jobs_dashboard is missing expected columns: %s",
                sorted(missing),
            )
        records = filtered[available].where(filtered[available].notna(), other=None).to_dict("records")
        for row in records:
            _serialize_dashboard_record(row)

        # Lazy import inside closure: Task must be resolved at call time so tests can
        # patch apps.tasks.models.Task after the hook is built (same circular-import reason).
        from apps.tasks.models import Task

        hour_ts_str = hour_timestamp.isoformat()
        for chunk_index, start in enumerate(range(0, len(records), _SYNC_TASK_CHUNK_SIZE)):
            chunk = records[start : start + _SYNC_TASK_CHUNK_SIZE]
            Task.objects.update_or_create(
                name=f"sync_dashboard_jobs_{hour_ts_str}_{chunk_index}",
                defaults={
                    "description": f"Sync dashboard job records from unified_jobs for {hour_ts_str} (chunk {chunk_index})",
                    "function_name": "sync_dashboard_job_records",
                    "task_data": {
                        "raw_jobs": chunk,
                        "hour_timestamp": hour_ts_str,
                        "_feature_flag": "DASHBOARD_COLLECTION",
                    },
                    "is_system_task": False,
                },
            )

    return hook
