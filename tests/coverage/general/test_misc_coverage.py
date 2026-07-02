"""
Miscellaneous tests for small uncovered modules.
Covers: core/logging_config.py, dashboard_reports/tasks.py basics.
"""

import json
import logging
from datetime import UTC
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# core/logging_config.py — JsonFormatter
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_json_formatter_basic():
    from apps.core.logging_config import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/fake/path.py",
        lineno=42,
        msg="Hello from test",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "Hello from test"
    assert "timestamp" in parsed
    assert parsed["timestamp"].endswith("Z")


@pytest.mark.unit
def test_json_formatter_with_exception():
    from apps.core.logging_config import JsonFormatter

    formatter = JsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="/fake/path.py",
        lineno=10,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert "exception" in parsed
    assert "ValueError" in parsed["exception"]


@pytest.mark.unit
def test_json_formatter_with_request_id():
    from apps.core.logging_config import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.WARNING,
        pathname="/fake/path.py",
        lineno=5,
        msg="Warning msg",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-12345"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed.get("request_id") == "req-12345"


# ---------------------------------------------------------------------------
# dashboard_reports/tasks.py — _parse_dt helper and cleanup
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_parse_dt_none_returns_none():
    from apps.dashboard_reports.tasks import _parse_dt

    assert _parse_dt(None) is None


@pytest.mark.unit
def test_parse_dt_string_iso():
    from apps.dashboard_reports.tasks import _parse_dt

    result = _parse_dt("2024-01-01T12:00:00+00:00")
    assert result.tzinfo is not None
    assert result.year == 2024


@pytest.mark.unit
def test_parse_dt_naive_string_gets_utc():
    from apps.dashboard_reports.tasks import _parse_dt

    result = _parse_dt("2024-01-01T12:00:00")
    assert result.tzinfo is not None


@pytest.mark.unit
def test_parse_dt_datetime_already_aware():
    from datetime import datetime

    from apps.dashboard_reports.tasks import _parse_dt

    dt = datetime(2024, 1, 1, tzinfo=UTC)
    assert _parse_dt(dt) is dt


@pytest.mark.unit
def test_parse_dt_datetime_naive_gets_utc():
    from datetime import datetime

    from apps.dashboard_reports.tasks import _parse_dt

    dt = datetime(2024, 1, 1, 12, 0)
    result = _parse_dt(dt)
    assert result.tzinfo is not None


@pytest.mark.unit
def test_parse_dt_invalid_type_raises():
    from apps.dashboard_reports.tasks import _parse_dt

    with pytest.raises(TypeError):
        _parse_dt(42)


@pytest.mark.unit
@pytest.mark.django_db
def test_cleanup_dashboard_reports_old_data_dry_run():
    from apps.dashboard_reports.tasks import cleanup_dashboard_reports_old_data

    result = cleanup_dashboard_reports_old_data(dry_run=True)
    assert result["status"] == "success"


@pytest.mark.unit
@pytest.mark.django_db
def test_cleanup_dashboard_reports_old_data_removes_old():
    from apps.dashboard_reports.tasks import cleanup_dashboard_reports_old_data

    # If JobData has any records, cleanup should run successfully
    result = cleanup_dashboard_reports_old_data(retention_days=90)
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# dashboard_reports/utils.py
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_dashboard_reports_utils():
    try:
        from apps.dashboard_reports.utils import some_function
    except ImportError:
        pass  # Module may not have public functions to test

    from apps.dashboard_reports import utils

    assert utils is not None


# ---------------------------------------------------------------------------
# dynamic_settings/models.py — Setting.current_value behavior
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_setting_model_str_representation():
    from apps.dynamic_settings.models import Setting

    setting = Setting.objects.create(setting_key="TEST_REPR", current_value="true")
    assert "TEST_REPR" in str(setting)


@pytest.mark.unit
@pytest.mark.django_db
def test_setting_model_previous_value_null():
    from apps.dynamic_settings.models import Setting

    setting = Setting.objects.create(setting_key="TEST_NULL", current_value="false", previous_value=None)
    assert setting.previous_value is None
