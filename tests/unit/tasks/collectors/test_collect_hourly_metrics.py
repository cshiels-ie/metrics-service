"""Unit tests for collect_hourly_metrics — specifically _build_dashboard_sync_hook."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from apps.tasks.collectors.collect_hourly_metrics import (
    _build_dashboard_sync_hook,
    _get_hourly_collectors,
    _serialize_dashboard_record,
)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame matching the unified_jobs_dashboard schema."""
    defaults = {
        "id": 1,
        "name": "job",
        "unified_job_template_id": 10,
        "organization_id": 1,
        "organization_name": "Org",
        "started": datetime(2024, 1, 1, tzinfo=UTC),
        "finished": datetime(2024, 1, 1, 1, tzinfo=UTC),
        "status": "successful",
        "elapsed": 60.0,
        "launched_by_id": 5,
        "launched_by_username": "user",
        "project_id": 2,
        "project_name": "Project",
        "created": datetime(2024, 1, 1, tzinfo=UTC),
        "modified": datetime(2024, 1, 1, tzinfo=UTC),
        "label_ids": None,
        "num_hosts": 3,
        "launch_type": "manual",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


HOUR_TS = datetime(2024, 1, 1, tzinfo=UTC)

# Both are lazy imports inside function bodies, so patch at the source module.
FEATURE_FLAG_PATH = "apps.tasks.task_groups.get_feature_enabled_from_db"
TASK_MODEL_PATH = "apps.tasks.models.Task"


@pytest.mark.unit
class TestBuildDashboardSyncHook:
    """Tests for _build_dashboard_sync_hook and its returned inner hook."""

    def test_returns_none_when_feature_disabled(self):
        """When DASHBOARD_COLLECTION is off, the builder returns None."""
        with patch(FEATURE_FLAG_PATH, return_value=False):
            result = _build_dashboard_sync_hook(HOUR_TS)
        assert result is None

    def test_returns_callable_when_feature_enabled(self):
        """When DASHBOARD_COLLECTION is on, the builder returns a callable hook."""
        with patch(FEATURE_FLAG_PATH, return_value=True):
            hook = _build_dashboard_sync_hook(HOUR_TS)
        assert callable(hook)

    def _enabled_hook(self):
        """Build a hook with DASHBOARD_COLLECTION enabled."""
        with patch(FEATURE_FLAG_PATH, return_value=True):
            return _build_dashboard_sync_hook(HOUR_TS)

    def test_hook_returns_early_when_raw_data_none(self):
        """hook(None) exits immediately without touching Task."""
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            hook(None)
        mock_task.objects.update_or_create.assert_not_called()

    def test_hook_returns_early_when_dataframe_empty(self):
        """hook(empty_df) exits without creating a Task."""
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            hook(pd.DataFrame())
        mock_task.objects.update_or_create.assert_not_called()

    def test_hook_returns_early_when_no_terminal_jobs(self):
        """If all jobs are pending/running or are sync launches, no Task is created."""
        df = _make_df(
            [
                {"status": "running", "launch_type": "manual"},
                {"id": 2, "status": "successful", "launch_type": "sync"},
            ]
        )
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            hook(df)
        mock_task.objects.update_or_create.assert_not_called()

    def test_hook_creates_task_for_terminal_non_sync_jobs(self):
        """Terminal non-sync jobs cause update_or_create to be called."""
        df = _make_df(
            [
                {"status": "successful", "launch_type": "manual"},
                {"id": 2, "status": "failed", "launch_type": "scheduled"},
            ]
        )
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            mock_task.objects.update_or_create.return_value = (MagicMock(), True)
            hook(df)
        mock_task.objects.update_or_create.assert_called_once()
        call_kwargs = mock_task.objects.update_or_create.call_args[1]
        assert call_kwargs["defaults"]["function_name"] == "sync_dashboard_job_records"

    def test_hook_serialises_datetime_fields_to_iso(self):
        """Datetime columns are converted to ISO strings before being stored in task_data."""
        started = datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
        df = _make_df([{"status": "successful", "launch_type": "manual", "started": started}])
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            mock_task.objects.update_or_create.return_value = (MagicMock(), True)
            hook(df)
        task_data = mock_task.objects.update_or_create.call_args[1]["defaults"]["task_data"]
        raw_jobs = task_data["raw_jobs"]
        assert raw_jobs[0]["started"] == started.isoformat()

    def test_hook_converts_num_hosts_to_int(self):
        """num_hosts is cast to int if not None."""
        df = _make_df([{"status": "successful", "launch_type": "manual", "num_hosts": 7.0}])
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            mock_task.objects.update_or_create.return_value = (MagicMock(), True)
            hook(df)
        task_data = mock_task.objects.update_or_create.call_args[1]["defaults"]["task_data"]
        assert task_data["raw_jobs"][0]["num_hosts"] == 7
        assert isinstance(task_data["raw_jobs"][0]["num_hosts"], int)

    def test_hook_chunks_large_batches(self):
        """Records exceeding _SYNC_TASK_CHUNK_SIZE are split across multiple tasks."""
        from apps.tasks.collectors.collect_hourly_metrics import _SYNC_TASK_CHUNK_SIZE

        # Build a DataFrame with chunk_size + 1 terminal jobs to force two chunks.
        rows = [{"id": i, "status": "successful", "launch_type": "manual"} for i in range(_SYNC_TASK_CHUNK_SIZE + 1)]
        df = _make_df(rows)
        hook = self._enabled_hook()
        with patch(TASK_MODEL_PATH) as mock_task:
            mock_task.objects.update_or_create.return_value = (MagicMock(), True)
            hook(df)

        assert mock_task.objects.update_or_create.call_count == 2

        first_call = mock_task.objects.update_or_create.call_args_list[0]
        second_call = mock_task.objects.update_or_create.call_args_list[1]

        # Names must carry chunk index so update_or_create is idempotent on retry.
        assert first_call[1]["name"].endswith("_0")
        assert second_call[1]["name"].endswith("_1")

        # First chunk is full, second has the remainder.
        assert len(first_call[1]["defaults"]["task_data"]["raw_jobs"]) == _SYNC_TASK_CHUNK_SIZE
        assert len(second_call[1]["defaults"]["task_data"]["raw_jobs"]) == 1


@pytest.mark.unit
class TestSerializeDashboardRecord:
    """Branch-coverage tests for _serialize_dashboard_record."""

    def test_datetime_field_none_left_unchanged(self):
        """When a datetime field value is None the field is not modified (covers val-is-None branch)."""
        row = {"started": None, "finished": None, "created": None, "modified": None, "num_hosts": 5}
        _serialize_dashboard_record(row)
        assert row["started"] is None
        assert row["num_hosts"] == 5

    def test_num_hosts_none_left_unchanged(self):
        """When num_hosts is None the field is not modified (covers is-not-None False branch)."""
        row = {"started": datetime(2024, 1, 1, tzinfo=UTC), "num_hosts": None}
        _serialize_dashboard_record(row)
        assert row["num_hosts"] is None
        assert row["started"] == datetime(2024, 1, 1, tzinfo=UTC).isoformat()

    def test_datetime_already_a_string_has_no_isoformat(self):
        """A non-datetime value without isoformat is left unchanged (covers hasattr False branch)."""
        row = {"started": "2024-01-01T00:00:00+00:00", "num_hosts": 3}
        _serialize_dashboard_record(row)
        assert row["started"] == "2024-01-01T00:00:00+00:00"

    def test_numpy_int_fields_coerced_to_python_int(self):
        """numpy.int64 values in integer fields are coerced to Python int without raising."""
        import numpy as np

        row = {
            "id": np.int64(5),
            "organization_id": np.int64(3),
            "unified_job_template_id": np.int64(7),
            "launched_by_id": np.int64(1),
            "project_id": np.int64(2),
            "num_hosts": np.float64(4.0),
            "elapsed": np.float64(60.5),
            "started": None,
            "finished": None,
            "created": None,
            "modified": None,
        }
        _serialize_dashboard_record(row)
        for field in ("id", "organization_id", "unified_job_template_id", "launched_by_id", "project_id", "num_hosts"):
            assert isinstance(row[field], int), f"{field}: expected int, got {type(row[field])}"
        assert isinstance(row["elapsed"], float)

    def test_nan_in_nullable_int_fields_becomes_none(self):
        """NaN in nullable FK columns (from pandas float64 upcast) is converted to None, not int(nan) ValueError."""

        row = {
            "id": 1,
            "organization_id": float("nan"),
            "unified_job_template_id": float("nan"),
            "launched_by_id": None,
            "project_id": float("nan"),
            "num_hosts": 0,
            "elapsed": float("nan"),
            "started": None,
            "finished": None,
            "created": None,
            "modified": None,
        }
        _serialize_dashboard_record(row)
        assert row["organization_id"] is None
        assert row["unified_job_template_id"] is None
        assert row["launched_by_id"] is None
        assert row["project_id"] is None
        assert row["elapsed"] is None
        assert row["id"] == 1  # non-NaN int field unchanged


@pytest.mark.unit
class TestGenericCollectMetricsHook:
    """Tests for the post_collect_hook try/except block in generic_collect_metrics."""

    def _make_registry(self):
        """Return a minimal collector registry with a no-rollup test collector."""
        collector = MagicMock()
        collector.gather.return_value = MagicMock()
        return {
            "test_collector": {
                "collector_func": MagicMock(return_value=collector),
                "rollup_processor": None,
            }
        }

    @patch("apps.tasks.models.HourlyMetricsCollection")
    @patch("apps.tasks.utils.log_task_execution")
    def test_hook_is_called_with_raw_data(self, mock_log, mock_hmc):
        """When post_collect_hook is provided it receives raw_data from gather()."""
        from apps.tasks.utils import generic_collect_metrics

        mock_hmc.objects.update_or_create.return_value = (MagicMock(), True)
        registry = self._make_registry()
        raw_data = registry["test_collector"]["collector_func"].return_value.gather.return_value

        hook = MagicMock()
        generic_collect_metrics(
            collector_type="test_collector",
            collector_registry=registry,
            collection_mode="hourly",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            db_connection=MagicMock(),
            post_collect_hook=hook,
        )
        hook.assert_called_once_with(raw_data)

    @patch("apps.tasks.models.HourlyMetricsCollection")
    @patch("apps.tasks.utils.log_task_execution")
    def test_hook_exception_does_not_abort_collection(self, mock_log, mock_hmc):
        """A failing hook is logged and swallowed — the rollup pipeline still returns success."""
        from apps.tasks.utils import generic_collect_metrics

        mock_hmc.objects.update_or_create.return_value = (MagicMock(), True)
        registry = self._make_registry()

        def bad_hook(_):
            """Always raises to simulate a hook failure."""
            raise RuntimeError("hook failed")

        result = generic_collect_metrics(
            collector_type="test_collector",
            collector_registry=registry,
            collection_mode="hourly",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            db_connection=MagicMock(),
            post_collect_hook=bad_hook,
        )
        # Hook failure must not propagate to the caller — dashboard sync is secondary to
        # the anonymisation rollup pipeline that follows in the same collection task.
        assert result.get("status") == "success"

    @patch("apps.tasks.models.TaskExecution")
    @patch("apps.tasks.models.HourlyMetricsCollection")
    @patch("apps.tasks.utils.log_task_execution")
    def test_hook_exception_emits_warning_and_creates_task_execution(self, mock_log, mock_hmc, mock_te):
        """A failing hook emits a logger.warning and persists a failed TaskExecution when an execution is linked."""
        from apps.tasks.utils import generic_collect_metrics

        mock_hmc.objects.update_or_create.return_value = (MagicMock(), True)
        registry = self._make_registry()

        task_execution = MagicMock()

        def bad_hook(_):
            """Always raises to simulate a hook scheduling failure."""
            raise RuntimeError("scheduling error")

        with (
            patch("apps.tasks.utils.logger") as mock_logger,
            patch("apps.tasks.models.TaskExecution.objects.get", return_value=task_execution),
        ):
            generic_collect_metrics(
                collector_type="test_collector",
                collector_registry=registry,
                collection_mode="hourly",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                db_connection=MagicMock(),
                task_execution_id=42,
                post_collect_hook=bad_hook,
            )

        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args_list[0][0][0]
        assert "post_collect_hook failed" in warning_msg
        assert "scheduling error" in warning_msg
        mock_te.objects.create.assert_called_once()
        create_kwargs = mock_te.objects.create.call_args[1]
        assert create_kwargs["status"] == "failed"
        assert "scheduling error" in create_kwargs["error_message"]

    @patch("apps.tasks.models.HourlyMetricsCollection")
    @patch("apps.tasks.utils.log_task_execution")
    def test_hook_exception_skips_task_execution_when_no_execution_linked(self, mock_log, mock_hmc):
        """No TaskExecution is created when task_execution_id is not provided (task_execution_instance is None)."""
        from apps.tasks.utils import generic_collect_metrics

        mock_hmc.objects.update_or_create.return_value = (MagicMock(), True)
        registry = self._make_registry()

        def bad_hook(_):
            """Always raises to simulate a hook failure."""
            raise RuntimeError("hook failed")

        with patch("apps.tasks.models.TaskExecution") as mock_te:
            generic_collect_metrics(
                collector_type="test_collector",
                collector_registry=registry,
                collection_mode="hourly",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                db_connection=MagicMock(),
                post_collect_hook=bad_hook,
            )
        mock_te.objects.create.assert_not_called()

    @patch("apps.tasks.models.HourlyMetricsCollection")
    @patch("apps.tasks.utils.log_task_execution")
    def test_no_hook_skips_hook_block(self, mock_log, mock_hmc):
        """When post_collect_hook=None the hook block is skipped and collection succeeds."""
        from apps.tasks.utils import generic_collect_metrics

        mock_hmc.objects.update_or_create.return_value = (MagicMock(), True)
        registry = self._make_registry()

        result = generic_collect_metrics(
            collector_type="test_collector",
            collector_registry=registry,
            collection_mode="hourly",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            db_connection=MagicMock(),
            post_collect_hook=None,
        )
        assert result.get("status") == "success"


@pytest.mark.unit
class TestHourlyCollectorRegistry:
    """Pin the registry wiring so a key rename doesn't silently drop the hook."""

    def test_unified_jobs_uses_dashboard_collector_and_has_hook_factory(self):
        """unified_jobs entry must use unified_jobs_dashboard and register a post_collect_hook_factory."""
        with patch("metrics_utility.library.collectors.controller.unified_jobs_dashboard", create=True):
            registry = _get_hourly_collectors()

        entry = registry.get("unified_jobs")
        assert entry is not None, "unified_jobs key missing from hourly collector registry"
        assert entry.get("post_collect_hook_factory") is _build_dashboard_sync_hook, (
            "unified_jobs registry entry must wire _build_dashboard_sync_hook as post_collect_hook_factory"
        )
