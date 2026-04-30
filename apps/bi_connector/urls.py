"""
Top-level URL configuration for the BI connector app.

urlpatterns is intentionally empty so the LOADED_APPS URL loop in
metrics_service/urls.py skips this module. The actual URL patterns are
assembled in apps/urls.py (step 3, before LOADED_APPS at step 4) using
the inner URL modules directly. This guarantees the bi_connector namespace
is always registered regardless of app-loading order in CI.

Layer 1 (pre-aggregated metrics):  /api/v1/bi/metrics/
Layer 2 (live AWX DB):             /api/v1/bi/controller/
Layer 3 (dashboard collected data):/api/v1/bi/dashboard/
Events (pre-collected):            /api/v1/bi/events/
"""

app_name = "bi_connector"

# Empty — URLs assembled in apps/urls.py to avoid duplicate namespace registration.
urlpatterns = []
