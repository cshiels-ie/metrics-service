"""URL configuration for the BI Export v1 API."""

from ansible_base.lib.routers import AssociationResourceRouter

from apps.bi_export.v1.views.anonymized import DailyMetricsSummaryViewSet
from apps.bi_export.v1.views.awx_db import (
    HostMetricSummaryMonthlyViewSet,
    HostMetricsViewSet,
    InstanceGroupsViewSet,
    InstancesViewSet,
)
from apps.bi_export.v1.views.dashboard import JobDataViewSet, JobHostSummaryViewSet

router = AssociationResourceRouter()
router.register(r"jobs", JobDataViewSet, basename="bi-export-jobs")
router.register(r"job_host_summaries", JobHostSummaryViewSet, basename="bi-export-job-host-summaries")
router.register(r"daily_metrics", DailyMetricsSummaryViewSet, basename="bi-export-daily-metrics")
router.register(r"controller/host_metrics", HostMetricsViewSet, basename="bi-export-host-metrics")
router.register(
    r"controller/host_metric_summary", HostMetricSummaryMonthlyViewSet, basename="bi-export-host-metric-summary"
)
router.register(r"controller/instances", InstancesViewSet, basename="bi-export-instances")
router.register(r"controller/instance_groups", InstanceGroupsViewSet, basename="bi-export-instance-groups")

urlpatterns = router.urls
