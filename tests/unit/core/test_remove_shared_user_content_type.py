"""Test for migration 0002_remove_shared_user_content_type."""

import importlib

import pytest
from ansible_base.rbac import permission_registry
from ansible_base.rbac.management.create_types import create_DAB_contenttypes
from ansible_base.rbac.models import DABContentType
from django.contrib.auth import get_user_model

_migration = importlib.import_module("apps.core.migrations.0002_remove_shared_user_content_type")
remove_shared_user_content_type = _migration.remove_shared_user_content_type

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
def test_migration_removes_shared_user_content_type(django_apps_registry):
    """Simulate the old config that registered User in RBAC, verify the
    migration cleans up the resulting shared.user DABContentType."""
    registry = permission_registry

    # Temporarily add User to the permission registry (the old behaviour)
    registry._registry.add(User)
    registry._name_to_model["user"] = User
    registry._parent_fields["user"] = None

    try:
        create_DAB_contenttypes()

        assert DABContentType.objects.filter(service="shared", model="user").exists(), (
            "create_DAB_contenttypes should have created a shared.user entry"
        )

        # Run the migration function
        remove_shared_user_content_type(django_apps_registry, None)

        assert not DABContentType.objects.filter(service="shared", model="user").exists(), (
            "Migration should have deleted the shared.user entry"
        )
    finally:
        # Restore the registry to the current (fixed) state
        registry._registry.discard(User)
        registry._name_to_model.pop("user", None)
        registry._parent_fields.pop("user", None)
        DABContentType.objects.filter(service="shared", model="user").delete()


@pytest.fixture
def django_apps_registry():
    """Provide the live Django apps registry, matching what RunPython passes."""
    from django.apps import apps

    return apps
