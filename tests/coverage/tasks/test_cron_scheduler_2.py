"""
Additional tests for uncovered paths in apps/tasks/cron_scheduler.py.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone


# ---------------------------------------------------------------------------
# start_scheduler / stop_scheduler global functions
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_start_scheduler_creates_and_starts(mock_apscheduler):
    import apps.tasks.cron_scheduler as cs

    cs._scheduler_instance = None
    with patch.object(cs.UnifiedTaskScheduler, "_sync_database_tasks"):
        result = cs.start_scheduler()
    assert result is not None
    assert cs._scheduler_instance is not None
    cs._scheduler_instance = None  # cleanup


@pytest.mark.unit
def test_stop_scheduler_stops_instance(mock_apscheduler):
    import apps.tasks.cron_scheduler as cs

    cs._scheduler_instance = None
    with patch.object(cs.UnifiedTaskScheduler, "_sync_database_tasks"):
        scheduler = cs.start_scheduler()

    assert cs._scheduler_instance is not None
    cs.stop_scheduler()
    assert cs._scheduler_instance is None


@pytest.mark.unit
def test_stop_scheduler_when_no_instance():
    import apps.tasks.cron_scheduler as cs

    cs._scheduler_instance = None
    cs.stop_scheduler()  # Should not raise
    assert cs._scheduler_instance is None


# ---------------------------------------------------------------------------
# _sync_database_tasks — with real DB tasks
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_sync_database_tasks_with_scheduled_task(user, mock_apscheduler):
    import apps.tasks.cron_scheduler as cs
    from apps.tasks.models import Task

    future_time = timezone.now() + timedelta(hours=1)
    task = Task.objects.create(
        name="future_sched",
        function_name="hello_world",
        task_data={},
        created_by=user,
        scheduled_time=future_time,
        status="pending",
    )

    scheduler = cs.UnifiedTaskScheduler()
    scheduler.scheduler = mock_apscheduler
    scheduler._sync_database_tasks()

    assert task.id in scheduler._db_task_jobs


@pytest.mark.unit
@pytest.mark.django_db
def test_sync_database_tasks_skips_flag_disabled_task(user, mock_apscheduler):
    import apps.tasks.cron_scheduler as cs
    from apps.dynamic_settings.models import Setting
    from apps.tasks.models import Task

    Setting.objects.get_or_create(setting_key="SYNC_SKIP_FLAG", defaults={"current_value": "false"})
    task = Task.objects.create(
        name="flagged_rec",
        function_name="hello_world",
        task_data={"_feature_flag": "SYNC_SKIP_FLAG"},
        cron_expression="0 * * * *",
        created_by=user,
        status="pending",
    )

    scheduler = cs.UnifiedTaskScheduler()
    scheduler.scheduler = mock_apscheduler
    scheduler._sync_database_tasks()

    # Task should NOT be in jobs because flag is disabled
    assert task.id not in scheduler._db_task_jobs


# ---------------------------------------------------------------------------
# _periodic_database_sync — immediate tasks
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_periodic_sync_handles_immediate_tasks(user, mock_apscheduler):
    import apps.tasks.cron_scheduler as cs
    from apps.tasks.models import Task

    task = Task.objects.create(
        name="immediate_task",
        function_name="hello_world",
        task_data={},
        created_by=user,
        status="pending",
    )

    scheduler = cs.UnifiedTaskScheduler()
    scheduler.scheduler = mock_apscheduler
    scheduler.running = True

    with (
        patch("apps.tasks.cron_scheduler.close_old_connections"),
        patch("apps.tasks.utils.awx_db_ready", return_value=True),
        patch.object(scheduler, "_execute_database_task") as mock_execute,
        patch("apps.tasks.models.Task.scheduled_tasks", return_value=Task.objects.none()),
        patch("apps.tasks.models.Task.recurring_tasks", return_value=Task.objects.none()),
    ):
        scheduler._periodic_database_sync()

    # Immediate task should have been submitted
    assert mock_execute.called or task.id in scheduler._db_task_jobs


# ---------------------------------------------------------------------------
# _execute_database_task — feature flag disabled for recurring
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_execute_database_task_flag_disabled_skips_recurse(user, mock_apscheduler):
    import apps.tasks.cron_scheduler as cs
    from apps.dynamic_settings.models import Setting
    from apps.tasks.models import Task

    Setting.objects.get_or_create(setting_key="EXEC_FLAG_OFF", defaults={"current_value": "false"})
    task = Task.objects.create(
        name="flagged_task",
        function_name="hello_world",
        task_data={"_feature_flag": "EXEC_FLAG_OFF"},
        cron_expression="0 * * * *",
        created_by=user,
        status="pending",
    )

    scheduler = cs.UnifiedTaskScheduler()
    scheduler.scheduler = mock_apscheduler
    scheduler._db_task_jobs[task.id] = f"db_recurring_{task.id}"

    with (
        patch("apps.tasks.cron_scheduler.close_old_connections"),
        patch("apps.tasks.tasks_system.submit_task_to_dispatcher") as mock_submit,
    ):
        scheduler._execute_database_task(task.id)

    # Should NOT submit when flag is disabled
    mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# _execute_database_task — pending non-recurring task success
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_execute_database_task_pending_non_recurring(user, mock_apscheduler, mock_dispatcherd_config):
    import apps.tasks.cron_scheduler as cs
    from apps.tasks.models import Task

    task = Task.objects.create(
        name="pending_exec",
        function_name="hello_world",
        task_data={},
        created_by=user,
        status="pending",
    )
    scheduler = cs.UnifiedTaskScheduler()
    scheduler.scheduler = mock_apscheduler
    scheduler._db_task_jobs[task.id] = f"db_task_{task.id}"

    with (
        patch("apps.tasks.cron_scheduler.close_old_connections"),
        patch("apps.tasks.tasks_system.submit_task_to_dispatcher") as mock_submit,
    ):
        scheduler._execute_database_task(task.id)

    mock_submit.assert_called_once_with(task)
    assert task.id not in scheduler._db_task_jobs  # Removed after submission
