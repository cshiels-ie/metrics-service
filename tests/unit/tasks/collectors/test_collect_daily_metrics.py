"""
Unit tests for apps/tasks/collectors/collect_daily_metrics.py

Tests cover:
- _get_daily_collectors: registry returns expected keys
- collect_daily_metrics: missing collector_type raises ValueError
- collect_daily_metrics: invalid since/until strings raise ValueError
- collect_daily_metrics: default since/until window (previous full day)
- collect_daily_metrics: explicit since/until strings parsed correctly
- collect_daily_metrics: collection_timestamp stored at 23:00 of since day
- collect_daily_metrics: success path delegates to generic_collect_metrics
- collect_daily_metrics: error propagation when generic_collect_metrics raises
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_utc(year, month, day, hour=0, minute=0, second=0):
    """Return a timezone-aware UTC datetime."""
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Tests for _get_daily_collectors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetDailyCollectors:
    """Tests for the _get_daily_collectors registry factory."""

    def test_returns_task_executions_service_key(self):
        """Registry must contain the 'task_executions_service' entry."""
        with (
            patch("metrics_utility.anonymized_rollups.TaskExecutionsAnonymizedRollup", MagicMock()),
            patch("metrics_utility.library.collectors.service.task_executions_service", MagicMock()),
        ):
            from apps.tasks.collectors.collect_daily_metrics import _get_daily_collectors

            registry = _get_daily_collectors()

        assert "task_executions_service" in registry

    def test_registry_entry_has_required_keys(self):
        """Each registry entry must have collector_func, rollup_processor, description."""
        with (
            patch("metrics_utility.anonymized_rollups.TaskExecutionsAnonymizedRollup", MagicMock()),
            patch("metrics_utility.library.collectors.service.task_executions_service", MagicMock()),
        ):
            from apps.tasks.collectors.collect_daily_metrics import _get_daily_collectors

            registry = _get_daily_collectors()

        entry = registry["task_executions_service"]
        assert "collector_func" in entry
        assert "rollup_processor" in entry
        assert "description" in entry


# ---------------------------------------------------------------------------
# Tests for collect_daily_metrics
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestCollectDailyMetrics:
    """Tests for the collect_daily_metrics task function."""

    # ------------------------------------------------------------------
    # Validation – missing / invalid parameters
    # ------------------------------------------------------------------

    def test_returns_error_when_collector_type_missing(self):
        """collect_daily_metrics returns error dict when collector_type is absent."""
        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        result = collect_daily_metrics()

        assert result["status"] == "error"
        assert "collector_type parameter is required" in result["error"]

    def test_returns_error_when_collector_type_empty_string(self):
        """collect_daily_metrics returns error dict for empty collector_type."""
        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        result = collect_daily_metrics(collector_type="")

        assert result["status"] == "error"
        assert "collector_type parameter is required" in result["error"]

    def test_returns_error_for_invalid_since_string(self):
        """collect_daily_metrics returns error dict for unparseable since."""
        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        result = collect_daily_metrics(collector_type="task_executions_service", since="not-a-date")

        assert result["status"] == "error"
        assert "Invalid since format" in result["error"]

    def test_returns_error_for_invalid_until_string(self):
        """collect_daily_metrics returns error dict for unparseable until."""
        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        result = collect_daily_metrics(
            collector_type="task_executions_service",
            since="2024-01-15T00:00:00+00:00",
            until="bad-date",
        )

        assert result["status"] == "error"
        assert "Invalid until format" in result["error"]

    # ------------------------------------------------------------------
    # Default time window (no since/until provided)
    # ------------------------------------------------------------------

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_default_window_covers_previous_full_day(self, mock_registry, mock_get_db, mock_generic):
        """Without since/until the window should be yesterday 00:00 → today 00:00 UTC."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        fixed_now = _make_utc(2024, 3, 10, 14, 30, 0)

        with patch("apps.tasks.collectors.collect_daily_metrics.timezone") as mock_tz:
            mock_tz.now.return_value = fixed_now

            from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

            collect_daily_metrics(collector_type="task_executions_service")

        call_kwargs = mock_generic.call_args.kwargs
        expected_since = _make_utc(2024, 3, 9, 0, 0, 0)
        expected_until = _make_utc(2024, 3, 10, 0, 0, 0)

        assert call_kwargs["collector_kwargs"]["since"] == expected_since
        assert call_kwargs["collector_kwargs"]["until"] == expected_until

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_collection_timestamp_is_since_at_23h(self, mock_registry, mock_get_db, mock_generic):
        """collection_timestamp must equal the since date at 23:00 UTC."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        fixed_now = _make_utc(2024, 3, 10, 14, 30, 0)

        with patch("apps.tasks.collectors.collect_daily_metrics.timezone") as mock_tz:
            mock_tz.now.return_value = fixed_now

            from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

            collect_daily_metrics(collector_type="task_executions_service")

        call_kwargs = mock_generic.call_args.kwargs
        expected_ts = _make_utc(2024, 3, 9, 23, 0, 0)
        assert call_kwargs["timestamp"] == expected_ts

    # ------------------------------------------------------------------
    # Explicit since / until strings
    # ------------------------------------------------------------------

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_explicit_since_until_parsed_correctly(self, mock_registry, mock_get_db, mock_generic):
        """Explicit ISO since/until strings must be parsed and forwarded."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(
            collector_type="task_executions_service",
            since="2024-01-15T00:00:00+00:00",
            until="2024-01-16T00:00:00+00:00",
        )

        call_kwargs = mock_generic.call_args.kwargs
        assert call_kwargs["collector_kwargs"]["since"] == _make_utc(2024, 1, 15, 0, 0, 0)
        assert call_kwargs["collector_kwargs"]["until"] == _make_utc(2024, 1, 16, 0, 0, 0)

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_explicit_since_with_z_suffix(self, mock_registry, mock_get_db, mock_generic):
        """'Z' suffix in ISO strings must be accepted (parsed as UTC)."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(
            collector_type="task_executions_service",
            since="2024-01-15T00:00:00Z",
            until="2024-01-16T00:00:00Z",
        )

        call_kwargs = mock_generic.call_args.kwargs
        assert call_kwargs["collector_kwargs"]["since"] == _make_utc(2024, 1, 15)
        assert call_kwargs["collector_kwargs"]["until"] == _make_utc(2024, 1, 16)

    # ------------------------------------------------------------------
    # generic_collect_metrics wiring
    # ------------------------------------------------------------------

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_passes_daily_collection_mode(self, mock_registry, mock_get_db, mock_generic):
        """collection_mode='daily' must be passed to generic_collect_metrics."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(collector_type="task_executions_service")

        assert mock_generic.call_args.kwargs["collection_mode"] == "daily"

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_uses_per_collector_db_connection(self, mock_registry, mock_get_db, mock_generic):
        """get_db_connection uses the database field from the collector registry entry."""
        mock_registry.return_value = {"task_executions_service": {"database": "default"}}
        fake_conn = MagicMock()
        mock_get_db.return_value = fake_conn
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(collector_type="task_executions_service")

        mock_get_db.assert_called_once_with("default")
        assert mock_generic.call_args.kwargs["db_connection"] is fake_conn

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_passes_execution_id_when_provided(self, mock_registry, mock_get_db, mock_generic):
        """execution_id kwarg must be forwarded as task_execution_id."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(collector_type="task_executions_service", execution_id=42)

        assert mock_generic.call_args.kwargs["task_execution_id"] == 42

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_returns_generic_collect_metrics_result(self, mock_registry, mock_get_db, mock_generic):
        """Return value of generic_collect_metrics must be propagated unchanged."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        expected = {"status": "success", "collection_id": 99, "task_type": "collect_task_executions_service"}
        mock_generic.return_value = expected

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        result = collect_daily_metrics(collector_type="task_executions_service")

        assert result is expected

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_passes_collector_type_to_generic(self, mock_registry, mock_get_db, mock_generic):
        """collector_type must be forwarded verbatim to generic_collect_metrics."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(collector_type="task_executions_service")

        assert mock_generic.call_args.kwargs["collector_type"] == "task_executions_service"

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_passes_registry_to_generic(self, mock_registry, mock_get_db, mock_generic):
        """The registry returned by _get_daily_collectors must be forwarded."""
        registry = {"task_executions_service": {"collector_func": MagicMock()}}
        mock_registry.return_value = registry
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        collect_daily_metrics(collector_type="task_executions_service")

        assert mock_generic.call_args.kwargs["collector_registry"] is registry

    # ------------------------------------------------------------------
    # task_execution_wrapper error handling
    # ------------------------------------------------------------------

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_raises_when_generic_raises(self, mock_registry, mock_get_db, mock_generic):
        """When generic_collect_metrics raises, the exception propagates."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.side_effect = RuntimeError("upstream failure")

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        with pytest.raises(RuntimeError, match="upstream failure"):
            collect_daily_metrics(collector_type="task_executions_service")

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_raises_when_db_connection_raises(self, mock_registry, mock_get_db, mock_generic):
        """When get_db_connection raises, the exception propagates."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.side_effect = Exception("DB unavailable")

        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        with pytest.raises(Exception, match="DB unavailable"):
            collect_daily_metrics(collector_type="task_executions_service")
        mock_generic.assert_not_called()

    # ------------------------------------------------------------------
    # Scheduler-injected hour_timestamp (retry-safety)
    # ------------------------------------------------------------------

    def test_returns_error_for_invalid_hour_timestamp(self):
        """collect_daily_metrics returns error dict for an unparseable hour_timestamp."""
        from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

        result = collect_daily_metrics(
            collector_type="task_executions_service",
            hour_timestamp="not-a-date",
        )

        assert result["status"] == "error"
        assert "Invalid hour_timestamp format" in result["error"]

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_uses_injected_hour_timestamp_as_today_midnight(self, mock_registry, mock_get_db, mock_generic):
        """When hour_timestamp is supplied it is used as today_midnight, not timezone.now()."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        # hour_timestamp represents today's midnight at dispatch time (2024-03-10 00:00 UTC)
        injected_midnight = "2024-03-10T00:00:00+00:00"

        with patch("apps.tasks.collectors.collect_daily_metrics.timezone") as mock_tz:
            # Wall clock is now the *next* day — must not affect the window
            mock_tz.now.return_value = _make_utc(2024, 3, 11, 2, 0, 0)

            from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

            collect_daily_metrics(
                collector_type="task_executions_service",
                hour_timestamp=injected_midnight,
            )

        call_kwargs = mock_generic.call_args.kwargs
        expected_since = _make_utc(2024, 3, 9, 0, 0, 0)
        expected_until = _make_utc(2024, 3, 10, 0, 0, 0)

        assert call_kwargs["collector_kwargs"]["since"] == expected_since
        assert call_kwargs["collector_kwargs"]["until"] == expected_until

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_retry_with_injected_timestamp_ignores_wall_clock(self, mock_registry, mock_get_db, mock_generic):
        """A retry that carries hour_timestamp must collect the originally intended day even if
        wall-clock now has advanced past midnight into the next calendar day."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        # Task was dispatched on 2024-03-10 (midnight = 2024-03-10T00:00:00Z)
        injected_midnight = "2024-03-10T00:00:00+00:00"

        with patch("apps.tasks.collectors.collect_daily_metrics.timezone") as mock_tz:
            # Retry happens after midnight — wall clock is now 2024-03-11
            mock_tz.now.return_value = _make_utc(2024, 3, 11, 0, 5, 0)

            from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

            result = collect_daily_metrics(
                collector_type="task_executions_service",
                hour_timestamp=injected_midnight,
            )

        assert result["status"] == "success"

        call_kwargs = mock_generic.call_args.kwargs
        # Window must still cover 2024-03-09 → 2024-03-10, not 2024-03-10 → 2024-03-11
        assert call_kwargs["collector_kwargs"]["since"] == _make_utc(2024, 3, 9, 0, 0, 0)
        assert call_kwargs["collector_kwargs"]["until"] == _make_utc(2024, 3, 10, 0, 0, 0)

    @patch("apps.tasks.collectors.collect_daily_metrics.generic_collect_metrics")
    @patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection")
    @patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors")
    def test_timezone_now_not_called_when_hour_timestamp_provided(self, mock_registry, mock_get_db, mock_generic):
        """timezone.now() must not be consulted when hour_timestamp is already present."""
        mock_registry.return_value = {"task_executions_service": {}}
        mock_get_db.return_value = MagicMock()
        mock_generic.return_value = {"status": "success"}

        with patch("apps.tasks.collectors.collect_daily_metrics.timezone") as mock_tz:
            from apps.tasks.collectors.collect_daily_metrics import collect_daily_metrics

            collect_daily_metrics(
                collector_type="task_executions_service",
                hour_timestamp="2024-03-10T00:00:00+00:00",
            )

        mock_tz.now.assert_not_called()
