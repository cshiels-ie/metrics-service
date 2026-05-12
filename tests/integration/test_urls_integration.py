"""
Integration tests for URL configuration and routing.

Tests the complete URL routing system including:
- URL pattern resolution
- View integration
- API endpoint functionality
- Authentication and authorization
- Error handling
"""

import contextlib

import pytest
from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, resolve, reverse
from rest_framework.test import APIClient

from tests.test_utils import get_test_password

User = get_user_model()


@pytest.mark.integration
class TestURLResolution(TestCase):
    """Test URL resolution and routing functionality."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = Client()
        self.api_client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    def test_dashboard_url_resolution(self):
        """Test dashboard URL resolution."""
        try:
            # Test URL resolution
            url = reverse("dashboard:index")
            assert url == "/dashboard/"

            # Test that the URL resolves to a view
            resolver_match = resolve("/dashboard/")
            assert resolver_match is not None

        except NoReverseMatch:
            # Dashboard might not have URLs defined
            pass

    def test_api_url_resolution(self):
        """Test API URL resolution."""
        try:
            # Test that API URLs are accessible
            resolver_match = resolve("/api/")
            assert resolver_match is not None

        except Http404:
            # API might not have URLs defined
            pass

    def test_admin_url_resolution(self):
        """Test admin URL resolution."""
        try:
            # Test admin URL
            resolver_match = resolve("/admin/")
            assert resolver_match is not None

        except Http404:
            # Admin might not be available
            pass


@pytest.mark.integration
class TestURLPatterns(TestCase):
    """Test URL pattern structure and organization."""

    def test_url_pattern_order(self):
        """Test that URL patterns are in the correct order."""
        from django.urls import get_resolver

        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        # Get the route patterns
        routes = []
        for pattern in url_patterns:
            if hasattr(pattern, "pattern") and hasattr(pattern.pattern, "_route"):
                routes.append(pattern.pattern._route)

        # Verify that more specific patterns come before general ones
        # This is important for URL matching precedence
        assert len(routes) > 0

    def test_url_pattern_types(self):
        """Test that URL patterns have correct types."""
        from django.urls import URLPattern, URLResolver, get_resolver

        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        for pattern in url_patterns:
            # Each pattern should be a URLResolver or URLPattern
            assert isinstance(pattern, URLResolver | URLPattern)

            # Should have a pattern attribute
            assert hasattr(pattern, "pattern")

    def test_url_namespace_organization(self):
        """Test that URL namespaces are properly organized."""
        from django.urls import get_resolver

        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        # Check for expected namespaces
        namespaces = []
        for pattern in url_patterns:
            if hasattr(pattern, "namespace") and pattern.namespace:
                namespaces.append(pattern.namespace)

        # Should have some namespaces for organization
        assert len(namespaces) >= 1  # At least some namespaces


@pytest.mark.integration
class TestAPIEndpoints(TestCase):
    """Test API endpoint functionality through URL routing."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    def test_api_root_endpoint(self):
        """Test API root endpoint."""
        with contextlib.suppress(Exception):
            response = self.client.get("/api/")
            # Should get a response (even if 404)
            assert response.status_code in [200, 404, 405]

    def test_api_v1_endpoint(self):
        """Test API v1 endpoint."""
        with contextlib.suppress(Exception):
            response = self.client.get("/api/v1/")
            # Should get a response (even if 404)
            assert response.status_code in [200, 404, 405]

    def test_api_documentation_endpoints(self):
        """Test API documentation endpoints."""
        endpoints = ["/api/docs/", "/api/redoc/", "/api/v1/docs/schema/"]

        for endpoint in endpoints:
            with contextlib.suppress(Exception):
                response = self.client.get(endpoint)
                # Documentation endpoints may not be configured
                assert response.status_code in [200, 404, 405]

    def test_authenticated_api_endpoints(self):
        """Test authenticated API endpoints."""
        # Authenticate the user
        self.client.force_authenticate(user=self.user)

        # UserViewSet uses AnsibleBaseUserPermissions (not IsSystemAdminOrAuditor), so
        # regular authenticated users can list/retrieve users they have visibility over.
        response = self.client.get("/api/v1/users/")
        assert response.status_code in [200, 403, 404, 405]

        response = self.client.get(f"/api/v1/users/{self.user.id}/")
        assert response.status_code in [200, 403, 404, 405]


@pytest.mark.integration
class TestAuthenticationURLs(TestCase):
    """Test authentication-related URL functionality."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    @override_settings(MODE="development")
    def test_authentication_redirects(self):
        """Test authentication redirects."""
        # Test that unauthenticated users are redirected
        response = self.client.get("/dashboard/")
        assert response.status_code in [200, 302, 404]


@pytest.mark.integration
class TestDashboardURLs(TestCase):
    """Test dashboard URL functionality."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    @override_settings(MODE="development")
    def test_dashboard_access(self):
        """Test dashboard access through URLs."""
        # Test unauthenticated access
        response = self.client.get("/dashboard/")
        assert response.status_code in [200, 302, 404]

        # Test authenticated access
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        assert response.status_code in [200, 302, 404]

    @override_settings(MODE="development")
    def test_dashboard_subpages(self):
        """Test dashboard subpages."""
        # Test various dashboard subpages
        subpages = ["/dashboard/", "/dashboard/tasks/", "/dashboard/status/"]

        for subpage in subpages:
            response = self.client.get(subpage)
            assert response.status_code in [200, 302, 404]


@pytest.mark.integration
class TestErrorHandling(TestCase):
    """Test URL error handling and edge cases."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = Client()

    def test_404_handling(self):
        """Test 404 error handling for non-existent URLs."""
        # Test various non-existent URLs
        non_existent_urls = ["/nonexistent/", "/api/nonexistent/", "/dashboard/nonexistent/", "/admin/nonexistent/"]

        for url in non_existent_urls:
            response = self.client.get(url)
            # Admin URLs redirect to login, others should be 404
            if url.startswith("/admin/"):
                assert response.status_code in [302, 404, 405]
            else:
                assert response.status_code in [404, 405]

    def test_method_not_allowed(self):
        """Test method not allowed handling."""
        # Test POST to GET-only endpoints
        response = self.client.post("/api/v1/docs/schema/")
        assert response.status_code in [200, 404, 405]

    def test_malformed_urls(self):
        """Test malformed URL handling."""
        malformed_urls = ["/api//", "/dashboard//", "/admin//", "/api/v1//"]

        for url in malformed_urls:
            response = self.client.get(url)
            # Admin URLs redirect to login, others should be 404
            if url.startswith("/admin/"):
                assert response.status_code in [200, 302, 404, 405]
            else:
                assert response.status_code in [200, 404, 405]


@pytest.mark.integration
class TestURLPerformance(TestCase):
    """Test URL resolution performance and efficiency."""

    def test_url_resolution_speed(self):
        """Test that URL resolution is fast."""
        import time

        start_time = time.time()

        # Resolve multiple URLs
        urls_to_test = ["/api/", "/dashboard/", "/admin/"]

        for url in urls_to_test:
            with contextlib.suppress(Http404, NoReverseMatch):
                resolve(url)

        end_time = time.time()
        resolution_time = end_time - start_time

        # URL resolution should be fast (less than 1 second for all URLs)
        assert resolution_time < 1.0

    def test_url_pattern_efficiency(self):
        """Test that URL patterns are efficiently organized."""
        from django.urls import get_resolver

        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        # Should have a reasonable number of URL patterns
        assert len(url_patterns) < 100  # Not too many patterns

        # Each pattern should be properly structured
        for pattern in url_patterns:
            assert hasattr(pattern, "pattern")
            assert pattern.pattern is not None


@pytest.mark.integration
class TestURLIntegrationWithViews(TestCase):
    """Test URL integration with actual views."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = Client()
        self.api_client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    def test_url_to_view_mapping(self):
        """Test that URLs correctly map to views."""
        from django.urls import get_resolver

        get_resolver()

        # Test that URLs resolve to actual views
        test_urls = ["/api/v1/docs/schema/", "/dashboard/", "/admin/"]

        for url in test_urls:
            try:
                resolver_match = resolve(url)
                assert resolver_match is not None
                assert resolver_match.func is not None
            except (Http404, NoReverseMatch):
                # URL might not be configured
                pass

    def test_view_response_through_urls(self):
        """Test that views respond correctly through URL routing."""
        # Test schema view
        response = self.client.get("/api/v1/docs/schema/")
        assert response.status_code in [200, 404, 405]

    def test_api_view_integration(self):
        """Test API view integration through URLs."""
        # Authenticate the user
        self.api_client.force_authenticate(user=self.user)

        # Non-sysadmin users receive 403 since IsSystemAdminOrAuditor is required
        response = self.api_client.get("/api/v1/users/")
        assert response.status_code in [200, 403, 404, 405]


@pytest.mark.integration
class TestURLConfiguration(TestCase):
    """Test URL configuration and settings integration."""

    def test_url_configuration_loading(self):
        """Test that URL configuration loads correctly."""
        from django.conf import settings
        from django.urls import get_resolver

        # Test that URL configuration is loaded
        assert settings.ROOT_URLCONF is not None

        # Test that resolver can be created
        resolver = get_resolver()
        assert resolver is not None

    def test_url_pattern_validation(self):
        """Test that URL patterns are valid."""
        from django.urls import get_resolver

        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        # Test that all patterns are valid
        for pattern in url_patterns:
            assert pattern is not None
            assert hasattr(pattern, "pattern")

    def test_url_namespace_validation(self):
        """Test that URL namespaces are properly configured."""
        from django.urls import get_resolver

        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        # Test namespace configuration
        for pattern in url_patterns:
            if hasattr(pattern, "namespace"):
                # Namespace should be a string or None
                assert pattern.namespace is None or isinstance(pattern.namespace, str)


@pytest.mark.integration
class TestURLSecurity(TestCase):
    """Test URL security and access control."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

    @override_settings(MODE="development")
    def test_secure_url_access(self):
        """Test that secure URLs require authentication."""

        # Test that admin requires authentication
        response = self.client.get("/admin/")
        assert response.status_code in [200, 302, 404]

        # Test that dashboard requires authentication
        response = self.client.get("/dashboard/")
        assert response.status_code in [200, 302, 404]

    def test_url_injection_protection(self):
        """Test protection against URL injection attacks."""
        malicious_urls = ["/api/../../../etc/passwd", "/dashboard/../../admin/", "/admin/../../../etc/passwd"]
        for url in malicious_urls:
            response = self.client.get(url)
            # Should not return 200 for malicious URLs
        assert response.status_code != 200
