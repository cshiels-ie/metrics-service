# test_tasks.py - Unit tests for dashboard_reports tasks

import contextlib
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.dashboard_reports.models import JobData
from apps.dashboard_reports.tasks import (
    _collect_data,
    _collect_jobs,
    _get_job_id_range,
    _parse_dt,
    _process_batches,
    _resolve_collection_params,
    _sync_jobs_atomically,
    cleanup_dashboard_reports_old_data,
    collect_dashboard_reports_data,
    collect_dashboard_reports_initial_data,
    sync_dashboard_host_summaries,
    sync_dashboard_job_records,
)


@pytest.mark.unit
class TestParseDt:
    """Tests for _parse_dt helper function."""

    def test_returns_tz_aware_datetime_unchanged(self):
        """_parse_dt returns a tz-aware datetime as the same object."""
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        assert _parse_dt(dt) is dt

    def test_normalizes_naive_datetime_to_utc(self):
        """_parse_dt attaches UTC to a naive datetime."""
        dt = datetime(2024, 1, 15, 12, 0)
        result = _parse_dt(dt)
        assert result == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

    def test_parses_iso_string(self):
        """_parse_dt converts an ISO-format string to a datetime."""
        result = _parse_dt("2024-01-15T12:00:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_returns_none_unchanged(self):
        """_parse_dt returns None when given None."""
        assert _parse_dt(None) is None

    def test_raises_for_unsupported_types(self):
        """_parse_dt raises TypeError for non-str, non-datetime, non-None values."""
        with pytest.raises(TypeError, match="_parse_dt"):
            _parse_dt(42)


@pytest.mark.unit
class TestSyncJobsAtomically:
    """Tests for _sync_jobs_atomically helper (DB-free via mocking)."""

    @patch("apps.dashboard_reports.tasks.transaction.atomic")
    @patch("apps.dashboard_reports.tasks.JobData.create_or_update_from_awx")
    def test_all_jobs_succeed(self, mock_create, mock_atomic):
        """_sync_jobs_atomically returns empty list when all jobs sync successfully."""
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_create.return_value = None
        failed = _sync_jobs_atomically([{"id": 1}, {"id": 2}])
        assert failed == []

    @patch("apps.dashboard_reports.tasks.transaction.atomic")
    @patch("apps.dashboard_reports.tasks.JobData.create_or_update_from_awx")
    def test_partial_failure_returns_failed_ids(self, mock_create, mock_atomic):
        """_sync_jobs_atomically collects failed job IDs and rolls back."""
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_create.side_effect = Exception("db error")
        failed = _sync_jobs_atomically([{"id": 10}, {"id": 11}])
        assert set(failed) == {10, 11}

    @patch("apps.dashboard_reports.tasks.transaction.atomic")
    def test_empty_jobs_list_returns_empty(self, mock_atomic):
        """_sync_jobs_atomically returns empty list with no jobs."""
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        failed = _sync_jobs_atomically([])
        assert failed == []


# --- Fixtures ---
@pytest.fixture
def mock_collect_data():
    """Patch _collect_data for dashboard_reports tasks."""
    with patch("apps.dashboard_reports.tasks._collect_data") as mock:
        yield mock


@pytest.fixture
def mock_create_task_result():
    """Patch create_task_result for dashboard_reports tasks."""
    with patch("apps.dashboard_reports.tasks.create_task_result") as mock:
        yield mock


@pytest.fixture
def mock_collect_data_deps():
    """Patch the internal helpers called by _collect_data."""
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = datetime(2024, 2, 1, tzinfo=UTC)
    with (
        patch("apps.dashboard_reports.tasks._resolve_collection_params") as mock_params,
        patch("apps.dashboard_reports.tasks.get_db_connection") as mock_db_conn,
        patch("apps.dashboard_reports.tasks._get_job_id_range") as mock_id_range,
        patch("apps.dashboard_reports.tasks._process_batches") as mock_batches,
        patch("apps.dashboard_reports.tasks.log_task_execution") as mock_log,
    ):
        mock_params.return_value = ("awx", since, until, 5000)
        mock_db_conn.return_value = MagicMock()
        mock_id_range.return_value = (100, 200)
        mock_batches.return_value = (42, None)
        yield mock_params, mock_db_conn, mock_id_range, mock_batches, mock_log, since, until


@pytest.mark.unit
class TestCollectJobs:
    """Tests for the _collect_jobs helper."""

    @patch("apps.dashboard_reports.tasks.dashboard_jobs")
    def test_passes_all_args_to_dashboard_jobs(self, mock_dashboard_jobs):
        """_collect_jobs forwards all keyword args including pagination params."""
        db_connection = MagicMock()
        since = datetime(2024, 1, 1, tzinfo=UTC)
        until = datetime(2024, 2, 1, tzinfo=UTC)
        expected_result = MagicMock()
        mock_dashboard_jobs.return_value.gather.return_value = expected_result

        result = _collect_jobs(db_connection, since, until, after_id=50, batch_size=100)

        mock_dashboard_jobs.assert_called_once_with(
            db=db_connection, since=since, until=until, after_id=50, batch_size=100, date_field="finished"
        )
        mock_dashboard_jobs.return_value.gather.assert_called_once()
        assert result == expected_result

    @patch("apps.dashboard_reports.tasks.dashboard_jobs")
    def test_defaults_pagination_params_to_none(self, mock_dashboard_jobs):
        """_collect_jobs defaults after_id and batch_size to None."""
        db_connection = MagicMock()
        since = datetime(2024, 1, 1, tzinfo=UTC)
        until = datetime(2024, 2, 1, tzinfo=UTC)
        mock_dashboard_jobs.return_value.gather.return_value = {}

        _collect_jobs(db_connection, since, until)

        mock_dashboard_jobs.assert_called_once_with(
            db=db_connection, since=since, until=until, after_id=None, batch_size=None, date_field="finished"
        )


@pytest.mark.unit
class TestCollectData:
    """Tests for the _collect_data core logic."""

    def test_success_returns_job_count(self, mock_collect_data_deps):
        """_collect_data returns correct job_count on success."""
        _, _, _, _, _, since, until = mock_collect_data_deps
        result = _collect_data("test_task")
        assert result["error"] is False
        assert result["data"]["job_count"] == 42
        assert result["data"]["date_range"]["start"] == since.isoformat()
        assert result["data"]["date_range"]["end"] == until.isoformat()

    def test_invalid_date_range_returns_error(self, mock_collect_data_deps):
        """_collect_data returns an error when since >= until."""
        mock_params, *_ = mock_collect_data_deps
        since = datetime(2024, 2, 1, tzinfo=UTC)
        until = datetime(2024, 1, 1, tzinfo=UTC)
        mock_params.return_value = ("awx", since, until, 5000)

        result = _collect_data("test_task")

        assert result["error"] is True
        assert "Invalid date range" in result["message"]

    def test_db_connection_error_returns_error(self, mock_collect_data_deps):
        """_collect_data returns error when DB connection fails."""
        _, mock_db_conn, *_ = mock_collect_data_deps
        mock_db_conn.side_effect = Exception("connection refused")

        result = _collect_data("test_task")

        assert result["error"] is True
        assert "Database error" in result["message"]

    def test_no_jobs_in_range_returns_zero_count(self, mock_collect_data_deps):
        """_collect_data returns job_count=0 when min_id is None (no jobs in window)."""
        _, _, mock_id_range, *_ = mock_collect_data_deps
        mock_id_range.return_value = (None, None)

        result = _collect_data("test_task")

        assert result["error"] is False
        assert result["data"]["job_count"] == 0

    def test_batch_error_propagates(self, mock_collect_data_deps):
        """_collect_data returns error when _process_batches reports a failure."""
        _, _, _, mock_batches, *_ = mock_collect_data_deps
        mock_batches.return_value = (0, "Collecting jobs failed: timeout")

        result = _collect_data("test_task")

        assert result["error"] is True
        assert "Collecting jobs failed" in result["message"]

    def test_invalid_settings_produce_clean_error(self, mock_collect_data_deps):
        """A ValueError from _resolve_collection_params is caught and returned as a task error."""
        mock_params, *_ = mock_collect_data_deps
        mock_params.side_effect = ValueError("BACKFILL_BATCH_SIZE must be a positive integer, got 'oops'")

        result = _collect_data("test_task")

        assert result["error"] is True
        assert "BACKFILL_BATCH_SIZE" in result["message"]

    def test_cursor_starts_at_min_id_minus_one(self, mock_collect_data_deps):
        """_collect_data always starts batching from min_id - 1 (safe cursor for concurrent writes)."""
        _, _, mock_id_range, mock_batches, *_ = mock_collect_data_deps
        mock_id_range.return_value = (500, 1000)

        _collect_data("test_task")

        call_kwargs = mock_batches.call_args
        # after_id is the 4th positional arg: (db_connection, since, until, max_id, after_id, ...)
        after_id_arg = call_kwargs[0][4]
        assert after_id_arg == 499  # min_id - 1


@pytest.mark.unit
class TestCollectDashboardReportsInitialData:
    """Tests for collect_dashboard_reports_initial_data."""

    def test_error_from_collect_data_propagates(self):
        """collect_dashboard_reports_initial_data returns error when _collect_data fails."""
        with (
            patch("apps.dashboard_reports.tasks._collect_data") as mock_collect,
            patch("apps.dashboard_reports.tasks.create_task_result") as mock_result,
            patch("apps.dashboard_reports.tasks._save_telemetry_details"),
        ):
            mock_collect.return_value = {"error": True, "message": "fail"}
            collect_dashboard_reports_initial_data()
            mock_result.assert_called_with("error", error="fail")

    def test_success_returns_data(self):
        """collect_dashboard_reports_initial_data returns success with data on success."""
        with (
            patch("apps.dashboard_reports.tasks._collect_data") as mock_collect,
            patch("apps.dashboard_reports.tasks.create_task_result") as mock_result,
            patch("apps.dashboard_reports.tasks._save_telemetry_details"),
        ):
            mock_collect.return_value = {"error": False, "data": {"job_count": 10}}
            collect_dashboard_reports_initial_data()
            mock_result.assert_called_with("success", data={"job_count": 10})

    def test_no_follow_up_task_creation(self):
        """collect_dashboard_reports_initial_data does NOT create a follow-up Task object."""
        with (
            patch("apps.dashboard_reports.tasks._collect_data") as mock_collect,
            patch("apps.dashboard_reports.tasks.create_task_result"),
            patch("apps.dashboard_reports.tasks._save_telemetry_details"),
            patch("apps.tasks.models.Task") as mock_task,
        ):
            mock_collect.return_value = {"error": False, "data": {}}
            collect_dashboard_reports_initial_data()
            mock_task.objects.get_or_create.assert_not_called()


@pytest.mark.unit
class TestCollectDashboardReportsData:
    """Tests for the deprecated collect_dashboard_reports_data task."""

    def test_error_in_collect_data(self, mock_collect_data, mock_create_task_result):
        """Returns error result when _collect_data reports failure."""
        mock_collect_data.return_value = {"error": True, "message": "fail"}
        collect_dashboard_reports_data()
        mock_create_task_result.assert_called_with("error", error="fail")

    def test_success_in_collect_data(self, mock_collect_data, mock_create_task_result):
        """Returns success result with data when _collect_data succeeds."""
        mock_collect_data.return_value = {"error": False, "data": {"foo": "bar"}}
        collect_dashboard_reports_data()
        mock_create_task_result.assert_called_with("success", data={"foo": "bar"})

    def test_missing_data_key(self, mock_collect_data, mock_create_task_result):
        """Returns success with empty dict when data key is absent from _collect_data result."""
        mock_collect_data.return_value = {"error": False}
        collect_dashboard_reports_data()
        mock_create_task_result.assert_called_with("success", data={})

    def test_error_message_fallback(self, mock_collect_data, mock_create_task_result):
        """Uses a generic error message when _collect_data returns no message."""
        mock_collect_data.return_value = {"error": True}
        collect_dashboard_reports_data()
        args, kwargs = mock_create_task_result.call_args
        assert args[0] == "error"
        assert "An unknown error occurred" in kwargs["error"]


@pytest.mark.unit
class TestSyncDashboardJobRecords:
    """Tests for sync_dashboard_job_records — the hourly hook-driven sync task."""

    @pytest.fixture(autouse=True)
    def patch_telemetry(self):
        with patch("apps.dashboard_reports.tasks._save_telemetry_details"):
            yield

    def _raw_job(self, job_id=1, num_hosts=5, label_ids=None):
        """Return a minimal raw job dict suitable for passing as raw_jobs input."""
        return {
            "id": job_id,
            "name": "Test Job",
            "unified_job_template_id": 10,
            "organization_id": 1,
            "organization_name": "Org",
            "started": "2024-01-01T00:00:00+00:00",
            "finished": "2024-01-01T01:00:00+00:00",
            "status": "successful",
            "elapsed": 3600.0,
            "launched_by_id": 5,
            "launched_by_username": "user",
            "project_id": 2,
            "project_name": "Project",
            "created": "2024-01-01T00:00:00+00:00",
            "modified": "2024-01-01T01:00:00+00:00",
            "label_ids": label_ids,
            "num_hosts": num_hosts,
        }

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_success_with_jobs(self, mock_result, mock_log, mock_sync):
        """sync_dashboard_job_records returns success with correct job_count."""
        raw_jobs = [self._raw_job(job_id=1), self._raw_job(job_id=2)]
        sync_dashboard_job_records(raw_jobs=raw_jobs, hour_timestamp="2024-01-01T00:00:00")
        mock_result.assert_called_once()
        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 2

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[1])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_failed_jobs_returns_error(self, mock_result, mock_log, mock_sync):
        """sync_dashboard_job_records returns error when _sync_jobs_atomically reports failures."""
        sync_dashboard_job_records(raw_jobs=[self._raw_job()], hour_timestamp="2024-01-01T00:00:00")
        args, kwargs = mock_result.call_args
        assert args[0] == "error"
        assert "Failed to sync" in kwargs["error"]

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_num_hosts_none_coerced_to_zero(self, mock_result, mock_log, mock_sync):
        """num_hosts=None in raw data is coerced to 0 rather than raising IntegrityError."""
        raw_jobs = [self._raw_job(num_hosts=None)]
        sync_dashboard_job_records(raw_jobs=raw_jobs, hour_timestamp="2024-01-01T00:00:00")
        assembled = mock_sync.call_args[0][0]
        assert assembled[0]["num_hosts"] == 0

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_label_ids_parsed_from_csv(self, mock_result, mock_log, mock_sync):
        """label_ids CSV string is parsed into a list of ints."""
        raw_jobs = [self._raw_job(label_ids="3,7,12")]
        sync_dashboard_job_records(raw_jobs=raw_jobs, hour_timestamp="2024-01-01T00:00:00")
        assembled = mock_sync.call_args[0][0]
        assert assembled[0]["labels"] == [3, 7, 12]

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_label_ids_with_spaces_parsed_correctly(self, mock_result, mock_log, mock_sync):
        """label_ids CSV with spaces around values (e.g. '3, 7, 12') is parsed without ValueError."""
        raw_jobs = [self._raw_job(label_ids="3, 7, 12")]
        sync_dashboard_job_records(raw_jobs=raw_jobs, hour_timestamp="2024-01-01T00:00:00")
        assembled = mock_sync.call_args[0][0]
        assert assembled[0]["labels"] == [3, 7, 12]

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_label_ids_zero_is_not_treated_as_empty(self, mock_result, mock_log, mock_sync):
        """label_ids=0 (falsy but valid scalar) must not be collapsed to an empty list."""
        raw_jobs = [self._raw_job(label_ids=0)]
        sync_dashboard_job_records(raw_jobs=raw_jobs, hour_timestamp="2024-01-01T00:00:00")
        assembled = mock_sync.call_args[0][0]
        assert assembled[0]["labels"] == [0]

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_empty_raw_jobs(self, mock_result, mock_log, mock_sync):
        """sync_dashboard_job_records handles empty raw_jobs gracefully."""
        sync_dashboard_job_records(raw_jobs=[], hour_timestamp="2024-01-01T00:00:00")
        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 0

    @patch("apps.dashboard_reports.tasks._sync_jobs_atomically", return_value=[])
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("apps.dashboard_reports.tasks.create_task_result")
    def test_host_summaries_set_to_none(self, mock_result, mock_log, mock_sync):
        """host_summaries is always None so backfill records are preserved by hourly sync."""
        raw_jobs = [self._raw_job()]
        sync_dashboard_job_records(raw_jobs=raw_jobs, hour_timestamp="2024-01-01T00:00:00")
        assembled = mock_sync.call_args[0][0]
        assert assembled[0]["host_summaries"] is None


@pytest.mark.unit
class TestCollectDataConnectionHandling:
    """Connection must never be closed by _collect_data (shared singleton)."""

    def test_does_not_close_connection_on_success(self, mock_collect_data_deps):
        """Connection is not closed after a successful collection (shared singleton must remain open)."""
        _, mock_db_conn, _, mock_batches, *_ = mock_collect_data_deps
        mock_connection = MagicMock()
        mock_db_conn.return_value = mock_connection
        mock_batches.return_value = (1, None)

        _collect_data("test_task")

        mock_connection.close.assert_not_called()

    def test_does_not_close_connection_on_batch_error(self, mock_collect_data_deps):
        """Connection is not closed even when a batch error is reported."""
        _, mock_db_conn, _, mock_batches, *_ = mock_collect_data_deps
        mock_connection = MagicMock()
        mock_db_conn.return_value = mock_connection
        mock_batches.return_value = (0, "Collecting jobs failed: timeout")

        _collect_data("test_task")

        mock_connection.close.assert_not_called()


# --- Cleanup tests ---
@pytest.mark.unit
class TestCleanupDashboardReportsOldData:
    """Tests for cleanup_dashboard_reports_old_data."""

    @pytest.fixture
    def mock_jobdata_objects(self):
        """Patch JobData ORM calls."""
        with patch("apps.dashboard_reports.tasks.JobData") as mock_jobdata:
            yield mock_jobdata

    @pytest.fixture
    def mock_log_task_execution(self):
        """Patch log_task_execution."""
        with patch("apps.dashboard_reports.tasks.log_task_execution") as mock_log:
            yield mock_log

    @pytest.fixture
    def mock_create_task_result_cleanup(self):
        """Patch create_task_result for cleanup tests."""
        with patch("apps.dashboard_reports.tasks.create_task_result") as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def mock_save_telemetry(self):
        """Patch _save_telemetry_details so unit tests don't hit the DB."""
        with patch("apps.dashboard_reports.tasks._save_telemetry_details"):
            yield

    def test_cleanup_success(self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup):
        """Successful deletion returns a success result with the correct record count."""
        mock_jobdata_objects.objects.filter.return_value.count.return_value = 5
        mock_create_task_result_cleanup.return_value = {"result": "success"}
        result = cleanup_dashboard_reports_old_data()
        assert result["result"] == "success"
        args, kwargs = mock_create_task_result_cleanup.call_args
        assert args[0] == "success"
        assert kwargs["data"]["deleted_records"] == 5
        assert "cutoff_date" in kwargs["data"]
        assert "retention_period_days" in kwargs["data"]

    def test_cleanup_no_records(self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup):
        """Returns success with deleted_records=0 when nothing falls outside the retention window."""
        mock_jobdata_objects.objects.filter.return_value.count.return_value = 0
        cleanup_dashboard_reports_old_data()
        args, kwargs = mock_create_task_result_cleanup.call_args
        assert args[0] == "success"
        assert kwargs["data"]["deleted_records"] == 0

    def test_cleanup_exception(self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup):
        """Returns an error result when the delete call raises."""
        mock_jobdata_objects.objects.filter.return_value.count.return_value = 3
        mock_jobdata_objects.objects.filter.return_value.delete.side_effect = Exception("db error")
        cleanup_dashboard_reports_old_data()
        args, kwargs = mock_create_task_result_cleanup.call_args
        assert args[0] == "error"
        assert "Cleanup failed" in kwargs["error"]

    def test_cleanup_defaults_to_initial_backfill_days_setting(
        self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup
    ):
        """When retention_period_days is omitted, INITIAL_BACKFILL_DAYS from settings is used."""
        from django.test import override_settings

        mock_jobdata_objects.objects.filter.return_value.count.return_value = 0
        with override_settings(DASHBOARD_COLLECTION={"INITIAL_BACKFILL_DAYS": 60}):
            cleanup_dashboard_reports_old_data()
        _, kwargs = mock_create_task_result_cleanup.call_args
        assert kwargs["data"]["retention_period_days"] == 60

    def test_cleanup_defaults_to_90_when_no_setting(
        self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup
    ):
        """Falls back to 90 when DASHBOARD_COLLECTION is not configured."""
        from django.test import override_settings

        mock_jobdata_objects.objects.filter.return_value.count.return_value = 0
        with override_settings(DASHBOARD_COLLECTION=None):
            cleanup_dashboard_reports_old_data()
        _, kwargs = mock_create_task_result_cleanup.call_args
        assert kwargs["data"]["retention_period_days"] == 90

    def test_cleanup_custom_retention(
        self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup
    ):
        """An explicit retention_period_days kwarg overrides the settings default."""
        mock_jobdata_objects.objects.filter.return_value.count.return_value = 2
        cleanup_dashboard_reports_old_data(retention_period_days=30)
        args, kwargs = mock_create_task_result_cleanup.call_args
        assert kwargs["data"]["retention_period_days"] == 30

    def test_cleanup_cutoff_date(self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup):
        """Cutoff date in the result is midnight on the expected day."""
        mock_jobdata_objects.objects.filter.return_value.count.return_value = 1
        cleanup_dashboard_reports_old_data(retention_period_days=1)
        _, kwargs = mock_create_task_result_cleanup.call_args
        actual_cutoff = kwargs["data"]["cutoff_date"]
        expected_date = (datetime.now(tz=UTC) - timedelta(days=1)).date().isoformat()
        assert actual_cutoff.startswith(expected_date)

    def test_cleanup_invalid_retention_string(
        self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup
    ):
        """Non-integer retention_period_days returns an error result."""
        cleanup_dashboard_reports_old_data(retention_period_days="not-a-number")
        args, kwargs = mock_create_task_result_cleanup.call_args
        assert args[0] == "error"
        assert "Invalid retention_period_days" in kwargs["error"]

    def test_cleanup_negative_retention_clamped(
        self, mock_jobdata_objects, mock_log_task_execution, mock_create_task_result_cleanup
    ):
        """Negative retention_period_days is clamped to 0 (deletes everything up to now)."""
        mock_jobdata_objects.objects.filter.return_value.delete.return_value = (10, {})
        cleanup_dashboard_reports_old_data(retention_period_days=-5)
        args, kwargs = mock_create_task_result_cleanup.call_args
        assert args[0] == "success"
        assert kwargs["data"]["retention_period_days"] == 0

    @pytest.mark.integration
    @pytest.mark.django_db
    def test_cleanup_with_db_data(self, db):
        """Test cleanup_dashboard_reports_old_data with real JobData records in the database."""
        cutoff = datetime.now().astimezone(UTC) - timedelta(days=90)
        old_job1 = JobData.objects.create(
            job_id=1001, finished=cutoff - timedelta(days=1), status="successful", elapsed=1.0
        )
        old_job2 = JobData.objects.create(
            job_id=1002, finished=cutoff - timedelta(days=10), status="successful", elapsed=1.0
        )
        new_job1 = JobData.objects.create(
            job_id=1003, finished=cutoff + timedelta(days=1), status="successful", elapsed=1.0
        )
        new_job2 = JobData.objects.create(
            job_id=1004, finished=cutoff + timedelta(days=10), status="successful", elapsed=1.0
        )
        result = cleanup_dashboard_reports_old_data(retention_period_days=90)
        assert result["deleted_records"] == 2

        remaining_ids = set(JobData.objects.values_list("id", flat=True))
        assert old_job1.id not in remaining_ids
        assert old_job2.id not in remaining_ids
        assert new_job1.id in remaining_ids
        assert new_job2.id in remaining_ids


# ---------------------------------------------------------------------------
# _resolve_collection_params
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestResolveCollectionParams:
    """Tests for _resolve_collection_params — all branches, no DB needed."""

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_explicit_since_until_used_directly(self, mock_jobdata):
        """When since and until are provided they are used without touching DB."""
        since = datetime(2024, 1, 1, tzinfo=UTC)
        until = datetime(2024, 2, 1, tzinfo=UTC)
        db_name, got_since, got_until, batch_size = _resolve_collection_params(
            {"since": since.isoformat(), "until": until.isoformat()}
        )
        assert got_since == since
        assert got_until == until
        assert db_name == "awx"
        mock_jobdata.last_timestamp.assert_not_called()

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_since_falls_back_to_last_timestamp(self, mock_jobdata):
        """When since is absent and last_timestamp() has a value, it is used as since."""
        ts = datetime(2024, 3, 15, tzinfo=UTC)
        mock_jobdata.last_timestamp.return_value = ts
        _, got_since, _, _ = _resolve_collection_params({})
        assert got_since == ts

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_since_computed_from_backfill_days_when_no_timestamp(self, mock_jobdata):
        """When since is absent and last_timestamp() is None, compute since from INITIAL_BACKFILL_DAYS."""
        from django.test import override_settings

        mock_jobdata.last_timestamp.return_value = None
        until = datetime(2024, 6, 1, tzinfo=UTC)

        with override_settings(DASHBOARD_COLLECTION={"INITIAL_BACKFILL_DAYS": 30, "BACKFILL_BATCH_SIZE": 500}):
            _, got_since, _, batch_size = _resolve_collection_params({"until": until.isoformat()})

        expected_since = (until - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        assert got_since == expected_since
        assert batch_size == 500

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_custom_database_kwarg(self, mock_jobdata):
        """The 'database' kwarg overrides the DEFAULT_DB_NAME."""
        mock_jobdata.last_timestamp.return_value = datetime(2024, 1, 1, tzinfo=UTC)
        db_name, *_ = _resolve_collection_params({"database": "custom_db"})
        assert db_name == "custom_db"

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_default_batch_size_applied(self, mock_jobdata):
        """BACKFILL_BATCH_SIZE defaults to 5_000 when not set."""
        mock_jobdata.last_timestamp.return_value = datetime(2024, 1, 1, tzinfo=UTC)
        _, _, _, batch_size = _resolve_collection_params({})
        assert batch_size == 5_000

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_invalid_batch_size_raises_value_error(self, mock_jobdata):
        """A non-integer BACKFILL_BATCH_SIZE raises ValueError with a descriptive message."""
        from django.test import override_settings

        mock_jobdata.last_timestamp.return_value = datetime(2024, 1, 1, tzinfo=UTC)
        with (
            override_settings(DASHBOARD_COLLECTION={"BACKFILL_BATCH_SIZE": "not-a-number"}),
            pytest.raises(ValueError, match="BACKFILL_BATCH_SIZE"),
        ):
            _resolve_collection_params({})

    @patch("apps.dashboard_reports.tasks.JobData")
    def test_invalid_backfill_days_raises_value_error(self, mock_jobdata):
        """A non-integer INITIAL_BACKFILL_DAYS raises ValueError with a descriptive message."""
        from django.test import override_settings

        mock_jobdata.last_timestamp.return_value = None
        with (
            override_settings(DASHBOARD_COLLECTION={"INITIAL_BACKFILL_DAYS": "not-a-number"}),
            pytest.raises(ValueError, match="INITIAL_BACKFILL_DAYS"),
        ):
            _resolve_collection_params({})


# ---------------------------------------------------------------------------
# _get_job_id_range
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGetJobIdRange:
    """Tests for _get_job_id_range — mocks both the query builder and DB cursor."""

    def _mock_db(self, fetchone_return):
        """Return a mock DB connection whose cursor context manager yields fetchone_return."""
        db = MagicMock()
        cursor_ctx = MagicMock()
        cursor_ctx.__enter__ = MagicMock(return_value=cursor_ctx)
        cursor_ctx.__exit__ = MagicMock(return_value=False)
        cursor_ctx.fetchone.return_value = fetchone_return
        db.cursor.return_value = cursor_ctx
        return db

    def test_returns_min_max_when_row_exists(self):
        """_get_job_id_range returns (min_id, max_id) from the cursor row."""
        since = datetime(2024, 1, 1, tzinfo=UTC)
        until = datetime(2024, 2, 1, tzinfo=UTC)
        db = self._mock_db(fetchone_return=(100, 999))

        with patch(
            "metrics_utility.library.collectors.dashboard.get_min_max_job_id_query",
            create=True,
            return_value=("SELECT 1", []),
        ):
            result = _get_job_id_range(db, since, until)

        assert result == (100, 999)

    def test_returns_none_none_when_no_rows(self):
        """_get_job_id_range returns (None, None) when cursor returns nothing."""
        since = datetime(2024, 1, 1, tzinfo=UTC)
        until = datetime(2024, 2, 1, tzinfo=UTC)
        db = self._mock_db(fetchone_return=None)

        with patch(
            "metrics_utility.library.collectors.dashboard.get_min_max_job_id_query",
            create=True,
            return_value=("SELECT 1", []),
        ):
            result = _get_job_id_range(db, since, until)

        assert result == (None, None)


# ---------------------------------------------------------------------------
# _process_batches
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestProcessBatches:
    """Tests for _process_batches — mocks _collect_jobs and _sync_jobs_atomically."""

    _since = datetime(2024, 1, 1, tzinfo=UTC)
    _until = datetime(2024, 2, 1, tzinfo=UTC)

    def _call(self, after_id, max_id, collect_side_effect=None, sync_return=None):
        """Invoke _process_batches with mocked _collect_jobs and _sync_jobs_atomically."""
        db = MagicMock()
        with (
            patch("apps.dashboard_reports.tasks._collect_jobs") as mock_collect,
            patch("apps.dashboard_reports.tasks._sync_jobs_atomically") as mock_sync,
            patch("apps.dashboard_reports.tasks.log_task_execution"),
        ):
            if collect_side_effect is not None:
                mock_collect.side_effect = collect_side_effect
            if sync_return is not None:
                mock_sync.return_value = sync_return
            result = _process_batches(db, self._since, self._until, max_id, after_id, 100, "test_task")
        return result, mock_collect, mock_sync

    def test_never_loops_when_cursor_at_max(self):
        """No collection happens when after_id >= max_id."""
        (total, err), mock_collect, _ = self._call(after_id=500, max_id=500)
        assert total == 0
        assert err is None
        mock_collect.assert_not_called()

    def test_single_successful_batch(self):
        """A single batch with results commits and returns (count, None)."""
        batch = {"results": [{"id": 101}, {"id": 102}], "count": 2}
        collect_side_effects = [batch, {"results": [], "count": 0}]

        (total, err), _, _ = self._call(
            after_id=99, max_id=200, collect_side_effect=collect_side_effects, sync_return=[]
        )
        assert err is None
        assert total == 2

    def test_empty_batch_breaks_loop(self):
        """An empty results list causes the loop to break without error."""
        batch = {"results": [], "count": 0}
        (total, err), mock_collect, _ = self._call(after_id=99, max_id=200, collect_side_effect=[batch])
        assert err is None
        assert total == 0
        mock_collect.assert_called_once()

    def test_collect_exception_returns_error(self):
        """An exception from _collect_jobs returns an error tuple."""
        (total, err), _, _ = self._call(after_id=99, max_id=200, collect_side_effect=Exception("timeout"))
        assert err is not None
        assert "Collecting jobs failed" in err

    def test_failed_sync_returns_error(self):
        """Failed jobs from _sync_jobs_atomically returns an error tuple."""
        batch = {"results": [{"id": 101}], "count": 1}
        (total, err), _, _ = self._call(after_id=99, max_id=200, collect_side_effect=[batch], sync_return=[101])
        assert err is not None
        assert "Failed to sync" in err

    def test_multi_batch_accumulates_count(self):
        """Two successful batches accumulate total_synced correctly."""
        batch1 = {"results": [{"id": 101}, {"id": 102}], "count": 2}
        batch2 = {"results": [{"id": 103}], "count": 1}
        empty = {"results": [], "count": 0}

        (total, err), _, _ = self._call(
            after_id=99, max_id=200, collect_side_effect=[batch1, batch2, empty], sync_return=[]
        )
        assert err is None
        assert total == 3

    def test_cursor_advances_to_max_id_of_previous_batch(self):
        """The second _collect_jobs call receives after_id = max(ids) from the first batch."""
        batch1 = {"results": [{"id": 101}, {"id": 105}], "count": 2}
        empty = {"results": [], "count": 0}

        _, mock_collect, _ = self._call(after_id=99, max_id=200, collect_side_effect=[batch1, empty], sync_return=[])

        assert mock_collect.call_count == 2
        second_call_kwargs = mock_collect.call_args_list[1][1]
        assert second_call_kwargs["after_id"] == 105  # max id from batch1, not batch1["count"]


@pytest.mark.unit
class TestSyncDashboardHostSummaries:
    """Tests for sync_dashboard_host_summaries — the hourly hook-driven host summary sync task."""

    def _raw_record(self, host_summary_id=1, host_name="web01", host_id=10, job_remote_id=42):
        """Return a minimal raw host summary dict as produced by the hook (wire format)."""
        return {
            "id": host_summary_id,
            "host_name": host_name,
            "host_id": host_id,
            "job_remote_id": job_remote_id,
        }

    def _make_job_data(self, job_id, pk=None):
        """Return a MagicMock with job_id and pk set to avoid auto-spec surprises."""
        jd = MagicMock()
        jd.job_id = job_id
        jd.pk = pk if pk is not None else job_id
        return jd

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.JobData._sync_host_summaries")
    @patch("apps.dashboard_reports.tasks.JobHostSummary")
    @patch("apps.dashboard_reports.tasks.JobData.objects")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("django.db.transaction.atomic", new=contextlib.nullcontext)
    def test_syncs_host_summaries_for_known_job(self, mock_log, mock_objects, mock_jhs, mock_sync, mock_result):
        """When JobData exists for job_remote_id, _sync_host_summaries is called with remapped fields."""
        job_data = self._make_job_data(job_id=123, pk=1)
        mock_objects.filter.return_value = [job_data]
        mock_jhs.objects.filter.return_value = []

        record = self._raw_record(host_summary_id=7, host_name="db01", host_id=99, job_remote_id=123)
        sync_dashboard_host_summaries(raw_host_summaries=[record], hour_timestamp="2024-01-01T00:00:00")

        mock_sync.assert_called_once_with(
            job_data,
            [{"id": 7, "host_id": 99, "host_name": "db01"}],
            {},
        )
        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 1

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.JobHostSummary")
    @patch("apps.dashboard_reports.tasks.JobData.objects")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    def test_skips_silently_when_job_data_not_found(self, mock_log, mock_objects, mock_jhs, mock_result):
        """When no JobData matches job_remote_id, the job is skipped without error."""
        mock_objects.filter.return_value = []
        mock_jhs.objects.filter.return_value = []

        sync_dashboard_host_summaries(raw_host_summaries=[self._raw_record()], hour_timestamp="2024-01-01T00:00:00")

        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 0

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.JobData._sync_host_summaries")
    @patch("apps.dashboard_reports.tasks.JobHostSummary")
    @patch("apps.dashboard_reports.tasks.JobData.objects")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("django.db.transaction.atomic", new=contextlib.nullcontext)
    def test_continues_after_individual_job_failure(self, mock_log, mock_objects, mock_jhs, mock_sync, mock_result):
        """An exception on one job is logged and remaining jobs are still processed."""
        job_a = self._make_job_data(job_id=1, pk=1)
        job_b = self._make_job_data(job_id=2, pk=2)
        mock_objects.filter.return_value = [job_a, job_b]
        mock_jhs.objects.filter.return_value = []
        mock_sync.side_effect = [RuntimeError("oops"), None]

        records = [self._raw_record(job_remote_id=1), self._raw_record(job_remote_id=2)]
        sync_dashboard_host_summaries(raw_host_summaries=records, hour_timestamp="2024-01-01T00:00:00")

        assert mock_sync.call_count == 2
        args, kwargs = mock_result.call_args
        assert args[0] == "error"
        assert kwargs["data"]["job_count"] == 1  # only job_b succeeded
        assert kwargs["data"]["failed"] == 1

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.JobData._sync_host_summaries")
    @patch("apps.dashboard_reports.tasks.JobHostSummary")
    @patch("apps.dashboard_reports.tasks.JobData.objects")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("django.db.transaction.atomic", new=contextlib.nullcontext)
    def test_groups_multiple_summaries_per_job(self, mock_log, mock_objects, mock_jhs, mock_sync, mock_result):
        """Multiple host summary records for the same job are grouped and passed together."""
        job_data = self._make_job_data(job_id=42, pk=1)
        mock_objects.filter.return_value = [job_data]
        mock_jhs.objects.filter.return_value = []

        records = [
            self._raw_record(host_summary_id=1, host_name="web01", job_remote_id=42),
            self._raw_record(host_summary_id=2, host_name="web02", job_remote_id=42),
        ]
        sync_dashboard_host_summaries(raw_host_summaries=records, hour_timestamp="2024-01-01T00:00:00")

        # One batch filter call for JobData (not one get per job).
        mock_objects.filter.assert_called_once()
        passed_summaries = mock_sync.call_args[0][1]
        assert len(passed_summaries) == 2
        assert {s["host_name"] for s in passed_summaries} == {"web01", "web02"}

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    def test_empty_raw_host_summaries(self, mock_log, mock_result):
        """Empty input returns success with job_count=0 without querying the DB."""
        sync_dashboard_host_summaries(raw_host_summaries=[], hour_timestamp="2024-01-01T00:00:00")
        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 0

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.JobData._sync_host_summaries")
    @patch("apps.dashboard_reports.tasks.JobHostSummary")
    @patch("apps.dashboard_reports.tasks.JobData.objects")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("django.db.transaction.atomic", new=contextlib.nullcontext)
    def test_null_host_id_is_preserved(self, mock_log, mock_objects, mock_jhs, mock_sync, mock_result):
        """host_id=None (deleted AWX host) is passed as None to _sync_host_summaries."""
        job_data = self._make_job_data(job_id=42, pk=1)
        mock_objects.filter.return_value = [job_data]
        mock_jhs.objects.filter.return_value = []

        record = self._raw_record(host_id=None)
        sync_dashboard_host_summaries(raw_host_summaries=[record], hour_timestamp="2024-01-01T00:00:00")

        passed_summaries = mock_sync.call_args[0][1]
        assert passed_summaries[0]["host_id"] is None

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    def test_records_with_null_job_remote_id_are_dropped(self, mock_log, mock_result):
        """Records where job_remote_id is None are ignored without error."""
        record = {"id": 1, "host_name": "h1", "host_id": 5, "job_remote_id": None}
        sync_dashboard_host_summaries(raw_host_summaries=[record], hour_timestamp="2024-01-01T00:00:00")
        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 0

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    def test_records_with_null_id_are_dropped(self, mock_log, mock_result):
        """Records where id is None are ignored without error."""
        record = {"id": None, "host_name": "h1", "host_id": 5, "job_remote_id": 42}
        sync_dashboard_host_summaries(raw_host_summaries=[record], hour_timestamp="2024-01-01T00:00:00")
        args, kwargs = mock_result.call_args
        assert args[0] == "success"
        assert kwargs["data"]["job_count"] == 0

    @patch("apps.dashboard_reports.tasks.create_task_result")
    @patch("apps.dashboard_reports.tasks.JobData._sync_host_summaries")
    @patch("apps.dashboard_reports.tasks.JobHostSummary")
    @patch("apps.dashboard_reports.tasks.JobData.objects")
    @patch("apps.dashboard_reports.tasks.log_task_execution")
    @patch("django.db.transaction.atomic", new=contextlib.nullcontext)
    def test_uses_pre_fetched_existing_host_summaries(self, mock_log, mock_objects, mock_jhs, mock_sync, mock_result):
        """Existing JobHostSummary objects are pre-fetched in one query and passed per job."""
        job_data = self._make_job_data(job_id=42, pk=10)
        mock_objects.filter.return_value = [job_data]

        existing_hs = MagicMock()
        existing_hs.job_data_id = 10
        existing_hs.host_summary_id = 99
        mock_jhs.objects.filter.return_value = [existing_hs]

        record = self._raw_record(host_summary_id=99, job_remote_id=42)
        sync_dashboard_host_summaries(raw_host_summaries=[record], hour_timestamp="2024-01-01T00:00:00")

        # Confirm the existing hs was passed in the dict keyed by host_summary_id.
        passed_existing = mock_sync.call_args[0][2]
        assert 99 in passed_existing
        assert passed_existing[99] is existing_hs
