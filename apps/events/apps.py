"""Events app configuration."""

from django.apps import AppConfig


class EventsConfig(AppConfig):
    """Django app configuration for the events app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"
    label = "events"
    verbose_name = "Events"
