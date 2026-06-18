"""
Unit tests for segment write key loading in apps.core.segment.

Covers load_segment_write_key_from_file (single file, plaintext).
"""

import os
from pathlib import Path
from unittest import mock

import pytest


@pytest.mark.unit
class TestReadSegmentKeyFromPath:
    """Tests for read_segment_key_from_path (low-level file reading)."""

    def test_reads_key_successfully(self, tmp_path):
        """Successfully reads and strips key from file."""
        from apps.core.segment import read_segment_key_from_path

        key_file = tmp_path / "key"
        key_file.write_text("  test-key-123  \n")

        result = read_segment_key_from_path(key_file)

        assert result == "test-key-123"

    def test_returns_none_when_not_a_file(self, tmp_path):
        """Returns None when path is a directory."""
        from apps.core.segment import read_segment_key_from_path

        result = read_segment_key_from_path(tmp_path)

        assert result is None

    def test_returns_none_when_file_empty(self, tmp_path):
        """Returns None when file is empty after strip."""
        from apps.core.segment import read_segment_key_from_path

        key_file = tmp_path / "key"
        key_file.write_text("   \n  ")

        result = read_segment_key_from_path(key_file)

        assert result is None

    def test_returns_none_on_os_error(self, tmp_path):
        """Returns None and suppresses OSError when reading file fails."""
        from apps.core.segment import read_segment_key_from_path

        path_mock = mock.MagicMock(spec=Path)
        path_mock.is_file.return_value = True
        os_error = OSError("Permission denied")
        os_error.filename = "/test/file"
        path_mock.read_text.side_effect = os_error

        result = read_segment_key_from_path(path_mock)

        assert result is None


@pytest.mark.unit
class TestLoadSegmentWriteKeyFromFile:
    """Tests for _load_segment_write_key_from_file (single plaintext file)."""

    def test_path_does_not_exist_does_nothing(self):
        """When path does not exist, SEGMENT_WRITE_KEY is not set."""
        from apps.core.segment import load_segment_write_key_from_file
        from metrics_service.settings import DYNACONF

        before = DYNACONF.get("SEGMENT_WRITE_KEY")
        nonexistent = Path("/nonexistent/segment-key-path")
        dynaconf_mock = mock.MagicMock()
        load_segment_write_key_from_file(path=nonexistent, dynaconf_instance=dynaconf_mock)
        dynaconf_mock.set.assert_not_called()
        assert DYNACONF.get("SEGMENT_WRITE_KEY") == before

    def test_path_is_file_sets_key_from_plaintext(self, tmp_path):
        """When path is a file, the raw plaintext key is read and set as-is."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("my-plaintext-write-key\n")
        dynaconf_mock = mock.MagicMock()
        dynaconf_mock.get.return_value = None
        load_segment_write_key_from_file(path=key_file, dynaconf_instance=dynaconf_mock)
        dynaconf_mock.set.assert_called_once_with("SEGMENT_WRITE_KEY", "my-plaintext-write-key")

    def test_path_is_file_whitespace_stripped(self, tmp_path):
        """Leading/trailing whitespace and newlines are stripped from the key."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("  key-with-spaces  \n")
        dynaconf_mock = mock.MagicMock()
        dynaconf_mock.get.return_value = None
        load_segment_write_key_from_file(path=key_file, dynaconf_instance=dynaconf_mock)
        dynaconf_mock.set.assert_called_once_with("SEGMENT_WRITE_KEY", "key-with-spaces")

    def test_path_is_dir_does_not_set(self, tmp_path):
        """When path is a directory (not a file), SEGMENT_WRITE_KEY is not set."""
        from apps.core.segment import load_segment_write_key_from_file

        dynaconf_mock = mock.MagicMock()
        load_segment_write_key_from_file(path=tmp_path, dynaconf_instance=dynaconf_mock)
        dynaconf_mock.set.assert_not_called()

    def test_path_is_file_empty_key_not_set(self, tmp_path):
        """When file content is empty after strip, key is not set."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("   \n  ")
        dynaconf_mock = mock.MagicMock()
        load_segment_write_key_from_file(path=key_file, dynaconf_instance=dynaconf_mock)
        dynaconf_mock.set.assert_not_called()

    def test_os_error_suppressed(self, tmp_path):
        """OSError when reading file is suppressed and key is not set."""
        from apps.core.segment import load_segment_write_key_from_file

        dynaconf_mock = mock.MagicMock()
        path_mock = mock.MagicMock(spec=Path)
        path_mock.exists.return_value = True
        path_mock.is_file.return_value = True
        os_error = OSError("Permission denied")
        os_error.filename = "/test/path"
        path_mock.read_text.side_effect = os_error
        load_segment_write_key_from_file(path=path_mock, dynaconf_instance=dynaconf_mock)
        dynaconf_mock.set.assert_not_called()

    def test_env_key_already_set_skips_file_load(self, tmp_path):
        """When METRICS_SERVICE_SEGMENT_WRITE_KEY is set in env, file is not loaded."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("file-key")
        dynaconf_mock = mock.MagicMock()

        with mock.patch.dict(os.environ, {"METRICS_SERVICE_SEGMENT_WRITE_KEY": "env-key"}):
            load_segment_write_key_from_file(path=key_file, dynaconf_instance=dynaconf_mock)

        dynaconf_mock.set.assert_not_called()

    def test_settings_key_already_set_skips_file_load(self, tmp_path):
        """When SEGMENT_WRITE_KEY is already in settings, file is not loaded."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("file-key")
        dynaconf_mock = mock.MagicMock()
        dynaconf_mock.get.return_value = "existing-key"

        load_segment_write_key_from_file(path=key_file, dynaconf_instance=dynaconf_mock)

        dynaconf_mock.set.assert_not_called()

    def test_default_path_when_path_not_provided(self):
        """When path is None, uses default from env or fallback path."""
        from apps.core.segment import load_segment_write_key_from_file

        dynaconf_mock = mock.MagicMock()
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("apps.core.segment.Path") as path_mock,
        ):
            path_instance = path_mock.return_value
            path_instance.exists.return_value = False

            load_segment_write_key_from_file(path=None, dynaconf_instance=dynaconf_mock)

            path_mock.assert_called_once_with("/etc/ansible-automation-platform/metrics/segment-write-key")

    def test_custom_path_from_env_when_path_not_provided(self):
        """When path is None and env var set, uses env var path."""
        from apps.core.segment import load_segment_write_key_from_file

        dynaconf_mock = mock.MagicMock()
        with (
            mock.patch.dict(os.environ, {"METRICS_SERVICE_SEGMENT_WRITE_KEY_FILE": "/custom/path"}),
            mock.patch("apps.core.segment.Path") as path_mock,
        ):
            path_instance = path_mock.return_value
            path_instance.exists.return_value = False

            load_segment_write_key_from_file(path=None, dynaconf_instance=dynaconf_mock)

            path_mock.assert_called_once_with("/custom/path")

    def test_does_not_set_when_key_empty(self, tmp_path):
        """Does not set SEGMENT_WRITE_KEY when file is empty."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("   \n  ")  # Empty after strip
        dynaconf_mock = mock.MagicMock()
        dynaconf_mock.get.return_value = None

        load_segment_write_key_from_file(path=key_file, dynaconf_instance=dynaconf_mock)

        dynaconf_mock.set.assert_not_called()

    def test_does_not_set_when_dynaconf_instance_none(self, tmp_path):
        """Does not set SEGMENT_WRITE_KEY when dynaconf_instance is None."""
        from apps.core.segment import load_segment_write_key_from_file

        key_file = tmp_path / "segment-write-key"
        key_file.write_text("test-key")

        # Should not raise error, just log warning
        load_segment_write_key_from_file(path=key_file, dynaconf_instance=None)

    def test_returns_early_when_path_not_exists(self, tmp_path):
        """Returns early when path does not exist (covers debug logging branch)."""
        from apps.core.segment import load_segment_write_key_from_file

        nonexistent = tmp_path / "nonexistent"
        dynaconf_mock = mock.MagicMock()
        dynaconf_mock.get.return_value = None

        # Should return early without calling set
        load_segment_write_key_from_file(path=nonexistent, dynaconf_instance=dynaconf_mock)

        dynaconf_mock.set.assert_not_called()
