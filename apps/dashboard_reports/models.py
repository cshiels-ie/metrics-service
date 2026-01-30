"""
Dashboard report models for automation-reports integration.

This module contains models for caching dashboard metrics data to enable
fast API responses without expensive real-time SQL queries.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

# Import base classes, handling both DAB and simple fallbacks
try:
    from ansible_base.lib.abstract_models import CommonModel

    DAB_AVAILABLE = True
except ImportError:
    # Provide simple alternative when DAB is not available
    DAB_AVAILABLE = False

    class CommonModel(models.Model):
        created = models.DateTimeField(auto_now_add=True)
        modified = models.DateTimeField(auto_now=True)

        class Meta:
            abstract = True


class DashboardReportCache(CommonModel):
    """
    Cached dashboard report data for automation-reports integration.

    Purpose:
        Store pre-calculated dashboard metrics to avoid expensive SQL queries
        on every API request. Updated by periodic collection tasks.

    Usage:
        - Populated by: collect_dashboard_reports() task (daily/weekly)
        - Read by: DashboardReportViewSet API endpoints
        - Cache invalidation: Task-driven updates (no TTL)

    Example:
        cache_entry = DashboardReportCache.objects.get(
            cache_key='job_templates_2025-01-01_2025-01-31'
        )
        job_templates = cache_entry.data['job_templates']
    """

    # Report type choices
    REPORT_TYPE_JOB_TEMPLATES = 'job_templates'
    REPORT_TYPE_TOP_PROJECTS = 'top_projects'
    REPORT_TYPE_TOP_USERS = 'top_users'

    REPORT_TYPE_CHOICES = [
        (REPORT_TYPE_JOB_TEMPLATES, 'Job Templates'),
        (REPORT_TYPE_TOP_PROJECTS, 'Top Projects'),
        (REPORT_TYPE_TOP_USERS, 'Top Users'),
    ]

    cache_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique key: '{report_type}_{start_date}_{end_date}'"
    )

    report_type = models.CharField(
        max_length=50,
        choices=REPORT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of report data cached"
    )

    data = models.JSONField(
        help_text="Cached report data in JSON format (matches automation-reports interface)"
    )

    date_range_start = models.DateTimeField(
        db_index=True,
        help_text="Start of data collection period (inclusive)"
    )

    date_range_end = models.DateTimeField(
        db_index=True,
        help_text="End of data collection period (exclusive)"
    )

    class Meta:
        db_table = 'dashboard_report_cache'
        ordering = ['-modified']
        indexes = [
            models.Index(fields=['report_type', 'modified'], name='dashboard_r_report_idx'),
            models.Index(fields=['cache_key', 'modified'], name='dashboard_r_cache_idx'),
        ]
        verbose_name = "Dashboard Report Cache"
        verbose_name_plural = "Dashboard Report Caches"

    def __str__(self):
        """
        Return string representation of the cache entry.

        Returns:
            str: Report type and date range
        """
        start_str = self.date_range_start.strftime('%Y-%m-%d')
        end_str = self.date_range_end.strftime('%Y-%m-%d')
        return f"{self.get_report_type_display()} ({start_str} to {end_str})"

    def is_fresh(self, max_age_hours: int = 24) -> bool:
        """
        Check if cache entry is fresh based on modification time.

        Args:
            max_age_hours: Maximum age in hours before considering stale (default: 24)

        Returns:
            bool: True if cache is fresh, False if stale
        """
        from datetime import timedelta

        age = timezone.now() - self.modified
        return age < timedelta(hours=max_age_hours)

    @classmethod
    def get_or_empty(cls, cache_key: str) -> dict:
        """
        Get cached data or return empty structure if not found.

        Args:
            cache_key: Cache key to look up

        Returns:
            dict: Cached data or empty dict with appropriate structure

        Example:
            data = DashboardReportCache.get_or_empty('job_templates_2025-01-01_2025-01-31')
        """
        cache_entry = cls.objects.filter(cache_key=cache_key).first()
        if cache_entry:
            return cache_entry.data

        # Return empty structure based on key pattern
        if 'job_templates' in cache_key:
            return {'job_templates': [], 'count': 0, 'timestamp': None}
        elif 'top_projects' in cache_key:
            return {'top_projects': [], 'count': 0, 'timestamp': None}
        elif 'top_users' in cache_key:
            return {'top_users': [], 'count': 0, 'timestamp': None}
        else:
            return {}


class Currency(CommonModel):
    """
    Currency options for dashboard cost calculations.

    Stores available currencies that users can select for displaying
    costs in the automation-reports dashboard. Currencies are used
    to format monetary values in the appropriate symbol and denomination.

    Example:
        usd = Currency.objects.get(code='USD')
        print(f"{usd.symbol}100")  # Output: $100
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Full currency name (e.g., 'US Dollar', 'Euro')"
    )

    symbol = models.CharField(
        max_length=10,
        help_text="Currency symbol (e.g., '$', '€', '£')"
    )

    code = models.CharField(
        max_length=3,
        unique=True,
        db_index=True,
        help_text="ISO 4217 currency code (e.g., 'USD', 'EUR', 'GBP')"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this currency is available for selection"
    )

    class Meta:
        db_table = 'dashboard_currency'
        ordering = ['name']
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"

    def __str__(self):
        """Return string representation of the currency."""
        return f"{self.name} ({self.symbol})"


class UserPreference(CommonModel):
    """
    User-specific dashboard preferences.

    Stores per-user settings for the automation-reports dashboard including
    currency preference and other UI preferences. Each user has exactly one
    preference record (OneToOneField relationship).

    Example:
        pref = UserPreference.objects.get(user=request.user)
        print(f"User prefers {pref.currency.code}")
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard_preferences',
        help_text="User who owns these preferences"
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User's preferred currency for cost display"
    )

    preferences_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional user preferences (extensible JSON structure)"
    )

    class Meta:
        db_table = 'dashboard_user_preference'
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"
        indexes = [
            models.Index(fields=['user'], name='dashboard_up_user_idx'),
        ]

    def __str__(self):
        """Return string representation of the preference."""
        return f"Preferences for {self.user.username}"


class FilterSet(CommonModel):
    """
    Saved filter configurations (saved views) for dashboard filtering.

    Allows users to save commonly-used filter combinations for quick access.
    Users can have multiple filter sets, but only one can be marked as default.

    Example:
        filter_set = FilterSet.objects.create(
            user=request.user,
            name="Last 30 days - Production",
            filters={'organizations': [1, 2], 'date_range': 'last_30_days'}
        )
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='filter_sets',
        help_text="User who created this filter set"
    )

    name = models.CharField(
        max_length=255,
        help_text="Display name for this saved filter set"
    )

    filters = models.JSONField(
        help_text="Filter configuration: {organizations: [], projects: [], labels: [], date_range: {}}"
    )

    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the user's default filter set (only one allowed per user)"
    )

    class Meta:
        db_table = 'dashboard_filter_set'
        ordering = ['-modified']
        verbose_name = "Filter Set"
        verbose_name_plural = "Filter Sets"
        indexes = [
            models.Index(fields=['user', 'is_default'], name='dashboard_fs_user_default_idx'),
            models.Index(fields=['user', '-modified'], name='dashboard_fs_user_mod_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_default'],
                condition=models.Q(is_default=True),
                name='one_default_per_user',
                violation_error_message="User can only have one default filter set"
            )
        ]

    def __str__(self):
        """Return string representation of the filter set."""
        default_marker = " (default)" if self.is_default else ""
        return f"{self.name}{default_marker} - {self.user.username}"


class TemplateMetadata(CommonModel):
    """
    Override metadata for AWX job templates.

    Stores user-defined overrides for job template metadata such as
    time estimates and custom costs. This allows users to provide more
    accurate data than auto-calculated values from job execution history.

    Example:
        metadata = TemplateMetadata.objects.create(
            template_id=42,
            template_name="Deploy Production",
            time_taken_manually_execute_minutes=120,
            time_taken_create_automation_minutes=240
        )
    """

    template_id = models.IntegerField(
        unique=True,
        db_index=True,
        help_text="AWX job template ID (from AWX database main_jobtemplate table)"
    )

    template_name = models.CharField(
        max_length=512,
        help_text="Cached template name for display (from AWX)"
    )

    time_taken_manually_execute_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="User override: Estimated time to perform this task manually (minutes)"
    )

    time_taken_create_automation_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="User override: Estimated time spent creating this automation (minutes)"
    )

    custom_cost_per_minute = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="User override: Custom cost per minute for this specific template"
    )

    notes = models.TextField(
        blank=True,
        help_text="User notes about this template"
    )

    class Meta:
        db_table = 'dashboard_template_metadata'
        ordering = ['template_name']
        verbose_name = "Template Metadata"
        verbose_name_plural = "Template Metadata"
        indexes = [
            models.Index(fields=['template_id'], name='dashboard_tm_template_idx'),
        ]

    def __str__(self):
        """Return string representation of the template metadata."""
        return f"Metadata for {self.template_name} (ID: {self.template_id})"
