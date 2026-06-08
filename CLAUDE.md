# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup

```bash
# Install dependencies (project uses uv)
uv sync --dev

# Run database migrations
.venv/bin/python manage.py migrate

# Initialize required objects (run after every migration)
python manage.py metrics_service init-service-id      # Required for DAB resource registry
python manage.py metrics_service init-default-settings # Initialize feature flag DB table
python manage.py metrics_service init-system-tasks     # Register scheduled background tasks

# Create superuser
python manage.py createsuperuser
```

### Running the Service

```bash
# Full service (Django + dispatcherd + APScheduler)
python manage.py metrics_service run

# Development server only
python manage.py runserver

# With Docker (includes PostgreSQL)
docker-compose up
```

### Testing

```bash
# Run all tests (--reuse-db is set by default in pytest config, DB is reused between runs)
uv run pytest

# Force DB recreation when schema changes
uv run pytest --create-db

# Run specific test file or directory
uv run pytest tests/unit/tasks/
uv run pytest tests/unit/tasks/test_task_groups.py::TestTaskGroup::test_name

# Run by marker
uv run pytest -m unit
uv run pytest -m integration

# With coverage (80% minimum enforced)
uv run pytest --cov=apps --cov=metrics_service --cov-report=term-missing
```

**Coverage measurement:** Always use `--cov=apps.module_name` (module path), never file paths. Run the full suite for accurate totals — individual files give misleading results.

### Code Quality

```bash
# Format + lint + test (via poe)
uv run poe check

# Individual steps
uv run poe format   # ruff format
uv run poe lint     # ruff check
uv run poe unit-test
```

### Running Django Commands with Imports

```bash
# Always use manage.py shell for one-off Django commands — plain python -c fails without Django setup
python manage.py shell -c "from apps.tasks.tasks import TASK_FUNCTIONS; print(list(TASK_FUNCTIONS))"
```

## Architecture Overview

### App Structure

```
apps/
  core/             # Custom User/Organization/Team models, DAB integration, RBAC, middleware
  tasks/            # Background task system: models, scheduling, execution, collectors, cleanup
  dynamic_settings/ # Runtime DB-backed feature flags (Setting model)
  settings/         # Dynaconf settings layering (defaults, dev, prod, test)
  dashboard/        # Web UI for task monitoring at /dashboard/
  dashboard_reports/ # SQL-based AWX job data collection for automation-reports integration
metrics_service/
  settings/         # Split Django settings (development, production, test)
  urls.py           # Framework-managed URL root (do not edit)
```

### Settings Loading Order (Dynaconf)

Settings are merged in this order (later overrides earlier):

1. `metrics_service/settings.py` — framework defaults (read-only)
2. `apps/settings/defaults.py` — project-wide defaults; defines `project_applications` (controls app load order)
3. `apps/core/settings.py` — DAB-related settings
4. `apps/*/settings.py` — per-app settings
5. `apps/settings/{mode}.py` — mode-specific (dev/prod/test)
6. `settings.local.py` — local overrides (git-ignored)
7. `/etc/ansible-automation-platform/metrics_service/settings.yaml` — prod
8. `METRICS_SERVICE_*` environment variables

Use Dynaconf merge markers when extending lists/dicts in app settings:
```python
INSTALLED_APPS = "@merge_unique my_new_app"
DATABASES__default__PORT = 5433
```

### URL Loading Order

`metrics_service/urls.py` is framework-managed (do not edit). URL patterns resolve in this order:

1. Django Ansible Base (DAB) URLs
2. Dynamic API root overrides
3. `apps/urls.py` — cross-app and service-level patterns (load here for priority)
4. Individual app `urls.py` in `project_applications` order (from `apps/settings/defaults.py`)
5. Debug toolbar (dev only)

To add a URL that must take priority over all apps, use `apps/urls.py`. To control relative priority between apps, reorder `project_applications` in `apps/settings/defaults.py` (this also affects settings load order).

### Task System (`apps/tasks/`)

The task system has several layers:

- **`models.py`** — `Task`, `TaskExecution`, `TaskChain` DB models
- **`tasks.py`** — `TASK_FUNCTIONS` registry (name→callable), `TASK_LOCKS` set (functions that acquire a PostgreSQL advisory lock during scheduled execution), and `TASK_METADATA` dict (queue routing, parameter docs, dashboard display)
- **`task_groups.py`** — `TASK_GROUPS` config: defines what tasks run, their cron schedules, args, and which feature flag controls them. **This is the source of truth for scheduled tasks** — edit here, then run `init-system-tasks` to sync to DB.
- **`cron_scheduler.py`** — APScheduler integration for recurring tasks
- **`dispatcherd_config.py`** — Dispatcherd worker configuration; queue names are `"metrics"`, `"maintenance"`, `"dashboard"`
- **`collectors/`** — `collect_hourly_metrics`, `collect_snapshot_metrics`, `collect_daily_metrics`, `daily_metrics_rollup`, `daily_anonymize_and_prepare`, `send_anonymized_to_segment`
- **`cleanup/`** — `cleanup_old_tasks`, `cleanup_activitystream`, `cleanup_metrics_data`
- **`simple/`** — `hello_world` (health check)
- **`services/`** — Output formatting utilities
- **`v1/`** — REST API for task CRUD (`/api/v1/tasks/`)

### Task Groups and Feature Flags

`task_groups.py` defines four groups:

- **`SYSTEM_TASKS_GROUP`** — Always enabled. Runs `cleanup_old_tasks` (daily 5 AM) and `hello_world` (hourly).
- **`METRICS_COLLECTION_GROUP`** — Controlled by `METRICS_COLLECTION` feature flag (default: enabled). All hourly/daily collection, `daily_metrics_rollup`, and `cleanup_metrics_data`. Disabling this stops local scheduled collection.
- **`ANONYMIZATION_GROUP`** — Controlled by `ANONYMIZED_DATA_COLLECTION` feature flag (default: enabled, customer opt-out). Only `daily_anonymize_and_prepare` — the task that transmits data to Red Hat. Disable to stop upstream transmission without stopping local collection.
- **`DASHBOARD_COLLECTION_GROUP`** — Controlled by `DASHBOARD_COLLECTION` feature flag (default: **disabled**, customer opt-in). SQL-based collection for `automation-reports` integration. Contains `collect_dashboard_reports_initial_data` (one-time backfill, no cron) and `cleanup_dashboard_reports_old_data`.

Feature flag resolution order (see `get_feature_enabled_from_db` in `task_groups.py`):
1. `dynamic_settings_setting` DB table
2. `FEATURE[<name>]` in Django settings (env var `METRICS_SERVICE_FEATURE__<NAME>`)
3. Top-level `FEATURE_<NAME>_ENABLED` attribute (set by installer in settings.yaml)
4. DAB `AAPFlag` model
5. Function default

```bash
# Toggle a flag (requires process/pod restart)
METRICS_SERVICE_FEATURE__ANONYMIZED_DATA_COLLECTION=false
METRICS_SERVICE_FEATURE__DASHBOARD_COLLECTION=true
```

### Dashboard Reports App (`apps/dashboard_reports/`)

A separate Django app that stores AWX job data for the `automation-reports` service. Key models: `JobData`, `JobLabel`, `JobHostSummary` (AWX job records), `SubscriptionCost` (singleton), `FilterSet`, `TemplateMetadata`. Data flows in via:

1. **Backfill**: `collect_dashboard_reports_initial_data` task queries AWX DB directly using `metrics_utility.library.collectors.dashboard.dashboard_jobs`
2. **Incremental**: `collect_hourly_metrics` for `unified_jobs` fires a `post_collect_hook` that calls `sync_dashboard_job_records` to write each hour's jobs to `JobData`

The AWX database is accessed via a named Django DB connection (`"awx"` by default) — not the metrics-service DB. Viewsets are in `apps/dashboard_reports/viewsets/` and use read-only queries against `JobData`.

### Collector Types

Three function signatures cover all collection tasks:

- `collect_hourly_metrics(collector_type, hour_timestamp=None)` — time-series, runs every hour. Types: `job_host_summary_service`, `unified_jobs`, `credentials_service`, `main_jobevent_service` (disabled by default)
- `collect_snapshot_metrics(collector_type)` — point-in-time snapshots, runs daily. Types: `execution_environments`, `config`, `controller_version_service`, `table_metadata`, `feature_flags_service`
- `collect_daily_metrics(collector_type, since=None, until=None)` — daily time-range collection (previous full day). Types: `task_executions_service`

All three delegate to `metrics_utility` for the actual AWX DB queries.

### API Structure

Each app exposes its own versioned API under a `v1/` subdirectory:
- `apps/tasks/v1/` — Task management endpoints (`/api/v1/tasks/`)
- `apps/core/v1/` — Core resource endpoints (users, orgs, teams)
- `apps/dynamic_settings/v1/` — Settings API
- `apps/dashboard_reports/` — Dashboard report endpoints (viewsets, no `v1/` subdirectory)

All viewsets use `BaseViewSet` / `UserManagementMixin` base classes from `apps/core/v1/viewsets/base.py`. OpenAPI docs at `/api/docs/`.

### Dynamic Settings (`apps/dynamic_settings/`)

Provides a DB-backed `Setting` model for runtime configuration. Feature flags are checked here at task execution time. Managed via:
- `python manage.py metrics_service init-default-settings` — seed defaults
- `python manage.py metrics_service remove-default-settings` — remove unmodified defaults
- `python manage.py dynamic_settings reload_config` — reload config from DB

## Key Development Patterns

### Adding a New Background Task

1. Implement the function in `apps/tasks/collectors/`, `apps/tasks/cleanup/`, or `apps/tasks/simple/`
2. Add to `TASK_FUNCTIONS` and `TASK_METADATA` in `apps/tasks/tasks.py` (include `queue`, `category`, `description`, `parameters`, `examples`)
3. Add to `TASK_LOCKS` in `tasks.py` if it needs a PostgreSQL advisory lock during scheduled execution
4. Add a task config entry to the appropriate `TaskGroup` in `apps/tasks/task_groups.py`
5. Run `python manage.py metrics_service init-system-tasks` to sync to DB

### Code Style

- Line length: 120 characters
- Ruff rules: security (bandit), complexity (mccabe/pylint), style checks. Migrations excluded.
- All new code requires type hints and docstrings on public methods
- Use lazy imports inside functions when importing `metrics_utility` — it keeps unrelated task registration working even if the dependency is missing

### Test Organization

- `tests/unit/` — unit tests (in `testpaths` from `pyproject.toml`)
- `tests/coverage/` — additional coverage-focused tests (not in `testpaths` by default; run explicitly with `uv run pytest tests/coverage/`)
- `tests/integration/` — integration tests
- `apps/core/tests/` — app-local tests (also in `testpaths`)
- `apps/dynamic_settings/tests/` — app-local tests
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
