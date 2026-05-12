"""
Unit tests for development mode permission functionality.

Tests that development endpoints are properly restricted when development mode is disabled.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestDevelopmentModeDisabled(TestCase):
    """Test that endpoints are blocked when development mode is disabled."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")  # noqa: S105

    @override_settings(MODE="production")
    def test_tasks_api_returns_403_when_development_mode_disabled(self):
        """Test that tasks API returns 403 when development mode is disabled."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/tasks/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @override_settings(MODE="production")
    def test_dashboard_returns_403_when_development_mode_disabled(self):
        """Test that dashboard returns 403 when development mode is disabled."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/dashboard/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
