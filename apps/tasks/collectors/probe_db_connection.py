"""
Connectivity probe task for optional external databases (EDA, Gateway, Lightspeed).

The probe attempts a DB connection and runs SELECT 1. It NEVER raises — it always
returns a structured dict so a failing probe does not abort adjacent task groups.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def probe_db_connection(**kwargs: Any) -> dict[str, Any]:
    """Check that a named Django DB alias is reachable.

    Attempts to connect and execute ``SELECT 1``. Never raises — always returns a
    structured result dict so a failed probe does not propagate to other task groups.

    Args:
        **kwargs: Must include ``source`` (str), one of ``'eda'``, ``'gateway'``,
            ``'lightspeed'``.

    Returns:
        dict with keys:
            - ``status``: ``'ok'`` or ``'error'``
            - ``message``: Human-readable result string
            - ``source``: The DB alias that was probed
            - ``timestamp``: ISO 8601 timestamp of the probe
    """
    from django.utils import timezone

    source = kwargs.get("source")
    if not source:
        return {
            "status": "error",
            "message": "probe_db_connection called without 'source' argument",
            "source": None,
            "timestamp": timezone.now().isoformat(),
        }

    try:
        from ..utils import get_db_connection

        conn = get_db_connection(source)
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        logger.info("probe_db_connection: %s is reachable", source)
        return {
            "status": "ok",
            "message": f"Successfully connected to {source} database",
            "source": source,
            "timestamp": timezone.now().isoformat(),
        }

    except Exception as e:
        logger.warning("probe_db_connection: cannot reach %s: %s", source, e)
        return {
            "status": "error",
            "message": str(e),
            "source": source,
            "timestamp": timezone.now().isoformat(),
        }
