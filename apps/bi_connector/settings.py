"""
BI Connector app settings.

Adds token authentication and per-user rate limiting for BI tool service accounts.
These settings merge into the global REST_FRAMEWORK config via Dynaconf.
"""

# Long-lived token auth for Tableau/Power BI/Grafana service accounts
INSTALLED_APPS = ["dynaconf_merge_unique", "rest_framework.authtoken"]

REST_FRAMEWORK__DEFAULT_AUTHENTICATION_CLASSES = [
    "dynaconf_merge_unique",
    "rest_framework.authentication.TokenAuthentication",
]

# Maximum date window (in days) for BI connector queries.
# Override via environment variable: METRICS_SERVICE_BI_CONNECTOR_MAX_DAYS_DEFAULT=14
BI_CONNECTOR_MAX_DAYS_DEFAULT = 7
