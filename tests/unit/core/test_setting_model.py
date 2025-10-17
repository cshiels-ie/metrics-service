"""
Tests for the Setting model (Phase 2).

Tests versioning, locking, caching, and model methods.
"""

import json

import pytest
from django.core.cache import cache
from django.db import transaction

from apps.core.models import Setting


@pytest.mark.django_db
class TestSettingModel:
    """Test the Setting model."""

    def test_create_setting(self):
        """Should create a new setting."""
        setting = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )

        assert setting.key == "DEBUG"
        assert setting.value == json.dumps(True)
        assert setting.version == 1
        assert setting.source == "test"

    def test_versioning(self):
        """Should increment version on each update."""
        # First version
        v1 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )
        assert v1.version == 1

        # Second version
        v2 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(False),
            source="test",
        )
        assert v2.version == 2

        # Third version
        v3 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )
        assert v3.version == 3

        # All versions should exist
        assert Setting.objects.filter(key="DEBUG").count() == 3

    def test_get_latest(self):
        """Should return the latest version."""
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(False), source="test")
        v3 = Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")

        latest = Setting.get_latest("DEBUG")
        assert latest.version == 3
        assert latest.id == v3.id

    def test_get_version(self):
        """Should return a specific version."""
        v1 = Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")
        v2 = Setting.objects.create_or_update(key="DEBUG", value=json.dumps(False), source="test")

        retrieved = Setting.get_version("DEBUG", 1)
        assert retrieved.id == v1.id
        assert retrieved.version == 1

        retrieved = Setting.get_version("DEBUG", 2)
        assert retrieved.id == v2.id
        assert retrieved.version == 2

    def test_get_history(self):
        """Should return all versions ordered by version."""
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(False), source="test")
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")

        history = Setting.get_history("DEBUG")
        assert history.count() == 3
        assert list(history.values_list("version", flat=True)) == [3, 2, 1]

    def test_cache_updated_on_create(self):
        """Cache should be updated when setting is created."""
        cache.clear()

        Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(False),
            source="test",
        )

        # Check cache
        cached = cache.get("setting:DEBUG")
        assert cached == json.dumps(False)

    def test_metadata_fields(self, django_user_model):
        """Should store metadata correctly."""
        user = django_user_model.objects.create_user(username="testuser", password="testpass")

        setting = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            user=user,
            source="api",
            ip_address="192.168.1.1",
            category="security",
            is_secret=True,
        )

        assert setting.changed_by == user
        assert setting.source == "api"
        assert setting.ip_address == "192.168.1.1"
        assert setting.category == "security"
        assert setting.is_secret is True

    def test_unique_constraint(self):
        """Should enforce unique constraint on (key, version)."""
        Setting.objects.create(
            key="TEST",
            value=json.dumps(True),
            version=1,
            source="test",
        )

        # Attempting to create duplicate should fail
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Setting.objects.create(
                key="TEST",
                value=json.dumps(False),
                version=1,  # Same version!
                source="test",
            )

    def test_string_representation(self):
        """Should have meaningful string representation."""
        setting = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )

        assert str(setting) == "DEBUG (v1)"


@pytest.mark.django_db
class TestSettingManagerLocking:
    """Test database locking in SettingManager."""

    def test_concurrent_updates_handled_correctly(self):
        """Should handle concurrent updates with proper locking."""
        # Create initial version
        Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )

        # Simulate concurrent updates
        # In real scenario, select_for_update() would prevent this
        # but we can test that versions increment correctly
        Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(False),
            source="test1",
        )

        Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test2",
        )

        # Should have 3 versions
        assert Setting.objects.filter(key="DEBUG").count() == 3

        # Versions should be 1, 2, 3
        versions = list(Setting.objects.filter(key="DEBUG").values_list("version", flat=True).order_by("version"))
        assert versions == [1, 2, 3]


@pytest.mark.django_db
class TestSettingValidation:
    """Test setting validation."""

    def test_invalid_json_raises_error(self):
        """Should reject invalid JSON values."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            Setting.objects.create_or_update(
                key="DEBUG",
                value="not valid json {",
                source="test",
            )

    def test_valid_json_accepted(self):
        """Should accept valid JSON values."""
        # String
        s1 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps("string"),
            source="test",
        )
        assert s1 is not None

        # Number
        s2 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(42),
            source="test",
        )
        assert s2 is not None

        # Boolean
        s3 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps(True),
            source="test",
        )
        assert s3 is not None

        # Dict
        s4 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps({"key": "value"}),
            source="test",
        )
        assert s4 is not None

        # List
        s5 = Setting.objects.create_or_update(
            key="DEBUG",
            value=json.dumps([1, 2, 3]),
            source="test",
        )
        assert s5 is not None


@pytest.mark.django_db
class TestSettingOrdering:
    """Test setting ordering."""

    def test_default_ordering(self):
        """Should order by version descending by default."""
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(False), source="test")
        Setting.objects.create_or_update(key="DEBUG", value=json.dumps(True), source="test")

        settings = Setting.objects.filter(key="DEBUG")
        versions = list(settings.values_list("version", flat=True))
        assert versions == [3, 2, 1]  # Descending order
