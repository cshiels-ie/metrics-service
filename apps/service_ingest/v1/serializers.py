"""Serializers for the service ingest API."""

from django.conf import settings
from rest_framework import serializers

from apps.service_ingest.models import ExternalEvent


class ExternalEventSerializer(serializers.ModelSerializer):
    """Validates and deserialises the ingest JSON envelope."""

    # Envelope fields (not stored directly on the model)
    schema_version = serializers.CharField(write_only=True)

    class Meta:
        model = ExternalEvent
        fields = [
            "id",
            "service_name",
            "schema_version",
            "payload_type",
            "collection_start",
            "collection_end",
            "event_timestamp",
            "payload",
            "status",
            "received_at",
        ]
        read_only_fields = ["id", "status", "received_at"]
        extra_kwargs = {
            "collection_start": {"required": False},
            "collection_end": {"required": False},
            "event_timestamp": {"required": False},
        }

    # Expose created as received_at for clarity in responses
    received_at = serializers.DateTimeField(source="created", read_only=True)

    def validate_service_name(self, value: str) -> str:
        """Ensure service_name matches the authenticated service token."""
        request = self.context.get("request")
        if request and hasattr(request.user, "service_name") and value != request.user.service_name:
            raise serializers.ValidationError(
                f"service_name '{value}' does not match authenticated service '{request.user.service_name}'"
            )
        known = getattr(settings, "SERVICE_SEGMENT_EVENTS", {})
        if value not in known:
            raise serializers.ValidationError(f"Unknown service '{value}'. Register it in SERVICE_SEGMENT_EVENTS.")
        return value

    def validate_payload(self, value) -> dict:
        if not isinstance(value, dict) or not value:
            raise serializers.ValidationError("payload must be a non-empty JSON object")
        return value

    def validate(self, attrs: dict) -> dict:
        payload_type = attrs.get("payload_type")
        if payload_type == "batch":
            if not attrs.get("collection_start") or not attrs.get("collection_end"):
                raise serializers.ValidationError(
                    "collection_start and collection_end are required for payload_type=batch"
                )
        elif payload_type == "event" and not attrs.get("event_timestamp"):
            raise serializers.ValidationError("event_timestamp is required for payload_type=event")
        # Drop envelope-only fields before saving
        attrs.pop("schema_version", None)
        return attrs
