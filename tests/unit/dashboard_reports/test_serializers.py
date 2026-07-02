import datetime

import pytest

from apps.dashboard_reports.serializers import (
    ChartDataItemSerializer,
    FilterOptionWithIdSerializer,
    ReportChartSerializer,
    ReportDetailSerializer,
    ReportSerializer,
    TopProjectSerializer,
    TopUserSerializer,
)
from apps.dashboard_reports.utils import sec2time


@pytest.mark.unit
class TestFilterOptionWithIdSerializer:
    """
    Unit tests for FilterOptionWithIdSerializer.
    Tests validation for correct, missing, and invalid 'id' field.
    """

    def test_valid_data(self):
        # Test serializer with valid data
        data = {"id": 1, "name": "Option"}
        serializer = FilterOptionWithIdSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["id"] == 1
        assert serializer.validated_data["name"] == "Option"

    def test_invalid_data_missing_id(self):
        # Test serializer with missing 'id' field
        data = {"name": "Option"}
        serializer = FilterOptionWithIdSerializer(data=data)
        assert not serializer.is_valid()
        assert "id" in serializer.errors

    def test_invalid_data_wrong_type(self):
        # Test serializer with 'id' field of wrong type
        data = {"id": "not-an-int", "name": "Option"}
        serializer = FilterOptionWithIdSerializer(data=data)
        assert not serializer.is_valid()
        assert "id" in serializer.errors


@pytest.mark.unit
class TestReportSerializer:
    """
    Unit tests for ReportSerializer.
    Tests serialization, method fields, and edge cases for JobData-like input.
    """

    @pytest.fixture
    def mock_job_data(self):
        # Mock the ValuesQuerySet dict produced by _build_aggregated_queryset.
        # template_name is sourced from the FK traversal key (template_metadata__template_name),
        # not the denormalized JobData.template_name field.
        return {
            "template_metadata__template_name": "Test Template",
            "template_metadata_id": 123,
            "time_taken_manually_execute_minutes": 30,
            "time_taken_create_automation_minutes": 60,
            "runs": 10,
            "successful_runs": 8,
            "failed_runs": 2,
            "elapsed": 3661,
            "automated_costs": 100.50,
            "manual_costs": 200.75,
            "time_savings": 7200,
            "savings": 100.25,
        }

    def test_serializers_fields(self, mock_job_data):
        # Test serialization of all fields

        serializer = ReportSerializer(mock_job_data)
        data = serializer.data
        assert data["template_name"] == "Test Template"
        assert data["id"] == 123
        assert data["runs"] == 10
        assert data["successful_runs"] == 8
        assert data["failed_runs"] == 2
        # Adjusted: elapsed is returned as string/decimal
        assert str(data["elapsed"]) in ("3661.00", "3661")
        assert data["elapsed_str"] == "1h 1min 1sec"
        assert str(data["time_savings"]) in ("7200.00", "7200")
        assert data["time_savings_str"] == "2h 0min 0sec"
        assert float(data["automated_costs"]) == 100.50
        assert float(data["manual_costs"]) == 200.75
        assert float(data["savings"]) == 100.25

    def test_elapsed_str_none(self, mock_job_data):
        # Provide all required fields, set elapsed/time_savings to None

        job_data = mock_job_data.copy()
        job_data["elapsed"] = None
        job_data["time_savings"] = None
        serializer = ReportSerializer(job_data)
        data = serializer.data
        assert data["elapsed_str"] == ""
        assert data["time_savings_str"] == ""

    def test_missing_fields(self):
        # Test serializer with missing optional fields

        job_data = {
            "template_metadata__template_name": "Missing Fields",
            "id": 1,
            "elapsed": 3600,
            "time_savings": 3600,
        }
        serializer = ReportSerializer(job_data)
        data = serializer.data
        assert data["template_name"] == "Missing Fields"
        assert data["elapsed_str"] == "1h 0min 0sec"
        assert data["time_savings_str"] == "1h 0min 0sec"

    def test_sec2time_negative_seconds(self):
        # Negative seconds are treated as their absolute value (time savings can go negative
        # during aggregation; we render the magnitude without a sign).
        assert sec2time(-1) == "0min 1sec"

    def test_sec2time_various(self):
        # Test sec2time utility function

        assert sec2time(3661) == "1h 1min 1sec"
        assert sec2time(59) == "0min 59sec"
        assert sec2time(3600) == "1h 0min 0sec"
        assert sec2time(0) == "0min 0sec"


@pytest.mark.unit
class TestTopUserSerializer:
    """
    Unit tests for TopUserSerializer.
    Tests serialization of user job execution stats and edge cases.
    """

    def test_valid_representation(self):
        # Test serializer output with valid user data
        obj = {"launched_by_id": 42, "launched_by_username": "alice", "count": 7}
        serializer = TopUserSerializer(obj)
        data = serializer.data
        assert data["id"] == 42
        assert data["name"] == "alice"
        assert data["execution_count"] == 7

    def test_missing_fields_representation(self):
        # Test serializer output with missing fields
        obj = {"launched_by_id": 1}
        serializer = TopUserSerializer(obj)
        data = serializer.data
        # Missing fields should not be present in output
        assert data["id"] == 1
        assert "name" not in data
        assert "execution_count" not in data

    def test_none_values_representation(self):
        # Test serializer output with None values

        obj = {"launched_by_id": None, "launched_by_username": None, "count": None}
        serializer = TopUserSerializer(obj)
        data = serializer.data
        assert data["id"] is None
        assert data["name"] is None
        assert data["execution_count"] is None


@pytest.mark.unit
class TestTopProjectSerializer:
    """
    Unit tests for TopProjectSerializer.
    Tests serialization of project job execution stats and edge cases.
    """

    def test_valid_representation(self):
        # Test serializer output with valid project data
        obj = {"project_id": 101, "project_name": "ProjectX", "count": 15}
        serializer = TopProjectSerializer(obj)
        data = serializer.data
        assert data["id"] == 101
        assert data["name"] == "ProjectX"
        assert data["execution_count"] == 15

    def test_missing_fields_representation(self):
        # Test serializer output with missing fields
        obj = {"project_id": 101}
        serializer = TopProjectSerializer(obj)
        data = serializer.data
        # Missing fields should not be present in output
        assert data["id"] == 101
        assert "name" not in data
        assert "execution_count" not in data

    def test_none_values_representation(self):
        # Test serializer output with None values

        obj = {"project_id": None, "project_name": None, "count": None}
        serializer = TopProjectSerializer(obj)
        data = serializer.data
        assert data["id"] is None
        assert data["name"] is None
        assert data["execution_count"] is None


@pytest.mark.unit
class TestChartDataItemSerializer:
    """
    Unit tests for ChartDataItemSerializer.
    Tests serialization of chart data items and edge cases.
    """

    def test_valid_representation(self):
        # Test serializer output with valid chart data
        obj = {"label": datetime.datetime(2024, 3, 11, 12, 0, 0), "value": 42}
        serializer = ChartDataItemSerializer(obj)
        data = serializer.data
        assert "label" in data
        assert data["value"] == 42
        # Check ISO format for datetime
        assert data["label"].startswith("2024-03-11T12:00:00")

    def test_missing_fields_representation(self):
        # Test serializer output with missing fields
        obj = {"value": 99}
        serializer = ChartDataItemSerializer(obj)
        data = serializer.data
        assert "value" in data
        assert "label" not in data

    def test_none_values_representation(self):
        # Test serializer output with None values
        obj = {"label": None, "value": None}
        serializer = ChartDataItemSerializer(obj)
        data = serializer.data
        assert data["label"] is None
        assert data["value"] is None

    def test_invalid_types(self):
        # Test serializer raises ValueError for invalid types
        obj = {"label": "not-a-date", "value": "not-an-int"}
        serializer = ChartDataItemSerializer(obj)

        with pytest.raises(ValueError):
            _ = serializer.data


@pytest.mark.unit
class TestReportChartSerializer:
    """
    Unit tests for ReportChartSerializer.
    Tests serialization of chart series and edge cases.
    """

    def test_valid_representation(self):
        # Test serializer output with valid chart series data
        obj = {
            "kind": "day",
            "items": [
                {"label": datetime.datetime(2024, 3, 11, 12, 0, 0), "value": 10},
                {"label": datetime.datetime(2024, 3, 12, 12, 0, 0), "value": 20},
            ],
        }
        serializer = ReportChartSerializer(obj)
        data = serializer.data
        assert data["kind"] == "day"
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 2
        assert data["items"][0]["value"] == 10
        assert data["items"][1]["value"] == 20
        assert data["items"][0]["label"].startswith("2024-03-11T12:00:00")

    def test_missing_fields_representation(self):
        # Test serializer output with missing fields
        obj = {"items": []}
        serializer = ReportChartSerializer(obj)
        data = serializer.data
        assert "kind" not in data
        assert "items" in data
        assert data["items"] == []

    def test_none_values_representation(self):
        # Test serializer output with None values
        obj = {"kind": None, "items": None}
        serializer = ReportChartSerializer(obj)
        data = serializer.data
        assert data["kind"] is None
        assert data["items"] is None

    def test_empty_items(self):
        # Test serializer output with empty items list

        obj = {"kind": "month", "items": []}
        serializer = ReportChartSerializer(obj)
        data = serializer.data
        assert data["kind"] == "month"
        assert data["items"] == []


@pytest.mark.unit
class TestReportDetailSerializer:
    """
    Unit tests for ReportDetailSerializer.
    Tests serialization of report detail, method fields, and edge cases.
    """

    @pytest.fixture
    def mock_report_detail(self):
        # Mock input dict for serializer
        return {
            "total_runs": 100,
            "total_successful_runs": 90,
            "total_failed_runs": 10,
            "total_num_hosts": 50,
            "total_elapsed": 7200,  # 2 hours
            "total_automated_costs": 123.45,
            "total_manual_costs": 234.56,
            "total_savings": 111.11,
            "total_time_savings": 3600,  # 1 hour
            "total_number_of_unique_hosts": 25,
            "top_users": [
                {"launched_by_id": 1, "launched_by_username": "alice", "count": 10},
                {"launched_by_id": 2, "launched_by_username": "bob", "count": 8},
            ],
            "top_projects": [{"project_id": 101, "project_name": "ProjectX", "count": 15}],
            "job_chart": {
                "kind": "day",
                "items": [{"label": "2024-03-11T12:00:00", "value": 10}, {"label": "2024-03-12T12:00:00", "value": 20}],
            },
            "host_chart": {
                "kind": "day",
                "items": [{"label": "2024-03-11T12:00:00", "value": 5}, {"label": "2024-03-12T12:00:00", "value": 7}],
            },
        }

    def test_valid_representation(self, mock_report_detail):
        # Test serializer output with all fields
        serializer = ReportDetailSerializer(mock_report_detail)
        data = serializer.data
        assert data["total_number_of_job_runs"] == 100
        assert data["total_number_of_successful_jobs"] == 90
        assert data["total_number_of_failed_jobs"] == 10
        assert data["total_number_of_host_job_runs"] == 50
        assert data["total_hours_of_automation"] == 2.0
        assert data["cost_of_automated_execution"] == 123.45
        assert data["cost_of_manual_automation"] == 234.56
        assert data["total_saving"] == 111.11
        assert data["total_time_saving"] == 1.0
        assert data["total_number_of_unique_hosts"] == 25
        assert isinstance(data["top_users"], list)
        assert data["top_users"][0]["id"] == 1
        assert data["top_users"][1]["name"] == "bob"
        assert isinstance(data["top_projects"], list)
        assert data["top_projects"][0]["name"] == "ProjectX"
        assert isinstance(data["job_chart"], dict)
        assert data["job_chart"]["kind"] == "day"
        assert isinstance(data["host_chart"], dict)
        assert data["host_chart"]["items"][0]["value"] == 5

    def test_missing_fields_representation(self):
        # Test serializer output with missing fields
        obj = {"total_runs": 10}
        serializer = ReportDetailSerializer(obj)
        data = serializer.data
        assert data["total_number_of_job_runs"] == 10
        # Method fields should fallback to 0
        assert data["total_hours_of_automation"] == 0
        assert data["cost_of_automated_execution"] == 0
        assert data["cost_of_manual_automation"] == 0
        assert data["total_saving"] == 0
        assert data["total_time_saving"] == 0

    def test_none_values_representation(self, mock_report_detail):
        # Test serializer output with None values for method fields
        obj = mock_report_detail.copy()
        obj["total_elapsed"] = None
        obj["total_automated_costs"] = None
        obj["total_manual_costs"] = None
        obj["total_savings"] = None
        obj["total_time_savings"] = None
        serializer = ReportDetailSerializer(obj)
        data = serializer.data
        assert data["total_hours_of_automation"] == 0
        assert data["cost_of_automated_execution"] == 0
        assert data["cost_of_manual_automation"] == 0
        assert data["total_saving"] == 0
        assert data["total_time_saving"] == 0

    def test_empty_lists(self, mock_report_detail):
        # Test serializer output with empty lists for top_users, top_projects, charts

        obj = mock_report_detail.copy()
        obj["top_users"] = []
        obj["top_projects"] = []
        obj["job_chart"] = {"kind": "day", "items": []}
        obj["host_chart"] = {"kind": "day", "items": []}
        serializer = ReportDetailSerializer(obj)
        data = serializer.data
        assert data["top_users"] == []
        assert data["top_projects"] == []
        assert data["job_chart"]["items"] == []
        assert data["host_chart"]["items"] == []
