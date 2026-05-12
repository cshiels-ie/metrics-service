"""
Django app configuration for tasks app.
"""

import logging
from pathlib import Path

import yaml
from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)

_FEATURE_FLAGS_FILE = Path(__file__).parent / "feature_flags.yaml"


def load_task_feature_flags(**kwargs) -> bool:
    """
    Upsert tasks feature flags into AAPFlag after each DAB purge cycle.

    Connected to the dab_feature_flags app post_migrate signal so it runs after
    purge_feature_flags() + load_feature_flags() in create_initial_data(). This
    ensures task-level feature flags survive every DAB migration without requiring
    a change to the django-ansible-base feature_flags.yaml.

    Only metadata fields are updated on existing flags — ``value`` is left alone so
    user-toggled states set via the Gateway UI are not overwritten.

    Returns True if flags were loaded successfully. On failure, logs at WARNING
    (with exception context) and returns False without re-raising, so migrate and
    other callers are not aborted by optional flag seeding.
    """
    try:
        from ansible_base.resource_registry.signals.handlers import no_reverse_sync
        from django.apps import apps as django_apps

        AAPFlag = django_apps.get_model("dab_feature_flags", "AAPFlag")

        with _FEATURE_FLAGS_FILE.open() as f:
            flags = yaml.safe_load(f) or []

        for flag_def in flags:
            existing = AAPFlag.objects.filter(name=flag_def["name"], condition=flag_def["condition"]).first()
            if existing:
                existing.support_level = flag_def.get("support_level", "TECHNOLOGY_PREVIEW")
                existing.visibility = flag_def.get("visibility", True)
                existing.ui_name = flag_def.get("ui_name", flag_def["name"])
                existing.description = flag_def.get("description", "")
                existing.labels = flag_def.get("labels", [])
                existing.toggle_type = flag_def.get("toggle_type", "run-time")
                existing.support_url = flag_def.get("support_url", "")
                existing.full_clean(exclude=["resource"])
                with no_reverse_sync():
                    existing.save()
            else:
                flag = AAPFlag(**flag_def)
                flag.full_clean(exclude=["resource"])
                with no_reverse_sync():
                    flag.save()
            logger.debug("Loaded task feature flag: %s", flag_def["name"])
    except Exception:
        logger.warning(
            "Failed to load tasks feature flags into AAPFlag",
            exc_info=True,
        )
        return False
    return True


def sync_flag_values_from_settings() -> bool:
    """
    Propagate installer-level feature flag overrides to AAPFlag rows and the Gateway.

    The installer writes top-level keys like ``FEATURE_DASHBOARD_COLLECTION_ENABLED: True``
    into settings.yaml. Dynaconf surfaces these as direct settings attributes (e.g.
    ``settings.FEATURE_DASHBOARD_COLLECTION_ENABLED``), but the AAPFlag row (read by the
    Gateway) still holds the YAML-seeded default (usually ``False``).

    This function reads each flag defined in ``feature_flags.yaml``, checks for a matching
    top-level settings attribute, and — when the value differs from the stored AAPFlag —
    updates the flag and saves **without** ``no_reverse_sync()`` so the change is pushed
    to the Gateway resource server.

    Called by ``init-default-settings`` (which runs during container startup) so the
    Gateway reflects the installer's intent after every deploy.

    Returns True if the sync completed without errors, False otherwise.
    """
    try:
        from django.apps import apps as django_apps
        from django.conf import settings

        AAPFlag = django_apps.get_model("dab_feature_flags", "AAPFlag")

        with _FEATURE_FLAGS_FILE.open() as f:
            flags = yaml.safe_load(f) or []

        for flag_def in flags:
            flag_name = flag_def["name"]  # e.g. "FEATURE_DASHBOARD_COLLECTION_ENABLED"
            settings_value = getattr(settings, flag_name, None)
            if settings_value is None:
                continue

            desired = "True" if settings_value else "False"

            flag = AAPFlag.objects.filter(name=flag_name, condition=flag_def.get("condition", "boolean")).first()
            if flag is None:
                logger.warning("sync_flag_values_from_settings: AAPFlag %s not found, skipping", flag_name)
                continue

            if flag.value == desired:
                logger.debug("AAPFlag %s already set to %s, skipping", flag_name, desired)
                continue

            flag.value = desired
            flag.full_clean(exclude=["resource"])
            flag.save()  # no no_reverse_sync() — intentionally syncs to Gateway
            logger.info("Updated AAPFlag %s to %s (from settings) and synced to Gateway", flag_name, desired)

    except Exception:
        logger.warning("Failed to sync flag values from settings to AAPFlag", exc_info=True)
        return False
    return True


class TasksConfig(AppConfig):
    """Configuration for the tasks app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Task Management"

    def ready(self):
        # Connect to the dab_feature_flags app post_migrate so task feature flags
        # are (re)loaded after every DAB purge_feature_flags() + load_feature_flags()
        # cycle. INSTALLED_APPS order ensures ansible_base.feature_flags connects its
        # handler first, so DAB's purge runs before ours adds the flags back.
        #
        # post_migrate dispatches with sender=<AppConfig instance>, not the class,
        # so we must pass the live instance here — id(class) != id(instance) and
        # Django's signal dispatch matches by id(), so using the class would mean
        # load_task_feature_flags is never called.
        from django.apps import apps as django_apps

        post_migrate.connect(
            load_task_feature_flags,
            sender=django_apps.get_app_config("dab_feature_flags"),
        )
