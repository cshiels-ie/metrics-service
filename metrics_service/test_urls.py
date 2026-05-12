"""
Simplified URL configuration for testing that avoids oauth2 provider conflicts.

This file follows the Ansible Services Framework pattern for dynamic URL loading.
Apps now own their full URL paths.
"""

from django.urls import include, path

urlpatterns = [
    # Core app (authentication, health, ping, api/v1/) - owns its full paths
    path("", include("apps.core.urls")),
    # Dashboard interface - app owns its full path (dashboard/)
    path("", include("apps.dashboard.urls")),
    # Dynamic settings API - app owns its full path (api/v1/settings/)
    path("", include("apps.dynamic_settings.urls")),
    # Tasks API - app owns its full path (api/v1/tasks/)
    path("", include("apps.tasks.urls")),
    # Dashboard reports API - app owns its full path (api/v1/dashboard_reports/)
    path("", include("apps.dashboard_reports.urls")),
    # Service-specific URLs (Prometheus, etc.)
    path("", include("apps.urls")),
]
