"""
Admin configuration for core models.
"""

from django.contrib import admin

from .models import (
    Organization,
    Setting,
    Team,
    User,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin for Organization model."""

    list_display = ("name", "created", "modified")
    search_fields = ("name", "description")
    filter_horizontal = ("users", "admins")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin for User model."""

    list_display = ("username", "email", "first_name", "last_name", "is_active")
    list_filter = ("is_active", "is_system_auditor", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin for Team model."""

    list_display = ("name", "organization", "created")
    list_filter = ("organization",)
    search_fields = ("name", "description", "organization__name")
    filter_horizontal = ("users", "admins", "team_parents")


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    """Admin for Setting model - Dynamic Preferences (Phase 2)."""

    list_display = ("key", "version", "category", "changed_by", "changed_at", "source")
    list_filter = ("category", "is_secret", "source", "changed_at")
    search_fields = ("key", "value")
    readonly_fields = ("version", "changed_at", "changed_by", "source", "ip_address")
    ordering = ("-changed_at",)

    def has_add_permission(self, request):
        """Prevent manual adds - use create_or_update instead."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Settings are immutable - prevent deletion via admin."""
        return False
