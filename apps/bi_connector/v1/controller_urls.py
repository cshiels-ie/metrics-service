"""
URL configuration for BI connector Layer 2 (live AWX DB) endpoints.

Mounts at /api/v1/controller/ via apps/bi_connector/urls.py.

Endpoints:
    GET /api/v1/controller/jobs/?since=&until=         - unified jobs (max 7-day window)
    GET /api/v1/controller/hosts/?since=&until=        - job host summaries (max 7-day window)
    GET /api/v1/controller/credentials/?since=&until=  - credentials usage (max 7-day window)
    GET /api/v1/controller/events/?since=&until=       - job events (max 3-day window)
    GET /api/v1/controller/snapshot/                   - current state (EEs, version, metadata, config)
"""

from django.urls import path

from .controller_views import (
    ControllerCredentialsView,
    ControllerEventsView,
    ControllerHostsView,
    ControllerJobsView,
    ControllerSnapshotView,
)

app_name = "controller"

urlpatterns = [
    path("jobs/", ControllerJobsView.as_view(), name="controller-jobs"),
    path("hosts/", ControllerHostsView.as_view(), name="controller-hosts"),
    path("credentials/", ControllerCredentialsView.as_view(), name="controller-credentials"),
    path("events/", ControllerEventsView.as_view(), name="controller-events"),
    path("snapshot/", ControllerSnapshotView.as_view(), name="controller-snapshot"),
]
