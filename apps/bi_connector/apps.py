"""
Django app configuration for bi_connector app.
"""

from django.apps import AppConfig


class BiConnectorConfig(AppConfig):
    """Configuration for the bi_connector app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bi_connector"
    label = "bi_connector"
    verbose_name = "BI Connector"
