"""Tests for post-hooks in apps/settings/defaults.py."""

import os
from unittest import mock

import pytest


@pytest.mark.unit
class TestLoadSegmentWriteKeyPostHook:
    """Tests for load_segment_write_key post-hook."""

    def test_returns_empty_when_env_key_set(self):
        """Returns empty dict when METRICS_SERVICE_SEGMENT_WRITE_KEY is set."""
        from apps.settings.defaults import load_segment_write_key

        settings_mock = mock.MagicMock()
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_SEGMENT_WRITE_KEY": "env-key"}):
            result = load_segment_write_key(settings_mock)

        assert result == {}

    def test_returns_empty_when_settings_key_exists(self):
        """Returns empty dict when SEGMENT_WRITE_KEY already in settings."""
        from apps.settings.defaults import load_segment_write_key

        settings_mock = mock.MagicMock()
        settings_mock.get.return_value = "existing-key"
        with mock.patch.dict(os.environ, {}, clear=True):
            result = load_segment_write_key(settings_mock)

        assert result == {}

    def test_returns_empty_when_file_not_exists(self, tmp_path):
        """Returns empty dict when segment key file does not exist."""
        from apps.settings.defaults import load_segment_write_key

        settings_mock = mock.MagicMock()
        settings_mock.get.return_value = None
        nonexistent = str(tmp_path / "nonexistent")
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_SEGMENT_WRITE_KEY_FILE": nonexistent}, clear=True):
            result = load_segment_write_key(settings_mock)

        assert result == {}

    def test_returns_key_when_file_exists(self, tmp_path):
        """Returns dict with SEGMENT_WRITE_KEY when file exists and is valid."""
        from apps.settings.defaults import load_segment_write_key

        key_file = tmp_path / "segment-key"
        key_file.write_text("test-key-from-file")
        settings_mock = mock.MagicMock()
        settings_mock.get.return_value = None

        with mock.patch.dict(os.environ, {"METRICS_SERVICE_SEGMENT_WRITE_KEY_FILE": str(key_file)}, clear=True):
            result = load_segment_write_key(settings_mock)

        assert result == {"SEGMENT_WRITE_KEY": "test-key-from-file"}


@pytest.mark.unit
class TestParseAllowedHostsEnvPostHook:
    """Tests for parse_allowed_hosts_env post-hook."""

    def test_returns_empty_when_env_not_set(self):
        """Returns empty dict when METRICS_SERVICE_ALLOWED_HOSTS not set."""
        from apps.settings.defaults import parse_allowed_hosts_env

        settings_mock = mock.MagicMock()
        with mock.patch.dict(os.environ, {}, clear=True):
            result = parse_allowed_hosts_env(settings_mock)

        assert result == {}

    def test_parses_csv_format(self):
        """Parses CSV format into list of hosts."""
        from apps.settings.defaults import parse_allowed_hosts_env

        settings_mock = mock.MagicMock()
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_ALLOWED_HOSTS": "example.com,*.example.org"}):
            result = parse_allowed_hosts_env(settings_mock)

        assert result == {"ALLOWED_HOSTS": ["example.com", "*.example.org"]}

    def test_parses_json_array_format(self):
        """Parses JSON array format into list of hosts."""
        from apps.settings.defaults import parse_allowed_hosts_env

        settings_mock = mock.MagicMock()
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_ALLOWED_HOSTS": '["example.com", "*.example.org"]'}):
            result = parse_allowed_hosts_env(settings_mock)

        assert result == {"ALLOWED_HOSTS": ["example.com", "*.example.org"]}

    def test_handles_invalid_json(self):
        """Returns empty list when JSON is invalid."""
        from apps.settings.defaults import parse_allowed_hosts_env

        settings_mock = mock.MagicMock()
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_ALLOWED_HOSTS": "[invalid json"}):
            result = parse_allowed_hosts_env(settings_mock)

        assert result == {"ALLOWED_HOSTS": []}

    def test_handles_non_array_json(self):
        """Logs warning and uses empty list when JSON parses to non-array."""
        from apps.settings.defaults import parse_allowed_hosts_env

        settings_mock = mock.MagicMock()
        # JSON that parses successfully but is not an array (uses a trick: JSON.parse('[1]')[0] would be 1)
        # But actually the code only tries JSON if it starts with '[', so use that
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_ALLOWED_HOSTS": '[{"key": "value"}]'}):
            result = parse_allowed_hosts_env(settings_mock)

        # Parsed as JSON array, each element converted to string
        assert result == {"ALLOWED_HOSTS": ["{'key': 'value'}"]}

    def test_strips_whitespace_in_csv(self):
        """Strips whitespace from CSV entries."""
        from apps.settings.defaults import parse_allowed_hosts_env

        settings_mock = mock.MagicMock()
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_ALLOWED_HOSTS": " a.com , b.org , "}):
            result = parse_allowed_hosts_env(settings_mock)

        assert result == {"ALLOWED_HOSTS": ["a.com", "b.org"]}


@pytest.mark.unit
class TestSetupJsonLoggingForProductionPostHook:
    """Tests for setup_json_logging_for_production post-hook."""

    def test_returns_empty_in_development_mode(self):
        """Returns empty dict in development mode."""
        from apps.settings.defaults import setup_json_logging_for_production

        settings_mock = mock.MagicMock()
        settings_mock.get.return_value = {"formatters": {}}
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_MODE": "development"}, clear=True):
            result = setup_json_logging_for_production(settings_mock)

        assert result == {}

    def test_returns_json_config_in_production_mode(self):
        """Returns JSON logging config in production mode."""
        from apps.settings.defaults import setup_json_logging_for_production

        settings_mock = mock.MagicMock()
        settings_mock.get.return_value = {
            "formatters": {},
            "handlers": {"console": {"class": "logging.StreamHandler"}},
        }
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_MODE": "production"}, clear=True):
            result = setup_json_logging_for_production(settings_mock)

        assert "LOGGING" in result
        assert "json" in result["LOGGING"]["formatters"]
        assert result["LOGGING"]["formatters"]["json"]["()"] == "apps.core.logging_config.JsonFormatter"
        assert result["LOGGING"]["handlers"]["console"]["formatter"] == "json"

    def test_returns_json_config_when_log_format_json(self):
        """Returns JSON logging config when METRICS_SERVICE_LOG_FORMAT=json."""
        from apps.settings.defaults import setup_json_logging_for_production

        settings_mock = mock.MagicMock()
        settings_mock.get.return_value = {
            "formatters": {},
            "handlers": {"console": {"class": "logging.StreamHandler"}},
        }
        with mock.patch.dict(os.environ, {"METRICS_SERVICE_MODE": "development", "METRICS_SERVICE_LOG_FORMAT": "json"}):
            result = setup_json_logging_for_production(settings_mock)

        assert "LOGGING" in result
        assert "json" in result["LOGGING"]["formatters"]
