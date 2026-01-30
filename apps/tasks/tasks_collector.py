"""
Metrics collection and anonymized data collection tasks for metrics_service.

This module provides tasks for collecting metrics and anonymized data using
the metrics-utility library. These tasks integrate with AWX/Automation Controller
for data collection and analysis.

WORKFLOW:
=========

1. Hourly Collection (24 times/day)
   - Tasks: collect_job_host_summary_hourly, collect_host_metrics_hourly, collect_main_host_hourly
   - Process: Collect CSV → Convert to JSON → Store in HourlyMetricsCollection (NOT anonymized)
   - Purpose: Raw data storage for debugging/inspection

2. Daily Rollup (once/day)
   - Task: daily_metrics_rollup()
   - Process: Aggregate 24 hourly JSON collections → Create summary → Store in DailyMetricsSummary
   - Status: "aggregated" (data is NOT anonymized yet)
   - Purpose: Summarize full day of metrics for anonymization

3. Daily Anonymize (once/day)
   - Task: daily_anonymize_and_prepare()
   - Process: Fetch aggregated summary → Apply anonymize_rollup_data() → Store AnonymizedMetricsPayload
   - Anonymization: Uses anonymize_rollup_data() from metrics-utility library
   - Status: Payload set to "pending", daily summary set to "anonymized"
   - Purpose: Prepare anonymized data for Segment.com

4. Send to Segment (as needed for pending payloads)
   - Task: send_anonymized_to_segment()
   - Process: Fetch pending payloads → Send via StorageSegment → Update status to "sent"
   - Purpose: Transmit anonymized data to Segment.com

IMPORTANT: All anonymization is handled by metrics-utility library. No custom
anonymization logic should exist in this file.
"""

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from django.utils import timezone

from .utils import (
    create_task_result,
    csv_to_json,
    generate_salt,
    get_db_connection,
    log_task_execution,
    parse_datetime_string,
    send_to_segment,
    task,
    task_execution_wrapper,
)

logger = logging.getLogger(__name__)

# Constants for repeated strings
MSG_METRICS_UTILITY_NOT_AVAILABLE = "metrics-utility is not available"
MSG_SEGMENT_NOT_AVAILABLE = "segment_not_available"
UTC_OFFSET_SUFFIX = "+00:00"
DEFAULT_DB_NAME = "awx"
DEFAULT_COLLECTORS = ["anonymized_rollups", "config", "job_host_summary", "main_host", "main_jobevent"]

# Import metrics-utility collectors and anonymization functions
try:
    from metrics_utility.anonymized_rollups.anonymized_rollups import (
        anonymize_data as anonymize_rollup_data,
    )
    from metrics_utility.library.anonymize import (
        anonymized_rollups_processor,
        compute_anonymized_rollup_from_raw_data,
    )
    from metrics_utility.library.collectors.controller import (
        config,
        job_host_summary,
        main_host,
        main_jobevent,
    )

    METRICS_UTILITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"metrics-utility not available: {e}")
    METRICS_UTILITY_AVAILABLE = False

    # Provide fallback attributes for testing when metrics-utility is not available
    anonymize_rollup_data = None
    anonymized_rollups_processor = None
    compute_anonymized_rollup_from_raw_data = None
    config = None
    job_host_summary = None
    main_host = None
    main_jobevent = None


# =============================================================================
# Helper Functions
# =============================================================================


def _get_date_defaults(
    collector_name: str, since_dt: datetime | None, until_dt: datetime | None
) -> tuple[datetime | None, datetime | None]:
    """Get default date values for collectors that require them."""
    # For collectors that require date ranges, provide sensible defaults if none given
    collectors_needing_dates = {"job_host_summary", "main_jobevent", "anonymized_rollups"}

    if collector_name in collectors_needing_dates:
        if since_dt is None:
            since_dt = datetime.now(UTC) - timedelta(days=30)
        if until_dt is None:
            until_dt = datetime.now(UTC)

    return since_dt, until_dt


# =============================================================================
# Collector Helper Functions
# =============================================================================


def _run_anonymized_rollups(
    db_connection, salt: str, since_dt: datetime | None, until_dt: datetime | None
) -> dict[str, Any]:
    """Run the anonymized_rollups collector."""
    return anonymized_rollups_processor(
        db=db_connection,
        salt=salt,
        since=since_dt,
        until=until_dt,
        ship_path=None,
        save_rollups=False,
    )


def _run_config_collector(db_connection) -> dict[str, Any]:
    """Run the config collector."""
    collector_instance = config(db=db_connection)
    return collector_instance.gather()


def _run_job_host_summary_collector(
    db_connection, since_dt: datetime | None, until_dt: datetime | None
) -> dict[str, Any]:
    """Run the job_host_summary collector."""
    if since_dt is not None and until_dt is not None:
        collector_instance = job_host_summary(db=db_connection, since=since_dt, until=until_dt)
    else:
        collector_instance = job_host_summary(db=db_connection)
    return collector_instance.gather()


def _run_main_host_collector(db_connection) -> dict[str, Any]:
    """Run the main_host collector."""
    collector_instance = main_host(db=db_connection)
    return collector_instance.gather()


def _run_main_jobevent_collector(
    db_connection, since_dt: datetime | None, until_dt: datetime | None = None
) -> dict[str, Any]:
    """Run the main_jobevent collector."""
    # Ensure we have valid dates
    if since_dt is None:
        since_dt = datetime.now(UTC) - timedelta(days=30)
    if until_dt is None:
        until_dt = datetime.now(UTC)

    collector_instance = main_jobevent(db=db_connection, since=since_dt, until=until_dt)
    return collector_instance.gather()


def _run_single_collector(collector_name: str, db_connection, since: str, until: str, salt: str) -> dict[str, Any]:
    """Run a single collector and return its data."""
    since_dt = parse_datetime_string(since)
    until_dt = parse_datetime_string(until)
    since_dt, until_dt = _get_date_defaults(collector_name, since_dt, until_dt)

    collector_functions = {
        "anonymized_rollups": lambda: _run_anonymized_rollups(db_connection, salt, since_dt, until_dt),
        "config": lambda: _run_config_collector(db_connection),
        "job_host_summary": lambda: _run_job_host_summary_collector(db_connection, since_dt, until_dt),
        "main_host": lambda: _run_main_host_collector(db_connection),
        "main_jobevent": lambda: _run_main_jobevent_collector(db_connection, since_dt, until_dt),
    }

    collector_func = collector_functions.get(collector_name)
    if collector_func is None:
        raise ValueError(f"Unknown collector: {collector_name}")

    return collector_func()


def _run_single_collector_with_format(
    collector_name: str,
    db_connection,
    since: str,
    until: str,
    salt: str,
    output_format: str = "json",
) -> dict[str, Any]:
    """
    Run a single collector and return data in specified format.

    Args:
        collector_name: Name of the collector to run
        db_connection: Database connection
        since: Start date string (ISO format)
        until: End date string (ISO format)
        salt: Salt for anonymization
        output_format: 'json' (default) or 'csv'

    Returns:
        dict: Collected data in requested format
            JSON format: Converted JSON structure from CSV files
            CSV format: {'csv_files': [...paths...], 'file_count': N}
    """
    since_dt = parse_datetime_string(since)
    until_dt = parse_datetime_string(until)
    since_dt, until_dt = _get_date_defaults(collector_name, since_dt, until_dt)

    collector_functions = {
        "anonymized_rollups": lambda: _run_anonymized_rollups(db_connection, salt, since_dt, until_dt),
        "config": lambda: _run_config_collector(db_connection),
        "job_host_summary": lambda: _run_job_host_summary_collector(db_connection, since_dt, until_dt),
        "main_host": lambda: _run_main_host_collector(db_connection),
        "main_jobevent": lambda: _run_main_jobevent_collector(db_connection, since_dt, until_dt),
    }

    collector_func = collector_functions.get(collector_name)
    if collector_func is None:
        raise ValueError(f"Unknown collector: {collector_name}")

    # Collectors return CSV file paths
    csv_file_paths = collector_func()

    # Return based on output format
    if output_format == "csv":
        # Return raw CSV file paths without conversion
        csv_list = csv_file_paths if isinstance(csv_file_paths, list) else [csv_file_paths]
        return {"csv_files": csv_list, "file_count": len(csv_list)}
    else:  # 'json' (default)
        # Convert CSV to JSON
        return csv_to_json(csv_file_paths)


def _collect_all_metrics(collectors_list: list, db_connection, since: str, until: str, salt: str) -> dict[str, Any]:
    """Collect data from all specified collectors."""
    all_results = {}

    for collector_name in collectors_list:
        try:
            collector_data = _run_single_collector(collector_name, db_connection, since, until, salt)
            all_results[collector_name] = collector_data
            logger.info(f"Successfully collected data from {collector_name}")
        except ValueError:
            logger.warning(f"Unknown collector: {collector_name}")
            continue
        except Exception as e:
            logger.error(f"Error running collector {collector_name}: {str(e)}")
            all_results[collector_name] = {"error": str(e)}

    return all_results


def _prepare_segment_data(
    collectors_list: list, all_results: dict, db_name: str, since: str, until: str, salt: str
) -> dict[str, Any]:
    """Prepare anonymized data for Segment.com."""
    segment_data = {
        "collectors_run": collectors_list,
        "collection_summary": {
            "total_collectors": len(collectors_list),
            "successful_collectors": len([k for k, v in all_results.items() if "error" not in v]),
            "failed_collectors": len([k for k, v in all_results.items() if "error" in v]),
            "collection_parameters": {
                "database": db_name,
                "since": since,
                "until": until,
                "salt_used": bool(salt),
            },
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Add the actual anonymized collector results
    for collector_name, data in all_results.items():
        if "error" not in data:
            segment_data[collector_name] = data

    return segment_data


# =============================================================================
# Aggregation Helpers (for daily rollups)
# =============================================================================


def _aggregate_collector_data(collections: list) -> dict:
    """
    Aggregate metrics from hourly collections.

    This function merges the actual raw data from all hourly collections
    for use in daily rollup and anonymization.

    Args:
        collections: List of HourlyMetricsCollection objects

    Returns:
        dict: Aggregated metrics containing:
            - records: Merged list of all records from hourly collections
            - total_records: Total count of records
            - hourly_snapshots: Metadata about each hourly collection
    """
    aggregated = {
        "records": [],
        "total_records": 0,
        "hourly_snapshots": [],
    }

    for collection in collections:
        data = collection.raw_data

        # Extract records from the raw data
        # csv_to_json returns {"records": [...], "total_records": N, "file_count": N}
        if isinstance(data, dict):
            records = data.get("records", [])
            record_count = len(records) if records else data.get("total_records", 0)
            # Merge records into aggregated list
            if records:
                aggregated["records"].extend(records)
        elif isinstance(data, list):
            # If raw_data is already a list, use it directly
            records = data
            record_count = len(data)
            aggregated["records"].extend(records)
        else:
            record_count = 0

        aggregated["total_records"] += record_count
        aggregated["hourly_snapshots"].append(
            {
                "hour": collection.collection_timestamp.hour,
                "collection_id": collection.id,
                "record_count": record_count,
                "timestamp": collection.collection_timestamp.isoformat(),
            }
        )

    return aggregated


# =============================================================================
# Hourly Collection Helper
# =============================================================================


def _collect_hourly_metrics(
    collector_name: str,
    collector_func,
    task_name: str,
    uses_date_range: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """
    Generic helper for hourly metrics collection tasks.

    Args:
        collector_name: Name of the collector type (e.g., "job_host_summary")
        collector_func: The collector class/function to instantiate
        task_name: Name of the task for logging
        uses_date_range: Whether the collector accepts since/until parameters
        **kwargs: Task parameters

    Returns:
        dict: Task result with collection status
    """
    if not METRICS_UTILITY_AVAILABLE:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    from django.utils import timezone

    from apps.tasks.models import HourlyMetricsCollection

    # Determine collection hour (default to previous hour)
    hour_timestamp_str = kwargs.get("hour_timestamp")
    collection_hour = None
    if hour_timestamp_str:
        collection_hour = parse_datetime_string(hour_timestamp_str)
    # Fallback to previous hour if no timestamp provided or parsing failed
    if collection_hour is None:
        now = timezone.now()
        collection_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    log_task_execution(task_name, "processing", f"Collecting {collector_name} for hour: {collection_hour.isoformat()}")

    try:
        db_name = kwargs.get("database", DEFAULT_DB_NAME)
        db_connection = get_db_connection(db_name)

        # Build collector parameters
        if uses_date_range:
            since = collection_hour
            until = collection_hour + timedelta(hours=1)
            collector = collector_func(db=db_connection, since=since, until=until)
            collection_params = {
                "database": db_name,
                "since": since.isoformat(),
                "until": until.isoformat(),
            }
        else:
            collector = collector_func(db=db_connection)
            collection_params = {
                "database": db_name,
                "collection_time": collection_hour.isoformat(),
            }

        # Gather and convert data
        csv_file_paths = collector.gather()
        collected_data = csv_to_json(csv_file_paths)

        # Store in HourlyMetricsCollection
        # Use update_or_create to handle retries and scheduler double-triggers
        # The unique_together constraint on (collector_type, collection_timestamp)
        # would cause IntegrityError if we used create() and a record already exists
        hourly_collection, created = HourlyMetricsCollection.objects.update_or_create(
            collector_type=collector_name,
            collection_timestamp=collection_hour,
            defaults={
                "raw_data": collected_data,
                "status": "collected",
                "collection_parameters": collection_params,
                "task_execution_id": kwargs.get("execution_id"),
                "error_message": "",  # Clear any previous error
            },
        )

        action = "Created" if created else "Updated"
        log_task_execution(task_name, "completed", f"{action} hourly collection ID: {hourly_collection.id}")

        return create_task_result(
            "success",
            {
                "task_type": task_name,
                "collector_type": collector_name,
                "collection_id": hourly_collection.id,
                "collection_timestamp": collection_hour.isoformat(),
                "data_size_bytes": hourly_collection.data_size_bytes,
                "records_collected": collected_data.get("total_records", 0),
                "was_retry": not created,
            },
        )

    except Exception as e:
        logger.error(f"Error in {task_name}: {str(e)}")

        # Store failed collection
        # Use update_or_create to handle cases where a record already exists
        # (e.g., a previous attempt created a record, or scheduler double-trigger)
        with contextlib.suppress(Exception):
            HourlyMetricsCollection.objects.update_or_create(
                collector_type=collector_name,
                collection_timestamp=collection_hour,
                defaults={
                    "raw_data": {},
                    "status": "failed",
                    "error_message": str(e),
                    "collection_parameters": {"database": kwargs.get("database", DEFAULT_DB_NAME)},
                },
            )

        return create_task_result("error", error=f"Collection failed: {str(e)}")


# =============================================================================
# Task Functions
# =============================================================================


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("collect_single_collector")
def collect_single_collector(**kwargs) -> dict[str, Any]:
    """
    Unified task to collect data from a single collector with configurable output format.

    This task consolidates all individual collector tasks into one parameterized function.
    It can run any available collector and return data in either JSON or CSV format.

    Args:
        **kwargs: Task data containing collection parameters:
            - collector_type (str): Collector to run (required)
                Options: 'anonymized_rollups', 'config', 'job_host_summary', 'main_host', 'main_jobevent'
            - database (str): Database name from Django settings (default: 'awx')
            - since (str): Start date for collection (ISO format, optional)
            - until (str): End date for collection (ISO format, optional)
            - salt (str): Salt for anonymization (optional, auto-generated UUID4)
            - output_format (str): Output format - 'json' or 'csv' (default: 'json')
                'json' - Convert CSV to JSON (standard behavior)
                'csv' - Return CSV file paths without conversion

    Returns:
        dict: Task result with collected data
            When output_format='json': Returns {'status': 'success', 'collected_data': {...json...}}
            When output_format='csv': Returns {'status': 'success', 'csv_files': [...paths...], 'file_count': N}
    """
    # Validate required parameters first
    collector_type = kwargs.get("collector_type")
    if not collector_type:
        return create_task_result("error", error="collector_type parameter is required")

    # Check if metrics-utility is available
    if not METRICS_UTILITY_AVAILABLE:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    log_task_execution("collect_single_collector", "processing", f"Collecting metrics using {collector_type} collector")

    try:
        db_name = kwargs.get("database", DEFAULT_DB_NAME)
        since = kwargs.get("since")
        until = kwargs.get("until")
        salt = kwargs.get("salt", generate_salt())
        output_format = kwargs.get("output_format", "json")

        # Validate output_format
        if output_format not in ["json", "csv"]:
            return create_task_result("error", error=f"Invalid output_format: {output_format}. Must be 'json' or 'csv'")

        # Get database connection
        db_connection = get_db_connection(db_name)

        # Run collector with specified output format
        collected_data = _run_single_collector_with_format(
            collector_type, db_connection, since, until, salt, output_format
        )

        # Build result based on output format
        if output_format == "csv":
            result_data = {
                "task_type": "collect_single_collector",
                "collector_type": collector_type,
                "csv_files": collected_data.get("csv_files", []),
                "file_count": collected_data.get("file_count", 0),
                "output_format": "csv",
                "parameters_used": {
                    "database": db_name,
                    "since": since,
                    "until": until,
                    "salt": salt,
                    "output_format": output_format,
                },
            }
        else:  # 'json'
            result_data = {
                "task_type": "collect_single_collector",
                "collector_type": collector_type,
                "collected_data": collected_data,
                "output_format": "json",
                "parameters_used": {
                    "database": db_name,
                    "since": since,
                    "until": until,
                    "salt": salt,
                    "output_format": output_format,
                },
            }

        return create_task_result("success", result_data)

    except ValueError as e:
        # Handle unknown collector type
        logger.error(f"Invalid collector_type in collect_single_collector: {str(e)}")
        return create_task_result("error", error=str(e))
    except Exception as e:
        logger.error(f"Error in collect_single_collector: {str(e)}")
        return create_task_result("error", error=f"Collection failed: {str(e)}")


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("full_process")
def full_process(**kwargs) -> dict[str, Any]:
    """
    Collect, anonymize, and send metrics data to Segment.com.

    Args:
        **kwargs: Task data containing collection and sending parameters:
            - database (str): Database name from Django settings (default: 'awx')
            - since (str): Start date for collection (optional)
            - until (str): End date for collection (optional)
            - salt (str): Salt for anonymization (optional, auto-generated UUID4)
            - user_id (str): User ID for Segment tracking (optional)
            - event_name (str): Event name for Segment tracking (default: 'metrics_collected')
            - collectors (list): List of specific collectors to run (optional)
            - send_to_segment_option (bool): Whether to send data to Segment (default: True)

    Returns:
        dict: Task result with collection, anonymization, and sending status
    """
    if not METRICS_UTILITY_AVAILABLE:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    log_task_execution("full_process", "processing", "Starting full metrics collection and Segment.com upload")

    try:
        db_name = kwargs.get("database", DEFAULT_DB_NAME)
        db_connection = get_db_connection(db_name)
        since = kwargs.get("since")
        until = kwargs.get("until")
        salt = kwargs.get("salt", generate_salt())
        user_id = kwargs.get("user_id", generate_salt())
        event_name = kwargs.get("event_name", "metrics_collected")
        collectors_list = kwargs.get("collectors", ["anonymized_rollups", "config", "job_host_summary"])
        send_to_segment_option = kwargs.get("send_to_segment_option", True)

        # Step 1: Collect metrics
        log_task_execution("full_process", "processing", "Collecting metrics data")
        all_results = _collect_all_metrics(collectors_list, db_connection, since, until, salt)

        # Step 2: Prepare anonymized data
        log_task_execution("full_process", "processing", "Preparing anonymized data for Segment.com")
        segment_data = _prepare_segment_data(collectors_list, all_results, db_name, since, until, salt)

        # Step 3: Send to Segment.com if enabled
        segment_status = "skipped"
        if send_to_segment_option:
            segment_status = send_to_segment(user_id, event_name, segment_data)

        return create_task_result(
            "success",
            {
                "task_type": "full_process",
                "collection_results": {
                    "segment_data": segment_data,
                    "collectors_run": collectors_list,
                    "successful_collections": len([k for k, v in all_results.items() if "error" not in v]),
                    "failed_collections": len([k for k, v in all_results.items() if "error" in v]),
                    "collection_errors": {k: v.get("error") for k, v in all_results.items() if "error" in v},
                },
                "anonymization_status": "completed",
                "segment_status": segment_status,
                "parameters_used": {
                    "database": db_name,
                    "since": since,
                    "until": until,
                    "salt": salt,
                    "collectors": collectors_list,
                    "send_to_segment": send_to_segment,
                    "event_name": event_name,
                    "user_id": user_id,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error in full_process: {str(e)}")
        return create_task_result("error", error=f"Full process failed: {str(e)}")


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("collect_metrics")
def collect_metrics(**kwargs) -> dict[str, Any]:
    """
    Unified task to collect metrics from multiple collectors.

    This task merges functionality from the former collect_all_metrics and collect_metrics tasks,
    providing a single entry point for multi-collector metrics collection.

    Args:
        **kwargs: Task data containing collection parameters:
            - database (str): Database name from Django settings (default: 'awx')
            - since (str): Start date for collection (ISO format, optional)
            - until (str): End date for collection (ISO format, optional)
            - salt (str): Salt for anonymization (default: 'default-salt')
            - collectors (list): List of specific collectors to run
                (default: DEFAULT_COLLECTORS = all available collectors)
                Options: ['anonymized_rollups', 'config', 'job_host_summary', 'main_host', 'main_jobevent']

    Returns:
        dict: Task result with collected metrics data from all collectors
    """
    if not METRICS_UTILITY_AVAILABLE:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    log_task_execution("collect_metrics", "processing", "Collecting metrics from multiple collectors")

    try:
        db_name = kwargs.get("database", DEFAULT_DB_NAME)
        db_connection = get_db_connection(db_name)
        since = kwargs.get("since")
        until = kwargs.get("until")
        salt = kwargs.get("salt", "default-salt")  # Added from collect_all_metrics
        collectors_list = kwargs.get("collectors", DEFAULT_COLLECTORS)  # From collect_metrics

        # Use shared helper function to collect from all specified collectors
        all_results = _collect_all_metrics(collectors_list, db_connection, since, until, salt)

        return create_task_result(
            "success",
            {
                "task_type": "collect_metrics",
                "collection_results": {
                    "collectors_run": collectors_list,
                    "successful_collections": len([k for k, v in all_results.items() if "error" not in v]),
                    "failed_collections": len([k for k, v in all_results.items() if "error" in v]),
                    "collection_errors": {k: v.get("error") for k, v in all_results.items() if "error" in v},
                    "collected_data": all_results,
                },
                "parameters_used": {
                    "database": db_name,
                    "since": since,
                    "until": until,
                    "salt": salt,  # Now included in parameters
                    "collectors": collectors_list,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error in collect_metrics: {str(e)}")
        return create_task_result("error", error=f"Metrics collection failed: {str(e)}")


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("anonymize_data")
def anonymize_data(**kwargs) -> dict[str, Any]:
    """
    Dedicated task to anonymize collected metrics data.

    Args:
        **kwargs: Task data containing anonymization parameters:
            - data (dict): Raw metrics data to anonymize (required)
            - salt (str): Salt for anonymization (auto-generated UUID4 if not provided)

    Returns:
        dict: Task result with anonymized data
    """
    if not METRICS_UTILITY_AVAILABLE:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    log_task_execution("anonymize_data", "processing", "Anonymizing collected metrics data")

    try:
        raw_data = kwargs.get("data")
        if not raw_data:
            return create_task_result("error", error="No data provided for anonymization")

        salt = kwargs.get("salt", generate_salt())
        output_format = kwargs.get("output_format", "segment_ready")

        anonymized_data = _prepare_segment_data(
            raw_data.get("collectors_run", []),
            raw_data.get("collected_data", {}),
            raw_data.get("database", "unknown"),
            raw_data.get("since"),
            raw_data.get("until"),
            salt,
        )

        return create_task_result(
            "success",
            {
                "task_type": "anonymize_data",
                "anonymized_data": anonymized_data,
                "anonymization_status": "completed",
                "parameters_used": {
                    "salt": salt,
                    "output_format": output_format,
                    "input_data_size": len(str(raw_data)),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error in anonymize_data: {str(e)}")
        return create_task_result("error", error=f"Anonymization failed: {str(e)}")


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("full_process_anonymize")
def full_process_anonymize(**kwargs) -> dict[str, Any]:
    """
    Collect anonymized metrics and send directly to Segment.com.

    Args:
        **kwargs: Task data containing collection and sending parameters:
            - database (str): Database name from Django settings (default: 'awx')
            - since (str): Start date for collection (optional)
            - until (str): End date for collection (optional)
            - salt (str): Salt for anonymization (optional, auto-generated UUID4)
            - user_id (str): User ID for Segment tracking (default: 'anonymous-user')
            - event_name (str): Event name for Segment (default: 'anonymized_metrics_collected')
            - send_to_segment (bool): Whether to send data to Segment (default: True)

    Returns:
        dict: Task result with collection and transmission status
    """
    if not METRICS_UTILITY_AVAILABLE:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    log_task_execution(
        "full_process_anonymize", "processing", "Starting anonymized metrics collection and Segment.com upload"
    )

    try:
        db_name = kwargs.get("database", DEFAULT_DB_NAME)
        db_connection = get_db_connection(db_name)
        since = kwargs.get("since")
        until = kwargs.get("until")
        salt = kwargs.get("salt", generate_salt())
        user_id = kwargs.get("user_id", "anonymous-user")
        event_name = kwargs.get("event_name", "anonymized_metrics_collected")
        should_send_to_segment = kwargs.get("send_to_segment", True)

        # Parse and apply defaults for dates
        since_dt = parse_datetime_string(since)
        until_dt = parse_datetime_string(until)
        since_dt, until_dt = _get_date_defaults("anonymized_rollups", since_dt, until_dt)

        # Step 1: Collect anonymized metrics
        log_task_execution("full_process_anonymize", "processing", "Collecting anonymized metrics data")
        anonymized_data = anonymized_rollups_processor(
            db=db_connection,
            salt=salt,
            since=since_dt,
            until=until_dt,
            ship_path=None,
            save_rollups=False,
        )

        # Step 2: Send to Segment.com if enabled
        segment_status = "skipped"
        if should_send_to_segment:
            segment_data = {
                "anonymized_rollups": anonymized_data,
                "collection_metadata": {
                    "database": db_name,
                    "since": since,
                    "until": until,
                    "salt": salt,
                    "collection_timestamp": datetime.now(UTC).isoformat(),
                },
            }
            segment_status = send_to_segment(user_id, event_name, segment_data)

        return create_task_result(
            "success",
            {
                "task_type": "full_process_anonymize",
                "collection_status": "completed",
                "anonymized_data_size": len(str(anonymized_data)),
                "segment_status": segment_status,
                "parameters_used": {
                    "database": db_name,
                    "since": since,
                    "until": until,
                    "salt": salt,
                    "send_to_segment": should_send_to_segment,
                    "event_name": event_name,
                    "user_id": user_id,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error in full_process_anonymize: {str(e)}")
        return create_task_result("error", error=f"Anonymized process failed: {str(e)}")


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("send_to_segment_task")
def send_to_segment_task(**kwargs) -> dict[str, Any]:
    """
    Dedicated task to send anonymized data to Segment.com.

    Args:
        **kwargs: Task data containing transmission parameters:
            - data (dict): Anonymized data to send (required)
            - user_id (str): User ID for tracking (default: 'anonymous-user')
            - event_name (str): Event name (default: 'metrics_sent')

    Returns:
        dict: Task result with transmission status
    """
    log_task_execution("send_to_segment_task", "processing", "Sending anonymized data to Segment.com")

    try:
        anonymized_data = kwargs.get("data")
        if not anonymized_data:
            return create_task_result("error", error="No data provided for transmission")

        user_id = kwargs.get("user_id", "anonymous-user")
        event_name = kwargs.get("event_name", "metrics_sent")

        segment_status = send_to_segment(user_id, event_name, anonymized_data)

        return create_task_result(
            "success",
            {
                "task_type": "send_to_segment_task",
                "segment_status": segment_status,
                "transmission_completed": segment_status == "success",
                "parameters_used": {
                    "user_id": user_id,
                    "event_name": event_name,
                    "data_size": len(str(anonymized_data)),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error in send_to_segment_task: {str(e)}")
        return create_task_result("error", error=f"Segment transmission failed: {str(e)}")


# =============================================================================
# Hourly Collection Tasks
# =============================================================================


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("collect_job_host_summary_hourly")
def collect_job_host_summary_hourly(**kwargs) -> dict[str, Any]:
    """
    Collect job host summary metrics hourly and store in HourlyMetricsCollection.

    Args:
        **kwargs: Task data containing:
            - hour_timestamp (str): ISO timestamp for the hour to collect (optional)
            - database (str): Database name (default: 'awx')

    Returns:
        dict: Task result with collection status and record ID
    """
    return _collect_hourly_metrics(
        collector_name="job_host_summary",
        collector_func=job_host_summary,
        task_name="collect_job_host_summary_hourly",
        uses_date_range=True,
        **kwargs,
    )


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("collect_host_metrics_hourly")
def collect_host_metrics_hourly(**kwargs) -> dict[str, Any]:
    """
    Collect host metrics (main_jobevent) hourly and store in HourlyMetricsCollection.

    Args:
        **kwargs: Task data containing:
            - hour_timestamp (str): ISO timestamp for the hour to collect (optional)
            - database (str): Database name (default: 'awx')

    Returns:
        dict: Task result with collection status and record ID
    """
    return _collect_hourly_metrics(
        collector_name="main_jobevent",
        collector_func=main_jobevent,
        task_name="collect_host_metrics_hourly",
        uses_date_range=True,
        **kwargs,
    )


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("collect_main_host_hourly")
def collect_main_host_hourly(**kwargs) -> dict[str, Any]:
    """
    Collect main_host metrics hourly and store in HourlyMetricsCollection.

    Args:
        **kwargs: Task data containing:
            - hour_timestamp (str): ISO timestamp for the hour to collect (optional)
            - database (str): Database name (default: 'awx')

    Returns:
        dict: Task result with collection status and record ID
    """
    return _collect_hourly_metrics(
        collector_name="main_host",
        collector_func=main_host,
        task_name="collect_main_host_hourly",
        uses_date_range=False,
        **kwargs,
    )


# =============================================================================
# Daily Rollup Task
# =============================================================================


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("daily_metrics_rollup")
def daily_metrics_rollup(**kwargs) -> dict[str, Any]:
    """
    Create daily summary from hourly collections.

    This task:
    1. Queries all hourly collections for the previous day
    2. Aggregates metrics (sums, averages, counts)
    3. Stores references to all 24 hourly snapshots
    4. Collects config data (once per day)
    5. Creates DailyMetricsSummary record

    Args:
        **kwargs: Task data containing:
            - summary_date (str): Date to summarize (YYYY-MM-DD, defaults to yesterday)
            - database (str): Database name (default: 'awx')

    Returns:
        dict: Task result with summary ID and statistics
    """
    from datetime import date

    from django.utils import timezone

    from apps.tasks.models import DailyMetricsSummary, HourlyMetricsCollection

    # Determine summary date (default to yesterday)
    summary_date_str = kwargs.get("summary_date")
    if summary_date_str:
        summary_date = date.fromisoformat(summary_date_str)
    else:
        summary_date = timezone.now().date() - timedelta(days=1)

    log_task_execution("daily_metrics_rollup", "processing", f"Creating daily summary for: {summary_date}")

    try:
        # Query all hourly collections for this date
        start_datetime = timezone.make_aware(datetime.combine(summary_date, datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)

        hourly_collections = HourlyMetricsCollection.objects.filter(
            collection_timestamp__gte=start_datetime, collection_timestamp__lt=end_datetime, status="collected"
        ).order_by("collector_type", "collection_timestamp")

        # Group by collector type
        collections_by_type: dict[str, list] = {}
        for collection in hourly_collections:
            if collection.collector_type not in collections_by_type:
                collections_by_type[collection.collector_type] = []
            collections_by_type[collection.collector_type].append(collection)

        # Build hourly collection IDs map
        hourly_collection_ids = {
            collector_type: [c.id for c in collections] for collector_type, collections in collections_by_type.items()
        }

        # Aggregate metrics for each collector type
        aggregated_metrics = {}
        missing_hours = []
        collector_types = ["job_host_summary", "main_host", "main_jobevent"]

        for collector_type in collector_types:
            collections = collections_by_type.get(collector_type, [])

            # Check for missing hours (should have 24 collections)
            if len(collections) < 24:
                collected_hours = {c.collection_timestamp.hour for c in collections}
                missing_hours.extend([f"{collector_type}:{hour}" for hour in range(24) if hour not in collected_hours])

            # Use the generic aggregator
            aggregated_metrics[collector_type] = _aggregate_collector_data(collections)

        # Collect config data (once per day)
        config_data = {}
        if METRICS_UTILITY_AVAILABLE:
            try:
                db_name = kwargs.get("database", DEFAULT_DB_NAME)
                db_connection = get_db_connection(db_name)
                config_collector = config(db=db_connection)
                config_data = config_collector.gather()
            except Exception as e:
                logger.error(f"Failed to collect config data: {str(e)}")
                config_data = {"error": str(e)}

        # Calculate count from the IDs we actually processed (not from a new query)
        # This avoids a race condition where new records could be inserted between
        # iteration and count/update, causing incorrect counts and marking unprocessed
        # records as "processed"
        all_processed_ids = []
        for ids_list in hourly_collection_ids.values():
            all_processed_ids.extend(ids_list)
        hourly_collections_count = len(all_processed_ids)

        # Create or update DailyMetricsSummary
        # Use update_or_create to handle retries and scheduler double-triggers gracefully
        # The unique constraint on summary_date would cause IntegrityError if we used
        # create() and a record already exists for this date
        daily_summary, created = DailyMetricsSummary.objects.update_or_create(
            summary_date=summary_date,
            defaults={
                "aggregated_metrics": aggregated_metrics,
                "hourly_collection_ids": hourly_collection_ids,
                "config_data": config_data,
                "status": "aggregated",
                "hourly_collections_count": hourly_collections_count,
                "missing_hours": missing_hours,
                "aggregation_completed_at": timezone.now(),
                "rollup_task_execution_id": kwargs.get("execution_id"),
                "error_message": "",  # Clear any previous error
            },
        )

        # Mark only the hourly collections we actually processed as "processed"
        # Uses the collected IDs to avoid race condition with newly inserted records
        HourlyMetricsCollection.objects.filter(id__in=all_processed_ids).update(status="processed")

        action = "Created" if created else "Updated"
        log_task_execution(
            "daily_metrics_rollup",
            "completed",
            f"{action} daily summary ID: {daily_summary.id} with {hourly_collections_count} hourly collections",
        )

        return create_task_result(
            "success",
            {
                "task_type": "daily_metrics_rollup",
                "summary_id": daily_summary.id,
                "summary_date": str(summary_date),
                "hourly_collections_count": hourly_collections_count,
                "missing_hours": missing_hours,
                "aggregated_collectors": list(aggregated_metrics.keys()),
                "created": created,  # True if new record, False if updated existing
            },
        )

    except Exception as e:
        logger.error(f"Error in daily_metrics_rollup: {str(e)}")
        return create_task_result("error", error=f"Rollup failed: {str(e)}")


# =============================================================================
# Anonymization and Sending Tasks - Helper Functions
# =============================================================================


def _get_payloads_to_send(payload_id: int | None, max_payloads: int, stale_threshold) -> list:
    """
    Get anonymized payloads ready to send.

    Args:
        payload_id: Specific payload ID to send (optional)
        max_payloads: Maximum number of payloads to retrieve
        stale_threshold: Datetime threshold for stale "sending" status

    Returns:
        QuerySet of AnonymizedMetricsPayload objects
    """
    from django.db.models import Q

    from apps.tasks.models import AnonymizedMetricsPayload

    if payload_id:
        return AnonymizedMetricsPayload.objects.filter(
            Q(id=payload_id) & (Q(status__in=["pending", "retry"]) | Q(status="sending", modified__lt=stale_threshold))
        )
    return AnonymizedMetricsPayload.objects.filter(
        Q(status__in=["pending", "retry"]) | Q(status="sending", modified__lt=stale_threshold)
    ).order_by("created")[:max_payloads]


def _handle_successful_send(payload, results: dict) -> None:
    """
    Handle successful payload send to Segment.

    Args:
        payload: AnonymizedMetricsPayload object
        results: Results dictionary to update
    """
    from django.utils import timezone

    payload.status = "sent"
    payload.sent_at = timezone.now()
    payload.error_message = ""
    payload.save()
    results["sent"] += 1

    # Update daily summary status separately (don't let this failure affect payload)
    try:
        if payload.daily_summary:
            payload.daily_summary.status = "sent"
            payload.daily_summary.save()
    except Exception as summary_error:
        logger.warning(f"Failed to update daily_summary for payload {payload.id}: {summary_error}")


def _handle_failed_send(payload, segment_status: str, results: dict) -> None:
    """
    Handle failed payload send to Segment.

    Args:
        payload: AnonymizedMetricsPayload object
        segment_status: Status returned from send_to_segment
        results: Results dictionary to update
    """
    payload.status = "retry"
    payload.retry_count += 1
    payload.error_message = f"Send failed: {segment_status}"
    payload.save()
    results["failed"] += 1


def _process_single_payload(payload, results: dict) -> None:
    """
    Process a single payload for sending to Segment.

    Args:
        payload: AnonymizedMetricsPayload object
        results: Results dictionary to update
    """
    # Track if this was a recovered stale payload
    was_stale = payload.status == "sending"
    if was_stale:
        results["recovered"] += 1
        logger.info(f"Recovering stale payload {payload.id} (stuck in 'sending' status)")

    # Check retry limit (for retry status or recovered stale payloads)
    if payload.status == "retry" and not payload.can_retry():
        payload.status = "failed"
        payload.error_message = "Max retries exceeded"
        payload.save()
        results["skipped"] += 1
        return

    # Update status to sending
    payload.status = "sending"
    payload.save()

    try:
        segment_status = send_to_segment(
            user_id=payload.segment_user_id,
            event_name=payload.segment_event_name,
            segment_data=payload.anonymized_data,
        )

        if segment_status == "success":
            _handle_successful_send(payload, results)
        else:
            _handle_failed_send(payload, segment_status, results)

    except Exception as e:
        logger.error(f"Error sending payload {payload.id}: {str(e)}")
        payload.status = "retry"
        payload.retry_count += 1
        payload.error_message = str(e)
        payload.save()
        results["failed"] += 1


# =============================================================================
# Anonymization and Sending Tasks
# =============================================================================


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("daily_anonymize_and_prepare")
def daily_anonymize_and_prepare(**kwargs) -> dict[str, Any]:
    """
    Anonymize daily summary and prepare payload for Segment.

    This task:
    1. Fetches DailyMetricsSummary (with aggregated, non-anonymized data)
    2. Applies anonymization using anonymize_rollup_data() from metrics-utility
    3. Creates AnonymizedMetricsPayload record
    4. Does NOT send (separate task handles sending)

    Args:
        **kwargs: Task data containing:
            - summary_date (str): Date to anonymize (YYYY-MM-DD, defaults to yesterday)
            - salt (str): Anonymization salt (auto-generated if not provided)

    Returns:
        dict: Task result with payload ID
    """
    from datetime import date

    from django.utils import timezone

    from apps.tasks.models import AnonymizedMetricsPayload, DailyMetricsSummary

    if not METRICS_UTILITY_AVAILABLE or anonymize_rollup_data is None:
        return create_task_result("error", error=MSG_METRICS_UTILITY_NOT_AVAILABLE)

    # Determine summary date
    summary_date_str = kwargs.get("summary_date")
    if summary_date_str:
        summary_date = date.fromisoformat(summary_date_str)
    else:
        summary_date = timezone.now().date() - timedelta(days=1)

    log_task_execution("daily_anonymize_and_prepare", "processing", f"Anonymizing daily summary for: {summary_date}")

    try:
        from django.db import transaction

        # Get daily summary (aggregated but not anonymized)
        daily_summary = DailyMetricsSummary.objects.get(summary_date=summary_date, status="aggregated")

        # Generate or use provided salt
        salt = kwargs.get("salt", generate_salt())

        # Prepare data structure for anonymization
        # anonymize_rollup_data expects a flattened structure with specific keys
        # Extract records from aggregated_metrics (each collector type has {"records": [...], ...})
        def extract_records(data: dict | list, default=None) -> list | dict:
            """Extract records from aggregated collector data structure."""
            if default is None:
                default = []
            if isinstance(data, dict):
                # New structure: {"records": [...], "total_records": N, "hourly_snapshots": [...]}
                return data.get("records", default)
            elif isinstance(data, list):
                # Legacy structure: direct list of records
                return data
            return default

        data_to_anonymize = {
            "job_host_summary": extract_records(daily_summary.aggregated_metrics.get("job_host_summary", {}), []),
            "jobs_by_template": extract_records(daily_summary.aggregated_metrics.get("jobs_by_template", {}), []),
            "module_stats": extract_records(daily_summary.aggregated_metrics.get("module_stats", {}), []),
            "collection_name_stats": extract_records(
                daily_summary.aggregated_metrics.get("collection_name_stats", {}), []
            ),
            "modules_used_per_playbook": extract_records(
                daily_summary.aggregated_metrics.get("modules_used_per_playbook", {}), []
            ),
            "main_jobevent": extract_records(daily_summary.aggregated_metrics.get("main_jobevent", {}), {}),
            "main_host": extract_records(daily_summary.aggregated_metrics.get("main_host", {}), {}),
        }

        # Apply anonymization using metrics-utility (modifies in-place)
        anonymize_rollup_data(data_to_anonymize, salt)

        # Add config and metadata
        anonymized_data = data_to_anonymize.copy()
        anonymized_data["config"] = daily_summary.config_data

        aggregation_timestamp = (
            daily_summary.aggregation_completed_at.isoformat() if daily_summary.aggregation_completed_at else None
        )
        anonymized_data["summary_metadata"] = {
            "summary_date": str(summary_date),
            "hourly_collections_count": daily_summary.hourly_collections_count,
            "missing_hours": daily_summary.missing_hours,
            "aggregation_timestamp": aggregation_timestamp,
        }

        # Use atomic transaction to prevent duplicate payloads
        with transaction.atomic():
            # Create AnonymizedMetricsPayload
            todays_date = datetime.now(UTC).date().isoformat()
            event_name = f"Controller Metrics Anonymized Daily {todays_date}"
            payload = AnonymizedMetricsPayload.objects.create(
                summary_date=summary_date,
                anonymized_data=anonymized_data,
                status="pending",
                daily_summary=daily_summary,
                anonymization_task_execution_id=kwargs.get("execution_id"),
                segment_event_name=kwargs.get("event_name", event_name),
                segment_user_id=kwargs.get("user_id", generate_salt()),
            )

            # Update daily summary status
            daily_summary.status = "anonymized"
            daily_summary.save()

        log_task_execution("daily_anonymize_and_prepare", "completed", f"Created anonymized payload ID: {payload.id}")

        return create_task_result(
            "success",
            {
                "task_type": "daily_anonymize_and_prepare",
                "payload_id": payload.id,
                "summary_date": str(summary_date),
                "payload_size_bytes": payload.payload_size_bytes,
            },
        )

    except DailyMetricsSummary.DoesNotExist:
        error_msg = f"No daily summary found for {summary_date} with status=aggregated"
        logger.error(error_msg)
        return create_task_result("error", error=error_msg)

    except Exception as e:
        logger.error(f"Error in daily_anonymize_and_prepare: {str(e)}")
        return create_task_result("error", error=f"Anonymization failed: {str(e)}")


@task(queue="metrics_collectors", decorate=False)
@task_execution_wrapper("send_anonymized_to_segment")
def send_anonymized_to_segment(**kwargs) -> dict[str, Any]:
    """
    Send anonymized payload to Segment.

    This task:
    1. Fetches AnonymizedMetricsPayload records with status=pending/retry
    2. Recovers stale "sending" payloads (stuck for > 10 minutes)
    3. Sends to Segment using send_to_segment helper
    4. Updates payload status based on result
    5. Handles retries for failed sends

    Args:
        **kwargs: Task data containing:
            - payload_id (int): Specific payload ID to send (optional)
            - max_payloads (int): Maximum number of payloads to send (default: 5)
            - stale_minutes (int): Minutes before "sending" status is considered stale (default: 10)

    Returns:
        dict: Task result with send statistics
    """
    from django.utils import timezone

    max_payloads = kwargs.get("max_payloads", 5)
    payload_id = kwargs.get("payload_id")
    stale_minutes = kwargs.get("stale_minutes", 10)

    log_task_execution("send_anonymized_to_segment", "processing", "Sending anonymized payloads to Segment")

    try:
        # Threshold for stale "sending" payloads (process crashed before completion)
        stale_threshold = timezone.now() - timedelta(minutes=stale_minutes)

        # Get payloads to send
        payloads = _get_payloads_to_send(payload_id, max_payloads, stale_threshold)

        # Initialize results
        results = {"sent": 0, "failed": 0, "skipped": 0, "recovered": 0}

        # Process each payload
        for payload in payloads:
            _process_single_payload(payload, results)

        log_task_execution(
            "send_anonymized_to_segment",
            "completed",
            f"Sent: {results['sent']}, Failed: {results['failed']}, "
            f"Skipped: {results['skipped']}, Recovered: {results['recovered']}",
        )

        return create_task_result(
            "success",
            {
                "task_type": "send_anonymized_to_segment",
                "results": results,
                "total_processed": sum(results.values()),
            },
        )

    except Exception as e:
        logger.error(f"Error in send_anonymized_to_segment: {str(e)}")
        return create_task_result("error", error=f"Send task failed: {str(e)}")


# NOTE: collect_dashboard_reports has been moved to apps.dashboard_reports.tasks
# It is imported in apps.tasks.tasks for backward compatibility
