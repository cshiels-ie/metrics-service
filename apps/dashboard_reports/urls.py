"""
URL configuration for dashboard_reports app.

This file defines URL patterns for the dashboard reports endpoints.
The dashboard endpoints are mounted at /api/v1/report/ for automation-reports integration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardReportViewSet

app_name = "dashboard_reports"

# Create router for dashboard report endpoints
dashboard_router = DefaultRouter()
dashboard_router.register(r"report", DashboardReportViewSet, basename="dashboard-report")

urlpatterns = [
    # Dashboard report endpoints at /api/v1/report/
    path("api/v1/", include(dashboard_router.urls)),
]
