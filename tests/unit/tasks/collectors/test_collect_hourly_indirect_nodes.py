"""Unit tests for indirect_managed_nodes hourly collector."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import psycopg2
import pytest
from psycopg2 import errors as pg_errors

from apps.tasks.collectors.collect_hourly_metrics import _get_hourly_collectors, collect_hourly_metrics
from apps.tasks.models import HourlyMetricsCollection


@pytest.mark.unit
class TestIndirectManagedNodesCollector:
    """Tests for indirect_managed_nodes hourly collector."""

    def test_collector_registered_in_hourly_registry(self):
        """indirect_managed_nodes is present in hourly collector registry."""
        registry = _get_hourly_collectors()
        assert "indirect_managed_nodes" in registry
        entry = registry["indirect_managed_nodes"]
        assert entry.get("collector_func") is not None
        assert entry.get("rollup_processor") is not None
        assert "indirect" in entry.get("description", "").lower()

    @pytest.mark.django_db
    def test_successful_collection_stores_deduplicated_host_ids(self):
        """Collector stores deduplicated host_remote_ids as a rollup dict."""
        sample_data = pd.DataFrame(
            {
                "id": [1, 2],
                "host_name": ["host1", "host2"],
                "created": [datetime(2024, 1, 1, tzinfo=UTC)] * 2,
                "host_remote_id": ["remote1", "remote2"],
            }
        )

        mock_collector = MagicMock()
        mock_collector.gather.return_value = sample_data

        mock_rollup_processor = MagicMock()
        mock_rollup_processor.return_value.prepare.return_value = {
            "indirect_node_ids": ["remote1", "remote2"],
            "indirect_nodes_total": 2,
        }

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": mock_rollup_processor,
                "description": "Test collector",
            }
        }

        ts = datetime(2024, 1, 1, tzinfo=UTC)
        with (
            patch("apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_hourly_metrics(
                collector_type="indirect_managed_nodes",
                hour_timestamp=ts.isoformat(),
            )

        assert result["status"] == "success"

        collection = HourlyMetricsCollection.objects.get(id=result["collection_id"])
        raw_data = collection.raw_data

        assert isinstance(raw_data, dict)
        assert raw_data["indirect_node_ids"] == ["remote1", "remote2"]
        assert raw_data["indirect_nodes_total"] == 2

    @pytest.mark.django_db
    def test_empty_result_set_succeeds(self):
        """Empty DataFrame collection completes without error."""
        empty_data = pd.DataFrame()

        mock_collector = MagicMock()
        mock_collector.gather.return_value = empty_data

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": _get_hourly_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
            }
        }

        ts = datetime(2024, 1, 1, tzinfo=UTC)
        with (
            patch("apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_hourly_metrics(
                collector_type="indirect_managed_nodes",
                hour_timestamp=ts.isoformat(),
            )

        assert result["status"] == "success"

        collection = HourlyMetricsCollection.objects.get(id=result["collection_id"])
        assert collection.status == "collected"

    @pytest.mark.django_db
    def test_missing_table_logs_error_and_fails_gracefully(self):
        """When table doesn't exist, error is logged and collection fails gracefully."""

        def raise_missing_table(**kwargs):
            raise pg_errors.ProgrammingError('relation "main_indirectmanagednodeaudit" does not exist')

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": raise_missing_table,
                "rollup_processor": _get_hourly_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
            }
        }

        ts = datetime(2024, 1, 1, tzinfo=UTC)
        with (
            patch("apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_hourly_metrics(
                collector_type="indirect_managed_nodes",
                hour_timestamp=ts.isoformat(),
            )

        assert result["status"] == "error"

        collection = HourlyMetricsCollection.objects.get(
            collector_type="indirect_managed_nodes",
            collection_timestamp=ts,
        )
        assert collection.status == "failed"
        assert "main_indirectmanagednodeaudit" in collection.error_message

    @pytest.mark.django_db
    def test_retry_with_same_timestamp_uses_existing_record(self):
        """Retry with same hour_timestamp returns existing collection due to unique constraint."""
        sample_data = pd.DataFrame(
            {
                "id": [1],
                "host_name": ["host1"],
                "created": [datetime(2024, 1, 1, tzinfo=UTC)],
            }
        )

        mock_collector = MagicMock()
        mock_collector.gather.return_value = sample_data

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": _get_hourly_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
            }
        }

        ts = datetime(2024, 1, 1, tzinfo=UTC)
        with (
            patch("apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result1 = collect_hourly_metrics(
                collector_type="indirect_managed_nodes",
                hour_timestamp=ts.isoformat(),
            )

            result2 = collect_hourly_metrics(
                collector_type="indirect_managed_nodes",
                hour_timestamp=ts.isoformat(),
            )

        assert result1["status"] == "success"
        assert result2["status"] == "success"
        assert result1["collection_id"] == result2["collection_id"]

        collection_count = HourlyMetricsCollection.objects.filter(
            collector_type="indirect_managed_nodes",
            collection_timestamp=ts,
        ).count()
        assert collection_count == 1

    @pytest.mark.django_db
    def test_invalid_timestamp_format_returns_error(self):
        """Invalid hour_timestamp format returns error without creating collection."""
        result = collect_hourly_metrics(
            collector_type="indirect_managed_nodes",
            hour_timestamp="not-a-date",
        )

        assert result["status"] == "error"
        assert "Invalid" in result["error"]

    @pytest.mark.django_db
    def test_missing_collector_type_returns_error(self):
        """Missing collector_type parameter returns error."""
        result = collect_hourly_metrics()

        assert result["status"] == "error"
        assert "collector_type" in result["error"]

    @pytest.mark.django_db
    def test_db_connection_failure_records_error(self):
        """OperationalError from DB connection failure is recorded as failed, not silently dropped.

        Distinct from ProgrammingError (missing table): ProgrammingError is caught and logged
        as a warning in the metrics-utility CLI layer. OperationalError bypasses that catch
        and must not be silently swallowed by the metrics-service task layer.
        """

        def raise_connection_error(**kwargs):
            raise psycopg2.OperationalError("could not connect to server")

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": raise_connection_error,
                "rollup_processor": _get_hourly_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
            }
        }

        ts = datetime(2024, 1, 1, tzinfo=UTC)
        with (
            patch("apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_hourly_metrics(
                collector_type="indirect_managed_nodes",
                hour_timestamp=ts.isoformat(),
            )

        assert result["status"] == "error"

        collection = HourlyMetricsCollection.objects.get(
            collector_type="indirect_managed_nodes",
            collection_timestamp=ts,
        )
        assert collection.status == "failed"
        assert "could not connect to server" in collection.error_message

    @pytest.mark.django_db
    def test_default_timestamp_when_not_provided(self):
        """When no timestamp provided, collector uses previous full hour."""
        sample_data = pd.DataFrame(
            {
                "id": [1],
                "host_name": ["host1"],
                "created": [datetime.now(UTC)],
            }
        )

        mock_collector = MagicMock()
        mock_collector.gather.return_value = sample_data

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": _get_hourly_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_hourly_metrics._get_hourly_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_hourly_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_hourly_metrics(collector_type="indirect_managed_nodes")

        assert result["status"] == "success"

        collection = HourlyMetricsCollection.objects.get(id=result["collection_id"])
        assert collection.collection_timestamp.minute == 0
        assert collection.collection_timestamp.second == 0
        assert collection.collection_timestamp.microsecond == 0
