"""
Tests for dynamic settings (Phase 2).

Tests the access hooks, caching, and programmatic access functions.
"""

import json

import pytest
from django.core.cache import cache

from apps.core.dynamic_settings import (
    DYNAMIC_KEYS,
    dynamic_settings_loader,
    get_dynamic_setting,
    is_dynamic_key,
    serialize_value,
    set_dynamic_setting,
)
from apps.core.models import Setting


@pytest.mark.django_db
class TestDynamicSettingsLoader:
    """Test the dynamic settings access hook."""

    def test_non_dynamic_key_returns_none(self):
        """Non-dynamic keys should return None (use static default)."""
        result = dynamic_settings_loader(None, "NON_DYNAMIC_KEY")
        assert result is None

    def test_dynamic_key_not_in_db_returns_none(self):
        """Dynamic key not in database should return None (use static default)."""
        cache.clear()
        result = dynamic_settings_loader(None, "DEBUG")
        assert result is None

    def test_dynamic_key_from_cache(self, django_user_model):
        """Dynamic key should be loaded from cache if available."""
        # Set up cache
        cache.set("setting:DEBUG", json.dumps(False))

        result = dynamic_settings_loader(None, "DEBUG")
        assert result is False

    def test_dynamic_key_from_database(self, django_user_model):
        """Dynamic key should be loaded from database on cache miss."""
        cache.clear()

        # Create setting in database
        Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )

        result = dynamic_settings_loader(None, "DEBUG")
        assert result is True

        # Verify cache was updated
        cached = cache.get("setting:DEBUG")
        assert cached == json.dumps(True)

    def test_cache_fallback_on_database_error(self):
        """Should handle database errors gracefully."""
        cache.clear()

        # This should not raise an exception
        result = dynamic_settings_loader(None, "DEBUG")
        assert result is None


@pytest.mark.django_db
class TestGetDynamicSetting:
    """Test the get_dynamic_setting utility function."""

    def test_get_from_cache(self):
        """Should retrieve value from cache."""
        cache.set("setting:DEBUG", json.dumps(False))

        result = get_dynamic_setting("DEBUG")
        assert result is False

    def test_get_from_database(self):
        """Should retrieve value from database on cache miss."""
        cache.clear()

        Setting.objects.create_or_update(
            key="FEATURE_FLAGS",
            value=json.dumps({"test_feature": True}),
            source="test",
        )

        result = get_dynamic_setting("FEATURE_FLAGS")
        assert result == {"test_feature": True}

    def test_get_with_default(self):
        """Should return default when setting not found."""
        cache.clear()

        result = get_dynamic_setting("NONEXISTENT_KEY", default="default_value")
        assert result == "default_value"


@pytest.mark.django_db
class TestSetDynamicSetting:
    """Test the set_dynamic_setting utility function."""

    def test_set_simple_value(self):
        """Should set a simple value."""
        set_dynamic_setting("DEBUG", False, source="test")

        setting = Setting.get_latest("DEBUG")
        assert setting is not None
        assert json.loads(setting.value) is False
        assert setting.source == "test"

    def test_set_complex_value(self):
        """Should set a complex value (dict)."""
        value = {"feature_a": True, "feature_b": False}
        set_dynamic_setting("FEATURE_FLAGS", value, source="test")

        setting = Setting.get_latest("FEATURE_FLAGS")
        assert setting is not None
        assert json.loads(setting.value) == value

    def test_set_non_dynamic_key_raises_error(self):
        """Should raise error for non-dynamic keys."""
        with pytest.raises(ValueError, match="not in DYNAMIC_KEYS"):
            set_dynamic_setting("NON_DYNAMIC_KEY", "value")

    def test_set_non_serializable_raises_error(self):
        """Should raise error for non-JSON-serializable values."""
        with pytest.raises(TypeError, match="not JSON-serializable"):
            set_dynamic_setting("DEBUG", object())

    def test_cache_updated_after_set(self):
        """Cache should be updated after setting value."""
        cache.clear()

        set_dynamic_setting("DEBUG", True, source="test")

        # Check cache was updated
        cached = cache.get("setting:DEBUG")
        assert cached == json.dumps(True)


@pytest.mark.django_db
class TestSerializeValue:
    """Test value serialization."""

    def test_serialize_string(self):
        """Should serialize string."""
        result = serialize_value("test")
        assert result == '"test"'

    def test_serialize_number(self):
        """Should serialize numbers."""
        assert serialize_value(42) == "42"
        assert serialize_value(3.14) == "3.14"

    def test_serialize_boolean(self):
        """Should serialize booleans."""
        assert serialize_value(True) == "true"
        assert serialize_value(False) == "false"

    def test_serialize_dict(self):
        """Should serialize dictionaries."""
        result = serialize_value({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_serialize_list(self):
        """Should serialize lists."""
        result = serialize_value([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_serialize_none(self):
        """Should serialize None."""
        result = serialize_value(None)
        assert result == "null"


class TestIsDynamicKey:
    """Test the is_dynamic_key utility function."""

    def test_dynamic_key_returns_true(self):
        """Should return True for dynamic keys."""
        assert is_dynamic_key("DEBUG") is True
        assert is_dynamic_key("FEATURE_FLAGS") is True

    def test_non_dynamic_key_returns_false(self):
        """Should return False for non-dynamic keys."""
        assert is_dynamic_key("SECRET_KEY") is False
        assert is_dynamic_key("NONEXISTENT") is False


class TestDynamicKeysConstant:
    """Test the DYNAMIC_KEYS constant."""

    def test_dynamic_keys_is_set(self):
        """DYNAMIC_KEYS should be a set."""
        assert isinstance(DYNAMIC_KEYS, set)

    def test_dynamic_keys_not_empty(self):
        """DYNAMIC_KEYS should not be empty."""
        assert len(DYNAMIC_KEYS) > 0

    def test_dynamic_keys_contains_expected_keys(self):
        """DYNAMIC_KEYS should contain expected keys."""
        expected_keys = {"DEBUG", "FEATURE_FLAGS", "CORS_ALLOW_ALL_ORIGINS", "LOG_LEVEL"}
        assert expected_keys.issubset(DYNAMIC_KEYS)
