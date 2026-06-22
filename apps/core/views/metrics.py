from ansible_base.lib.utils.views.ansible_base import AnsibleBaseView
from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor
from django_prometheus.exports import ExportToDjangoView


class PrometheusMetricsView(AnsibleBaseView):
    """Prometheus metrics endpoint restricted to system admins and auditors."""

    permission_classes = [IsSystemAdminOrAuditor]

    def get(self, request):
        return ExportToDjangoView(request)
