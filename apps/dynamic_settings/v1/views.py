"""API for supported runtime dashboard settings."""

from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard_reports.config import (
    DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS,
    include_sync_workflow_jobs,
)
from apps.dynamic_settings.utils import log_setting_change


class DashboardSettingsSerializer(serializers.Serializer):
    """Supported dashboard runtime settings."""

    include_sync_workflow_jobs = serializers.BooleanField()


class DashboardSettingsView(APIView):
    """Read or update deployment-wide dashboard collection settings."""

    permission_classes = [IsSystemAdminOrAuditor]

    @extend_schema(
        summary="Get dashboard collection settings",
        responses={200: DashboardSettingsSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response({"include_sync_workflow_jobs": include_sync_workflow_jobs()})

    @extend_schema(
        summary="Update dashboard collection settings",
        request=DashboardSettingsSerializer,
        responses={200: DashboardSettingsSerializer},
    )
    def patch(self, request: Request) -> Response:
        serializer = DashboardSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["include_sync_workflow_jobs"]

        setting = log_setting_change(
            user=request.user,
            setting_key=DASHBOARD_INCLUDE_SYNC_WORKFLOW_JOBS,
            new_value=value,
        )
        if setting is None:
            return Response({"detail": "Unable to update dashboard settings."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(DashboardSettingsSerializer({"include_sync_workflow_jobs": value}).data)
