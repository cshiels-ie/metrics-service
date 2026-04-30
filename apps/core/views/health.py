from ansible_base.lib.utils.views.ansible_base import AnsibleBaseView
from django.db import close_old_connections, connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class HealthView(AnsibleBaseView):
    """
    Health check endpoint to verify service health.

    Checks database connectivity and returns overall health status.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        health_status: dict = {"status": "healthy", "checks": {}}

        # Database check
        try:
            # Close any stale connections before health check
            close_old_connections()
            connection.ensure_connection()
            health_status["checks"]["database"] = "ok"
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["database"] = f"error: {str(e)}"

        # Segment send check (no data is shown if there's no payloads to check)
        try:
            from apps.tasks.models import AnonymizedMetricsPayload

            most_recent = AnonymizedMetricsPayload.objects.all().order_by("-modified").first()
            if most_recent is not None:
                health_status["checks"]["segment_send"] = {}

                if most_recent.status == "failed":
                    health_status["checks"]["segment_send"]["status"] = "failed"
                    health_status["checks"]["segment_send"]["last_failure_at"] = str(most_recent.modified.isoformat())
                else:
                    health_status["checks"]["segment_send"]["status"] = "ok"
                    health_status["checks"]["segment_send"]["last_success_at"] = str(most_recent.modified.isoformat())
        except Exception as e:
            health_status["checks"]["segment_send"] = {}
            health_status["checks"]["segment_send"]["error"] = str(e)

        http_status = (
            status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
        )

        return Response(health_status, status=http_status)
