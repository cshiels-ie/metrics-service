from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from .v1 import urls as v1_urls
from .views import HealthView, MetricsSpectacularSwaggerView, PingView

urlpatterns = [
    path("ping/", PingView.as_view(), name="ping"),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/", include(v1_urls)),
    # OpenAPI / Swagger UI docs.
    # DAB's ansible_base.api_documentation is excluded from dynamic URL
    # registration (via ANSIBLE_BASE_APPS_EXCLUDE_VIEW_LIST) so we register
    # the endpoints here with MetricsSpectacularSwaggerView in place of the
    # upstream SpectacularSwaggerView.  That subclass restores the gateway
    # service prefix (e.g. /api/metrics) in the schema URL so the Swagger UI
    # fetches the schema from the correct external path.
    path("api/v1/docs/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", MetricsSpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
