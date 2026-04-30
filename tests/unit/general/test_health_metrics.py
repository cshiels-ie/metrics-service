"""
Unit tests for health check and metrics endpoints.
"""

from unittest.mock import patch

import pytest
from rest_framework import status


@pytest.mark.unit
class TestHealthEndpoint:
    """Test cases for /health endpoint."""

    def test_health_check_returns_200_when_database_is_healthy(self, client, db):
        """Test that health endpoint returns 200 when database is accessible."""
        response = client.get("/health/")
        assert response.status_code == status.HTTP_200_OK

    def test_health_check_returns_correct_json_structure(self, client, db):
        """Test that health endpoint returns correct JSON structure when healthy."""
        response = client.get("/health/")
        json_response = response.json()
        assert json_response["status"] == "healthy"
        assert json_response["checks"]["database"] == "ok"

    def test_health_check_returns_503_when_database_fails(self, client, db):
        """Test that health endpoint returns 503 when database connection fails."""

        with patch("django.db.connection.ensure_connection", side_effect=Exception("DB Error")):
            response = client.get("/health/")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_health_check_works_without_authentication(self, client, db):
        """Test that health endpoint doesn't require authentication."""
        response = client.get("/health/")
        json_response = response.json()
        assert json_response["status"] == "healthy"
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    @patch("apps.core.views.health.close_old_connections")
    def test_health_check_fails_when_segment_payloads_failed(self, mock_close, client):
        """Test that health endpoint reports segment check failed when single failed segment payload exist."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.tasks.models import AnonymizedMetricsPayload

        now = timezone.now()
        summary_date = now.date() - timedelta(days=1)
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date, anonymized_data={"test": "data"}, status="failed", retry_count=3
        )

        response = client.get("/health/")
        json_response = response.json()
        assert json_response["status"] == "healthy"
        assert json_response["checks"]["segment_send"]["status"] == "failed"
        assert "last_failure_at" in json_response["checks"]["segment_send"]
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    @patch("apps.core.views.health.close_old_connections")
    def test_health_check_fails_when_multiple_segment_payloads_failed(self, mock_close, client):
        """Test that health endpoint reports segment check failed status when many failed segment payloads exist."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.tasks.models import AnonymizedMetricsPayload

        now = timezone.now()
        summary_date = now.date() - timedelta(days=1)
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date - timedelta(days=3),
            anonymized_data={"test": "data"},
            status="sent",
            retry_count=3,
        )
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date - timedelta(days=2),
            anonymized_data={"test": "data"},
            status="sent",
            retry_count=3,
        )
        # Last to be 'modified' so it should be the one involved in the health check
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date, anonymized_data={"test": "data"}, status="failed", retry_count=3
        )

        response = client.get("/health/")
        json_response = response.json()
        assert json_response["status"] == "healthy"
        assert json_response["checks"]["segment_send"]["status"] == "failed"
        assert "last_failure_at" in json_response["checks"]["segment_send"]
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    @patch("apps.core.views.health.close_old_connections")
    def test_health_check_passes_when_multiple_segment_payloads_send(self, mock_close, client):
        """Test that health endpoint reports segment ok when many failed segment payloads exist."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.tasks.models import AnonymizedMetricsPayload

        now = timezone.now()
        summary_date = now.date() - timedelta(days=1)
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date - timedelta(days=3),
            anonymized_data={"test": "data"},
            status="failed",
            retry_count=3,
        )
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date - timedelta(days=2),
            anonymized_data={"test": "data"},
            status="failed",
            retry_count=3,
        )
        # Last to be 'modified' so it should be the one involved in the health check
        AnonymizedMetricsPayload.objects.create(
            summary_date=summary_date, anonymized_data={"test": "data"}, status="sent", retry_count=3
        )

        response = client.get("/health/")
        json_response = response.json()
        assert json_response["status"] == "healthy"
        assert json_response["checks"]["segment_send"]["status"] == "ok"
        assert "last_success_at" in json_response["checks"]["segment_send"]
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.unit
class TestMetricsEndpoint:
    """Test cases for /metrics endpoint."""

    def test_metrics_endpoint_returns_200(self, client, db):
        """Test that metrics endpoint returns 200."""
        response = client.get("/metrics")
        assert response.status_code == status.HTTP_200_OK

    def test_metrics_endpoint_returns_prometheus_format(self, client, db):
        """Test that metrics endpoint returns text/plain content type."""
        response = client.get("/metrics")
        assert response.status_code == status.HTTP_200_OK
        assert "text/plain" in response["Content-Type"]

    def test_metrics_endpoint_contains_django_metrics(self, client, db):
        """Test that metrics endpoint contains Django metrics."""
        # TODO: Your code here!
        # Hint: Use response.content.decode() to get the text
        # Check that it contains strings like "django_" or "python_"
        # Example: assert 'django_http_requests_total' in response.content.decode()
        response = client.get("/metrics")
        assert "django_" in response.content.decode()

    def test_metrics_endpoint_works_without_authentication(self, client):
        """Test that metrics endpoint doesn't require authentication."""
        response = client.get("/metrics")
        assert response.status_code == status.HTTP_200_OK
        assert "django_" in response.content.decode()
