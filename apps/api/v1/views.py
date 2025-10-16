"""
API v1 views for metrics_service following AAP standards.
"""

from ansible_base.lib.utils.views.django_app_api import AnsibleBaseDjangoAppApiView
from ansible_base.oauth2_provider.permissions import OAuth2ScopePermission
from ansible_base.rbac.api.permissions import AnsibleBaseObjectPermissions
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.core.models import Organization, User
from apps.core.permissions import SystemAuditorAwarePermissions
from apps.core.utils import log_configuration_change
from metrics_service.settings import DYNACONF

from .serializers import OrganizationSerializer, UserSerializer


class UserViewSet(AnsibleBaseDjangoAppApiView, viewsets.ModelViewSet):
    """ViewSet for User model following AAP patterns."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [OAuth2ScopePermission, SystemAuditorAwarePermissions]
    search_fields = ["username", "first_name", "last_name", "email"]
    filterset_fields = {
        "username": ["exact", "icontains"],
        "email": ["exact", "icontains"],
        "is_active": ["exact"],
        "is_superuser": ["exact"],
        "is_system_auditor": ["exact"],
        "created": ["gte", "lte"],
    }
    ordering_fields = ["username", "email", "first_name", "last_name", "created"]
    ordering = ["username"]

    def get_queryset(self):
        """Filter queryset based on user permissions using DAB patterns."""
        # Use DAB's access_qs method - when DAB is fully configured, this will handle all RBAC
        return User.access_qs(self.request.user, queryset=self.queryset)

    @extend_schema(
        operation_id="users_me_retrieve",
        description="Get current user information",
        responses={200: UserSerializer},
    )
    @action(detail=False, methods=["get"])
    def me(self, request):
        """Return current user information."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        operation_id="users_set_password",
        description="Set user password",
        request={"password": "string"},
        responses={204: None},
    )
    @action(detail=True, methods=["post"])
    def set_password(self, request, pk=None):
        """Set password for a user."""
        user = self.get_object()
        password = request.data.get("password")

        if not password:
            return Response({"error": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationViewSet(AnsibleBaseDjangoAppApiView, viewsets.ModelViewSet):
    """ViewSet for Organization model following AAP patterns."""

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [OAuth2ScopePermission, SystemAuditorAwarePermissions]
    search_fields = ["name", "description"]
    filterset_fields = {
        "name": ["exact", "icontains"],
        "description": ["icontains"],
        "extra_field": ["exact", "icontains", "isnull"],
        "created": ["gte", "lte"],
        "modified": ["gte", "lte"],
    }
    ordering_fields = ["name", "created", "modified"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter queryset based on user permissions using DAB patterns."""
        user = self.request.user
        return Organization.access_qs(user, queryset=self.queryset)

    @extend_schema(
        operation_id="organizations_users",
        description="Get users in organization OR add user to organization",
        request={
            "GET": None,  # No request body for GET
            "POST": {"id": "integer", "disassociate": "boolean"},
        },
        responses={
            200: UserSerializer(many=True),  # GET response
            204: None,  # POST response
        },
    )
    @action(detail=True, methods=["get", "post"])
    def users(self, request, pk=None):
        """Get users in organization OR add user to organization."""
        organization = self.get_object()

        if request.method == "GET":
            # Return list of users (current behavior)
            users = organization.users.all()
            serializer = UserSerializer(users, many=True, context={"request": request})
            return Response(serializer.data)

        elif request.method == "POST":
            # Add/remove user to/from organization
            user_id = request.data.get("id")
            disassociate = request.data.get("disassociate", False)

            if not user_id:
                return Response({"error": "User id is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(id=user_id)

                if disassociate:
                    organization.users.remove(user)
                else:
                    organization.users.add(user)

                return Response(status=status.HTTP_204_NO_CONTENT)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


class ConfigView(AnsibleBaseDjangoAppApiView, viewsets.ViewSet):
    permission_classes = [IsAdminUser, AnsibleBaseObjectPermissions]

    @extend_schema(operation_id="config_retrieve", description="Get current configuration", responses={200: dict})
    def list(self, request):
        return Response(DYNACONF.to_dict())

    @extend_schema(
        operation_id="config_update", description="Update current configuration", request=dict, responses={204: None}
    )
    @action(detail=False, methods=["post"])
    def update_config(self, request):
        """Update configuration settings and log changes."""
        # Take a snapshot of current settings the change
        old_settings = {}
        for key in request.data:
            old_settings[key] = DYNACONF.get(key)

        # Make the change
        DYNACONF.merge(request.data)

        # Log each change by calling the helper function
        for key, new_value in request.data.items():
            old_value = old_settings.get(key)
            log_configuration_change(
                user=request.user,
                setting_key=key,
                old_value=old_value,
                new_value=new_value,
                source="api",
                request=request,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id="config_reload",
        description="Reload current configuration from files and environment variables",
        responses={204: {"message": "Configuration reloaded successfully"}},
    )
    @action(detail=False, methods=["post"])
    def reload(self, request):
        """Reload configuration from files and log changes."""
        try:
            # Take a snapshot of current settings before reload
            old_settings = DYNACONF.as_dict()
            # Reload the configuration
            DYNACONF.reload()
            # Get new settings and find what changed
            new_settings = DYNACONF.as_dict()
            # each change by calling the diary robot
            for key in new_settings:
                old_value = old_settings.get(key)
                new_value = new_settings.get(key)

                # Only log if the value actually changed
                if old_value != new_value:
                    log_configuration_change(
                        user=request.user,
                        setting_key=key,
                        old_value=old_value,
                        new_value=new_value,
                        source="reload",
                        request=request,
                    )

            return Response({"message": "Configuration reloaded successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        operation_id="config_rollback",
        description="Rollback (undo) a configuration change",
        responses={
            200: {"message": "string", "setting_key": "string", "rolled_back_to": "any"},
            400: {"error": "string"},
            404: {"error": "string"},
        },
    )
    @action(detail=False, methods=["post"], url_path="rollback/(?P<change_id>[0-9]+)")
    def rollback(self, request, change_id=None):
        """
        Rollback a configuration change by ID.

        Toy analogy: Press the UNDO button!
        """
        from apps.core.utils import rollback_configuration_change

        result = rollback_configuration_change(change_id=change_id, user=request.user, request=request)

        if result["success"]:
            return Response(result, status=status.HTTP_200_OK)
        else:
            status_code = status.HTTP_404_NOT_FOUND if "not found" in result["error"] else status.HTTP_400_BAD_REQUEST
            return Response({"error": result["error"]}, status=status_code)

    def config(self, request):
        if request.method == "GET":
            return Response(DYNACONF.to_dict())
        elif request.method == "POST":
            DYNACONF.merge(request.data)
            return Response(status=status.HTTP_204_NO_CONTENT)
