"""
Dynamic settings loader for Phase 2 runtime configuration.

This module implements ADR 0014 Phase 2 access hooks that enable runtime
configuration changes without service restart. Settings are loaded from:
1. Redis cache (fastest)
2. Database (if cache miss)
3. Static defaults (if database unavailable)

Usage:
    Access hooks are registered in metrics_service/settings/__init__.py
    and are automatically invoked when dynamic keys are accessed via
    django.conf.settings.
"""

import json
import logging
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Define which keys can be dynamically changed at runtime
# Add new keys here as needed for runtime configuration
DYNAMIC_KEYS = {
    "DEBUG",
    "FEATURE_FLAGS",
    "CORS_ALLOW_ALL_ORIGINS",
    "LOG_LEVEL",
    "DISPATCHERD_ENABLED",
}


def dynamic_settings_loader(settings_obj: Any, key: str, *args: Any, **kwargs: Any) -> Any:
    """
    Access hook that loads dynamic settings from cache/database.

    This function is called by Dynaconf when accessing settings keys that
    are registered as dynamic. It implements a three-tier fallback:
    1. Cache (Redis) - fastest, always checked first
    2. Database - slower, checked on cache miss
    3. Static defaults - fallback if both fail

    Args:
        settings_obj: Dynaconf settings instance
        key: Setting key being accessed
        *args: Additional arguments (unused)
        **kwargs: Additional keyword arguments (unused)

    Returns:
        The setting value from cache/database, or None to use static default

    Execution Flow:
        1. Check if key is in DYNAMIC_KEYS (skip if not)
        2. Try cache first (Redis with no expiration)
        3. Fall back to database if cache miss
        4. Fall back to static defaults if database unavailable
        5. Update cache with database value on cache miss
    """
    # Only process keys that are marked as dynamic
    if key not in DYNAMIC_KEYS:
        # Not a dynamic key, return None to let Dynaconf use static value
        return None

    # Try cache first (fastest path)
    cache_key = f"setting:{key}"
    try:
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            logger.debug(f"Dynamic setting {key} loaded from cache")
            return _deserialize_value(cached_value)
    except Exception as e:
        logger.warning(f"Cache lookup failed for {key}: {e}")

    # Cache miss - try database
    try:
        from apps.core.models import Setting

        setting = Setting.get_latest(key)
        if setting:
            logger.info(f"Dynamic setting {key} loaded from database (cache miss)")
            value = _deserialize_value(setting.value)

            # Update cache for next access
            try:
                cache.set(cache_key, setting.value, timeout=None)
            except Exception as e:
                logger.warning(f"Failed to update cache for {key}: {e}")

            return value
    except Exception as e:
        logger.warning(f"Failed to load {key} from database: {e}")

    # Fall back to static defaults (return None = use existing value in settings_obj)
    logger.debug(f"Dynamic setting {key} falling back to static default")
    return None


def _deserialize_value(value: str) -> Any:
    """
    Deserialize JSON value from database/cache.

    Args:
        value: JSON-serialized string value

    Returns:
        Deserialized Python object (dict, list, str, int, bool, etc.)

    Raises:
        ValueError: If value is not valid JSON
    """
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to deserialize value: {value} - {e}")
        raise ValueError(f"Invalid JSON value: {e}") from e


def serialize_value(value: Any) -> str:
    """
    Serialize Python value to JSON for storage.

    Args:
        value: Python object to serialize

    Returns:
        JSON-serialized string

    Raises:
        TypeError: If value is not JSON-serializable
    """
    try:
        return json.dumps(value)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize value: {value} - {e}")
        raise TypeError(f"Value is not JSON-serializable: {e}") from e


def get_dynamic_setting(key: str, default: Any = None) -> Any:
    """
    Get a dynamic setting value directly (bypass Dynaconf).

    This is a utility function for programmatic access to dynamic settings
    without going through the Django settings object.

    Args:
        key: Setting key name
        default: Default value if setting not found

    Returns:
        Setting value or default

    Example:
        >>> from apps.core.dynamic_settings import get_dynamic_setting
        >>> debug_mode = get_dynamic_setting('DEBUG', False)
    """
    # Try cache first
    cache_key = f"setting:{key}"
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return _deserialize_value(cached_value)

    # Try database
    try:
        from apps.core.models import Setting

        setting = Setting.get_latest(key)
        if setting:
            value = _deserialize_value(setting.value)
            # Update cache
            cache.set(cache_key, setting.value, timeout=None)
            return value
    except Exception as e:
        logger.warning(f"Failed to get dynamic setting {key}: {e}")

    return default


def set_dynamic_setting(
    key: str,
    value: Any,
    user: Any = None,
    source: str = "programmatic",
    category: str = "",
) -> None:
    """
    Set a dynamic setting value programmatically.

    This creates a new version in the database and updates the cache.

    Args:
        key: Setting key name
        value: New value (will be JSON-serialized)
        user: User making the change (optional)
        source: Source of change (default: 'programmatic')
        category: Setting category (optional)

    Raises:
        ValueError: If key is not in DYNAMIC_KEYS
        TypeError: If value is not JSON-serializable

    Example:
        >>> from apps.core.dynamic_settings import set_dynamic_setting
        >>> set_dynamic_setting('DEBUG', False, source='script')
    """
    if key not in DYNAMIC_KEYS:
        raise ValueError(f"Key '{key}' is not in DYNAMIC_KEYS and cannot be changed dynamically")

    from apps.core.models import Setting

    # Serialize value
    serialized_value = serialize_value(value)

    # Create new version in database (also updates cache)
    Setting.objects.create_or_update(
        key=key,
        value=serialized_value,
        user=user,
        source=source,
        category=category,
    )

    logger.info(f"Dynamic setting {key} updated to {value} via {source}")


def is_dynamic_key(key: str) -> bool:
    """
    Check if a key is configured as dynamic.

    Args:
        key: Setting key name

    Returns:
        True if key can be changed dynamically, False otherwise
    """
    return key in DYNAMIC_KEYS


def get_dynamic_keys() -> set[str]:
    """
    Get the set of all keys that can be changed dynamically.

    Returns:
        Set of dynamic key names
    """
    return DYNAMIC_KEYS.copy()

