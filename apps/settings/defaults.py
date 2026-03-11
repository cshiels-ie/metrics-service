"""
Top level settings file for all apps.

The settings here overrides any setting previously loaded
from the `metrics_service.settings`.
"""

from dynaconf import Dynaconf, post_hook

# Extra applications added after PSF templating
extra_applications = [
    "django_prometheus",
    "django_extensions",
]

# Default DAB applications layd out from PSF, add/remove according to the project needs,
# adjust `pyproject` dab extra dependencies acording to apps added/removed here
dab_applications = [
    "ansible_base.feature_flags",  # Must be first to ensure table exists before other apps' post_migrate signals
    "ansible_base.activitystream",
    "ansible_base.api_documentation",
    "ansible_base.jwt_consumer",
    "ansible_base.rbac",
    "ansible_base.resource_registry",
    "ansible_base.rest_filters",
    "ansible_base.rest_pagination",
]

# List of applications from the apps/ folder
project_applications = [
    "apps.core",
    "apps.dynamic_settings",
    "apps.tasks",
    "apps.dashboard",
]

# Final state of the INSTALLED_APPS that will merge with the rest of the settings
INSTALLED_APPS = [
    "dynaconf_merge_unique",  # DO NOT REMOVE THIS
    *dab_applications,
    *project_applications,
    *extra_applications,
]

# Enable debug mode
DEBUG = False

# REST framework settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "apps.core.renderers.ServiceBrowsableAPIRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
}

# Title of Swagger the API documentation
SPECTACULAR_SETTINGS__TITLE = "metrics_service API"
# Description of Swagger the API documentation
SPECTACULAR_SETTINGS__DESCRIPTION = "API documentation for the metrics_service"
# Version of Swagger the API documentation
SPECTACULAR_SETTINGS__VERSION = "v1"
# Split components into request and response for generating clients
SPECTACULAR_SETTINGS__COMPONENT_SPLIT_REQUEST = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "default",
    },
}
CSRF_TRUSTED_ORIGINS = []

# Databases settings, using PostgreSQL by default
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "",  # require to be set at runtime
        "PORT": "5432",
        "USER": "metrics_service",
        "PASSWORD": "",  # require to be set at runtime
        "NAME": "metrics_service",
        "OPTIONS": {
            "sslmode": "prefer",
        },
    },
    # AWX database for metrics-utility collector integration
    # Override with METRICS_SERVICE_DATABASES__awx__HOST, etc.
    "awx": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "",  # require to be set at runtime
        "PORT": "5432",
        "USER": "myuser",
        "PASSWORD": "",  # require to be set at runtime
        "NAME": "awx",
        "OPTIONS": {
            "sslmode": "prefer",
        },
    },
}

# Feature flag defaults
# only used by `metrics_service init-default-settings` (and `... run`)
# and only used when not already changed in the settings DB table
# also used by tasks - unless set in the db.
FEATURE_ENABLED = {
    "ANONYMIZED_DATA_COLLECTION": True,  # Controls all metrics collection, rollup, anonymization, and sending
}

# URL_PREFIX: Controls both URL routing AND URL generation
# - When None (default): Traditional standalone mode
#   * Routes work at /api/v1/, /api/, /health/, etc.
#   * URLs generated with /api/ prefix
# - When set (e.g., "/api/metrics"): Gateway deployment mode
#   * Routes work at /<prefix>/v1/, /<prefix>/, etc.
#   * URLs generated with /<prefix>/ prefix
#   * Example: /api/metrics/v1/ instead of /api/v1/
# - Used in production AAP deployments where Gateway routes /api/metrics/* to this service
# - Health and Prometheus endpoints (/health/, /metrics/) stay at root for monitoring
# Set via environment: METRICS_SERVICE_URL_PREFIX="/api/metrics"
URL_PREFIX = None


@post_hook
def load_prometheus_middlewares(settings: Dynaconf) -> dict:
    """Defer to execute after all settings are loaded."""
    middleware = settings.get("MIDDLEWARE", [])
    if "django_prometheus" in " ".join(middleware):
        return {}
    new = [
        "django_prometheus.middleware.PrometheusBeforeMiddleware",
        *middleware,
        "django_prometheus.middleware.PrometheusAfterMiddleware",
    ]
    return {"MIDDLEWARE": new}
