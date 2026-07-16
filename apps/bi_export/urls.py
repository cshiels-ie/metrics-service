"""URL configuration for the BI Export app.

All endpoints are exposed under /api/v1/export/ so customers can point
BI tools (Looker, Power BI, Grafana) at a single consistent base URL.
"""

from django.urls import include, path

urlpatterns = [
    path("api/v1/export/", include(("apps.bi_export.v1.urls", "bi_export"), namespace="bi-export-v1")),
]
