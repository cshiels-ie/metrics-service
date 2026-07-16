"""BI Export app configuration."""

from django.apps import AppConfig


class BIExportConfig(AppConfig):
    """Django app configuration for the bi_export app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bi_export"
    verbose_name = "BI Export"
