"""URL configuration for dynamic settings API."""

from django.urls import path

from .views import DashboardSettingsView

urlpatterns = [
    path("dashboard/", DashboardSettingsView.as_view(), name="dashboard-settings"),
]
