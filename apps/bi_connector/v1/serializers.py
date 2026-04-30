"""
Serializers for BI connector metrics endpoints (Layer 1).

Flattens DailyMetricsSummary.aggregated_metrics JSON blob into top-level fields
for BI tool compatibility (Tableau, Power BI require flat columnar data).
"""

from rest_framework import serializers

from apps.tasks.models import DailyMetricsSummary, HourlyMetricsCollection


class HourlyMetricsCollectionListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer — excludes large raw_data field."""

    collector_type_display = serializers.CharField(source="get_collector_type_display", read_only=True)

    class Meta:
        model = HourlyMetricsCollection
        fields = [
            "id",
            "collector_type",
            "collector_type_display",
            "collection_timestamp",
            "status",
            "data_size_bytes",
            "error_message",
            "created",
        ]


class HourlyMetricsCollectionDetailSerializer(HourlyMetricsCollectionListSerializer):
    """Detail serializer — includes raw_data and collection_parameters."""

    class Meta(HourlyMetricsCollectionListSerializer.Meta):
        fields = HourlyMetricsCollectionListSerializer.Meta.fields + [
            "raw_data",
            "collection_parameters",
            "task_execution",
        ]


class DailyMetricsSummaryListSerializer(serializers.ModelSerializer):
    """
    List serializer with flattened aggregated_metrics for BI tool compatibility.

    Each collector type is exposed as a separate top-level field (metrics_<type>)
    rather than nested inside the aggregated_metrics JSON blob. BI tools (Tableau,
    Power BI) require flat columnar data and cannot natively traverse nested JSON.

    The AnonymizedMetricsPayload model is deliberately NOT exposed here — its data
    is salt-hashed per day and cannot be joined across dates.
    """

    metrics_job_host_summary_service = serializers.SerializerMethodField()
    metrics_unified_jobs = serializers.SerializerMethodField()
    metrics_credentials_service = serializers.SerializerMethodField()
    metrics_main_jobevent_service = serializers.SerializerMethodField()
    metrics_execution_environments = serializers.SerializerMethodField()
    metrics_controller_version_service = serializers.SerializerMethodField()
    metrics_table_metadata = serializers.SerializerMethodField()

    class Meta:
        model = DailyMetricsSummary
        fields = [
            "id",
            "summary_date",
            "status",
            "hourly_collections_count",
            "missing_hours",
            "aggregation_completed_at",
            "error_message",
            "config_data",
            "metrics_job_host_summary_service",
            "metrics_unified_jobs",
            "metrics_credentials_service",
            "metrics_main_jobevent_service",
            "metrics_execution_environments",
            "metrics_controller_version_service",
            "metrics_table_metadata",
            "created",
            "modified",
        ]

    def get_metrics_job_host_summary_service(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("job_host_summary_service", {})

    def get_metrics_unified_jobs(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("unified_jobs", {})

    def get_metrics_credentials_service(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("credentials_service", {})

    def get_metrics_main_jobevent_service(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("main_jobevent_service", {})

    def get_metrics_execution_environments(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("execution_environments", {})

    def get_metrics_controller_version_service(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("controller_version_service", {})

    def get_metrics_table_metadata(self, obj: DailyMetricsSummary) -> dict:
        return obj.aggregated_metrics.get("table_metadata", {})


class DailyMetricsSummaryDetailSerializer(DailyMetricsSummaryListSerializer):
    """Detail serializer — adds raw aggregated_metrics blob and hourly collection IDs."""

    class Meta(DailyMetricsSummaryListSerializer.Meta):
        fields = DailyMetricsSummaryListSerializer.Meta.fields + [
            "hourly_collection_ids",
            "aggregated_metrics",
            "rollup_task_execution",
        ]
