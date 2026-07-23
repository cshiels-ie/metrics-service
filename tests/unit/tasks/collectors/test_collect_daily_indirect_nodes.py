"""Unit tests for indirect_managed_nodes daily collector."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import psycopg2
import pytest
from psycopg2 import errors as pg_errors

from apps.tasks.collectors.collect_daily_metrics import _get_daily_collectors, collect_daily_metrics
from apps.tasks.models import HourlyMetricsCollection


@pytest.mark.unit
class TestIndirectManagedNodesDailyCollector:
    """Tests for indirect_managed_nodes daily collector."""

    def test_collector_registered_in_daily_registry(self):
        """indirect_managed_nodes is present in daily collector registry with correct DB."""
        registry = _get_daily_collectors()
        assert "indirect_managed_nodes" in registry
        entry = registry["indirect_managed_nodes"]
        assert entry.get("collector_func") is not None
        assert entry.get("rollup_processor") is not None
        assert entry.get("database") == "awx"
        assert "indirect" in entry.get("description", "").lower()

    def test_collector_not_in_snapshot_registry(self):
        """indirect_managed_nodes is NOT in the snapshot registry."""
        from apps.tasks.collectors.collect_snapshot_metrics import _get_snapshot_collectors

        registry = _get_snapshot_collectors()
        assert "indirect_managed_nodes" not in registry

    @pytest.mark.django_db
    def test_successful_collection_stores_grouped_data(self):
        """Collector stores org/collection grouped rollup data."""
        sample_data = pd.DataFrame(
            {
                "id": [1, 2],
                "host_name": ["host1", "host2"],
                "created": [datetime(2024, 1, 1, tzinfo=UTC)] * 2,
                "host_remote_id": [None, None],
                "organization_name": ["OrgA", "OrgA"],
                "events": ['["cisco.ios.ios_command"]', '["cisco.ios.ios_config"]'],
            }
        )

        mock_collector = MagicMock()
        mock_collector.gather.return_value = sample_data

        mock_rollup_processor = MagicMock()
        mock_rollup_processor.return_value.prepare.return_value = {
            "groups": {
                "OrgA||cisco.ios": {
                    "organization_name": "OrgA",
                    "collection": "cisco.ios",
                    "host_names": ["host1", "host2"],
                    "host_count": 2,
                },
            },
            "indirect_nodes_total": 2,
        }

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": mock_rollup_processor,
                "description": "Test collector",
                "database": "awx",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_daily_metrics(
                collector_type="indirect_managed_nodes",
                since="2024-01-01T00:00:00+00:00",
                until="2024-01-02T00:00:00+00:00",
            )

        assert result["status"] == "success"

        collection = HourlyMetricsCollection.objects.get(id=result["collection_id"])
        raw_data = collection.raw_data

        assert isinstance(raw_data, dict)
        assert raw_data["indirect_nodes_total"] == 2

    @pytest.mark.django_db
    def test_db_routing_uses_awx_database(self):
        """Collector routes to the AWX database, not the default metrics-service DB."""
        mock_collector = MagicMock()
        mock_collector.gather.return_value = pd.DataFrame()

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": _get_daily_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
                "database": "awx",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors", return_value=mock_registry),
            patch(
                "apps.tasks.collectors.collect_daily_metrics.get_db_connection", return_value=MagicMock()
            ) as mock_get_db,
        ):
            collect_daily_metrics(
                collector_type="indirect_managed_nodes",
                since="2024-01-01T00:00:00+00:00",
                until="2024-01-02T00:00:00+00:00",
            )

        mock_get_db.assert_called_once_with("awx")

    @pytest.mark.django_db
    def test_empty_result_set_succeeds(self):
        """Empty DataFrame collection completes without error."""
        mock_collector = MagicMock()
        mock_collector.gather.return_value = pd.DataFrame()

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": _get_daily_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
                "database": "awx",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_daily_metrics(
                collector_type="indirect_managed_nodes",
                since="2024-01-01T00:00:00+00:00",
                until="2024-01-02T00:00:00+00:00",
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
                "rollup_processor": _get_daily_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
                "database": "awx",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_daily_metrics(
                collector_type="indirect_managed_nodes",
                since="2024-01-01T00:00:00+00:00",
                until="2024-01-02T00:00:00+00:00",
            )

        assert result["status"] == "error"
        collection = HourlyMetricsCollection.objects.get(
            collector_type="indirect_managed_nodes",
        )
        assert collection.status == "failed"
        assert "main_indirectmanagednodeaudit" in collection.error_message

    @pytest.mark.django_db
    def test_db_connection_failure_records_error(self):
        """OperationalError from DB connection failure is recorded as failed."""

        def raise_connection_error(**kwargs):
            raise psycopg2.OperationalError("could not connect to server")

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": raise_connection_error,
                "rollup_processor": _get_daily_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
                "database": "awx",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_daily_metrics(
                collector_type="indirect_managed_nodes",
                since="2024-01-01T00:00:00+00:00",
                until="2024-01-02T00:00:00+00:00",
            )

        assert result["status"] == "error"
        collection = HourlyMetricsCollection.objects.get(
            collector_type="indirect_managed_nodes",
        )
        assert collection.status == "failed"
        assert "could not connect to server" in collection.error_message

    @pytest.mark.django_db
    def test_missing_collector_type_returns_error(self):
        """Missing collector_type parameter returns error."""
        result = collect_daily_metrics()

        assert result["status"] == "error"
        assert "collector_type" in result["error"]

    @pytest.mark.django_db
    def test_default_since_until_when_not_provided(self):
        """When no since/until provided, collector defaults to previous full calendar day."""
        mock_collector = MagicMock()
        mock_collector.gather.return_value = pd.DataFrame(
            {"id": [1], "host_name": ["host1"], "created": [datetime.now(UTC)]}
        )

        mock_registry = {
            "indirect_managed_nodes": {
                "collector_func": MagicMock(return_value=mock_collector),
                "rollup_processor": _get_daily_collectors()["indirect_managed_nodes"]["rollup_processor"],
                "description": "Test collector",
                "database": "awx",
            }
        }

        with (
            patch("apps.tasks.collectors.collect_daily_metrics._get_daily_collectors", return_value=mock_registry),
            patch("apps.tasks.collectors.collect_daily_metrics.get_db_connection", return_value=MagicMock()),
        ):
            result = collect_daily_metrics(collector_type="indirect_managed_nodes")

        assert result["status"] == "success"
        collection = HourlyMetricsCollection.objects.get(id=result["collection_id"])
        assert collection.collection_timestamp.hour == 23
        assert collection.collection_timestamp.minute == 0
        assert collection.collection_timestamp.second == 0
        assert collection.collection_timestamp.microsecond == 0
