"""
Tests for AAP-80896: Swagger UI schema URL and feature_flags redirect include service prefix.

Two bugs were fixed:

1. The Swagger UI (/api/metrics/v1/docs/) fetched its OpenAPI schema from a
   bare internal path (/api/v1/docs/schema/) that is unreachable through the
   AAP Gateway.  MetricsSpectacularSwaggerView overrides _get_schema_url to
   prepend the service prefix stored on the request by ServicePrefixMiddleware.

2. The feature_flags redirect (/api/v1/feature_flags/) sent a 301 Location
   header pointing to /api/v1/feature_flags/states/ — a path unreachable
   through the gateway.  The redirect URL was updated to the fully-prefixed
   /api/metrics/v1/feature_flags/states/.
"""

import pytest
from django.test import RequestFactory, TestCase
from django.urls import set_script_prefix
from rest_framework.test import APIClient


class TestMetricsSpectacularSwaggerView(TestCase):
    """Unit tests for MetricsSpectacularSwaggerView._get_schema_url."""

    def _make_request(self, path="/api/v1/docs/", api_service_prefix=None):
        """Return a GET request, optionally with _api_service_prefix set."""
        factory = RequestFactory()
        request = factory.get(path)
        if api_service_prefix is not None:
            request._api_service_prefix = api_service_prefix
        return request

    def test_schema_url_without_prefix_is_unchanged(self):
        """When no service prefix is present, the schema URL is the bare Django path."""
        from apps.core.views.swagger import MetricsSpectacularSwaggerView

        view = MetricsSpectacularSwaggerView()
        request = self._make_request()
        schema_url = view._get_schema_url(request)
        # Without prefix the URL should be the canonical Django-generated path.
        self.assertIn("/api/v1/docs/schema/", schema_url)
        self.assertNotIn("/api/metrics", schema_url)

    def test_schema_url_with_api_metrics_prefix(self):
        """When _api_service_prefix='/api/metrics', schema URL gains that prefix."""
        from apps.core.views.swagger import MetricsSpectacularSwaggerView

        view = MetricsSpectacularSwaggerView()
        request = self._make_request(api_service_prefix="/api/metrics")
        schema_url = view._get_schema_url(request)
        self.assertIn("/api/metrics/v1/docs/schema/", schema_url)
        # The old bare internal path must not appear.
        self.assertNotIn("/api/v1/docs/schema/", schema_url)

    def test_schema_url_with_custom_prefix(self):
        """Any non-empty _api_service_prefix is prepended correctly."""
        from apps.core.views.swagger import MetricsSpectacularSwaggerView

        view = MetricsSpectacularSwaggerView()
        request = self._make_request(api_service_prefix="/api/custom-service")
        schema_url = view._get_schema_url(request)
        self.assertIn("/api/custom-service/v1/docs/schema/", schema_url)

    def test_schema_url_with_empty_string_prefix_is_unchanged(self):
        """An empty _api_service_prefix leaves the URL unchanged."""
        from apps.core.views.swagger import MetricsSpectacularSwaggerView

        view = MetricsSpectacularSwaggerView()
        request = self._make_request(api_service_prefix="")
        schema_url = view._get_schema_url(request)
        self.assertIn("/api/v1/docs/schema/", schema_url)

    def test_schema_url_query_params_are_preserved(self):
        """lang/version query params from the request are forwarded to the schema URL."""
        from apps.core.views.swagger import MetricsSpectacularSwaggerView

        view = MetricsSpectacularSwaggerView()
        factory = RequestFactory()
        request = factory.get("/api/v1/docs/", {"lang": "en", "version": "v1"})
        request._api_service_prefix = "/api/metrics"
        schema_url = view._get_schema_url(request)
        self.assertIn("lang=en", schema_url)
        self.assertIn("version=v1", schema_url)

    def test_view_class_is_subclass_of_spectacular_swagger_view(self):
        """MetricsSpectacularSwaggerView is a proper subclass."""
        from drf_spectacular.views import SpectacularSwaggerView

        from apps.core.views.swagger import MetricsSpectacularSwaggerView

        self.assertTrue(issubclass(MetricsSpectacularSwaggerView, SpectacularSwaggerView))

    def test_view_exported_from_core_views(self):
        """MetricsSpectacularSwaggerView is exported from apps.core.views."""
        from apps.core.views import MetricsSpectacularSwaggerView

        self.assertIsNotNone(MetricsSpectacularSwaggerView)


@pytest.mark.django_db
class TestSwaggerEndpointWithPrefix:
    """Integration tests for the Swagger UI endpoint with the gateway prefix."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        set_script_prefix("/")
        yield
        set_script_prefix("/")

    def test_swagger_ui_endpoint_responds_200(self):
        """GET /api/v1/docs/ returns 200 (Swagger UI page)."""
        response = self.client.get("/api/v1/docs/")
        assert response.status_code == 200

    def test_swagger_schema_endpoint_responds_200(self):
        """GET /api/v1/docs/schema/ returns 200 (OpenAPI JSON schema)."""
        response = self.client.get("/api/v1/docs/schema/")
        assert response.status_code == 200

    def test_swagger_ui_via_api_metrics_prefix_responds_200(self):
        """GET /api/metrics-service/v1/docs/ (service prefix) returns 200."""
        # The service name prefix derived from ROOT_URLCONF is 'metrics-service'.
        from django.conf import settings

        service_name = settings.ROOT_URLCONF.split(".")[0].replace("_", "-")
        response = self.client.get(f"/api/{service_name}/v1/docs/")
        assert response.status_code == 200

    def test_swagger_ui_schema_url_contains_service_prefix(self):
        """Swagger UI served via /api/<svc>/v1/docs/ embeds the prefixed schema URL.

        The ``{{ schema_url|escapejs }}`` template filter may encode non-ASCII
        characters and some ASCII punctuation (e.g. '-' → \\u002D) as JSON
        unicode escapes.  We therefore search for the JS-escaped form of the
        URL as well as the literal form.
        """
        from django.conf import settings
        from django.utils.html import escapejs

        service_name = settings.ROOT_URLCONF.split(".")[0].replace("_", "-")
        response = self.client.get(
            f"/api/{service_name}/v1/docs/",
            HTTP_ACCEPT="text/html",
        )
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        expected_path = f"/api/{service_name}/v1/docs/schema/"
        # The schema URL may appear as-is or JS-escaped by the template filter.
        assert expected_path in html or escapejs(expected_path) in html


@pytest.mark.django_db
class TestFeatureFlagsRedirect:
    """Tests for the feature_flags redirect URL (AAP-80896 fix 2)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        set_script_prefix("/")
        yield
        set_script_prefix("/")

    def test_feature_flags_redirect_location_contains_metrics_prefix(self):
        """GET /api/v1/feature_flags/ redirects to a URL that includes /api/metrics/."""
        response = self.client.get("/api/v1/feature_flags/", follow=False)
        assert response.status_code == 301
        location = response["Location"]
        assert location == "/api/metrics/v1/feature_flags/states/"

    def test_feature_flags_redirect_is_permanent(self):
        """The redirect is permanent (HTTP 301)."""
        response = self.client.get("/api/v1/feature_flags/", follow=False)
        assert response.status_code == 301

    def test_feature_flags_redirect_via_service_prefix_uses_prefixed_location(self):
        """GET /api/<svc>/v1/feature_flags/ redirects to the prefixed states URL."""
        from django.conf import settings

        service_name = settings.ROOT_URLCONF.split(".")[0].replace("_", "-")
        response = self.client.get(f"/api/{service_name}/v1/feature_flags/", follow=False)
        assert response.status_code == 301
        location = response["Location"]
        # The Location must include the metrics service prefix.
        assert location == "/api/metrics/v1/feature_flags/states/"
