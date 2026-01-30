"""
Dashboard report models for automation-reports integration.

This module contains models for caching dashboard metrics data to enable
fast API responses without expensive real-time SQL queries.
"""

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
