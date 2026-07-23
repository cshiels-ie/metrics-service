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
        Harden permission classes on DAB-provided views that are insufficiently
        restricted by default when ansible_base.rbac is in INSTALLED_APPS.

        DAB's activitystream view falls through to IsAuthenticated when RBAC is
        active; OldFeatureFlagsStateListView has no explicit permission class at
        all. Both are patched here to require at minimum Platform Auditor role,
        matching the restriction already applied to dashboard_reports viewsets.

        This uses class-attribute patching rather than URL shadowing because the
        DAB URL patterns are registered before the project's apps/urls.py
        patterns, so URL-level overrides cannot take precedence.
        """
        from ansible_base.activitystream.views import EntryReadOnlyViewSet
        from ansible_base.feature_flags.views import OldFeatureFlagsStateListView
        from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor

        EntryReadOnlyViewSet.permission_classes = [IsSystemAdminOrAuditor]
        OldFeatureFlagsStateListView.permission_classes = [IsSystemAdminOrAuditor]

    @staticmethod
    def _create_managed_roles(sender, **kwargs):
        from ansible_base.rbac import permission_registry
        from django.apps import apps

        permission_registry.create_managed_roles(apps)
