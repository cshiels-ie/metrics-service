"""
Django signals for core models.
"""

import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import Organization, Setting, User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Handle User post-save signal."""
    if created:
        logger.info(f"User created: {instance.username} (ID: {instance.id})")
    else:
        logger.info(f"User updated: {instance.username} (ID: {instance.id})")


@receiver(pre_delete, sender=User)
def user_pre_delete(sender, instance, **kwargs):
    """Handle User pre-delete signal."""
    logger.info(f"User being deleted: {instance.username} (ID: {instance.id})")


@receiver(post_save, sender=Organization)
def organization_post_save(sender, instance, created, **kwargs):
    """Handle Organization post-save signal."""
    if created:
        logger.info(f"Organization created: {instance.name} (ID: {instance.id})")
    else:
        logger.info(f"Organization updated: {instance.name} (ID: {instance.id})")


@receiver(post_save, sender=Setting)
def setting_post_save(sender, instance, created, **kwargs):
    """
    Handle Setting post-save signal - Update cache for Phase 2 dynamic preferences.

    This signal ensures that the Redis cache is automatically updated whenever
    a Setting is created or modified, maintaining cache consistency with the database.

    Args:
        sender: The Setting model class
        instance: The Setting instance being saved
        created: True if this is a new record, False if update
        **kwargs: Additional signal arguments
    """
    if created:
        from django.core.cache import cache

        cache_key = f"setting:{instance.key}"

        try:
            # Update cache with new value (no expiration for dynamic settings)
            cache.set(cache_key, instance.value, timeout=None)
            logger.info(
                f"Cache updated for setting {instance.key} " f"(v{instance.version}) by {instance.changed_by or 'system'}"
            )
        except Exception as e:
            logger.error(f"Failed to update cache for setting {instance.key}: {e}", exc_info=True)
