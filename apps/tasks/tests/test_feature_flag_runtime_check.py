"""
Tests for runtime feature flag checking in task scheduler.

The implementation reads _feature_flag from task.task_data (live DB) at execution time
in _execute_database_task. All DB access is mocked here so these tests
do not require @pytest.mark.django_db.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.tasks.cron_scheduler import UnifiedTaskScheduler


def _make_mock_task(task_id=42, task_data=None, status="pending", cron_expression="0 * * * *"):
    """Return a MagicMock resembling a Task DB object."""
    mock_task = MagicMock()
    mock_task.id = task_id
    mock_task.name = f"test_task_{task_id}"
    mock_task.task_data = task_data if task_data is not None else {}
    mock_task.status = status
    mock_task.cron_expression = cron_expression
    mock_task.function_name = "hello_world"
    mock_task.max_attempts = 3
    mock_task.created_by = None
    mock_task.is_system_task = True
    return mock_task


@pytest.mark.unit
class TestFeatureFlagRuntimeCheck:
    """Test runtime feature flag checking for task execution.

    _execute_database_task reads _feature_flag from the live DB task record so that
    toggling the flag takes effect immediately without restarting the scheduler or
    re-running init-system-tasks.
    """

    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db")
    @patch("apps.tasks.models.Task")
    def test_task_executes_when_feature_flag_enabled(self, mock_task_cls, mock_get_feature, mock_submit):
        """Task is submitted when its feature flag is enabled."""
        mock_get_feature.return_value = True
        mock_task = _make_mock_task(task_id=1, task_data={"_feature_flag": "ANONYMIZED_DATA_COLLECTION"})
        mock_task_cls.objects.get.return_value = mock_task
        mock_task_cls.objects.create.return_value = MagicMock(id=100, name="execution_copy")

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(1)

        mock_get_feature.assert_called_once_with("ANONYMIZED_DATA_COLLECTION")
        mock_submit.assert_called_once()

    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db")
    @patch("apps.tasks.models.Task")
    def test_task_skips_when_feature_flag_disabled(self, mock_task_cls, mock_get_feature, mock_submit):
        """Task is NOT dispatched when its feature flag is disabled in the DB."""
        mock_get_feature.return_value = False
        mock_task_cls.objects.get.return_value = _make_mock_task(
            task_data={"_feature_flag": "ANONYMIZED_DATA_COLLECTION"}
        )

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(42)

        mock_get_feature.assert_called_once_with("ANONYMIZED_DATA_COLLECTION")
        mock_submit.assert_not_called()

    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db")
    @patch("apps.tasks.models.Task")
    def test_recurring_task_skips_when_metrics_collection_disabled(self, mock_task_cls, mock_get_feature, mock_submit):
        """Recurring metrics template is not dispatched when METRICS_COLLECTION is false."""
        mock_get_feature.return_value = False
        mock_task = _make_mock_task(
            task_id=7,
            task_data={"_feature_flag": "METRICS_COLLECTION"},
            cron_expression="5 * * * *",
        )
        mock_task_cls.objects.get.return_value = mock_task

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(7)

        mock_get_feature.assert_called_once_with("METRICS_COLLECTION")
        mock_submit.assert_not_called()
        mock_task_cls.objects.create.assert_not_called()

    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    @patch("apps.tasks.models.Task")
    def test_task_executes_when_no_feature_flag(self, mock_task_cls, mock_submit):
        """Task executes without a feature flag check when task_data has no _feature_flag."""
        mock_task = _make_mock_task(task_id=5, task_data={})
        mock_task_cls.objects.get.return_value = mock_task
        mock_task_cls.objects.create.return_value = MagicMock(id=100, name="execution_copy")

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(5)

        mock_submit.assert_called_once()

    @pytest.mark.django_db
    @override_settings(FEATURE={"METRICS_COLLECTION": True, "ANONYMIZED_DATA_COLLECTION": True})
    def test_get_all_enabled_tasks_includes_feature_flag(self):
        """get_all_enabled_tasks propagates each group's feature_flag into task configs."""
        from apps.tasks.task_groups import ANONYMIZATION_GROUP, METRICS_COLLECTION_GROUP, get_all_enabled_tasks

        all_tasks = get_all_enabled_tasks()

        for task in METRICS_COLLECTION_GROUP.tasks:
            task_id = task["task_id"]
            if task_id in all_tasks:
                assert "feature_flag" in all_tasks[task_id]
                assert all_tasks[task_id]["feature_flag"] == "METRICS_COLLECTION"

        for task in ANONYMIZATION_GROUP.tasks:
            task_id = task["task_id"]
            if task_id in all_tasks:
                assert all_tasks[task_id]["feature_flag"] == "ANONYMIZED_DATA_COLLECTION"

    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db")
    @patch("apps.tasks.models.Task")
    def test_feature_flag_checked_at_execution_time(self, mock_task_cls, mock_get_feature, mock_submit):
        """Flag is re-read from DB on each fire so runtime changes take effect immediately."""
        mock_task = _make_mock_task(task_id=10, task_data={"_feature_flag": "ANONYMIZED_DATA_COLLECTION"})
        mock_task_cls.objects.get.return_value = mock_task
        mock_task_cls.objects.create.return_value = MagicMock(id=100, name="execution_copy")

        scheduler = UnifiedTaskScheduler()

        # First fire — flag enabled
        mock_get_feature.return_value = True
        scheduler._execute_database_task(10)
        assert mock_submit.call_count == 1

        # Second fire — flag disabled at runtime, no restart needed
        mock_get_feature.return_value = False
        scheduler._execute_database_task(10)
        assert mock_submit.call_count == 1  # Not incremented

    @patch("apps.tasks.tasks_system.submit_task_to_dispatcher")
    @patch("apps.tasks.task_groups.get_feature_enabled_from_db")
    @patch("apps.tasks.models.Task")
    def test_feature_flag_error_prevents_execution(self, mock_task_cls, mock_get_feature, mock_submit):
        """Errors reading the feature flag are caught by the outer try/except; task is not dispatched."""
        mock_get_feature.side_effect = Exception("Database error")
        mock_task_cls.objects.get.return_value = _make_mock_task(
            task_data={"_feature_flag": "ANONYMIZED_DATA_COLLECTION"}
        )

        scheduler = UnifiedTaskScheduler()
        scheduler._execute_database_task(42)

        mock_submit.assert_not_called()
