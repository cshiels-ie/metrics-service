"""
Dashboard report serializers for automation-reports integration.

These serializers match the automation-reports TypeScript interfaces exactly
to ensure API contract compatibility with the React frontend.
"""

from rest_framework import serializers


class ReportSerializer(serializers.Serializer):
    """
    Serializer for dashboard report data.

    This serializer matches the automation-reports Report TypeScript interface exactly,
    ensuring API contract compatibility with the React frontend.

    TypeScript interface (from automation-reports):
        interface Report {
            name: string;
            runs: number;
            elapsed: string;
            cluster: number;
            elapsed_str: string;
            num_hosts: number;
            time_taken_manually_execute_minutes: number;
            time_taken_create_automation_minutes: number;
            successful_runs: number;
            failed_runs: number;
            automated_costs: number;  // Frontend formats with currency symbol
            manual_costs: number;      // Frontend formats with currency symbol
            savings: number;           // Frontend formats with currency symbol
        }
    """

    name = serializers.CharField(help_text="Job template name")
    runs = serializers.IntegerField(help_text="Total number of runs")
    elapsed = serializers.IntegerField(help_text="Total elapsed time in seconds")
    cluster = serializers.IntegerField(help_text="Cluster identifier")
    elapsed_str = serializers.CharField(help_text="Human-readable elapsed time (e.g., '2h 15m')")
    num_hosts = serializers.IntegerField(help_text="Number of unique hosts")
    time_taken_manually_execute_minutes = serializers.IntegerField(
        help_text="Estimated time to execute manually (minutes)"
    )
    time_taken_create_automation_minutes = serializers.IntegerField(
        help_text="Time taken to create automation (minutes)"
    )
    successful_runs = serializers.IntegerField(help_text="Number of successful runs")
    failed_runs = serializers.IntegerField(help_text="Number of failed runs")
    automated_costs = serializers.FloatField(help_text="Automation costs (numeric, frontend will format)")
    manual_costs = serializers.FloatField(help_text="Manual execution costs (numeric, frontend will format)")
    savings = serializers.FloatField(help_text="Cost savings from automation (numeric, frontend will format)")


class ReportResponseSerializer(serializers.Serializer):
    """
    Paginated response serializer for dashboard reports.

    Matches the automation-reports ReportResponse TypeScript interface:
        interface ReportResponse {
            count: number;
            next: string;
            previous: string;
            results: Report[];
        }
    """

    count = serializers.IntegerField(help_text="Total number of reports")
    next = serializers.CharField(allow_null=True, help_text="URL to next page (null if last page)")
    previous = serializers.CharField(allow_null=True, help_text="URL to previous page (null if first page)")
    results = ReportSerializer(many=True, help_text="Array of report data")


class ProjectSummarySerializer(serializers.Serializer):
    """
    Serializer for top projects summary.

    Used by the dashboard details endpoint to show top projects by job count.

    Matches the automation-reports TopProject TypeScript interface:
        interface TopProject {
            project_id: number;
            project_name: string;
            count: string;
        }
    """

    project_id = serializers.IntegerField(help_text="Project ID")
    project_name = serializers.CharField(help_text="Project name")
    count = serializers.CharField(help_text="Number of jobs executed (as string)")


class UserSummarySerializer(serializers.Serializer):
    """
    Serializer for top users summary.

    Used by the dashboard details endpoint to show top users by execution count.

    Matches the automation-reports TopUser TypeScript interface:
        interface TopUser {
            user_id: number;
            user_name: string;
            count: string;
        }
    """

    user_id = serializers.IntegerField(help_text="User ID")
    user_name = serializers.CharField(help_text="Username")
    count = serializers.CharField(help_text="Number of jobs executed (as string)")


class DashboardDetailsSerializer(serializers.Serializer):
    """
    Comprehensive dashboard details serializer.

    Returns all dashboard data including job templates, top projects, top users,
    summary totals for the dashboard statistics cards, and chart data.
    Used by the /api/v1/report/details/ endpoint.
    """

    job_templates = serializers.DictField(
        help_text="Job template data with array of Report objects"
    )
    top_projects = serializers.DictField(
        help_text="Top projects data with array of project summaries"
    )
    top_users = serializers.DictField(
        help_text="Top users data with array of user summaries"
    )
    date_range = serializers.DictField(
        help_text="Date range of the data (start and end ISO timestamps)"
    )
    total_number_of_successful_jobs = serializers.DictField(
        help_text="Total successful jobs: {value: number}"
    )
    total_number_of_failed_jobs = serializers.DictField(
        help_text="Total failed jobs: {value: number}"
    )
    total_number_of_unique_hosts = serializers.DictField(
        help_text="Total unique hosts automated: {value: number}"
    )
    total_hours_of_automation = serializers.DictField(
        help_text="Total automation hours: {value: number}"
    )
    total_number_of_job_runs = serializers.DictField(
        help_text="Total number of job executions: {value: number}"
    )
    total_number_of_host_job_runs = serializers.DictField(
        help_text="Total host job runs (runs * hosts): {value: number}"
    )
    job_chart = serializers.DictField(
        help_text="Job runs chart data: {items: [], range: {}}"
    )
    host_chart = serializers.DictField(
        help_text="Host jobs chart data: {items: [], range: {}}"
    )


# =============================================================================
# New Serializers for Template Options and Settings Endpoints
# =============================================================================


class CurrencySerializer(serializers.Serializer):
    """
    Serializer for currency options.

    Matches TypeScript interface: {id: number; name: string; symbol: string;}

    Used in filter options response to provide currency selection dropdown.
    """

    id = serializers.IntegerField(help_text="Currency ID")
    name = serializers.CharField(help_text="Currency full name (e.g., 'US Dollar')")
    symbol = serializers.CharField(help_text="Currency symbol (e.g., '$')")


class FilterSetSerializer(serializers.Serializer):
    """
    Serializer for saved filter sets (saved views).

    Matches TypeScript interface: {id: number; name: string; filters: any;}

    Allows users to save and recall commonly-used filter combinations.
    """

    id = serializers.IntegerField(help_text="Filter set ID")
    name = serializers.CharField(help_text="User-defined name for this saved view")
    filters = serializers.JSONField(
        help_text="Filter configuration: {organizations: [], projects: [], labels: [], date_range: {}}"
    )


class FilterOptionSerializer(serializers.Serializer):
    """
    Generic filter option serializer.

    Matches TypeScript interface: {id: number; name: string; key?: string;}

    Used for organizations, projects, date ranges, and other simple filter options.
    """

    id = serializers.IntegerField(help_text="Option ID")
    name = serializers.CharField(help_text="Option display name")
    key = serializers.CharField(required=False, help_text="Option key for date ranges")


class ClusterOptionSerializer(serializers.Serializer):
    """
    Serializer for cluster/execution environment options.

    Transforms AWX database query results {id, name, type} to match the
    frontend interface {key, value, type, cluster_id}.

    TypeScript interface (from automation-reports):
        interface ClusterOption {
            key: string | number;
            value: string;
            type: string;
            cluster_id: string | number;
        }
    """

    key = serializers.IntegerField(
        source='id',
        help_text="Cluster/execution environment ID (maps from 'id' field)"
    )
    value = serializers.CharField(
        source='name',
        help_text="Cluster/execution environment name (maps from 'name' field)"
    )
    type = serializers.CharField(
        help_text="Type identifier (e.g., 'execution_environment')"
    )
    cluster_id = serializers.IntegerField(
        default=1,
        help_text="Cluster ID (defaults to 1 for single-cluster deployments)"
    )


class FilterOptionWithIdSerializer(serializers.Serializer):
    """
    Serializer for filter options with automation-reports compatibility.

    Transforms AWX database query results {id, name} to match the
    frontend FilterOptionWithId interface {key, value, cluster_id}.

    This is used for organizations, projects, labels, and instances endpoints
    to ensure compatibility with the automation-reports dropdown components.

    TypeScript interface (from automation-reports):
        interface FilterOptionWithId {
            key: string | number;
            value: string;
            cluster_id: string | number;
        }
    """

    key = serializers.IntegerField(
        source='id',
        help_text="Option ID (maps from 'id' field)"
    )
    value = serializers.CharField(
        source='name',
        help_text="Option display name (maps from 'name' field)"
    )
    cluster_id = serializers.IntegerField(
        default=1,
        help_text="Cluster ID (defaults to 1 for single-cluster deployments)"
    )


class FilterOptionResponseSerializer(serializers.Serializer):
    """
    Master aggregation serializer for template options endpoint.

    Matches TypeScript FilterOptionResponse interface exactly.

    This is the CRITICAL endpoint that provides all filter dropdowns,
    settings, currencies, and saved views in a single response.

    TypeScript interface (from automation-reports):
        interface FilterOptionResponse {
            automated_process_cost_per_minute: number | string;
            clusters: ClusterOption[];
            date_ranges: FilterOption[];
            labels: FilterOptionWithId[];
            manual_cost_automation_per_hour: number | string;
            organizations: FilterOption[];
            instances: FilterOptionWithId[];
            currencies: Currency[];
            projects: FilterOptionWithId[];
            currency: number;
            enable_template_creation_time: boolean;
            filter_sets: FilterSet[];
            max_pdf_job_templates: number;
        }
    """

    # Global cost settings (from Setting model)
    automated_process_cost_per_minute = serializers.CharField(
        help_text="Cost per minute for automated processes (from settings)"
    )
    manual_cost_automation_per_hour = serializers.CharField(
        help_text="Hourly cost for manual task execution (from settings)"
    )
    enable_template_creation_time = serializers.BooleanField(
        help_text="Whether to include template creation time in cost calculations"
    )
    max_pdf_job_templates = serializers.IntegerField(
        help_text="Maximum number of templates to include in PDF exports"
    )

    # User's current currency preference
    currency = serializers.IntegerField(
        help_text="Current user's selected currency ID"
    )

    # Arrays of filter options
    currencies = CurrencySerializer(
        many=True,
        help_text="Available currencies for cost display"
    )
    filter_sets = FilterSetSerializer(
        many=True,
        help_text="User's saved filter configurations"
    )
    organizations = FilterOptionWithIdSerializer(
        many=True,
        help_text="Available organizations for filtering (from AWX database)"
    )
    projects = FilterOptionWithIdSerializer(
        many=True,
        help_text="Available projects for filtering (from AWX database)"
    )
    labels = FilterOptionWithIdSerializer(
        many=True,
        help_text="Available labels for filtering (from AWX database)"
    )
    instances = FilterOptionWithIdSerializer(
        many=True,
        help_text="Available instances for filtering (from AWX database)"
    )
    clusters = ClusterOptionSerializer(
        many=True,
        help_text="Available clusters/execution environments (from AWX database)"
    )
    date_ranges = FilterOptionSerializer(
        many=True,
        help_text="Predefined date range options (Last 7/30/90 days, Custom)"
    )


class TemplateMetadataSerializer(serializers.Serializer):
    """
    Serializer for job template metadata overrides.

    Used by PUT /api/v1/templates/{id}/ endpoint to allow users
    to override auto-calculated time estimates and costs.

    Example:
        {
            "template_id": 42,
            "template_name": "Deploy Production",
            "time_taken_manually_execute_minutes": 120,
            "time_taken_create_automation_minutes": 240,
            "custom_cost_per_minute": "1.50",
            "notes": "Complex multi-step deployment"
        }
    """

    template_id = serializers.IntegerField(
        read_only=True,
        help_text="AWX job template ID (read-only, set via URL)"
    )
    template_name = serializers.CharField(
        help_text="Cached template name for display"
    )
    time_taken_manually_execute_minutes = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="User override: Estimated manual execution time (minutes)"
    )
    time_taken_create_automation_minutes = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="User override: Time spent creating automation (minutes)"
    )
    custom_cost_per_minute = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="User override: Custom cost per minute for this template"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="User notes about this template"
    )


class UserPreferenceSerializer(serializers.Serializer):
    """
    Serializer for user dashboard preferences.

    Used by POST /api/v1/common/settings/ endpoint to save
    user-specific preferences like currency selection.

    Example:
        {
            "currency": 1,
            "preferences": {
                "theme": "dark",
                "default_date_range": "last_30_days"
            }
        }
    """

    currency = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Currency ID for cost display (FK to Currency model)"
    )
    preferences_data = serializers.JSONField(
        required=False,
        help_text="Additional user preferences (extensible JSON structure)"
    )


class PaginatedFilterOptionsSerializer(serializers.Serializer):
    """
    Paginated response serializer for filter options.

    Matches the OptionsResponse TypeScript interface from automation-reports:
        interface OptionsResponse {
            count: number;
            next: string | null;
            previous: string | null;
            results: FilterOptionWithId[];
        }
    """

    count = serializers.IntegerField(
        help_text="Total number of options available"
    )
    next = serializers.CharField(
        allow_null=True,
        help_text="URL to next page (null if last page)"
    )
    previous = serializers.CharField(
        allow_null=True,
        help_text="URL to previous page (null if first page)"
    )
    results = FilterOptionWithIdSerializer(
        many=True,
        help_text="Array of filter options in {key, value, cluster_id} format"
    )
