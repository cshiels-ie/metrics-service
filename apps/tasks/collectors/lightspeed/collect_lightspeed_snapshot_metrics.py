"""
Snapshot metrics collector for Lightspeed (AI assistant).

Collects daily snapshots from the Lightspeed PostgreSQL database using the
``ms_aap_readonly`` read-only account. If the Lightspeed DB is unreachable
(credentials missing or host not configured), returns a structured error
result without raising — so the LIGHTSPEED_COLLECTION_GROUP fails cleanly
and does not affect other task groups.
"""

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from ...utils import create_task_result, generic_collect_metrics, get_db_connection, parse_datetime_string
from ._registry import _get_lightspeed_collectors

logger = logging.getLogger(__name__)


def collect_lightspeed_snapshot_metrics(**kwargs: Any) -> dict[str, Any]:
    """Collect a snapshot from the Lightspeed database.

    Args:
        **kwargs: Task data containing:
            - collector_type (str): One of the keys in the Lightspeed collector registry
              (e.g., ``'lightspeed_config'``).
            - collection_timestamp (str): Optional ISO timestamp; defaults to
              23:00 of the previous day.

    Returns:
        dict: Task result with collection status and HourlyMetricsCollection record ID.
    """
    collector_type = kwargs.pop("collector_type", None)
    if not collector_type:
        return create_task_result("error", error="collector_type parameter is required")

    execution_id = kwargs.get("execution_id")

    registry = _get_lightspeed_collectors()
    if collector_type not in registry:
        valid = ", ".join(sorted(registry.keys()))
        return create_task_result(
            "error", error=f"Unknown Lightspeed collector_type: '{collector_type}'. Valid: {valid}"
        )

    collection_timestamp_str = kwargs.get("collection_timestamp")
    if collection_timestamp_str:
        collection_timestamp = parse_datetime_string(collection_timestamp_str)
        if collection_timestamp is None:
            return create_task_result(
                "error", error=f"Invalid collection_timestamp format: {collection_timestamp_str}"
            )
    else:
        collection_timestamp = timezone.now().replace(hour=23, minute=0, second=0, microsecond=0) - timedelta(days=1)

    try:
        db_connection = get_db_connection("lightspeed")
    except Exception as e:
        logger.warning("collect_lightspeed_snapshot_metrics: cannot connect to Lightspeed DB: %s", e)
        return create_task_result(
            "error",
            {"collector_type": collector_type, "source": "lightspeed"},
            error=f"Lightspeed database connection failed: {e}",
        )

    collection_date = collection_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

    return generic_collect_metrics(
        collector_type=collector_type,
        collector_registry=registry,
        collection_mode="snapshot",
        timestamp=collection_timestamp,
        db_connection=db_connection,
        collector_kwargs={"collection_time": collection_date},
        task_execution_id=execution_id,
    )
