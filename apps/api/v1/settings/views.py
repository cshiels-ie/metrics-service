"""
ViewSets for Settings API - Phase 2 Dynamic Preferences.
"""

from django.db.models import Max
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.dynamic_settings import DYNAMIC_KEYS
from apps.core.models import Setting

from .serializers import SettingCreateSerializer, SettingHistorySerializer, SettingSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List all current settings",
        description="Get all settings showing only their latest versions",
    ),
    retrieve=extend_schema(
        summary="Get setting details with history",
        description="Get a specific setting with all its version history",
    ),
    create=extend_schema(
        summary="Create or update a setting",
        description="Create a new version of a setting (updates the value)",
    ),
)
class SettingViewSet(viewsets.ModelViewSet):
    """
    API endpoints for dynamic settings management (Phase 2).

    Dynamic settings can be changed at runtime without restarting the service.
    Each change creates a new immutable version with full audit trail.

    Endpoints:
    - GET /api/v1/settings/ - List all current settings (latest versions)
    - GET /api/v1/settings/{key}/ - Get specific setting with history
    - POST /api/v1/settings/ - Create/update a setting
    - GET /api/v1/settings/available_keys/ - List available dynamic keys
    - POST /api/v1/settings/{key}/revert/ - Revert to a specific version
    """

    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "key"

    def get_queryset(self):
        """
        Return queryset based on action.

        For list: only latest versions of each setting
        For retrieve: all versions of a specific key (for history)
        """
        queryset = Setting.objects.all()

        if self.action == "list":
            # Get only latest version of each key
            # Annotate with max version per key, then filter
            latest_versions = Setting.objects.values("key").annotate(max_version=Max("version"))

            # Build filter for latest versions
            latest_queries = []
            for item in latest_versions:
                latest_queries.append((item["key"], item["max_version"]))

            # Filter to only latest versions
            if latest_queries:
                from django.db.models import Q

                q_objects = Q()
                for key, version in latest_queries:
                    q_objects |= Q(key=key, version=version)
                queryset = queryset.filter(q_objects)

        elif self.action == "retrieve":
            # For retrieve, we want all versions of the specific key
            key = self.kwargs.get("key")
            if key:
                queryset = queryset.filter(key=key).order_by("-version")

        return queryset

    def get_object(self):
        """
        Get a single setting object.

        For retrieve action, returns the latest version of the key.
        """
        key = self.kwargs.get(self.lookup_field)
        if self.action == "retrieve":
            # Return latest version for the key
            return Setting.get_latest(key)
        return super().get_object()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "create":
            return SettingCreateSerializer
        elif self.action == "history":
            return SettingHistorySerializer
        return SettingSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new version of a setting.

        This endpoint creates or updates a setting by creating a new version.
        """
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        setting = serializer.save()

        # Return the created setting with standard serializer
        output_serializer = SettingSerializer(setting)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get available dynamic keys",
        description="List all settings keys that can be changed dynamically at runtime",
        responses={200: {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}}},
    )
    @action(detail=False, methods=["get"])
    def available_keys(self, request):
        """
        List all keys that can be dynamically changed.

        Returns:
            List of setting keys configured as dynamic
        """
        return Response({"keys": sorted(list(DYNAMIC_KEYS))})

    @extend_schema(
        summary="Get setting history",
        description="Get all versions of a setting ordered by version (newest first)",
        responses={200: SettingHistorySerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def history(self, request, key=None):
        """
        Get version history for a specific setting.

        Args:
            key: Setting key name

        Returns:
            List of all versions of the setting
        """
        versions = Setting.get_history(key)
        serializer = self.get_serializer(versions, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Revert setting to previous version",
        description="Revert a setting to a specific version by creating a new version with the old value",
        request={"type": "object", "properties": {"version": {"type": "integer"}}},
        responses={201: SettingSerializer},
    )
    @action(detail=True, methods=["post"])
    def revert(self, request, key=None):
        """
        Revert a setting to a previous version.

        This creates a new version with the value from the specified version.

        Args:
            key: Setting key name
            version: Version number to revert to (from request body)

        Returns:
            The newly created setting version with the reverted value
        """
        version_number = request.data.get("version")
        if not version_number:
            return Response({"error": "Version number is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            version_number = int(version_number)
        except (TypeError, ValueError):
            return Response({"error": "Version must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the specified version
        old_version = Setting.get_version(key, version_number)
        if not old_version:
            return Response(
                {"error": f"Version {version_number} not found for key '{key}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get client IP
        ip_address = None
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        # Create new version with old value
        new_setting = Setting.objects.create_or_update(
            key=key,
            value=old_version.value,
            user=request.user if request.user.is_authenticated else None,
            source="api_revert",
            ip_address=ip_address,
            category=old_version.category,
            is_secret=old_version.is_secret,
        )

        serializer = SettingSerializer(new_setting)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
