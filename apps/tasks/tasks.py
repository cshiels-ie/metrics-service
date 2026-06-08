"""
Background tasks for metrics_service using dispatcherd.

This module serves as an aggregator, importing and re-exporting tasks from
individual task modules:
- simple/: Simple system tasks
- cleanup/: Cleanup and maintenance tasks
- collectors/: Metrics collection and anonymization tasks
  - collectors/eda/: EDA snapshot collectors (opt-in)
  - collectors/gateway/: Gateway snapshot collectors (opt-in)
  - collectors/lightspeed/: Lightspeed snapshot collectors (opt-in)
- tasks_system: Core task execution infrastructure and utilities

Queue routing is defined per-function in TASK_METADATA ("queue" field).
"""

import logging

# Dashboard reports tasks
from ..dashboard_reports.tasks import (
    cleanup_dashboard_reports_old_data,
    collect_dashboard_reports_data,
    collect_dashboard_reports_initial_data,
    sync_dashboard_job_records,
)

# Import cleanup tasks
from .cleanup.cleanup_activitystream import cleanup_activitystream
from .cleanup.cleanup_metrics_data import cleanup_metrics_data
from .cleanup.cleanup_old_tasks import cleanup_old_tasks

# Import collector tasks
from .collectors.collect_daily_metrics import collect_daily_metrics
from .collectors.collect_hourly_metrics import collect_hourly_metrics
from .collectors.collect_snapshot_metrics import collect_snapshot_metrics
from .collectors.daily_anonymize_and_prepare import daily_anonymize_and_prepare
from .collectors.daily_metrics_rollup import daily_metrics_rollup
from .collectors.send_anonymized_to_segment import send_anonymized_to_segment

# Per-source collectors for EDA, Gateway, and Lightspeed (opt-in)
from .collectors.eda.collect_eda_snapshot_metrics import collect_eda_snapshot_metrics
from .collectors.gateway.collect_gateway_snapshot_metrics import collect_gateway_snapshot_metrics
from .collectors.lightspeed.collect_lightspeed_snapshot_metrics import collect_lightspeed_snapshot_metrics
from .collectors.probe_db_connection import probe_db_connection

# Note: Hourly and snapshot collectors handle all collector types via collector_type parameter
# Import system tasks
from .simple.hello_world import hello_world
from .tasks_system import create_system_tasks, submit_task_to_dispatcher

logger = logging.getLogger(__name__)

# Task configuration for dispatcherd
TASK_FUNCTIONS = {
    # System tasks
    "hello_world": hello_world,
    "cleanup_old_tasks": cleanup_old_tasks,
    "cleanup_activitystream": cleanup_activitystream,
    "cleanup_metrics_data": cleanup_metrics_data,
    # Metrics Collection (hourly time-series, daily snapshots, and daily time-range)
    "collect_hourly_metrics": collect_hourly_metrics,
    "collect_snapshot_metrics": collect_snapshot_metrics,
    "collect_daily_metrics": collect_daily_metrics,
    # Daily Rollup and Anonymization Tasks
    "daily_metrics_rollup": daily_metrics_rollup,
    "daily_anonymize_and_prepare": daily_anonymize_and_prepare,
    "send_anonymized_to_segment": send_anonymized_to_segment,
    # Dashboard reports
    "collect_dashboard_reports_data": collect_dashboard_reports_data,
    "collect_dashboard_reports_initial_data": collect_dashboard_reports_initial_data,
    "cleanup_dashboard_reports_old_data": cleanup_dashboard_reports_old_data,
    "sync_dashboard_job_records": sync_dashboard_job_records,
    # Connectivity probes and opt-in source collectors (EDA, Gateway, Lightspeed)
    "probe_db_connection": probe_db_connection,
    "collect_eda_snapshot_metrics": collect_eda_snapshot_metrics,
    "collect_gateway_snapshot_metrics": collect_gateway_snapshot_metrics,
    "collect_lightspeed_snapshot_metrics": collect_lightspeed_snapshot_metrics,
}

# Tasks that require a PostgreSQL advisory lock during scheduled execution.
# The lock key is the function name. Locking is applied in execute_db_task,
# so direct invocations (e.g. run_task.py) run without contention.
TASK_LOCKS = {
    "collect_hourly_metrics",
    "collect_snapshot_metrics",
    "daily_metrics_rollup",
    "daily_anonymize_and_prepare",
    "send_anonymized_to_segment",
    "collect_dashboard_reports_initial_data",
    "cleanup_dashboard_reports_old_data",
    "sync_dashboard_job_records",
    # Opt-in snapshot collectors (probe_db_connection intentionally omitted — fast, non-mutating)
    "collect_eda_snapshot_metrics",
    "collect_gateway_snapshot_metrics",
    "collect_lightspeed_snapshot_metrics",
}


def get_queue_for_function(function_name: str) -> str:
    """Get the appropriate queue name for a task function; or 'maintenance'"""
    metadata = TASK_METADATA.get(function_name)
    return (metadata and metadata.get("queue", None)) or "maintenance"


_DASHBOARD_REPORTS_CATEGORY = "Dashboard Reports"

# Enhanced task metadata for dashboard display
TASK_METADATA = {
    # Testing
    "hello_world": {
        "queue": "maintenance",
        "category": "Testing",
        "description": "Simple hello world task for testing the dispatcherd integration",
        "parameters": {},
        "examples": [{"name": "Basic Hello World", "data": {}}],
    },
    # Maintenance
    "cleanup_old_tasks": {
        "queue": "maintenance",
        "category": "Maintenance",  # task system records
        "description": "Clean up old completed and failed tasks (preserves recurring tasks by default)",
        "parameters": {
            "days_old": {
                "type": "integer",
                "default": 5,
                "description": "Number of days old tasks should be to qualify for cleanup",
                "min": 1,
                "max": 365,
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "If true, only count tasks that would be deleted without actually deleting",
            },
            "include_executions": {
                "type": "boolean",
                "default": True,
                "description": "Also cleanup related TaskExecution records",
            },
            "preserve_recurring": {
                "type": "boolean",
                "default": True,
                "description": "If true, exclude recurring tasks from cleanup (recommended)",
            },
        },
        "examples": [
            {"name": "Standard cleanup (5 days)", "data": {"days_old": 5}},
            {"name": "Test cleanup (dry run)", "data": {"days_old": 7, "dry_run": True}},
            {"name": "Conservative cleanup", "data": {"days_old": 10, "include_executions": False}},
            {"name": "Include recurring tasks", "data": {"days_old": 30, "preserve_recurring": False}},
        ],
    },
    "cleanup_activitystream": {
        "queue": "maintenance",
        "category": "Maintenance",  # DAB activity stream audit log
        "description": "Clean up old ActivityStream (django-ansible-base) audit log entries",
        "parameters": {
            "days_old": {
                "type": "integer",
                "default": 7,
                "description": "Number of days old ActivityStream entries must be before they are removed",
                "min": 1,
                "max": 365,
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "If true, only count entries that would be deleted without actually deleting",
            },
        },
        "examples": [
            {"name": "Default (7 days)", "data": {}},
            {"name": "Dry run", "data": {"dry_run": True}},
            {"name": "Extended retention (30 days)", "data": {"days_old": 30}},
        ],
    },
    "cleanup_metrics_data": {
        "queue": "metrics",
        "category": "Maintenance",  # metrics collection data
        "description": "Clean up old metrics data based on retention policies",
        "parameters": {
            "hourly_retention_days": {
                "type": "integer",
                "default": 7,
                "description": "Number of days to retain hourly collection data",
                "min": 1,
                "max": 365,
            },
            "daily_retention_days": {
                "type": "integer",
                "default": 30,
                "description": "Number of days to retain daily rollup data",
                "min": 1,
                "max": 730,
            },
            "payload_retention_days": {
                "type": "integer",
                "default": 7,
                "description": "Number of days to retain anonymized payloads",
                "min": 1,
                "max": 90,
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "If true, only count records that would be deleted without actually deleting",
            },
        },
        "examples": [
            {"name": "Default retention", "data": {}},
            {
                "name": "Custom retention",
                "data": {"hourly_retention_days": 14, "daily_retention_days": 60, "payload_retention_days": 14},
            },
            {"name": "Dry run", "data": {"dry_run": True}},
        ],
    },
    # Metrics Collection (Hourly and Snapshot)
    "collect_hourly_metrics": {
        "queue": "metrics",
        "category": "Metrics Collection",
        "description": "Collect hourly time-series metrics for a specific collector type",
        "parameters": {
            "collector_type": {
                "type": "string",
                "required": True,
                "description": "Type of collector to run (e.g., unified_jobs)",
            },
            "hour_timestamp": {
                "type": "string",
                "description": "ISO timestamp for the hour to collect (defaults to current hour)",
            },
        },
        "examples": [
            {"name": "Job host summary", "data": {"collector_type": "job_host_summary_service"}},
            {"name": "Unified jobs", "data": {"collector_type": "unified_jobs"}},
            {"name": "Credentials", "data": {"collector_type": "credentials_service"}},
            {"name": "Job events", "data": {"collector_type": "main_jobevent_service"}},
            {
                "name": "Specific hour",
                "data": {"collector_type": "job_host_summary_service", "hour_timestamp": "2024-01-01T00:00:00Z"},
            },
        ],
    },
    "collect_daily_metrics": {
        "queue": "metrics",
        "category": "Metrics Collection",
        "description": "Collect daily time-range metrics (previous full day) for a specific collector type",
        "parameters": {
            "collector_type": {
                "type": "string",
                "required": True,
                "description": "Type of daily collector to run (e.g., task_executions_service)",
            },
            "since": {
                "type": "string",
                "description": "ISO timestamp for start of collection window (defaults to yesterday 00:00 UTC)",
            },
            "until": {
                "type": "string",
                "description": "ISO timestamp for end of collection window (defaults to today 00:00 UTC)",
            },
        },
        "examples": [
            {"name": "Task executions (default: yesterday)", "data": {"collector_type": "task_executions_service"}},
            {
                "name": "Task executions (specific day)",
                "data": {
                    "collector_type": "task_executions_service",
                    "since": "2024-01-01T00:00:00Z",
                    "until": "2024-01-02T00:00:00Z",
                },
            },
        ],
    },
    "collect_snapshot_metrics": {
        "queue": "metrics",
        "category": "Metrics Collection",
        "description": "Collect daily snapshot metrics for a specific collector type",
        "parameters": {
            "collector_type": {
                "type": "string",
                "required": True,
                "description": "Type of collector to run (e.g., execution_environments)",
            },
        },
        "examples": [
            {"name": "Execution environments", "data": {"collector_type": "execution_environments"}},
            {"name": "System config", "data": {"collector_type": "config"}},
            {"name": "Controller version", "data": {"collector_type": "controller_version_service"}},
            {"name": "Table metadata", "data": {"collector_type": "table_metadata"}},
            {"name": "Feature flags", "data": {"collector_type": "feature_flags_service"}},
        ],
    },
    # Daily Rollup and Anonymization
    "daily_metrics_rollup": {
        "queue": "metrics",
        "category": "Metrics Rollup",
        "description": "Merge hourly collections and create daily rollup summary",
        "parameters": {
            "summary_date": {
                "type": "string",
                "description": "ISO date for the rollup (defaults to yesterday)",
            },
        },
        "examples": [
            {"name": "Default (yesterday)", "data": {}},
            {"name": "Specific date", "data": {"summary_date": "2024-01-01"}},
        ],
    },
    "daily_anonymize_and_prepare": {
        "queue": "metrics",
        "category": "Metrics Anonymization",
        "description": "Anonymize daily rollup and prepare payload for transmission",
        "parameters": {
            "summary_date": {
                "type": "string",
                "description": "ISO date for the summary to anonymize (defaults to yesterday)",
            },
        },
        "examples": [
            {"name": "Default (yesterday)", "data": {}},
            {"name": "Specific date", "data": {"summary_date": "2024-01-01"}},
        ],
    },
    "send_anonymized_to_segment": {
        "queue": "metrics",
        "category": "Metrics Transmission",
        "description": "Send anonymized metrics payloads to Segment.com",
        "parameters": {
            "payload_id": {
                "type": "integer",
                "description": "Specific payload ID to send (optional, sends pending/retry payloads if not specified)",
            },
            "max_payloads": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of payloads to send in one task execution",
                "min": 1,
                "max": 100,
            },
            "stale_minutes": {
                "type": "integer",
                "default": 10,
                "description": "Minutes before 'sending' status is considered stale and recovered",
                "min": 1,
                "max": 60,
            },
        },
        "examples": [
            {"name": "Default (send pending)", "data": {}},
            {"name": "Specific payload", "data": {"payload_id": 123}},
            {"name": "Send batch of 10", "data": {"max_payloads": 10}},
            {"name": "Recover stale payloads (30 min)", "data": {"stale_minutes": 30}},
        ],
    },
    "collect_dashboard_reports_data": {
        "queue": "dashboard",
        "category": _DASHBOARD_REPORTS_CATEGORY,
        "description": "Collect data for automation-reports dashboard (job templates, top projects/users) with configurable date range",
        "parameters": {
            "since": {
                "type": "string",
                "description": "Start datetime for collection (ISO format, defaults to last collected timestamp or 90 days ago)",
                "pattern": "datetime",
            },
            "until": {
                "type": "string",
                "description": "End datetime for collection (ISO format, defaults to now)",
                "pattern": "datetime",
            },
        },
        "examples": [
            {"name": "Default collection (last 90 days)", "data": {}},
            {
                "name": "Custom date range",
                "data": {"since": "2024-01-30T00:00:00Z", "until": "2024-01-31T23:59:59Z"},
            },
            {"name": "Last 7 days", "data": {"since": "2024-01-24T00:00:00Z", "until": "2024-01-31T00:00:00Z"}},
        ],
    },
    "collect_dashboard_reports_initial_data": {
        "queue": "dashboard",
        "category": _DASHBOARD_REPORTS_CATEGORY,
        "description": "One-time backfill of historical AWX job data (window controlled by DASHBOARD_COLLECTION['INITIAL_BACKFILL_DAYS'], default 90 days). Ongoing incremental sync is driven automatically by the hourly_unified_jobs hook after this completes.",
        "parameters": {
            "since": {
                "type": "string",
                "description": "Start datetime for collection (ISO format, defaults to 90 days ago)",
                "pattern": "datetime",
            },
            "until": {
                "type": "string",
                "description": "End datetime for collection (ISO format, defaults to now)",
                "pattern": "datetime",
            },
        },
        "examples": [
            {"name": "Default (last 90 days)", "data": {}},
            {
                "name": "Custom date range",
                "data": {"since": "2024-01-01T00:00:00Z", "until": "2024-03-31T23:59:59Z"},
            },
        ],
    },
    "sync_dashboard_job_records": {
        "queue": "dashboard",
        "category": _DASHBOARD_REPORTS_CATEGORY,
        "description": "Write unified_jobs data collected during the hourly rollup to the dashboard JobData table",
        "parameters": {
            "hour_timestamp": {
                "type": "string",
                "description": "ISO timestamp of the hour being synced",
            },
            "raw_jobs": {
                "type": "array",
                "description": "Serialised unified_jobs rows from the hourly collector hook",
            },
        },
        "examples": [
            {
                "name": "Sync one hour of job records",
                "data": {
                    "hour_timestamp": "2024-01-01T00:00:00+00:00",
                    "raw_jobs": [
                        {
                            "id": 1,
                            "name": "Demo Job Template",
                            "unified_job_template_id": 10,
                            "organization_id": 1,
                            "organization_name": "Default",
                            "started": "2024-01-01T00:01:00+00:00",
                            "finished": "2024-01-01T00:02:30+00:00",
                            "status": "successful",
                            "elapsed": 90.0,
                            "launched_by_id": 1,
                            "launched_by_username": "admin",
                            "project_id": 5,
                            "project_name": "Demo Project",
                            "created": "2024-01-01T00:00:50+00:00",
                            "modified": "2024-01-01T00:02:30+00:00",
                            "label_ids": None,
                            "num_hosts": 3,
                        }
                    ],
                },
            },
        ],
    },
    "cleanup_dashboard_reports_old_data": {
        "queue": "dashboard",
        "category": "Maintenance",  # dashboard report JobData
        "description": "Delete dashboard report JobData records older than the retention period (defaults to DASHBOARD_COLLECTION.INITIAL_BACKFILL_DAYS)",
        "parameters": {
            "retention_period_days": {
                "type": "integer",
                "default": None,
                "description": "Number of days to retain dashboard report data. Defaults to DASHBOARD_COLLECTION.INITIAL_BACKFILL_DAYS (or 90 if unset).",
                "min": 0,
                "max": 365,
            },
        },
        "examples": [
            {"name": "Default (matches INITIAL_BACKFILL_DAYS)", "data": {}},
            {"name": "Extended retention", "data": {"retention_period_days": 180}},
        ],
    },
    # Connectivity Probes
    "probe_db_connection": {
        "queue": "metrics",
        "category": "Connectivity",
        "description": "Check that an optional external database (eda/gateway/lightspeed) is reachable. Never raises — always returns a structured result.",
        "parameters": {
            "source": {
                "type": "string",
                "required": True,
                "description": "Database alias to probe: 'eda', 'gateway', or 'lightspeed'",
            },
        },
        "examples": [
            {"name": "Probe EDA", "data": {"source": "eda"}},
            {"name": "Probe Gateway", "data": {"source": "gateway"}},
            {"name": "Probe Lightspeed", "data": {"source": "lightspeed"}},
        ],
    },
    # EDA Collection
    "collect_eda_snapshot_metrics": {
        "queue": "metrics",
        "category": "Metrics Collection",
        "description": "Collect a daily snapshot from the EDA database. Returns a structured error result if the EDA DB is unreachable.",
        "parameters": {
            "collector_type": {
                "type": "string",
                "required": True,
                "description": "EDA collector type to run",
            },
            "collection_timestamp": {
                "type": "string",
                "description": "ISO timestamp for the collection (defaults to 23:00 of the previous day)",
            },
        },
        "examples": [
            {"name": "EDA config snapshot", "data": {"collector_type": "eda_config"}},
            {"name": "EDA activation counts", "data": {"collector_type": "eda_activations"}},
        ],
    },
    # Gateway Collection
    "collect_gateway_snapshot_metrics": {
        "queue": "metrics",
        "category": "Metrics Collection",
        "description": "Collect a daily snapshot from the Gateway database. Returns a structured error result if the Gateway DB is unreachable.",
        "parameters": {
            "collector_type": {
                "type": "string",
                "required": True,
                "description": "Gateway collector type to run",
            },
            "collection_timestamp": {
                "type": "string",
                "description": "ISO timestamp for the collection (defaults to 23:00 of the previous day)",
            },
        },
        "examples": [
            {"name": "Gateway config snapshot", "data": {"collector_type": "gateway_config"}},
        ],
    },
    # Lightspeed Collection
    "collect_lightspeed_snapshot_metrics": {
        "queue": "metrics",
        "category": "Metrics Collection",
        "description": "Collect a daily snapshot from the Lightspeed database. Returns a structured error result if the Lightspeed DB is unreachable.",
        "parameters": {
            "collector_type": {
                "type": "string",
                "required": True,
                "description": "Lightspeed collector type to run",
            },
            "collection_timestamp": {
                "type": "string",
                "description": "ISO timestamp for the collection (defaults to 23:00 of the previous day)",
            },
        },
        "examples": [
            {"name": "Lightspeed config snapshot", "data": {"collector_type": "lightspeed_config"}},
        ],
    },
}

# Explicit exports for better IDE support
__all__ = [
    # System tasks
    "hello_world",
    "cleanup_old_tasks",
    "cleanup_activitystream",
    "cleanup_metrics_data",
    "submit_task_to_dispatcher",
    "create_system_tasks",
    # Metrics collection (hourly, snapshot, and daily time-range)
    "collect_hourly_metrics",
    "collect_snapshot_metrics",
    "collect_daily_metrics",
    # Daily rollup and anonymization tasks
    "daily_metrics_rollup",
    "daily_anonymize_and_prepare",
    "send_anonymized_to_segment",
    # Configuration
    "TASK_FUNCTIONS",
    "TASK_LOCKS",
    "TASK_METADATA",
    "get_queue_for_function",
    # Dashboard reports
    "collect_dashboard_reports_data",
    "collect_dashboard_reports_initial_data",
    "cleanup_dashboard_reports_old_data",
    # Connectivity probes and opt-in source collectors
    "probe_db_connection",
    "collect_eda_snapshot_metrics",
    "collect_gateway_snapshot_metrics",
    "collect_lightspeed_snapshot_metrics",
]
