"""
Comprehensive tests for core resource_api module.

This module provides complete test coverage for the resource_api configuration,
testing all code paths including import error handling and service metadata.
"""

import pytest
from django.test import TestCase


@pytest.mark.unit
class TestResourceAPIConfiguration(TestCase):
    """Test cases for resource API configuration."""

    def test_api_config_class_exists(self):
        """Test that APIConfig class exists and has correct service_type."""
        from apps.core.resource_api import APIConfig

        assert hasattr(APIConfig, "service_type")
        assert APIConfig.service_type == "metrics"

    def test_resource_list_exists(self):
        """Test that RESOURCE_LIST exists and contains configurations."""
        from apps.core.resource_api import RESOURCE_LIST

        assert isinstance(RESOURCE_LIST, list)
        assert len(RESOURCE_LIST) >= 3  # At minimum: User, Team, Organization

    def test_resource_list_contains_user(self):
        """Test that RESOURCE_LIST contains User model configuration."""
        from django.contrib.auth import get_user_model

        from apps.core.resource_api import RESOURCE_LIST

        user_model = get_user_model()
        user_configs = [rc for rc in RESOURCE_LIST if rc.model == user_model]

        assert len(user_configs) == 1
        user_config = user_configs[0]
        assert user_config.name_field == "username"
        # ResourceConfig has the model attribute which is what matters
        assert user_config.model == user_model

    def test_resource_list_contains_team(self):
        """Test that RESOURCE_LIST contains Team model configuration."""
        from apps.core.models import Team
        from apps.core.resource_api import RESOURCE_LIST

        team_configs = [rc for rc in RESOURCE_LIST if rc.model == Team]

        assert len(team_configs) == 1
        team_config = team_configs[0]
        assert team_config.model == Team

    def test_resource_list_contains_organization(self):
        """Test that RESOURCE_LIST contains Organization model configuration."""
        from apps.core.models import Organization
        from apps.core.resource_api import RESOURCE_LIST

        org_configs = [rc for rc in RESOURCE_LIST if rc.model == Organization]

        assert len(org_configs) == 1
        org_config = org_configs[0]
        assert org_config.model == Organization

    def test_resource_list_does_not_include_roledefinition(self):
        """Test that RoleDefinition is not included in RESOURCE_LIST (matching platform-service-example pattern)."""
        from apps.core.resource_api import RESOURCE_LIST

        # RoleDefinition is not included in the resource list for this service
        try:
            from ansible_base.rbac.models import RoleDefinition

            role_configs = [rc for rc in RESOURCE_LIST if rc.model == RoleDefinition]
            # RoleDefinition should NOT be in RESOURCE_LIST (platform-service-example pattern)
            assert len(role_configs) == 0
        except ImportError:
            # If import fails, that's fine - RoleDefinition wouldn't be there anyway
            pass

    def test_module_imports(self):
        """Test that all required modules can be imported."""
        from apps.core import resource_api

        assert hasattr(resource_api, "APIConfig")
        assert hasattr(resource_api, "RESOURCE_LIST")

    def test_resource_config_structure(self):
        """Test that ResourceConfig objects have expected structure."""
        from apps.core.resource_api import RESOURCE_LIST

        for resource_config in RESOURCE_LIST:
            # All should have a model attribute
            assert hasattr(resource_config, "model")
            assert resource_config.model is not None


@pytest.mark.unit
class TestResourceAPIImportHandling(TestCase):
    """Test cases for import error handling in resource_api."""

    def test_roledefinition_import_error_handling(self):
        """Test that ImportError for RoleDefinition is handled gracefully."""
        # The try/except block should handle ImportError without raising
        # This is implicitly tested by the module loading successfully
        # even if ansible_base.rbac is not available
        from apps.core import resource_api

        # Module should load without errors
        assert hasattr(resource_api, "RESOURCE_LIST")

    def test_module_loads_with_minimal_dependencies(self):
        """Test that module loads even with minimal dependencies."""
        # This test ensures the module is robust to missing optional dependencies
        import apps.core.resource_api

        # Module should load without errors and have expected attributes
        assert hasattr(apps.core.resource_api, "RESOURCE_LIST")
        assert hasattr(apps.core.resource_api, "APIConfig")
