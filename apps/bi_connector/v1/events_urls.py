"""
URL configuration for BI connector events endpoints.

Mounts at /api/v1/bi/events/ via apps/urls.py.

Endpoints:
    GET /api/v1/bi/events/                        - list JobEvent rows (requires since/until)
    GET /api/v1/bi/events/<id>/                   - single JobEvent detail
    GET /api/v1/bi/events/daily-summary/          - list DailyEventSummary rows (requires since/until)
    GET /api/v1/bi/events/daily-summary/<summary_date>/ - single day summary detail
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .events_views import DailyEventSummaryViewSet, JobEventViewSet

app_name = "events"

router = DefaultRouter()
router.register(r"daily-summary", DailyEventSummaryViewSet, basename="events-daily-summary")
router.register(r"", JobEventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
]
