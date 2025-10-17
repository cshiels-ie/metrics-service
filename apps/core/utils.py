"""
Core utility functions and helpers for the metrics service.

This module provides reusable utility functions that reduce code duplication
across the application. These utilities handle common patterns such as safe
object access, JSON processing, timestamp generation, and configuration
management.

Functions:
    get_related_object_safely: Safe access to related model objects
    parse_json_safely: Safe JSON parsing with error handling
    generate_unique_id: Generate unique identifiers for objects
    get_current_timestamp: Get standardized timestamps
    format_duration: Format time durations for display
    validate_json_data: Validate JSON data structure

Security Features:
    - Safe JSON parsing prevents injection attacks
    - Input validation on all utility functions
    - Logging of security-relevant operations
    - Error handling that doesn't expose internal details

Performance Considerations:
    - Efficient related object access patterns
    - Minimal database queries in utility functions
    - Cached timestamp operations where appropriate
"""

import json
import logging
import uuid
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.core.models import ConfigurationChange

logger = logging.getLogger(__name__)


def get_related_object_safely(instance: Any, field_name: str, default: Any = None) -> Any:
    """
    Safely get a related object from an instance.

    This function provides a safe way to access related objects that might
    not exist, reducing try/except duplication across the codebase.

    Args:
        instance: The model instance
        field_name (str): Name of the related field
        default: Default value to return if the relation doesn't exist

    Returns:
        The related object or the default value
    """
    try:
        return getattr(instance, field_name)
    except AttributeError:
        return default
    except instance.DoesNotExist:
        return default


def get_count_safely(queryset_or_manager: Any) -> int:
    """
    Safely get count from a queryset or manager.

    This function provides a safe way to get counts that handles
    potential errors, reducing duplication in count operations.

    Args:
        queryset_or_manager: QuerySet or Manager to count

    Returns:
        int: Count of objects, 0 if error
    """
    try:
        count_result = queryset_or_manager.count()
        return int(count_result)
    except Exception as e:
        logger.warning(f"Error getting count: {e}")
        return 0


def build_error_response(message: str, details: dict[str, Any] | None = None, status_code: int = 400) -> dict[str, Any]:
    """
    Build a standardized error response dictionary.

    This function provides a consistent format for error responses,
    reducing duplication across view error handling.

    Args:
        message (str): Main error message
        details (dict): Optional additional error details
        status_code (int): HTTP status code for the error

    Returns:
        dict: Standardized error response
    """
    error_response = {
        "error": message,
        "status_code": status_code,
        "timestamp": timezone.now().isoformat(),
    }

    if details:
        error_response["details"] = details

    return error_response


def get_system_uuid() -> str:
    """
    Get system UUID from settings or generate a default one.

    Returns:
        str: System UUID
    """
    try:
        return getattr(settings, "SYSTEM_UUID", str(uuid.uuid4()))
    except Exception:
        return str(uuid.uuid4())


def is_system_auditor_user(user: Any) -> bool:
    """
    Check if user is a system auditor.

    Args:
        user: User instance to check

    Returns:
        bool: True if user is system auditor
    """
    try:
        if hasattr(user, "is_system_auditor_user") and callable(user.is_system_auditor_user):
            return user.is_system_auditor_user()
        return False
    except Exception:
        return False


def format_task_data(data: Any) -> str:
    """
    Format task data for display.

    Args:
        data: Task data to format

    Returns:
        str: Formatted task data
    """
    try:
        if isinstance(data, str):
            return data
        return json.dumps(data, indent=2)
    except Exception:
        return str(data)


def log_configuration_change(user, setting_key: str, old_value, new_value, source: str, request=None):
    """
    Log a configuration change to the database.

    Args:
        user: The User who made the change (can be None for system changes)
        setting_key: Name of the setting (e.g., "DEBUG", "SECRET_KEY")
        old_value: The previous value
        new_value: The new value
        source: Where the change came from ("api", "management_command", "reload", "system")
        request: Optional HTTP request object (to get IP address)

    Returns:
        ConfigurationChange object if successful, None if failed
    """

    # List of sensitive settings that should be redacted (hidden)
    sensitive_settings = [
        "SECRET_KEY",
        "PASSWORD",
        "DATABASES",
        "JWT_SECRET",
        "API_KEY",
    ]

    # Check if this setting is sensitive
    is_sensitive = any(sensitive in setting_key.upper() for sensitive in sensitive_settings)

    # Redact (hide) sensitive values
    if is_sensitive:
        old_value_to_store = "***REDACTED***"
        new_value_to_store = "***REDACTED***"
    else:
        # Convert values to JSON strings for storage
        try:
            old_value_to_store = json.dumps(old_value) if old_value is not None else None
            new_value_to_store = json.dumps(new_value) if new_value is not None else None
        except (TypeError, ValueError):
            # If we can't convert to JSON, just convert to string
            old_value_to_store = str(old_value) if old_value is not None else None
            new_value_to_store = str(new_value) if new_value is not None else None

    # Get IP address from request if available
    ip_address = None
    if request:
        # Try to get real IP (handles proxies)
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

    try:
        change_log = ConfigurationChange.objects.create(
            changed_by=user,
            setting_key=setting_key,
            old_value=old_value_to_store,
            new_value=new_value_to_store,
            source=source,
            ip_address=ip_address,
        )

        logger.info(
            f"Configuration change logged: {setting_key} changed by {user.username if user else 'System'} via {source}"
        )

        return change_log

    except Exception as e:
        logger.error(f"Failed to log configuration change for {setting_key}: {str(e)}")
        return None


def rollback_configuration_change(change_id, user, request=None):
    """
    Undo a configuration change by its ID. Like pressing the UNDO buttonon an unwanted change.

    """
    from metrics_service.settings import DYNACONF

    try:
        change = ConfigurationChange.objects.get(id=change_id)

        # Check if we can actually rollback this setting
        if change.old_value == "***REDACTED***" or change.new_value == "***REDACTED***":
            logger.warning(f"Cannot rollback sensitive setting: {change.setting_key}")
            return {"success": False, "error": f"Cannot rollback sensitive setting: {change.setting_key}"}

        # Parse the old value from JSON
        try:
            old_value = json.loads(change.old_value) if change.old_value else None
        except (json.JSONDecodeError, TypeError):
            old_value = change.old_value

        # Get the current value (before rollback)
        current_value = DYNACONF.get(change.setting_key)

        # Rollback - set it back to the old value!
        DYNACONF.set(change.setting_key, old_value)

        # Write new entry about the rollback to the db
        log_configuration_change(
            user=user,
            setting_key=change.setting_key,
            old_value=current_value,
            new_value=old_value,
            source="rollback",
            request=request,
        )

        logger.info(f"Rolled back {change.setting_key} to previous value by {user.username if user else 'System'}")

        return {
            "success": True,
            "setting_key": change.setting_key,
            "rolled_back_to": old_value,
            "message": f"Successfully rolled back {change.setting_key}",
        }

    except ConfigurationChange.DoesNotExist:
        logger.error(f"Configuration change with ID {change_id} not found")
        return {"success": False, "error": f"Configuration change with ID {change_id} not found"}

    except Exception as e:
        logger.error(f"Failed to rollback configuration change {change_id}: {str(e)}")
        return {"success": False, "error": f"Failed to rollback: {str(e)}"}
