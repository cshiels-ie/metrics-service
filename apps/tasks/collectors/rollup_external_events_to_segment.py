"""
Daily rollup and send of per-event ExternalEvents to Segment.

Runs once per day (midnight cron). Aggregates all pending per-event
payloads from the previous calendar day, grouped by service and event name,
and sends one rolled-up Segment track per group.
"""

import logging
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def rollup_external_events_to_segment(execution_id: int | None = None, **kwargs) -> dict:
    """
    Aggregate and send yesterday's pending per-event ExternalEvents to Segment.

    Groups by (service_name, segment_event_name) and sends a single Segment
    track per group containing a count and the full list of payloads.
    Marks all processed events as sent.
    """
    from apps.service_ingest.models import ExternalEvent
    from apps.tasks.collectors.send_anonymized_to_segment import send_to_segment
    from apps.tasks.utils import create_task_result

    yesterday = date.today() - timedelta(days=1)
    pending = ExternalEvent.objects.filter(
        payload_type="event",
        status="pending",
        created__date=yesterday,
    ).order_by("service_name", "segment_event_name", "created")

    total = pending.count()
    if total == 0:
        logger.info("No pending per-events to roll up for %s", yesterday)
        return create_task_result("success", {"date": str(yesterday), "groups_sent": 0, "events_processed": 0})

    # Group by (service_name, segment_event_name)
    groups: dict[tuple, list] = {}
    for event in pending:
        key = (event.service_name, event.segment_event_name, event.segment_anonymous_id)
        groups.setdefault(key, []).append(event)

    groups_sent = 0
    events_sent = 0

    for (service_name, event_name, anon_id), events in groups.items():
        rollup_payload = {
            "date": str(yesterday),
            "service_name": service_name,
            "event_count": len(events),
            "events": [e.payload for e in events],
        }

        result = send_to_segment(
            user_id=anon_id,
            event_name=event_name,
            segment_data=rollup_payload,
        )

        now = timezone.now()
        if result.get("status") == "success":
            pks = [e.pk for e in events]
            ExternalEvent.objects.filter(pk__in=pks).update(
                status="sent",
                sent_at=now,
                error_message="",
            )
            groups_sent += 1
            events_sent += len(events)
            logger.info("Rolled up %d events for %s/%s", len(events), service_name, event_name)
        else:
            error = result.get("error", "Unknown error")
            logger.warning("Failed rollup for %s/%s: %s", service_name, event_name, error)
            pks = [e.pk for e in events]
            ExternalEvent.objects.filter(pk__in=pks).update(
                status="failed",
                error_message=error,
            )

    logger.info(
        "Rollup complete for %s: %d groups, %d/%d events sent",
        yesterday,
        groups_sent,
        events_sent,
        total,
    )
    return create_task_result(
        "success",
        {
            "date": str(yesterday),
            "groups_sent": groups_sent,
            "events_processed": total,
            "events_sent": events_sent,
        },
    )
