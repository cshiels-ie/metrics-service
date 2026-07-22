from ansible_base.rbac.api.permissions import AnsibleBaseUserPermissions, IsSystemAdminOrAuditor
from ansible_base.rbac.policies import visible_users
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import User
from apps.core.v1.serializers import UserSerializer

from .base import BaseViewSet


class UserViewSet(BaseViewSet):
    """CRUD viewset for User resources.

    Read access (list, retrieve) is restricted to Platform Auditor role or higher.
    Write access (create, update, destroy) is restricted to system administrators.
    The /me action is accessible to any authenticated user.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        """
        Return permission instances based on the current action.

        - me: any authenticated user may read their own profile.
        - list / retrieve: Platform Auditor or system admin required.
        - create / update / partial_update / destroy: system admin only
          (IsSystemAdminOrAuditor denies unsafe methods for non-admins, while
          AnsibleBaseUserPermissions enforces user-management business rules such
          as preventing self-deletion).
        """
        if self.action == "me":
            return [IsAuthenticated()]
        if self.action in ("list", "retrieve"):
            return [IsSystemAdminOrAuditor()]
        # Write operations: require system admin AND user-management business rules.
        return [IsSystemAdminOrAuditor(), AnsibleBaseUserPermissions()]

    def filter_queryset(self, queryset):
        queryset = visible_users(self.request.user, queryset=queryset)
        return super(BaseViewSet, self).filter_queryset(queryset)

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
