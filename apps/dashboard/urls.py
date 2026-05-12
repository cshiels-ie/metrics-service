"""
URL configuration for dashboard app.

This file defines URL patterns specific to this app. It is automatically loaded
by the platform-service-framework when the app is registered in `apps/settings.py`
under `project_applications`.

URLs defined here load at step 4 in the URL loading order, after `apps/urls.py`
(step 3). The order among apps follows the order in `project_applications`.

For full documentation, see: metrics_service/urls.py

"""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("api/dashboard/", views.dashboard_view, name="dashboard"),
]
