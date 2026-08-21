from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from ansible_base.rbac.triggers import dab_post_migrate

        from . import signals  # noqa: F401

        dab_post_migrate.connect(
            self._create_managed_roles,
            dispatch_uid="core.create_managed_roles",
        )

        self._restrict_dab_view_permissions()

    @staticmethod
    def _restrict_dab_view_permissions():
        """
        Patch class attributes on DAB-provided views that are misconfigured for
        this service by default when ansible_base.rbac is in INSTALLED_APPS.

        Permission hardening:
        DAB's activitystream view falls through to IsAuthenticated when RBAC is
        active; OldFeatureFlagsStateListView has no explicit permission class at
        all. Both are patched here to require at minimum Platform Auditor role,
        matching the restriction already applied to dashboard_reports viewsets.

        Authentication (ServiceMetadataView):
        The gateway's populate_service_id self-heal probes
        GET /api/v1/service-index/metadata/ to resolve a service whose
        ServiceCluster.service_id is still NULL after a 2.6->2.7 upgrade. The
        default RBAC auth class (use_rbac_permissions=True) re-calls the gateway
        (jwt_claims) during authentication, but that call is authenticated with
        the service token whose issuer the gateway cannot yet resolve, so it 503s
        and the probe 403s -- leaving service_id NULL forever. Authenticate this
        one endpoint without the RBAC claims fetch so the probe can succeed; all
        other endpoints keep use_rbac_permissions=True.

        This uses class-attribute patching rather than URL shadowing because the
        DAB URL patterns are registered before the project's apps/urls.py
        patterns, so URL-level overrides cannot take precedence.
        """
        from ansible_base.activitystream.views import EntryReadOnlyViewSet
        from ansible_base.feature_flags.views import OldFeatureFlagsStateListView
        from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor
        from ansible_base.resource_registry.views import ServiceMetadataView

        from .authentication import ServiceJWTAuthenticationNoRBAC

        EntryReadOnlyViewSet.permission_classes = [IsSystemAdminOrAuditor]
        OldFeatureFlagsStateListView.permission_classes = [IsSystemAdminOrAuditor]
        ServiceMetadataView.authentication_classes = [ServiceJWTAuthenticationNoRBAC]

    @staticmethod
    def _create_managed_roles(sender, **kwargs):
        from ansible_base.rbac import permission_registry
        from django.apps import apps

        permission_registry.create_managed_roles(apps)
