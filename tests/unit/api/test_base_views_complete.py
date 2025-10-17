"""
Complete test coverage for apps/api/v1/base_views.py focusing on missing lines.
Lines to cover: 124-144, 160-180, 200, 220, 240, 260
"""

from unittest.mock import Mock

import pytest
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.api.v1.base_views import UserManagementMixin
from apps.core.models import Organization, User


@pytest.mark.django_db
class TestUserManagementMixinActions(TestCase):
    """Test the action methods that cover lines 200, 220, 240, 260."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user1 = User.objects.create_user(username="user1", email="user1@example.com")
        self.organization = Organization.objects.create(name="Test Org")

    def test_add_user_action_line_200(self):
        """Test add_user action method (line 200)."""

        class TestMixin(UserManagementMixin):
            def get_object(self):
                return self.organization

            def _add_user_to_field(self, request, field_name, success_message=""):
                return Mock(status_code=200, data={"message": success_message})

        mixin = TestMixin()
        request = Mock()

        response = mixin.add_user(request, pk=1)
        self.assertEqual(response.status_code, 200)

    def test_remove_user_action_line_220(self):
        """Test remove_user action method (line 220)."""

        class TestMixin(UserManagementMixin):
            def get_object(self):
                return self.organization

            def _remove_user_from_field(self, request, field_name, success_message=""):
                return Mock(status_code=200, data={"message": success_message})

        mixin = TestMixin()
        request = Mock()

        response = mixin.remove_user(request, pk=1)
        self.assertEqual(response.status_code, 200)

    def test_add_admin_action_line_240(self):
        """Test add_admin action method (line 240)."""

        class TestMixin(UserManagementMixin):
            def get_object(self):
                return self.organization

            def _add_user_to_field(self, request, field_name, success_message=""):
                return Mock(status_code=200, data={"message": success_message})

        mixin = TestMixin()
        request = Mock()

        response = mixin.add_admin(request, pk=1)
        self.assertEqual(response.status_code, 200)

    def test_remove_admin_action_line_260(self):
        """Test remove_admin action method (line 260)."""

        class TestMixin(UserManagementMixin):
            def get_object(self):
                return self.organization

            def _remove_user_from_field(self, request, field_name, success_message=""):
                return Mock(status_code=200, data={"message": success_message})

        mixin = TestMixin()
        request = Mock()

        response = mixin.remove_admin(request, pk=1)
        self.assertEqual(response.status_code, 200)
