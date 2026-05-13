"""
Shared fixtures for collector tests.

This module provides fixtures specific to metrics collectors testing.
"""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone


@pytest.fixture
def collection_hour():
    """Standard collection hour timestamp (previous hour)."""
    now = timezone.now()
    return now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


@pytest.fixture
def mock_anonymize_rollups():
    """Mock metrics-utility anonymization function."""
    mock_func = MagicMock()
    mock_func.return_value = {
        "anonymized_data": "test",
    }
    return mock_func


@pytest.fixture
def anonymized_payload_factory():
    """Factory for creating AnonymizedMetricsPayload objects."""

    def _create_payload(**kwargs):
        from apps.tasks.models import AnonymizedMetricsPayload

        defaults = {
            "summary_date": timezone.now().date(),
            "anonymized_data": {"test": "data"},
            "status": "pending",
        }
        defaults.update(kwargs)
        return AnonymizedMetricsPayload.objects.create(**defaults)

    return _create_payload
