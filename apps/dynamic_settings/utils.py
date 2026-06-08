"""
Utility functions for dynamic settings management.

This module provides functions for logging setting changes and
rolling back configuration changes.
"""

import json
import logging

from .models import Setting

logger = logging.getLogger(__name__)


def log_setting_change(user, setting_key: str, new_value, old_value=None):
    """
    Log a settings change to the database.

    Args:
        user: User making the change
        setting_key: The setting key being changed
        new_value: The new value
        old_value: Optional old value from DYNACONF (before the change)

    Returns:
        Setting object if successful, None if failed
    """

    # List of sensitive settings that should be redacted
    sensitive_settings = [
        "SECRET_KEY",
        "PASSWORD",
        "DATABASES",
        "JWT_SECRET",
        "API_KEY",
    ]

    # Check if this setting is sensitive
    is_sensitive = any(sensitive in setting_key.upper() for sensitive in sensitive_settings)

    # Redact sensitive values
    if is_sensitive:
        new_value_to_store = "***REDACTED***"
        old_value_to_store = "***REDACTED***" if old_value is not None else None
    else:
        # Convert values to JSON strings for storage
        try:
            new_value_to_store = json.dumps(new_value) if new_value is not None else None
        except (TypeError, ValueError):
            # If we can't convert to JSON, just convert to string
            new_value_to_store = str(new_value) if new_value is not None else None

        try:
            old_value_to_store = json.dumps(old_value) if old_value is not None else None
        except (TypeError, ValueError):
            # If we can't convert to JSON, just convert to string
            old_value_to_store = str(old_value) if old_value is not None else None

    try:
        setting, created = Setting.objects.get_or_create(
            setting_key=setting_key,
            defaults={
                "last_modified_by": user,
                "previous_value": old_value_to_store,  # Use the actual DYNACONF value
                "current_value": new_value_to_store,
            },
        )

        # If setting already existed, update it with new values
        if not created:
            # Use old_value if provided (actual DYNACONF value), otherwise use DB's current_value
            setting.previous_value = old_value_to_store if old_value is not None else setting.current_value
            setting.current_value = new_value_to_store
            setting.last_modified_by = user
            setting.save()

        logger.info(
            f"Setting change logged: {setting_key} changed to {new_value} by {user.username if user else 'System'}"
        )

        return setting

    except Exception as e:
        logger.error(f"Failed to log setting change for {setting_key}: {str(e)}")
        return None


def _parse_setting_value(value_str):
    """
    Helper to parse a setting value from JSON string.
    Returns the parsed value or the original string if parsing fails.
    """
    if not value_str:
        return None
    try:
        return json.loads(value_str)
    except (json.JSONDecodeError, TypeError):
        return value_str


def rollback_configuration_change(change_id, user):
    """
    Undo a settings change by its key id.
    """
    from metrics_service.settings import DYNACONF

    try:
        setting = Setting.objects.get(id=change_id)
    except Setting.DoesNotExist:
        logger.error(f"Configuration change with ID {change_id} not found")
        return {"success": False, "error": f"Configuration change with ID {change_id} not found"}

    # Check if we can actually rollback this setting
    if setting.previous_value == "***REDACTED***" or setting.current_value == "***REDACTED***":
        logger.warning(f"Cannot rollback sensitive setting: {setting.setting_key}")
        return {"success": False, "error": f"Cannot rollback sensitive setting: {setting.setting_key}"}

    try:
        # Parse values from JSON
        previous_value = _parse_setting_value(setting.previous_value)
        current_value = _parse_setting_value(setting.current_value)

        # Rollback - set it back to the old value!
        DYNACONF.set(setting.setting_key, previous_value)

        # Write new entry about the rollback to the db
        log_setting_change(
            user=user,
            setting_key=setting.setting_key,
            new_value=previous_value,
            old_value=current_value,  # The value before rollback
        )

        logger.info(
            f"Rolled back {setting.setting_key} to previous value {setting.previous_value} by {user.username if user else 'System'}"
        )

        return {
            "success": True,
            "setting_key": setting.setting_key,
            "rolled_back_to": previous_value,
            "message": f"Successfully rolled back {setting.setting_key}",
        }

    except Exception as e:
        logger.error(f"Failed to rollback configuration change {change_id}: {str(e)}")
        return {"success": False, "error": f"Failed to rollback: {str(e)}"}


# uv run ./manage.py metrics_service remove-default-settings [--all-settings]
def remove_default_settings(all_settings: bool = False, **_kwargs) -> int:
    """
    Remove settings from the database.

    With all_settings=True removes every row. Without it this is a no-op —
    there are no longer any known-default keys to target individually.
    The **_kwargs absorbs legacy all_known= callers without raising.
    """
    if not all_settings:
        logger.debug("No settings found to remove")
        return 0

    deleted_count, _ = Setting.objects.all().delete()
    if deleted_count > 0:
        logger.info(f"Removed {deleted_count} settings from database")
    return deleted_count


# uv run ./manage.py metrics_service init-default-settings
def initialize_default_settings(**_kwargs) -> None:
    """
    Upgrade hook for FEATURE flag DB rows.

    No flags are pre-seeded into the database. Feature flags resolve at runtime
    from the ``settings.FEATURE`` dict (env var overrides via
    ``METRICS_SERVICE_FEATURE__*`` merge in via dynaconf) with ``false`` DB rows
    as explicit opt-outs.

    On each call, any ``true`` DB row for a FEATURE flag key is deleted — a
    ``true`` row is redundant (the static default and env var both produce
    ``true`` when no row exists) and blocks env var overrides.  ``false`` rows
    are kept: they represent an explicit opt-out that must survive upgrades.

    The **_kwargs absorbs legacy overwrite= callers without raising.
    """
    from django.conf import settings as django_settings

    feature_dict = getattr(django_settings, "FEATURE", {})
    cleaned_count = 0
    for flag_key in feature_dict:
        try:
            deleted, _ = Setting.objects.filter(
                setting_key=flag_key,
                current_value=json.dumps(True),
            ).delete()
            if deleted:
                logger.info(f"Removed redundant 'true' row for '{flag_key}'; env var now applies")
                cleaned_count += deleted
        except Exception as e:
            logger.warning(f"Failed to clean up feature flag row for '{flag_key}': {e}")
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} redundant feature flag row(s)")
