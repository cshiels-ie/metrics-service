"""
Tests for BI connector Layer 1 API endpoints (metrics-service DB).

Covers DailyMetricsSummaryViewSet and HourlyMetricsCollectionViewSet:
- Authentication enforcement
- Feature flag disabled → 404
- Flat column serialization of aggregated_metrics JSON
- Date range and collector_type filtering
- Read-only enforcement (write methods rejected)
- summary_date used as lookup field for daily detail
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from tests.test_utils import get_test_password

_FLAG_PATCH = "apps.tasks.task_groups.get_feature_enabled_from_db"


@pytest.mark.unit
@pytest.mark.django_db
class TestDailyMetricsSummaryViewSet(APITestCase):
    """Tests for GET /api/v1/metrics/daily/ and /api/v1/metrics/daily/<summary_date>/"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def _create_summary(self, summary_date, aggregated_metrics=None, summary_status="aggregated"):
        from apps.tasks.models import DailyMetricsSummary

        if isinstance(summary_date, str):
            summary_date = date.fromisoformat(summary_date)
        return DailyMetricsSummary.objects.create(
            summary_date=summary_date,
            status=summary_status,
            aggregated_metrics=aggregated_metrics or {},
        )

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_list_requires_authentication(self):
        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    # --- Flat column serialization ---

    def test_list_flattens_aggregated_metrics_to_top_level_fields(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(
            summary_date="2025-01-15",
            aggregated_metrics={
                "unified_jobs": {"total": 42, "successful": 40},
                "credentials_service": {"usage_count": 5},
            },
        )

        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["metrics_unified_jobs"] == {"total": 42, "successful": 40}
        assert result["metrics_credentials_service"] == {"usage_count": 5}

    def test_list_returns_empty_dict_for_missing_collector_type(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-15", aggregated_metrics={})

        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["metrics_unified_jobs"] == {}
        assert result["metrics_table_metadata"] == {}

    def test_list_does_not_include_raw_aggregated_metrics_blob(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-15", aggregated_metrics={"unified_jobs": {"total": 1}})

        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert "aggregated_metrics" not in result

    def test_detail_includes_raw_aggregated_metrics_blob(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(
            summary_date="2025-01-15",
            aggregated_metrics={"unified_jobs": {"total": 1}},
        )

        url = reverse("bi_connector:metrics:daily-metrics-detail", kwargs={"summary_date": "2025-01-15"})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "aggregated_metrics" in response.data
        assert response.data["aggregated_metrics"]["unified_jobs"]["total"] == 1

    def test_detail_uses_summary_date_as_lookup_field(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-02-20")

        url = reverse("bi_connector:metrics:daily-metrics-detail", kwargs={"summary_date": "2025-02-20"})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["summary_date"]) == "2025-02-20"

    def test_detail_not_found_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:metrics:daily-metrics-detail", kwargs={"summary_date": "1999-01-01"})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Filtering ---

    def test_filter_by_exact_summary_date(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-10")
        self._create_summary(summary_date="2025-01-20")

        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url, {"summary_date": "2025-01-10"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert str(response.data["results"][0]["summary_date"]) == "2025-01-10"

    def test_filter_by_summary_date_gte(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-01")
        self._create_summary(summary_date="2025-01-15")
        self._create_summary(summary_date="2025-02-01")

        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url, {"summary_date__gte": "2025-01-15"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_filter_by_status(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-01", summary_status="aggregated")
        self._create_summary(summary_date="2025-01-02", summary_status="pending")

        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.get(url, {"status": "aggregated"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    # --- Read-only enforcement ---

    def test_post_returns_405(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:metrics:daily-metrics-list")
        response = self.client.post(url, {"summary_date": "2025-01-01"})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_returns_405(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-15")
        url = reverse("bi_connector:metrics:daily-metrics-detail", kwargs={"summary_date": "2025-01-15"})
        response = self.client.put(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self):
        self.client.force_authenticate(user=self.user)
        self._create_summary(summary_date="2025-01-15")
        url = reverse("bi_connector:metrics:daily-metrics-detail", kwargs={"summary_date": "2025-01-15"})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.unit
@pytest.mark.django_db
class TestHourlyMetricsCollectionViewSet(APITestCase):
    """Tests for GET /api/v1/metrics/hourly/ and /api/v1/metrics/hourly/<id>/"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def _create_collection(
        self, collector_type="unified_jobs", hours_ago=1, raw_data=None, collection_status="collected"
    ):
        from apps.tasks.models import HourlyMetricsCollection

        ts = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_ago)
        return HourlyMetricsCollection.objects.create(
            collector_type=collector_type,
            collection_timestamp=ts,
            raw_data=raw_data or {"count": 1},
            status=collection_status,
        )

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_list_requires_authentication(self):
        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    # --- Serializer ---

    def test_list_excludes_raw_data(self):
        self.client.force_authenticate(user=self.user)
        self._create_collection(raw_data={"large": "payload"})

        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert "raw_data" not in result
        assert "collector_type" in result

    def test_detail_includes_raw_data(self):
        self.client.force_authenticate(user=self.user)
        collection = self._create_collection(raw_data={"jobs_total": 99})

        url = reverse("bi_connector:metrics:hourly-metrics-detail", kwargs={"pk": collection.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["raw_data"] == {"jobs_total": 99}

    # --- Filtering ---

    def test_filter_by_collector_type(self):
        self.client.force_authenticate(user=self.user)
        self._create_collection(collector_type="unified_jobs", hours_ago=2)
        self._create_collection(collector_type="credentials_service", hours_ago=3)

        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.get(url, {"collector_type": "unified_jobs"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["collector_type"] == "unified_jobs"

    def test_filter_by_status(self):
        self.client.force_authenticate(user=self.user)
        self._create_collection(collection_status="collected", hours_ago=2)
        self._create_collection(collection_status="processed", hours_ago=3)

        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.get(url, {"status": "collected"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    # --- Read-only enforcement ---

    def test_post_returns_405(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:metrics:hourly-metrics-list")
        response = self.client.post(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self):
        self.client.force_authenticate(user=self.user)
        collection = self._create_collection()
        url = reverse("bi_connector:metrics:hourly-metrics-detail", kwargs={"pk": collection.pk})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
