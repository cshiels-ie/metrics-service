"""Runtime configuration for dashboard report collection."""

import json
import logging

from apps.dynamic_settings.models import Setting

logger = logging.getLogger(__name__)

DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS = "DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS"


def include_sync_workflow_jobs() -> bool:
    """Return whether dashboard collection should include sync/workflow jobs.

    The setting is deliberately default-off so deployments retain the existing
    dashboard behavior when no database override has been configured.
    """
    try:
        value = (
            Setting.objects.filter(setting_key=DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS)
            .values_list("current_value", flat=True)
            .first()
        )
        if value is None:
            return False
        parsed = json.loads(value)
        if isinstance(parsed, bool):
            return parsed
    except (TypeError, json.JSONDecodeError):
        logger.warning("Invalid value for %s; using false", DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS)
    except Exception:
        logger.exception("Unable to read %s; using false", DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS)
    return False
