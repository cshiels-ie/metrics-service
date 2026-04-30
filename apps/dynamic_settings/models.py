"""
Setting model for storing configuration with rollback capability.
"""

import contextlib

from ansible_base.activitystream.models import AuditableModel
from ansible_base.lib.abstract_models import CommonModel
from django.core.cache import cache
from django.db import models

from apps.core.models import User


class Setting(CommonModel, AuditableModel):
    """
    Stores configuration settings with rollback capability.
    """

    class Meta:
        app_label = "dynamic_settings"
        ordering = ["-modified"]  # Show newest changes first
        indexes = [
            models.Index(fields=["setting_key", "-modified"]),  # Fast lookup by setting
            models.Index(fields=["last_modified_by", "-modified"]),  # Fast lookup by user
        ]

    # WHO changed it
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configuration_changes",
        help_text="The user who made this configuration change. Null if changed via system process.",
    )

    # WHAT was changed
    setting_key = models.CharField(
        max_length=255, help_text="The name of the setting that was changed (e.g., 'DEBUG', 'SECRET_KEY')", unique=True
    )

    previous_value = models.TextField(
        blank=True,
        null=True,
        help_text="The previous value of the setting (JSON serialized). May be redacted for sensitive settings.",
    )

    current_value = models.TextField(
        blank=True,
        null=True,
        help_text="The new value of the setting (JSON serialized). May be redacted for sensitive settings.",
    )

    def save(self, *args, **kwargs):
        """Save the setting and invalidate the feature flag cache entry."""
        super().save(*args, **kwargs)
        with contextlib.suppress(Exception):
            # Lazy import avoids a circular dependency with apps.tasks
            from apps.tasks.task_groups import _feature_flag_cache_key

            cache.delete(_feature_flag_cache_key(self.setting_key))

    def __str__(self):
        """String representation showing who changed what and when."""
        user_name = self.last_modified_by.username if self.last_modified_by else "System"
        return f"{user_name} changed {self.setting_key} at {self.modified}"
