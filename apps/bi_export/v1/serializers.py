"""Serializers for the BI Export API."""

from rest_framework import serializers

from apps.dashboard_reports.models import JobData, JobHostSummary
from apps.tasks.models import DailyMetricsSummary


class JobDataSerializer(serializers.ModelSerializer):
    """Raw job execution records from the dashboard collection."""

    label_ids = serializers.SerializerMethodField()

    class Meta:
        model = JobData
        fields = [
            "id",
            "job_id",
            "template_name",
            "template_id",
            "project_id",
            "project_name",
            "organization_id",
            "organization_name",
            "status",
            "started",
            "finished",
            "elapsed",
            "num_hosts",
            "launched_by_id",
            "launched_by_username",
            "label_ids",
            "awx_created",
            "awx_modified",
        ]

    def get_label_ids(self, obj):
        return list(obj.labels.values_list("label_id", flat=True))


class JobHostSummarySerializer(serializers.ModelSerializer):
    """Host-level results for each job from the dashboard collection."""

    job_id = serializers.IntegerField(source="job_data.job_id", read_only=True)

    class Meta:
        model = JobHostSummary
        fields = [
            "id",
            "job_data_id",
            "job_id",
            "host_summary_id",
            "host_id",
            "host_name",
        ]


class DailyMetricsSummaryListSerializer(serializers.ModelSerializer):
    """Lightweight list response — excludes the full aggregated_metrics blob."""

    class Meta:
        model = DailyMetricsSummary
        fields = [
            "id",
            "summary_date",
            "status",
            "hourly_collections_count",
            "aggregation_completed_at",
        ]


class DailyMetricsSummaryDetailSerializer(serializers.ModelSerializer):
    """Full detail response — includes the complete aggregated_metrics JSON."""

    class Meta:
        model = DailyMetricsSummary
        fields = [
            "id",
            "summary_date",
            "status",
            "hourly_collections_count",
            "missing_hours",
            "aggregation_completed_at",
            "aggregated_metrics",
        ]
