"""
Custom Swagger UI view with service-prefix-aware schema URL.

When the metrics service sits behind a gateway (e.g. the AAP Gateway) that
proxies requests under a prefix such as ``/api/metrics``, Django's ``reverse()``
generates paths that omit that prefix (e.g. ``/api/v1/docs/schema/``).  The
``ServicePrefixMiddleware`` stores the stripped prefix on the request as
``_api_service_prefix`` so that views can reconstruct the full external URL.

``MetricsSpectacularSwaggerView`` overrides ``_get_schema_url`` to prepend
the service prefix, giving the Swagger UI the correct schema location
(e.g. ``/api/metrics/v1/docs/schema/``) instead of the bare internal path.
"""

from drf_spectacular.plumbing import get_relative_url, set_query_parameters
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.reverse import reverse


class MetricsSpectacularSwaggerView(SpectacularSwaggerView):
    """Swagger UI view that restores the gateway service prefix in the schema URL.

    Without this override, the Swagger UI fetches the OpenAPI schema from the
    bare Django-generated path (e.g. ``/api/v1/docs/schema/``).  When the
    service is accessed through a gateway that prefixes all requests with
    ``/api/metrics``, that bare path is unreachable via the gateway and the
    Swagger UI fails to load.

    The override prepends the prefix stored by ``ServicePrefixMiddleware`` on
    ``request._api_service_prefix`` (e.g. ``/api/metrics``), so the Swagger UI
    receives the full externally-reachable URL
    (e.g. ``/api/metrics/v1/docs/schema/``).

    When the service is accessed directly (no gateway, no prefix), the
    attribute is absent and the URL is left unchanged.
    """

    def _get_schema_url(self, request):
        schema_url = self.url or get_relative_url(reverse(self.url_name, request=request))
        prefix = getattr(request, "_api_service_prefix", "")
        if prefix and schema_url.startswith("/api"):
            # Replace /api with /api/metrics (or whatever the prefix is)
            # e.g. /api/v1/docs/schema/ -> /api/metrics/v1/docs/schema/
            schema_url = prefix + schema_url[4:]
        return set_query_parameters(
            url=schema_url,
            lang=request.GET.get("lang"),
            version=request.GET.get("version"),
        )
