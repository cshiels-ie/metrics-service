"""
Unit tests for tasks API permission enforcement.

Tests that the tasks API requires system admin or auditor roles.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestTasksAPIPermissions(TestCase):
    """Test that tasks API requires IsSystemAdminOrAuditor."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")  # noqa: S105

    def test_tasks_api_returns_403_for_regular_user(self):
        """Test that tasks API returns 403 for a non-admin, non-auditor user."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/tasks/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tasks_api_allows_superuser(self):
        """Test that tasks API allows superuser access."""
        superuser = User.objects.create_superuser(username="admin", email="admin@example.com", password="testpass123")  # noqa: S105
        self.client.force_authenticate(user=superuser)

        response = self.client.get("/api/v1/tasks/")

        assert response.status_code == status.HTTP_200_OK
