"""
On-demand BI controller data collection task.

Invoked by ControllerTimeSeriesView when a BI tool requests live AWX data.
Runs inside dispatcherd so the HTTP request returns immediately (202) while
the potentially long-running AWX query executes in the background.

Result stored in Task.result_data by the tasks_system machinery and readable
via GET /api/v1/tasks/<task_id>/ once status == "completed".
"""

import logging

from apps.tasks.utils import get_db_connection, parse_datetime_string

logger = logging.getLogger(__name__)


def collect_bi_controller_data(task_data: dict | None = None, **kwargs) -> dict:
    """
    Collect live AWX data for a single collector type over an explicit date range.

    task_data keys:
        collector_key (str)  — matches a key in _get_hourly_collectors() registry
        since         (str)  — ISO 8601 datetime string
        until         (str)  — ISO 8601 datetime string

    Returns a dict compatible with the tasks_system success/error convention:
        {"status": "success", "collector_type": ..., "since": ..., "until": ..., "data": [...]}
    """
    collector_key = task_data.get("collector_key") if task_data else None
    since_str = task_data.get("since") if task_data else None
    until_str = task_data.get("until") if task_data else None

    if not all([collector_key, since_str, until_str]):
        return {"status": "error", "error": "task_data must contain collector_key, since, and until"}

    since = parse_datetime_string(since_str)
    until = parse_datetime_string(until_str)

    if since is None or until is None:
        return {"status": "error", "error": f"Invalid datetime values: since={since_str!r}, until={until_str!r}"}

    try:
        conn = get_db_connection()
    except Exception as e:
        logger.error("AWX DB unavailable for bi_collect %s: %s", collector_key, e)
        return {"status": "error", "error": f"AWX database unavailable: {e}"}

    try:
        from apps.tasks.collectors.collect_hourly_metrics import _get_hourly_collectors

        collectors = _get_hourly_collectors()

        if collector_key not in collectors:
            return {"status": "error", "error": f"Unknown collector_key: {collector_key!r}"}

        collector = collectors[collector_key]["collector_func"](db=conn, since=since, until=until)
        data = collector.gather()
    except Exception as e:
        logger.error("Collection failed for bi_collect %s: %s", collector_key, e)
        return {"status": "error", "error": f"Collection failed: {e}"}

    logger.info("bi_collect %s completed: %d records", collector_key, len(data) if isinstance(data, list) else 1)
    return {
        "status": "success",
        "collector_type": collector_key,
        "since": since_str,
        "until": until_str,
        "data": data,
    }
