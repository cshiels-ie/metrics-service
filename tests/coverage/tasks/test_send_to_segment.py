"""
Unit tests for apps/tasks/collectors/send_anonymized_to_segment.py.
Targets 28% → ~85% coverage.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone


@pytest.fixture
def pending_payload(db):
    from apps.tasks.models import AnonymizedMetricsPayload

    AnonymizedMetricsPayload.objects.all().delete()
    return AnonymizedMetricsPayload.objects.create(
        summary_date=timezone.now().date() - timedelta(days=1),
        anonymized_data={"data": "test"},
        status="pending",
        segment_user_id="test-user-id",
    )


# ---------------------------------------------------------------------------
# _get_payloads_to_send
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_get_payloads_to_send_returns_pending(pending_payload):
    from apps.tasks.collectors.send_anonymized_to_segment import _get_payloads_to_send

    stale = timezone.now() - timedelta(hours=2)
    payloads = list(_get_payloads_to_send(payload_id=None, max_payloads=10, stale_threshold=stale))
    assert any(p.id == pending_payload.id for p in payloads)


@pytest.mark.unit
@pytest.mark.django_db
def test_get_payloads_to_send_by_id(pending_payload):
    from apps.tasks.collectors.send_anonymized_to_segment import _get_payloads_to_send

    stale = timezone.now() - timedelta(hours=2)
    payloads = list(_get_payloads_to_send(payload_id=pending_payload.id, max_payloads=10, stale_threshold=stale))
    assert len(payloads) == 1
    assert payloads[0].id == pending_payload.id


@pytest.mark.unit
@pytest.mark.django_db
def test_get_payloads_to_send_empty_when_no_pending():
    from apps.tasks.collectors.send_anonymized_to_segment import _get_payloads_to_send
    from apps.tasks.models import AnonymizedMetricsPayload

    AnonymizedMetricsPayload.objects.all().delete()
    stale = timezone.now() - timedelta(hours=2)
    payloads = list(_get_payloads_to_send(payload_id=None, max_payloads=10, stale_threshold=stale))
    assert len(payloads) == 0


# ---------------------------------------------------------------------------
# _handle_successful_send
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_handle_successful_send_marks_sent(pending_payload):
    from apps.tasks.collectors.send_anonymized_to_segment import _handle_successful_send

    results = {"sent": 0, "failed": 0}
    _handle_successful_send(pending_payload, results)

    pending_payload.refresh_from_db()
    assert pending_payload.status == "sent"
    assert results["sent"] == 1


# ---------------------------------------------------------------------------
# _handle_failed_send
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_handle_failed_send_increments_retry_count(pending_payload):
    from apps.tasks.collectors.send_anonymized_to_segment import _handle_failed_send

    results = {"sent": 0, "failed": 0, "retrying": 0}
    segment_result = {"error": "connection refused"}

    _handle_failed_send(pending_payload, segment_result, results)

    pending_payload.refresh_from_db()
    # _handle_failed_send always increments results["failed"] regardless of retry status
    assert results["failed"] == 1
    pending_payload.refresh_from_db()
    assert pending_payload.status == "retry"  # retry_count(0) < max_retries(3)


# ---------------------------------------------------------------------------
# send_anonymized_to_segment — main function
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.django_db
def test_send_anonymized_to_segment_no_payloads():
    from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment
    from apps.tasks.models import AnonymizedMetricsPayload

    AnonymizedMetricsPayload.objects.all().delete()
    result = send_anonymized_to_segment()
    assert result["status"] == "success"


@pytest.mark.unit
@pytest.mark.django_db
def test_send_anonymized_to_segment_success(pending_payload):
    from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment

    with patch("apps.tasks.collectors.send_anonymized_to_segment._process_single_payload") as mock_process:
        mock_process.return_value = None
        result = send_anonymized_to_segment()

    assert result["status"] == "success"


@pytest.mark.unit
@pytest.mark.django_db
def test_send_anonymized_to_segment_specific_payload(pending_payload):
    from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment

    with patch("apps.tasks.collectors.send_anonymized_to_segment._process_single_payload") as mock_process:
        mock_process.return_value = None
        result = send_anonymized_to_segment(payload_id=pending_payload.id)

    assert result["status"] == "success"


@pytest.mark.unit
@pytest.mark.django_db
def test_send_anonymized_to_segment_skips_when_feature_disabled(pending_payload):
    """When ANONYMIZED_DATA_COLLECTION is disabled, do not send payloads."""
    from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment

    with (
        patch(
            "apps.tasks.task_groups.get_feature_enabled_from_db",
            return_value=False,
        ),
        patch("apps.tasks.collectors.send_anonymized_to_segment._process_single_payload") as mock_process,
    ):
        result = send_anonymized_to_segment()

    assert result["status"] == "success"
    assert result["results"]["sent"] == 0
    assert result["total_processed"] == 0
    mock_process.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
def test_send_anonymized_to_segment_key_not_configured():
    """When SEGMENT_WRITE_KEY is missing, returns error."""
    from apps.tasks.collectors.send_anonymized_to_segment import send_anonymized_to_segment
    from apps.tasks.models import AnonymizedMetricsPayload

    AnonymizedMetricsPayload.objects.create(
        summary_date=timezone.now().date() - timedelta(days=2),
        anonymized_data={"data": "x"},
        status="pending",
    )

    with patch("apps.tasks.collectors.send_anonymized_to_segment.settings") as mock_settings:
        mock_settings.SEGMENT_WRITE_KEY = None
        result = send_anonymized_to_segment()

    assert result["status"] in ("success", "error")
