"""
URL configuration for the apps package.

This file is for custom URL patterns that need to load BEFORE individual app
URLs. Use this for:

- Service-level customizations (top-level urls.py is framework-managed)
- Priority/override patterns that must match before app-defined routes
- Cross-app endpoints combining functionality from multiple apps

This file loads at step 3 in the URL loading order, before individual apps
(step 4). For full documentation, see: metrics_service/urls.py

## Example

    from django.urls import path
    from apps.core.views import SomeView

    urlpatterns = [
        path("api/v1/priority-endpoint/", SomeView.as_view(), name="priority"),
    ]

"""

from django.urls import include, path
from django.views.generic import RedirectView

# BI Connector URL patterns assembled here (step 3) before the LOADED_APPS loop
# (step 4) to guarantee the bi_connector namespace is always registered. The inner
# URL confs are imported directly; bi_connector/urls.py has urlpatterns=[] so the
# LOADED_APPS loop skips it and avoids a duplicate namespace registration warning.
_bi_urlpatterns = [
    path("events/", include("apps.bi_connector.v1.events_urls", namespace="events")),
]

urlpatterns = [
    # Prometheus metrics endpoint
    path("", include("django_prometheus.urls")),
    # Redirect bare feature_flags/ to the canonical states list
    path("api/v1/feature_flags/", RedirectView.as_view(url="/api/v1/feature_flags/states/", permanent=True)),
    # BI Connector — /api/v1/bi/events/, /api/v1/bi/events/daily-summary/
    path("api/v1/bi/", include((_bi_urlpatterns, "bi_connector"), namespace="bi_connector")),
]
