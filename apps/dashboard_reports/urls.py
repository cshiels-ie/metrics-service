"""
URL configuration for dashboard_reports app.

This file defines URL patterns for the dashboard reports endpoints.
The dashboard endpoints are mounted at /api/v1/ for automation-reports integration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AapAuthSettingsViewSet,
    CommonSettingsViewSet,
    CostsViewSet,
    DashboardReportViewSet,
    ExportViewSet,
    FilterSetViewSet,
    InstancesViewSet,
    LabelsViewSet,
    OrganizationsViewSet,
    ProjectsViewSet,
    TemplateMetadataViewSet,
    TemplateOptionsViewSet,
)

app_name = "dashboard_reports"

# Main dashboard router for report endpoints
dashboard_router = DefaultRouter()
dashboard_router.register(r"report", DashboardReportViewSet, basename="dashboard-report")
dashboard_router.register(r"templates", TemplateMetadataViewSet, basename="template-metadata")
dashboard_router.register(r"organizations", OrganizationsViewSet, basename="organizations")
dashboard_router.register(r"projects", ProjectsViewSet, basename="projects")
dashboard_router.register(r"labels", LabelsViewSet, basename="labels")
dashboard_router.register(r"instances", InstancesViewSet, basename="instances")

# Template options router (filter options endpoints)
template_options_router = DefaultRouter()
template_options_router.register(r"", TemplateOptionsViewSet, basename="template-options")

# Common settings router (user preferences and saved views)
common_router = DefaultRouter()
common_router.register(r"settings", CommonSettingsViewSet, basename="common-settings")
common_router.register(r"filter_set", FilterSetViewSet, basename="filter-set")

# AAP Auth router (OAuth settings)
aap_auth_router = DefaultRouter()
aap_auth_router.register(r"settings", AapAuthSettingsViewSet, basename="aap-auth-settings")

urlpatterns = [
    # Dashboard report endpoints at /api/v1/
    path("api/v1/", include(dashboard_router.urls)),
    # Template options endpoints at /api/v1/template_options/
    path("api/v1/template_options/", include(template_options_router.urls)),
    # Common settings endpoints at /api/v1/common/
    path("api/v1/common/", include(common_router.urls)),
    # AAP auth endpoints at /api/v1/aap_auth/
    path("api/v1/aap_auth/", include(aap_auth_router.urls)),
    # Export endpoints (custom actions)
    path(
        "api/v1/report/csv/",
        ExportViewSet.as_view({'get': 'export_csv'}),
        name='report-csv-export',
    ),
    path(
        "api/v1/report/pdf/",
        ExportViewSet.as_view({'post': 'export_pdf'}),
        name='report-pdf-export',
    ),
    # Costs update endpoint
    path(
        "api/v1/costs/",
        CostsViewSet.as_view({'post': 'create'}),
        name='costs-update',
    ),
]
