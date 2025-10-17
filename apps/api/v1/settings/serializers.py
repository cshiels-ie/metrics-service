"""
Serializers for Settings API - Phase 2 Dynamic Preferences.
"""

import json

from rest_framework import serializers

from apps.core.models import Setting


class SettingSerializer(serializers.ModelSerializer):
    """
    Serializer for Setting model with JSON value handling.

    This serializer handles the versioned, immutable Setting model for
    dynamic preferences. Values are stored as JSON strings but presented
    as Python objects in the API.
    """

    value_json = serializers.SerializerMethodField(
        help_text="Parsed JSON value (for display only)",
    )
    changed_by_username = serializers.SerializerMethodField(
        help_text="Username of the person who made the change",
    )

    class Meta:
        model = Setting
        fields = [
            "id",
            "key",
            "value",
            "value_json",
            "version",
            "category",
            "is_secret",
            "changed_by",
            "changed_by_username",
            "changed_at",
            "source",
            "ip_address",
        ]
        read_only_fields = [
            "id",
            "version",
            "changed_at",
            "changed_by",
            "value_json",
            "changed_by_username",
        ]

    def get_value_json(self, obj: Setting) -> dict | list | str | int | bool | None:
        """
        Parse and return the JSON value.

        If the value is marked as secret, return a redacted placeholder.
        """
        if obj.is_secret:
            return "***REDACTED***"

        try:
            return json.loads(obj.value)
        except json.JSONDecodeError:
            # If not valid JSON, return as string
            return obj.value

    def get_changed_by_username(self, obj: Setting) -> str | None:
        """Get the username of the user who made the change."""
        return obj.changed_by.username if obj.changed_by else None


class SettingCreateSerializer(serializers.Serializer):
    """
    Serializer for creating/updating settings (creates new version).

    This is a separate serializer since creating a setting actually creates
    a new version, not a new setting record.
    """

    key = serializers.CharField(
        max_length=255,
        help_text="Setting key name (e.g., 'DEBUG', 'FEATURE_FLAGS')",
    )
    value = serializers.JSONField(
        help_text="Setting value (will be JSON-serialized for storage)",
    )
    category = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
        help_text="Category for organization (e.g., 'security', 'features')",
    )
    is_secret = serializers.BooleanField(
        default=False,
        help_text="Whether this setting contains sensitive data",
    )

    def validate_key(self, value: str) -> str:
        """Validate that the key is in DYNAMIC_KEYS."""
        from apps.core.dynamic_settings import DYNAMIC_KEYS

        if value not in DYNAMIC_KEYS:
            raise serializers.ValidationError(
                f"Key '{value}' is not configured as a dynamic setting. "
                f"Available keys: {', '.join(sorted(DYNAMIC_KEYS))}"
            )
        return value

    def validate_value(self, value: dict | list | str | int | bool | None) -> str:
        """Ensure value is JSON-serializable and return as JSON string."""
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            raise serializers.ValidationError(f"Value must be JSON-serializable: {e}")

    def create(self, validated_data: dict) -> Setting:
        """Create new version of a setting."""
        from apps.core.models import Setting

        # Get user and IP from request context
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None

        # Get client IP
        ip_address = None
        if request:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(",")[0].strip()
            else:
                ip_address = request.META.get("REMOTE_ADDR")

        # Value is already serialized by validate_value
        return Setting.objects.create_or_update(
            key=validated_data["key"],
            value=validated_data["value"],  # Already JSON string
            user=user,
            source="api",
            ip_address=ip_address,
            category=validated_data.get("category", ""),
            is_secret=validated_data.get("is_secret", False),
        )


class SettingHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for setting history (all versions of a key).
    """

    value_json = serializers.SerializerMethodField()
    changed_by_username = serializers.SerializerMethodField()

    class Meta:
        model = Setting
        fields = [
            "version",
            "value",
            "value_json",
            "changed_by_username",
            "changed_at",
            "source",
        ]
        read_only_fields = fields

    def get_value_json(self, obj: Setting) -> dict | list | str | int | bool | None:
        """Parse and return the JSON value."""
        if obj.is_secret:
            return "***REDACTED***"

        try:
            return json.loads(obj.value)
        except json.JSONDecodeError:
            return obj.value

    def get_changed_by_username(self, obj: Setting) -> str | None:
        """Get the username of the user who made the change."""
        return obj.changed_by.username if obj.changed_by else None

