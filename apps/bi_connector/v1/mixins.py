"""
Mixins for BI connector views.
"""

from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import NotFound
from rest_framework.throttling import UserRateThrottle


class BiConnectorThrottle(UserRateThrottle):
    """
    Per-user throttle scoped to BI connector endpoints only.

    Rate is controlled by REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["bi_connector"],
    defaulting to 30/hour. Override without restart:
        METRICS_SERVICE_REST_FRAMEWORK__DEFAULT_THROTTLE_RATES__BI_CONNECTOR=60/hour
    """

    scope = "bi_connector"

    def get_rate(self):
        try:
            return super().get_rate()
        except ImproperlyConfigured:
            return "30/hour"


class BiConnectorEnabledMixin:
    """
    Returns 404 for all requests when the BI_CONNECTOR feature flag is disabled.

    The endpoint appears to not exist when the feature is off — this avoids
    revealing the API surface to unauthenticated users or misconfigured tools.
    Enable via: METRICS_SERVICE_FEATURE_ENABLED__BI_CONNECTOR=true

    Also applies BiConnectorThrottle (30 req/hour per user) to all BI endpoints.
    This throttle is scoped exclusively to BI connector views and does not affect
    any other API endpoints.
    """

    throttle_classes = [BiConnectorThrottle]

    def initial(self, request, *args, **kwargs):
        from apps.tasks.task_groups import get_feature_enabled_from_db

        if not get_feature_enabled_from_db("BI_CONNECTOR", default=False):
            raise NotFound()
        super().initial(request, *args, **kwargs)


class DateRangeRequiredMixin:
    """
    Mixin that enforces mandatory since/until query parameters with a maximum window.

    Protects the DB from unbounded BI queries. The default window is controlled by the
    BI_CONNECTOR_MAX_DAYS_DEFAULT Django setting (default: 7).

    Configurable without code changes:
        METRICS_SERVICE_BI_CONNECTOR_MAX_DAYS_DEFAULT=14
    """

    MAX_DAYS_SETTING: str = "BI_CONNECTOR_MAX_DAYS_DEFAULT"

    def _get_max_days(self) -> int:
        from django.conf import settings

        return getattr(settings, self.MAX_DAYS_SETTING, 7)

    def _parse_date_param(self, value: str):
        """
        Parse an ISO 8601 date or datetime string.

        Returns a ``datetime.date`` for date-only strings (e.g. ``"2024-01-15"``)
        and a ``datetime.datetime`` for strings that include a time component.
        This distinction matters: filtering a Django ``DateField`` with a ``datetime``
        raises a database type mismatch on strict backends.
        """
        from datetime import date

        import dateutil.parser

        # Try date-only first so DateField filters receive a date, not a datetime.
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            pass
        try:
            return dateutil.parser.parse(value)
        except (ValueError, TypeError):
            return None

    def get_queryset(self):
        """Apply since/until date filtering to the queryset."""
        from datetime import timedelta

        from rest_framework.exceptions import ValidationError

        qs = super().get_queryset()
        since_str = self.request.query_params.get("since")
        until_str = self.request.query_params.get("until")

        if not since_str or not until_str:
            raise ValidationError({"detail": "Both 'since' and 'until' query parameters are required (ISO 8601)."})

        since = self._parse_date_param(since_str)
        until = self._parse_date_param(until_str)

        if since is None:
            raise ValidationError({"detail": f"Invalid 'since' datetime format: {since_str!r}. Use ISO 8601."})
        if until is None:
            raise ValidationError({"detail": f"Invalid 'until' datetime format: {until_str!r}. Use ISO 8601."})

        try:
            if until <= since:
                raise ValidationError({"detail": "'until' must be after 'since'."})
            max_days = self._get_max_days()
            delta: timedelta = until - since
        except TypeError as exc:
            # since and until parsed as different types (date vs datetime) — reject clearly.
            raise ValidationError(
                {"detail": "Mix of date-only and datetime 'since'/'until' is not supported. Use a consistent format."}
            ) from exc

        if delta.total_seconds() > max_days * 86400:
            raise ValidationError({"detail": f"Date range cannot exceed {max_days} days. Requested {delta.days} days."})

        date_field = getattr(self, "DATE_RANGE_FIELD", "awx_created")
        return qs.filter(**{f"{date_field}__gte": since, f"{date_field}__lte": until})
