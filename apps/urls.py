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

from django.urls import path
from django.views.generic import RedirectView

from apps.core.views.metrics import PrometheusMetricsView

urlpatterns = [
    # Prometheus metrics endpoint — requires system admin or auditor
    path("api/v1/metrics", PrometheusMetricsView.as_view(), name="prometheus-django-metrics"),
    # Backwards-compat redirects for old paths
    path("api/metrics", RedirectView.as_view(url="/api/v1/metrics", permanent=True)),
    path("metrics", RedirectView.as_view(url="/api/v1/metrics", permanent=False)),
    # Redirect bare feature_flags/ to the canonical states list
    path("api/v1/feature_flags/", RedirectView.as_view(url="/api/v1/feature_flags/states/", permanent=True)),
]
