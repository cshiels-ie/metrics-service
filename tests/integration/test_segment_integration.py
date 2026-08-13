"""Integration test for sending data to the mock Segment server."""

import json
import urllib.request
from datetime import date

import pytest
from django.conf import settings
from django.test import TestCase, override_settings

MOCK_SEGMENT_URL = getattr(settings, "SEGMENT_URL", "") or "http://localhost:8765"


def _mock_segment_get(path):
    """GET a path on the mock segment server."""
    with urllib.request.urlopen(f"{MOCK_SEGMENT_URL}{path}") as resp:  # noqa: S310
        return json.loads(resp.read())


def _mock_segment_post(path):
    """POST to a path on the mock segment server."""
    req = urllib.request.Request(f"{MOCK_SEGMENT_URL}{path}", method="POST")  # noqa: S310
    urllib.request.urlopen(req)  # noqa: S310


@pytest.mark.integration
@override_settings(
    SEGMENT_URL=MOCK_SEGMENT_URL,
    SEGMENT_WRITE_KEY="test-integration-key",
    FEATURE={"ANONYMIZED_DATA_COLLECTION": True},
)
class TestSegmentIntegration(TestCase):
    def setUp(self):
        _mock_segment_post("/reset")

    def test_send_to_segment_hits_mock_server(self):
        from apps.tasks.collectors.send_anonymized_to_segment import send_to_segment

        result = send_to_segment(
            user_id="test-user-integration",
            event_name="test_event",
            segment_data={"host_count": 42, "license_type": "enterprise"},
        )

        assert result["status"] == "success"

        captured = _mock_segment_get("/requests")
        assert len(captured) >= 1

        batch = captured[0]["body"]["batch"]
        event = batch[0]
        assert event["event"] == "test_event"
        assert event["properties"]["data"]["host_count"] == 42

    def test_send_anonymized_to_segment_with_payload(self):
        from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment
        from apps.tasks.models import AnonymizedMetricsPayload

        payload = AnonymizedMetricsPayload.objects.create(
            summary_date=date(2026, 1, 15),
            anonymized_data={"host_count": 10, "license_type": "trial"},
            status="pending",
            segment_event_name="daily_metrics_rollup",
            segment_user_id="test-user-integration",
        )

        result = send_anonymized_to_segment()

        assert result["status"] == "success"
        assert result["results"]["sent"] == 1

        payload.refresh_from_db()
        assert payload.status == "sent"

        captured = _mock_segment_get("/requests")
        assert len(captured) >= 1
        batch = captured[0]["body"]["batch"]
        assert batch[0]["properties"]["data"]["host_count"] == 10
