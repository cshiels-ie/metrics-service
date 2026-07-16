"""Views for the service ingest API."""

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.service_ingest.authentication import ServiceTokenAuthentication
from apps.service_ingest.models import ExternalEvent
from apps.service_ingest.v1.serializers import ExternalEventSerializer

logger = logging.getLogger(__name__)


class IngestView(APIView):
    """
    POST /api/v1/ingest/events/

    Accepts a JSON telemetry envelope from an authenticated AAP service.
    Batch payloads are dispatched to Segment immediately via dispatcherd.
    Per-event payloads are stored and sent by the daily rollup task.
    """

    authentication_classes = [ServiceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ExternalEventSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        service_name = request.user.service_name
        segment_event_name = settings.SERVICE_SEGMENT_EVENTS.get(service_name, f"{service_name} Analytics")

        event = serializer.save(segment_event_name=segment_event_name)

        if event.payload_type == "batch":
            self._dispatch_batch_task(event)

        logger.info(
            "Received %s payload from %s (event_id=%s)",
            event.payload_type,
            service_name,
            event.pk,
        )
        return Response(
            {"id": event.pk, "status": "accepted", "payload_type": event.payload_type},
            status=status.HTTP_202_ACCEPTED,
        )

    def _dispatch_batch_task(self, event: ExternalEvent) -> None:
        """Create a Task and dispatch it immediately via dispatcherd.

        Uses crum.impersonate(None) to temporarily clear the thread-local user
        so DAB's CommonModel doesn't try to assign our ServiceUser as created_by.
        """
        try:
            import crum

            from apps.tasks.models import Task
            from apps.tasks.tasks import submit_task_to_dispatcher

            with crum.impersonate(None):
                task = Task.objects.create(
                    name=f"Send external batch from {event.service_name} (event {event.pk})",
                    function_name="send_external_batch_to_segment",
                    task_data={"event_id": event.pk},
                    is_system_task=True,
                )
            submit_task_to_dispatcher(task)
            logger.debug("Dispatched batch send task %s for event %s", task.pk, event.pk)
        except Exception:
            logger.exception("Failed to dispatch batch send task for event %s", event.pk)
            # Do not fail the ingest response — the event is stored; operator can retry
