"""
URL configuration for BI connector Layer 1 (metrics-service DB) endpoints.

Mounts at /api/v1/metrics/ via apps/bi_connector/urls.py.

Endpoints:
    GET /api/v1/metrics/daily/                    - list DailyMetricsSummary (filterable by date)
    GET /api/v1/metrics/daily/<summary_date>/     - single day detail with raw collector blobs
    GET /api/v1/metrics/hourly/                   - list HourlyMetricsCollection (filterable)
    GET /api/v1/metrics/hourly/<id>/              - single hourly record with raw_data
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .metrics_views import DailyMetricsSummaryViewSet, HourlyMetricsCollectionViewSet

app_name = "metrics"

router = DefaultRouter()
router.register(r"daily", DailyMetricsSummaryViewSet, basename="daily-metrics")
router.register(r"hourly", HourlyMetricsCollectionViewSet, basename="hourly-metrics")

urlpatterns = [
    path("", include(router.urls)),
]
