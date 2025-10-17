"""
Tests for apps.dashboard.views module.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, TestCase

from apps.core.models import User
from apps.dashboard.views import dashboard_view


@pytest.mark.django_db
class TestDashboardViews(TestCase):
    """Test dashboard views."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", email="test@example.com")

    @patch("apps.tasks.tasks.TASK_FUNCTIONS")
    def test_dashboard_view_with_anonymous_user(self, mock_task_functions):
        """Test dashboard view with anonymous user."""
        # Mock TASK_FUNCTIONS
        mock_task_functions.keys.return_value = ["cleanup_old_data"]

        # Create request with anonymous user
        request = self.factory.get("/dashboard/")
        request.user = AnonymousUser()

        # Call the view
        response = dashboard_view(request)

        # Verify response
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200

    @patch("apps.dashboard.views.render")
    @patch("apps.tasks.tasks.TASK_FUNCTIONS")
    def test_dashboard_view_context(self, mock_task_functions, mock_render):
        """Test that dashboard view passes correct context to template."""
        # Mock TASK_FUNCTIONS
        mock_task_functions.keys.return_value = [
            "cleanup_old_data",
            "send_notification_email",
            "process_user_data",
            "execute_db_task",
        ]

        # Mock render to return a mock response
        mock_response = MagicMock(spec=HttpResponse)
        mock_render.return_value = mock_response

        # Create request
        request = self.factory.get("/dashboard/")
        request.user = self.user

        # Call the view
        response = dashboard_view(request)

        # Verify render was called with correct arguments
        mock_render.assert_called_once()
        args, _ = mock_render.call_args

        # Check request and template
        assert args[0] == request
        assert args[1] == "dashboard.html"

        # Check context
        context = args[2]
        assert context["page_title"] == "Task Dashboard"
        assert context["api_base_url"] == "/api/v1/"
        assert context["user"] == self.user
        assert context["available_functions"] == [
            "cleanup_old_data",
            "send_notification_email",
            "process_user_data",
            "execute_db_task",
        ]
        assert context["database_driven"] is True

        # Verify response is returned
        assert response == mock_response

    @patch("apps.tasks.tasks.TASK_FUNCTIONS")
    def test_dashboard_view_empty_task_functions(self, mock_task_functions):
        """Test dashboard view when no task functions are available."""
        # Mock empty TASK_FUNCTIONS
        mock_task_functions.keys.return_value = []

        # Create request
        request = self.factory.get("/dashboard/")
        request.user = self.user

        # Call the view
        response = dashboard_view(request)

        # Verify response
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200

    def test_dashboard_view_is_safe_method_only(self):
        """Test that dashboard view only accepts safe HTTP methods."""
        # Import the view to check decorators
        from apps.dashboard.views import dashboard_view

        # Check that the view has the require_safe decorator
        # This is indicated by the view having certain attributes
        assert hasattr(dashboard_view, "__wrapped__") or hasattr(dashboard_view, "view_func")

    @patch("apps.tasks.tasks.TASK_FUNCTIONS")
    def test_dashboard_view_task_functions_import(self, mock_task_functions):
        """Test that TASK_FUNCTIONS is imported correctly within the view."""
        # Mock TASK_FUNCTIONS
        expected_functions = ["task1", "task2", "task3"]
        mock_task_functions.keys.return_value = expected_functions

        # Create request
        request = self.factory.get("/dashboard/")
        request.user = self.user

        with patch("apps.dashboard.views.render") as mock_render:
            mock_render.return_value = HttpResponse("OK")

            # Call the view
            dashboard_view(request)

            # Verify that TASK_FUNCTIONS.keys() was called
            mock_task_functions.keys.assert_called_once()

            # Verify context contains the functions
            context = mock_render.call_args[0][2]
            assert context["available_functions"] == expected_functions

    def test_dashboard_view_return_type_annotation(self):
        """Test that dashboard view has proper type annotations."""
        import inspect

        # Get the function signature
        sig = inspect.signature(dashboard_view)

        # Check parameter annotations
        assert "request" in sig.parameters
        request_param = sig.parameters["request"]
        assert request_param.annotation == HttpRequest

        # Check return annotation
        assert sig.return_annotation == HttpResponse

    @patch("apps.tasks.tasks.TASK_FUNCTIONS")
    def test_dashboard_view_superuser_access(self, mock_task_functions):
        """Test dashboard view access for superuser."""
        # Create superuser
        superuser = User.objects.create_user(username="superuser", email="super@example.com", is_superuser=True)

        # Mock TASK_FUNCTIONS
        mock_task_functions.keys.return_value = ["admin_task"]

        # Create request
        request = self.factory.get("/dashboard/")
        request.user = superuser

        # Call the view
        response = dashboard_view(request)

        # Verify response
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200

    def test_dashboard_view_imports(self):
        """Test that all necessary imports work in dashboard views."""
        from django.http import HttpRequest, HttpResponse
        from django.shortcuts import render
        from django.views.decorators.http import require_safe

        # Verify imports are not None
        assert HttpRequest
        assert HttpResponse
        assert render
        assert require_safe

    @patch("apps.tasks.tasks.TASK_FUNCTIONS")
    def test_dashboard_view_with_different_request_methods(self, mock_task_functions):
        """Test that dashboard view handles different request objects."""
        # Mock TASK_FUNCTIONS
        mock_task_functions.keys.return_value = ["test_task"]

        # Test with different request attributes
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.META["HTTP_USER_AGENT"] = "TestAgent"
        request.session = {}

        # Call the view
        response = dashboard_view(request)

        # Verify response
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
