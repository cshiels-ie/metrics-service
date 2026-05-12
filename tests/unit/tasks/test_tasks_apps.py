"""
Unit tests for apps.tasks.apps — TasksConfig and load_task_feature_flags.
"""

import io
from contextlib import nullcontext
from unittest.mock import MagicMock, call, patch

import pytest
import yaml
from django.test import TestCase, override_settings

from apps.tasks.apps import load_task_feature_flags, sync_flag_values_from_settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_FLAGS = [
    {
        "name": "FEATURE_ANONYMIZED_DATA_COLLECTION_ENABLED",
        "ui_name": "Anonymized Data Collection",
        "visibility": True,
        "condition": "boolean",
        "value": "True",
        "support_level": "TECHNOLOGY_PREVIEW",
        "description": "A test flag.",
        "support_url": "",
        "toggle_type": "run-time",
        "labels": ["metrics"],
    },
    {
        "name": "FEATURE_DASHBOARD_COLLECTION_ENABLED",
        "ui_name": "Dashboard Reports Collection",
        "visibility": True,
        "condition": "boolean",
        "value": "False",
        "support_level": "TECHNOLOGY_PREVIEW",
        "description": "Another test flag.",
        "support_url": "",
        "toggle_type": "run-time",
        "labels": ["metrics"],
    },
]


def _make_patches(flags=_SAMPLE_FLAGS, existing_flag=None):
    """Return (mock_aap_flag_class, list-of-active-patches) ready to start."""
    yaml_content = yaml.dump(flags)

    mock_file_path = MagicMock()
    mock_file_path.open.return_value.__enter__ = lambda s: io.StringIO(yaml_content)
    mock_file_path.open.return_value.__exit__ = MagicMock(return_value=False)

    mock_aap_flag_class = MagicMock()
    mock_aap_flag_class.objects.filter.return_value.first.return_value = existing_flag

    return mock_file_path, mock_aap_flag_class


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoadTaskFeatureFlags(TestCase):
    """Tests for load_task_feature_flags signal handler."""

    # ------------------------------------------------------------------
    # Create path — flag does not exist yet
    # ------------------------------------------------------------------

    def test_creates_new_flags_when_none_exist(self):
        """Creates an AAPFlag instance for every entry in the YAML when none exist."""
        mock_file_path, mock_aap_flag_class = _make_patches(existing_flag=None)

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
            patch(
                "ansible_base.resource_registry.signals.handlers.no_reverse_sync",
                return_value=nullcontext(),
            ),
        ):
            load_task_feature_flags()

        # One AAPFlag(**flag_def) call per flag in the YAML
        assert mock_aap_flag_class.call_count == len(_SAMPLE_FLAGS)
        for flag_def in _SAMPLE_FLAGS:
            mock_aap_flag_class.assert_any_call(**flag_def)

        # full_clean and save called for each new instance
        new_instance = mock_aap_flag_class.return_value
        assert new_instance.full_clean.call_count == len(_SAMPLE_FLAGS)
        new_instance.full_clean.assert_called_with(exclude=["resource"])
        assert new_instance.save.call_count == len(_SAMPLE_FLAGS)

    def test_new_flag_full_clean_excludes_resource(self):
        """full_clean(exclude=['resource']) is called to skip the reverse FK check."""
        mock_file_path, mock_aap_flag_class = _make_patches(flags=[_SAMPLE_FLAGS[0]], existing_flag=None)

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
            patch(
                "ansible_base.resource_registry.signals.handlers.no_reverse_sync",
                return_value=nullcontext(),
            ),
        ):
            load_task_feature_flags()

        mock_aap_flag_class.return_value.full_clean.assert_called_once_with(exclude=["resource"])

    # ------------------------------------------------------------------
    # Update path — flag already exists
    # ------------------------------------------------------------------

    def test_updates_existing_flag_fields(self):
        """Updates metadata fields on an existing AAPFlag without recreating it."""
        existing = MagicMock()
        flag_def = _SAMPLE_FLAGS[0]
        mock_file_path, mock_aap_flag_class = _make_patches(flags=[flag_def], existing_flag=existing)

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
            patch(
                "ansible_base.resource_registry.signals.handlers.no_reverse_sync",
                return_value=nullcontext(),
            ),
        ):
            load_task_feature_flags()

        # No new AAPFlag(**) call — existing instance is mutated instead
        mock_aap_flag_class.assert_not_called()

        assert existing.support_level == flag_def["support_level"]
        assert existing.visibility == flag_def["visibility"]
        assert existing.ui_name == flag_def["ui_name"]
        assert existing.description == flag_def["description"]
        assert existing.labels == flag_def["labels"]
        assert existing.toggle_type == flag_def["toggle_type"]
        assert existing.support_url == flag_def["support_url"]

        existing.full_clean.assert_called_once_with(exclude=["resource"])
        existing.save.assert_called_once()

    def test_existing_flag_full_clean_excludes_resource(self):
        """full_clean(exclude=['resource']) is also used on the update path."""
        existing = MagicMock()
        mock_file_path, mock_aap_flag_class = _make_patches(flags=[_SAMPLE_FLAGS[0]], existing_flag=existing)

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
            patch(
                "ansible_base.resource_registry.signals.handlers.no_reverse_sync",
                return_value=nullcontext(),
            ),
        ):
            load_task_feature_flags()

        existing.full_clean.assert_called_once_with(exclude=["resource"])

    # ------------------------------------------------------------------
    # AAPFlag lookup uses correct name + condition filter
    # ------------------------------------------------------------------

    def test_filters_by_name_and_condition(self):
        """AAPFlag is looked up by (name, condition) for each flag in the YAML."""
        mock_file_path, mock_aap_flag_class = _make_patches(existing_flag=None)

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
            patch(
                "ansible_base.resource_registry.signals.handlers.no_reverse_sync",
                return_value=nullcontext(),
            ),
        ):
            load_task_feature_flags()

        expected_calls = [call(name=f["name"], condition=f["condition"]) for f in _SAMPLE_FLAGS]
        assert mock_aap_flag_class.objects.filter.call_args_list == expected_calls

    # ------------------------------------------------------------------
    # Exception resilience
    # ------------------------------------------------------------------

    @patch("apps.tasks.apps.logger")
    def test_logs_exception_and_does_not_raise(self, mock_logger):
        """An unexpected exception is caught and logged; the function never raises."""
        mock_file_path = MagicMock()
        mock_file_path.open.side_effect = OSError("file not found")

        mock_aap_flag_class = MagicMock()

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
        ):
            assert load_task_feature_flags() is False  # must not raise

        mock_logger.warning.assert_called_once_with(
            "Failed to load tasks feature flags into AAPFlag",
            exc_info=True,
        )

    @patch("apps.tasks.apps.logger")
    def test_empty_yaml_is_a_no_op(self, mock_logger):
        """An empty YAML file results in no AAPFlag interactions."""
        mock_file_path, mock_aap_flag_class = _make_patches(flags=[], existing_flag=None)

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
            patch(
                "ansible_base.resource_registry.signals.handlers.no_reverse_sync",
                return_value=nullcontext(),
            ),
        ):
            load_task_feature_flags()

        mock_aap_flag_class.objects.filter.assert_not_called()
        mock_logger.exception.assert_not_called()

    # ------------------------------------------------------------------
    # TasksConfig.ready wires up the signal
    # ------------------------------------------------------------------


@pytest.mark.unit
class TestSyncFlagValuesFromSettings(TestCase):
    """Tests for sync_flag_values_from_settings."""

    def _make_mock_flag(self, value: str) -> MagicMock:
        flag = MagicMock()
        flag.value = value
        return flag

    def _make_file_patch(self, flags=_SAMPLE_FLAGS):
        yaml_content = yaml.dump(flags)
        mock_file_path = MagicMock()
        mock_file_path.open.return_value.__enter__ = lambda s: io.StringIO(yaml_content)
        mock_file_path.open.return_value.__exit__ = MagicMock(return_value=False)
        return mock_file_path

    @override_settings(FEATURE_DASHBOARD_COLLECTION_ENABLED=True)
    def test_updates_aap_flag_when_settings_differs(self):
        """AAPFlag.value is updated and saved (without no_reverse_sync) when settings say True but flag is False."""
        mock_flag = self._make_mock_flag("False")
        mock_aap_flag_class = MagicMock()
        mock_aap_flag_class.objects.filter.return_value.first.return_value = mock_flag
        mock_file_path = self._make_file_patch()

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
        ):
            result = sync_flag_values_from_settings()

        assert result is True
        assert mock_flag.value == "True"
        mock_flag.save.assert_called_once()

    @override_settings(FEATURE_DASHBOARD_COLLECTION_ENABLED=False)
    def test_updates_aap_flag_to_false_when_settings_says_false(self):
        """AAPFlag.value is set to False and saved when settings override disagrees."""
        mock_flag = self._make_mock_flag("True")
        mock_aap_flag_class = MagicMock()
        mock_aap_flag_class.objects.filter.return_value.first.return_value = mock_flag
        mock_file_path = self._make_file_patch()

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
        ):
            sync_flag_values_from_settings()

        assert mock_flag.value == "False"
        mock_flag.save.assert_called_once()

    @override_settings(FEATURE_DASHBOARD_COLLECTION_ENABLED=True)
    def test_skips_save_when_value_already_matches(self):
        """No save is triggered when the AAPFlag value already matches the settings."""
        mock_flag = self._make_mock_flag("True")
        mock_aap_flag_class = MagicMock()
        mock_aap_flag_class.objects.filter.return_value.first.return_value = mock_flag
        mock_file_path = self._make_file_patch()

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
        ):
            sync_flag_values_from_settings()

        mock_flag.save.assert_not_called()

    def test_no_op_when_no_settings_override(self):
        """Flags with no matching top-level settings attr are left untouched."""
        mock_flag = self._make_mock_flag("False")
        mock_aap_flag_class = MagicMock()
        mock_aap_flag_class.objects.filter.return_value.first.return_value = mock_flag
        mock_file_path = self._make_file_patch()

        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", return_value=mock_aap_flag_class),
        ):
            result = sync_flag_values_from_settings()

        assert result is True
        mock_flag.save.assert_not_called()

    @patch("apps.tasks.apps.logger")
    @override_settings(FEATURE_DASHBOARD_COLLECTION_ENABLED=True)
    def test_returns_false_and_logs_on_exception(self, mock_logger):
        """Returns False and logs a warning when an unexpected exception occurs."""
        mock_file_path = self._make_file_patch()
        with (
            patch("apps.tasks.apps._FEATURE_FLAGS_FILE", mock_file_path),
            patch("django.apps.apps.get_model", side_effect=Exception("registry down")),
        ):
            result = sync_flag_values_from_settings()

        assert result is False
        mock_logger.warning.assert_called_once_with(
            "Failed to sync flag values from settings to AAPFlag", exc_info=True
        )

    def test_ready_connects_signal_to_feature_flags_app(self):
        """TasksConfig.ready() connects load_task_feature_flags to the dab_feature_flags
        AppConfig *instance*, not the class.

        post_migrate dispatches with sender=<AppConfig instance>. Django's signal
        dispatch matches by id(), so id(class) != id(instance) — connecting with the
        class means the handler is never called. We must pass the live instance from
        django.apps.apps.get_app_config("dab_feature_flags").
        """
        from django.apps import apps as django_apps
        from django.db.models.signals import post_migrate

        from apps.tasks.apps import TasksConfig, load_task_feature_flags

        dab_ff_instance = django_apps.get_app_config("dab_feature_flags")

        config = TasksConfig("apps.tasks", __import__("apps.tasks"))
        with patch.object(post_migrate, "connect") as mock_connect:
            config.ready()

        mock_connect.assert_called_once_with(load_task_feature_flags, sender=dab_ff_instance)
