"""One-time resource sync task — pulls users, orgs, teams and RBAC assignments from gateway."""

import logging
from io import StringIO

from ansible_base.resource_registry.tasks.sync import SyncExecutor

from ..utils import create_task_result

logger = logging.getLogger(__name__)


def sync_resources_from_gateway(**kwargs) -> dict:
    """
    Sync all shared resources and RBAC role assignments from the gateway.

    Runs SyncExecutor with no resource type filter so organization and team
    objects are created before user assignments that reference them, avoiding
    DoesNotExist errors on object-scoped roles.

    Idempotent — safe to run on upgrade and on first boot.
    """
    stdout = StringIO()
    executor = SyncExecutor(stdout=stdout)

    try:
        executor.run()
    except Exception as exc:
        logger.error("resource sync failed: %s", exc, exc_info=True)
        output = stdout.getvalue()
        return create_task_result("error", data={"output": output}, error=str(exc))

    output = stdout.getvalue()
    results = getattr(executor, "results", {})
    summary = {k: len(v) for k, v in results.items() if isinstance(v, list)}
    logger.info("resource sync complete: %s", summary)

    return create_task_result("success", {"summary": summary, "output": output})
