"""Django app configuration for bi_connector app."""

import logging
from pathlib import Path

import yaml
from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)

_FEATURE_FLAGS_FILE = Path(__file__).parent / "feature_flags.yaml"


def load_bi_connector_feature_flags(**kwargs) -> bool:
    """
    Upsert bi_connector feature flags into AAPFlag after each DAB purge cycle.

    Connected to the dab_feature_flags app post_migrate signal so it runs after
    purge_feature_flags() + load_feature_flags() in create_initial_data(). This
    ensures bi_connector feature flags survive every DAB migration without requiring
    a change to the django-ansible-base feature_flags.yaml.
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
            logger.debug("Loaded bi_connector feature flag: %s", flag_def["name"])
    except Exception:
        logger.warning("Failed to load bi_connector feature flags into AAPFlag", exc_info=True)
        return False
    return True


class BiConnectorConfig(AppConfig):
    """Configuration for the bi_connector app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bi_connector"
    label = "bi_connector"
    verbose_name = "BI Connector"

    def ready(self):
        from django.apps import apps as django_apps

        try:
            dab_ff_config = django_apps.get_app_config("dab_feature_flags")
        except LookupError:
            logger.debug("dab_feature_flags not installed; skipping bi_connector feature flag signal")
            return

        post_migrate.connect(load_bi_connector_feature_flags, sender=dab_ff_config)
