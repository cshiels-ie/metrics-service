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
            automated_costs: string;
            manual_costs: string;
            savings: string;
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
    automated_costs = serializers.CharField(help_text="Automation costs (formatted currency)")
    manual_costs = serializers.CharField(help_text="Manual execution costs (formatted currency)")
    savings = serializers.CharField(help_text="Cost savings from automation (formatted currency)")


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
    """

    project_id = serializers.IntegerField(help_text="Project ID")
    project_name = serializers.CharField(help_text="Project name")
    job_count = serializers.IntegerField(help_text="Number of jobs executed")


class UserSummarySerializer(serializers.Serializer):
    """
    Serializer for top users summary.

    Used by the dashboard details endpoint to show top users by execution count.
    """

    user_id = serializers.IntegerField(help_text="User ID")
    username = serializers.CharField(help_text="Username")
    job_count = serializers.IntegerField(help_text="Number of jobs executed")


class DashboardDetailsSerializer(serializers.Serializer):
    """
    Comprehensive dashboard details serializer.

    Returns all dashboard data including job templates, top projects, and top users.
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
