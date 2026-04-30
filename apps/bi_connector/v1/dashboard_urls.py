"""
URL configuration for BI connector dashboard endpoints.

Mounts at /api/v1/dashboard/ via apps/bi_connector/urls.py.

Endpoints:
    GET /api/v1/dashboard/jobs/                  - list JobData (filterable by date, status, template, org)
    GET /api/v1/dashboard/jobs/<job_id>/         - single job detail with label IDs and host summaries
    GET /api/v1/dashboard/templates/             - list TemplateMetadata (time estimates)
    GET /api/v1/dashboard/templates/<template_id>/ - single template metadata detail
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .dashboard_views import JobDataViewSet, TemplateMetadataViewSet

app_name = "dashboard"

router = DefaultRouter()
router.register(r"jobs", JobDataViewSet, basename="dashboard-jobs")
router.register(r"templates", TemplateMetadataViewSet, basename="dashboard-templates")

urlpatterns = [
    path("", include(router.urls)),
]
