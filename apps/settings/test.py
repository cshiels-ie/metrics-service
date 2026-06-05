"""
Testing environment overrides
Inherits from ./defaults.py and adds test-specific settings

NOTE: Tests use PostgreSQL to match the production environment setup.
"""

import os

# Basic required settings
DEBUG = False
TESTING = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
# Use env in CI/SAST to avoid hardcoded-secret findings; default is test-only and never production
SECRET_KEY = os.environ.get("METRICS_SERVICE_SECRET_KEY", "test-only-secret-key-for-testing-purposes-only")
SEGMENT_WRITE_KEY = "test-only-segment-write-key-for-testing-only-purposes"

ANSIBLE_BASE_BYPASS_SUPERUSER_FLAGS = ["is_superuser"]
ANSIBLE_BASE_BYPASS_ACTION_FLAGS = {
    "create": "is_superuser",
    "read": "is_superuser",
    "update": "is_superuser",
    "delete": "is_superuser",
}

# Additional DAB RBAC settings required for tests
ANSIBLE_BASE_CHECK_RELATED_PERMISSIONS = ["use", "change", "view"]
ANSIBLE_BASE_CACHE_PARENT_PERMISSIONS = False
ANSIBLE_BASE_EVALUATIONS_IGNORE_CONFLICTS = False
ANSIBLE_BASE_DELETE_REQUIRE_CHANGE = False
ANSIBLE_BASE_CREATOR_DEFAULTS = ["add", "change", "delete", "view"]

# Service identification
SERVICE_ID = "test-service-id"

# URLs - simplified for testing to avoid oauth2 provider conflicts
ROOT_URLCONF = "metrics_service.test_urls"

# Disable caching during tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Use faster password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Email settings for testing
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable logging during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
    },
}

# Disable dispatcherd during tests to avoid background processes
DISPATCHERD_ENABLED = False

# Disable feature enables during tests
# NOTE: relies on get_feature_enabled_from_db falling back to directly using these settings when not in DB...
# ...and on init-default-settings never happening during tests. If it does, @override_settings won't work.
FEATURE = {
    "ANONYMIZED_DATA_COLLECTION": False,
}

# REST Framework settings for tests
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Test database settings
TEST_DATABASE_PREFIX = "test_"
