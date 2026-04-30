"""
Logging utilities for container-friendly output.

Provides a JSON formatter for structured logs suitable for aggregation
(Kubernetes, Splunk, ELK, etc.).
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any


class DispatcherdReconnectFilter(logging.Filter):
    """Suppress transient pg_notify reconnection errors logged by the asyncio event loop.

    When dispatcherd loses its PostgreSQL NOTIFY/LISTEN connection it retries every
    second and the asyncio event loop logs each failed attempt at ERROR level via the
    'asyncio' logger.  These are expected during service startup or a brief DB restart
    and are not actionable — dispatcherd recovers automatically once the DB is reachable.

    The filter matches on 'CallbackHolder.done_callback', which is unique to
    dispatcherd's asyncio_tasks.py, so unrelated asyncio errors are unaffected.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.name == "asyncio" and "CallbackHolder.done_callback" in record.getMessage())


class JsonFormatter(logging.Formatter):
    """
    Format log records as single-line JSON for container stdout.

    Output is one JSON object per line, suitable for log drivers and
    centralized logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string."""
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        log_obj: dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if getattr(record, "request_id", None):
            log_obj["request_id"] = record.request_id
        return json.dumps(log_obj)
