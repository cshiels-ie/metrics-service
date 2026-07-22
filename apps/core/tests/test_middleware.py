"""Tests for core middleware."""

import pytest
from django.conf import settings
from django.test import TestCase
from django.urls import set_script_prefix
from rest_framework import status
from rest_framework.test import APIClient


def get_service_name():
    """Get the service name from settings."""
    return settings.ROOT_URLCONF.split(".")[0].replace("_", "-")


# Test parameters for the three URL access patterns
SERVICE_NAME = get_service_name()
URL_PATTERNS = [
    pytest.param(
        "/api/v1/",
        None,  # No prefix expected
        id="canonical",
    ),
    pytest.param(
        f"/{SERVICE_NAME}/api/v1/",
        f"/{SERVICE_NAME}/",
        id="service-prefix",
    ),
    pytest.param(
        f"/api/{SERVICE_NAME}/v1/",
        f"/api/{SERVICE_NAME}/",
        id="api-service-prefix",
    ),
]


class TestServicePrefixMiddleware(TestCase):
    """Tests for ServicePrefixMiddleware.

    Two routing modes:
    1. /api/<service-name>/... → /api/... (no SCRIPT_NAME, canonical URLs)
    2. /<service-name>/... → /... (SCRIPT_NAME set for prefixed URLs)
    """

    def setUp(self):
        self.client = APIClient()
        self.service_name = get_service_name()

    def tearDown(self):
        # Reset script prefix to avoid affecting other tests
        set_script_prefix("/")

    def test_request_without_prefix_works(self):
        """Direct requests without service prefix work normally."""
        response = self.client.get("/ping/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_request_with_api_service_prefix_routes_to_api(self):
        """/api/<service-name>/v1/ routes to /api/v1/."""
        response = self.client.get(f"/api/{self.service_name}/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_service_prefix_preserves_prefix_in_urls(self):
        """/api/<service-name>/... generates URLs with the service prefix."""
        response = self.client.get(f"/api/{self.service_name}/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # URLs should include the service prefix
        for url in data.values():
            self.assertIn(f"/api/{self.service_name}/v1/", url)

    def test_api_service_prefix_root_returns_prefixed_urls(self):
        """/api/<service-name>/ returns URLs with the service prefix."""
        response = self.client.get(f"/api/{self.service_name}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should have v1 endpoint
        self.assertIn("v1", data)
        # v1 URL should include service prefix
        self.assertIn(f"/api/{self.service_name}/v1/", data["v1"])

    def test_request_with_service_prefix_routes_to_root(self):
        """/<service-name>/ping/ routes to /ping/."""
        response = self.client.get(f"/{self.service_name}/ping/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"ping": "pong"})

    def test_service_prefix_sets_script_name(self):
        """/<service-name>/... sets SCRIPT_NAME so URLs include the prefix."""
        response = self.client.get(f"/{self.service_name}/api/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # URLs should include the service prefix
        for url in data.values():
            self.assertIn(f"/{self.service_name}/", url)


class TestAPIRootViewMiddleware(TestCase):
    def setUp(self):
        self.client = APIClient()

    def tearDown(self):
        # Reset script prefix to avoid affecting other tests
        set_script_prefix("/")

    def test_middleware_serves_index_for_404_with_children(self):
        # /api/v1/ has child routes, so even if it were a 404, middleware would serve index
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_trailing_slash_404_not_intercepted(self):
        # Paths not ending in / should not be intercepted
        response = self.client.get("/nonexistent")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_404_without_children_not_intercepted(self):
        # A path with no child routes should remain 404
        response = self.client.get("/completely/fake/path/with/no/children/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestServicePrefixMiddlewareUnit(TestCase):
    """Unit tests for ServicePrefixMiddleware."""

    def test_middleware_class_exists(self):
        from apps.core.middleware import ServicePrefixMiddleware

        self.assertTrue(callable(ServicePrefixMiddleware))

    def test_middleware_get_response_callable(self):
        from apps.core.middleware import ServicePrefixMiddleware

        def mock_get_response(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = ServicePrefixMiddleware(mock_get_response)
        self.assertIsNotNone(middleware)

    def test_middleware_uses_url_prefix_when_set(self):
        """When URL_PREFIX is set, api_prefix and service_prefix are derived from it."""
        from apps.core.middleware import ServicePrefixMiddleware

        with self.settings(URL_PREFIX="/api/metrics"):

            def mock_get_response(request):
                from django.http import HttpResponse

                return HttpResponse("OK")

            middleware = ServicePrefixMiddleware(mock_get_response)
            self.assertEqual(middleware.api_prefix, "/api/metrics")
            self.assertEqual(middleware.service_prefix, "/metrics")

    def test_middleware_falls_back_to_root_urlconf_when_url_prefix_unset(self):
        """When URL_PREFIX is None, prefix is derived from ROOT_URLCONF."""
        from apps.core.middleware import ServicePrefixMiddleware

        with self.settings(URL_PREFIX=None):

            def mock_get_response(request):
                from django.http import HttpResponse

                return HttpResponse("OK")

            middleware = ServicePrefixMiddleware(mock_get_response)
            expected_service_name = settings.ROOT_URLCONF.split(".")[0].replace("_", "-")
            self.assertEqual(middleware.service_prefix, f"/{expected_service_name}")
            self.assertEqual(middleware.api_prefix, f"/api/{expected_service_name}")

    def test_middleware_routes_url_prefix_path(self):
        """With URL_PREFIX set, requests at the API prefix are rewritten to /api/...

        Directly instantiates ServicePrefixMiddleware inside the settings context so
        the cached api_prefix reflects the override — using self.client would not
        work because ClientHandler loads middleware before override_settings takes
        effect.
        """
        from django.test import RequestFactory

        from apps.core.middleware import ServicePrefixMiddleware

        with self.settings(URL_PREFIX="/api/metrics"):
            factory = RequestFactory()
            request = factory.get("/api/metrics/v1/")

            rewritten_paths = []

            def capture_get_response(req):
                from django.http import HttpResponse

                rewritten_paths.append(req.path_info)
                return HttpResponse("OK")

            middleware = ServicePrefixMiddleware(capture_get_response)
            middleware(request)

            # Path must be rewritten to the canonical /api/ form
            self.assertEqual(rewritten_paths[0], "/api/v1/")
            # The original prefixed path is stored for DRF breadcrumbs / templates
            self.assertEqual(request._api_service_prefix, "/api/metrics")
            # get_full_path() must restore the prefixed form so response URLs are correct
            self.assertIn("/api/metrics/", request.get_full_path())

    def test_middleware_strips_trailing_slash_from_url_prefix(self):
        """URL_PREFIX with a trailing slash is handled correctly."""
        from apps.core.middleware import ServicePrefixMiddleware

        with self.settings(URL_PREFIX="/api/metrics/"):

            def mock_get_response(request):
                from django.http import HttpResponse

                return HttpResponse("OK")

            middleware = ServicePrefixMiddleware(mock_get_response)
            self.assertEqual(middleware.api_prefix, "/api/metrics")
            self.assertEqual(middleware.service_prefix, "/metrics")

    def test_middleware_url_prefix_not_under_api_segment(self):
        """URL_PREFIX that does not start with '/api/' is used verbatim as service_prefix."""
        from apps.core.middleware import ServicePrefixMiddleware

        with self.settings(URL_PREFIX="/apis/metrics"):

            def mock_get_response(request):
                from django.http import HttpResponse

                return HttpResponse("OK")

            middleware = ServicePrefixMiddleware(mock_get_response)
            self.assertEqual(middleware.api_prefix, "/apis/metrics")
            # '/apis/metrics' does not start with '/api/' so service_prefix is unchanged
            self.assertEqual(middleware.service_prefix, "/apis/metrics")


class TestAPIRootViewMiddlewareUnit(TestCase):
    """Unit tests for APIRootViewMiddleware."""

    def test_middleware_class_exists(self):
        from apps.core.middleware import APIRootViewMiddleware

        self.assertTrue(callable(APIRootViewMiddleware))

    def test_middleware_get_response_callable(self):
        from apps.core.middleware import APIRootViewMiddleware

        def mock_get_response(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = APIRootViewMiddleware(mock_get_response)
        self.assertIsNotNone(middleware)


@pytest.mark.django_db
class TestBrowsableAPIURLs:
    """Test that all URLs in the browsable API are correct for all access patterns.

    Tests three access patterns:
    1. /api/v1/                       → canonical URLs (no prefix)
    2. /<service>/api/v1/             → prefixed URLs (/<service>/...)
    3. /api/<service>/v1/             → prefixed URLs (/api/<service>/...)

    For each pattern, verifies:
    - Breadcrumb URLs
    - Form action URLs
    - GET button href
    - Request info path display
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.service_name = SERVICE_NAME
        set_script_prefix("/")
        yield
        set_script_prefix("/")

    def _get_html_content(self, path):
        """Get HTML response content."""
        response = self.client.get(path, HTTP_ACCEPT="text/html")
        assert response.status_code == status.HTTP_200_OK
        return response.content.decode("utf-8")

    def _extract_breadcrumbs(self, content):
        """Extract breadcrumb URLs from HTML content."""
        import re

        breadcrumb_match = re.search(r'<ul class="breadcrumb"[^>]*>(.*?)</ul>', content, re.DOTALL)
        if breadcrumb_match:
            breadcrumb_html = breadcrumb_match.group(1)
            return re.findall(r'href="([^"]+)"', breadcrumb_html)
        return []

    def _extract_form_actions(self, content):
        """Extract form action URLs from HTML content."""
        import re

        return re.findall(r'action="([^"]+)"', content)

    def _extract_request_info_path(self, content):
        """Extract the path shown in request info (e.g., 'GET /api/v1/')."""
        import re

        match = re.search(r"<b>GET</b>\s+([^\s<]+)", content)
        return match.group(1) if match else None

    def _extract_get_button_href(self, content):
        """Extract the GET button href."""
        import re

        match = re.search(r'href="([^"]+)"[^>]*>\s*GET\s*</a>', content)
        return match.group(1) if match else None

    def _assert_urls_have_correct_prefix(self, urls, expected_prefix):
        """Assert that URLs have the correct prefix (or no prefix if None)."""
        api_urls = [url for url in urls if "/api" in url]
        assert len(api_urls) > 0, f"Expected API URLs, got: {urls}"

        for url in api_urls:
            if expected_prefix is None:
                # Canonical - should not contain service name
                assert f"/{self.service_name}/" not in url, f"URL {url} should not have service prefix"
            else:
                # Prefixed - should contain the expected prefix
                assert expected_prefix in url, f"URL {url} should contain {expected_prefix}"

    @pytest.mark.parametrize("path,expected_prefix", URL_PATTERNS)
    def test_breadcrumbs(self, path, expected_prefix):
        """Breadcrumb URLs have correct prefix."""
        content = self._get_html_content(path)
        breadcrumbs = self._extract_breadcrumbs(content)
        # Breadcrumbs may not be present in all templates
        if len(breadcrumbs) > 0:
            self._assert_urls_have_correct_prefix(breadcrumbs, expected_prefix)

    @pytest.mark.parametrize("path,expected_prefix", URL_PATTERNS)
    def test_form_actions(self, path, expected_prefix):
        """Form action URLs have correct prefix."""
        content = self._get_html_content(path)
        form_actions = self._extract_form_actions(content)
        self._assert_urls_have_correct_prefix(form_actions, expected_prefix)

    @pytest.mark.parametrize("path,expected_prefix", URL_PATTERNS)
    def test_get_button(self, path, expected_prefix):
        """GET button href has correct prefix."""
        content = self._get_html_content(path)
        get_href = self._extract_get_button_href(content)
        assert get_href is not None, "GET button href not found"
        self._assert_urls_have_correct_prefix([get_href], expected_prefix)

    @pytest.mark.parametrize("path,expected_prefix", URL_PATTERNS)
    def test_request_info_path(self, path, expected_prefix):
        """Request info path display has correct prefix."""
        content = self._get_html_content(path)
        request_path = self._extract_request_info_path(content)
        assert request_path is not None, "Request info path not found"
        self._assert_urls_have_correct_prefix([request_path], expected_prefix)

    @pytest.mark.parametrize("path,expected_prefix", URL_PATTERNS)
    def test_no_double_slashes_in_breadcrumbs(self, path, expected_prefix):
        """Breadcrumb URLs should not contain double slashes."""
        content = self._get_html_content(path)
        breadcrumbs = self._extract_breadcrumbs(content)
        for url in breadcrumbs:
            # Check for double slashes (but not in http://)
            url_without_protocol = url.replace("http://", "").replace("https://", "")
            assert "//" not in url_without_protocol, f"Double slash found in URL: {url}"


# ---------------------------------------------------------------------------
# NullByteQueryParamMiddleware tests  (AAP-74806)
# ---------------------------------------------------------------------------


class TestNullByteQueryParamMiddleware(TestCase):
    """Tests for NullByteQueryParamMiddleware.

    Null bytes (%00) in query parameter values cause PostgreSQL to raise a
    DataError, which DAB's FieldLookupBackend does not catch, resulting in a
    500.  The middleware must intercept these requests and return 400.
    """

    def setUp(self):
        self.client = APIClient()

    # --- _contains_null_byte unit tests ---

    def test_contains_null_byte_detects_percent_encoded(self):
        """'%00' is recognised as a null byte."""
        from apps.core.middleware.null_byte import NullByteQueryParamMiddleware

        self.assertTrue(NullByteQueryParamMiddleware._contains_null_byte("operation=%00"))

    def test_contains_null_byte_detects_percent_encoded_among_other_params(self):
        """'%00' is detected when other query params are also present."""
        from apps.core.middleware.null_byte import NullByteQueryParamMiddleware

        self.assertTrue(NullByteQueryParamMiddleware._contains_null_byte("q=%00&other=val"))

    def test_contains_null_byte_detects_literal_null(self):
        """A literal \\x00 character is recognised."""
        from apps.core.middleware.null_byte import NullByteQueryParamMiddleware

        self.assertTrue(NullByteQueryParamMiddleware._contains_null_byte("operation=foo\x00bar"))

    def test_contains_null_byte_clean_string_returns_false(self):
        """A clean query string without null bytes returns False."""
        from apps.core.middleware.null_byte import NullByteQueryParamMiddleware

        self.assertFalse(NullByteQueryParamMiddleware._contains_null_byte("operation=create&page=1"))

    def test_contains_null_byte_empty_string_returns_false(self):
        """An empty query string returns False."""
        from apps.core.middleware.null_byte import NullByteQueryParamMiddleware

        self.assertFalse(NullByteQueryParamMiddleware._contains_null_byte(""))

    def test_contains_null_byte_unicode_without_null_returns_false(self):
        """Unicode characters that do not encode a null byte are allowed."""
        from apps.core.middleware.null_byte import NullByteQueryParamMiddleware

        # %E2%80%99 = U+2019 RIGHT SINGLE QUOTATION MARK — no null byte
        self.assertFalse(NullByteQueryParamMiddleware._contains_null_byte("operation=%E2%80%99"))

    # --- Integration tests against the live test server ---

    def test_activitystream_null_byte_returns_400(self):
        """GET /api/v1/activitystream/?operation=%E2%80%99%00%E2%80%99 returns 400.

        This is the exact reproducer from AAP-74806.  Without the middleware
        the request reaches PostgreSQL and produces a 500.
        """
        # Use the raw WSGI path so Django sees the percent-encoded form
        response = self.client.get(
            "/api/v1/activitystream/",
            QUERY_STRING="operation=%E2%80%99%00%E2%80%99",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("null byte", data["detail"].lower())

    def test_null_byte_param_returns_400_on_tasks_endpoint(self):
        """Null byte in query param returns 400 on any list endpoint, not just activitystream."""
        response = self.client.get(
            "/api/v1/tasks/",
            QUERY_STRING="name=%00",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_null_byte_only_in_value_returns_400(self):
        """Null byte embedded in a multi-character value is still rejected."""
        response = self.client.get(
            "/api/v1/activitystream/",
            QUERY_STRING="operation=foo%00bar",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_clean_request_passes_through(self):
        """A request without null bytes passes through and is not affected."""
        response = self.client.get("/api/v1/activitystream/", QUERY_STRING="page=1")
        # Should not be a middleware 400; activitystream may return 200 or other non-400
        self.assertNotEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unicode_without_null_byte_passes_through(self):
        """Non-ASCII characters that are not null bytes are allowed through."""
        # %E2%80%99 = ' (U+2019) — valid UTF-8, no null byte
        response = self.client.get(
            "/api/v1/activitystream/",
            QUERY_STRING="operation=%E2%80%99",
        )
        # The middleware must NOT return 400 for this; the filter backend may return
        # its own error, but that is not a middleware-level null-byte rejection.
        # We only check that the middleware did not misfire.
        data = response.json() if response.status_code == 400 else {}
        if response.status_code == 400:
            self.assertNotIn("null byte", data.get("detail", "").lower())

    def test_middleware_response_is_json(self):
        """400 response from the middleware has a JSON Content-Type."""
        response = self.client.get(
            "/api/v1/tasks/",
            QUERY_STRING="name=%00",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("application/json", response.get("Content-Type", ""))
