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

# Run specific subset
uv run pytest tests/unit/tasks/
uv run pytest -m unit
uv run pytest -m integration

# With coverage (80% minimum enforced)
uv run pytest --cov=apps --cov=metrics_service --cov-report=term-missing
```

**Coverage measurement:** Always run coverage on the module (`--cov=apps.tasks`), never on file paths. Run the full test suite, not individual files, to get accurate coverage.

### Code Quality

```bash
# Format + lint + test (via poe task runner)
uv run poe check

# Individual poe tasks
uv run poe format   # ruff format
uv run poe lint     # ruff check
uv run poe unit-test

# Or directly
.venv/bin/ruff format . && .venv/bin/ruff check . --fix
```

### Running Django Commands with Imports

```bash
# For one-off commands that need Django context
python manage.py shell -c "from apps.tasks.tasks import TASK_FUNCTIONS; print(list(TASK_FUNCTIONS))"

# Never use plain python -c for Django imports — it fails without Django setup
```

## Architecture Overview

### App Structure

```
apps/
  core/              # Custom User/Organization/Team models, DAB integration, RBAC
  tasks/             # Background task system (models, scheduling, execution)
  dynamic_settings/  # Runtime DB-backed feature flags (Setting model)
  settings/          # Dynaconf settings layering (see below)
  dashboard/         # Web UI for task monitoring at /dashboard/
  dashboard_reports/ # AWX job data collection + REST API for automation-reports UI
  bi_connector/      # Read-only REST API for BI tools (Tableau, Power BI, Grafana)
metrics_service/
  settings/          # Split Django settings (development, production, test)
```

### Settings Loading Order (Dynaconf)

Settings are merged in this order (later overrides earlier):

1. `metrics_service/settings.py` — framework defaults (read-only)
2. `apps/settings/defaults.py` — project-wide defaults
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

### Task System (`apps/tasks/`)

The task system has several layers:

- **`models.py`** — `Task`, `TaskExecution`, `TaskChain` DB models
- **`tasks.py`** — `TASK_FUNCTIONS` registry mapping function names to callables
- **`task_groups.py`** — `TASK_GROUPS` config: defines what tasks run, their cron schedules, args, and which feature flag controls them. This is the source of truth for scheduled tasks — edit here, then run `init-system-tasks` to sync to DB.
- **`cron_scheduler.py`** — APScheduler integration for recurring tasks
- **`dispatcherd_config.py`** — Dispatcherd worker configuration
- **`collectors/`** — Metrics collection functions (`collect_hourly_metrics`, `collect_snapshot_metrics`, `daily_metrics_rollup`, `daily_anonymize_and_prepare`, `send_anonymized_to_segment`)
- **`cleanup/`** — Cleanup functions (`cleanup_old_tasks`, `cleanup_activitystream`, `cleanup_metrics_data`)
- **`simple/`** — Simple tasks (`hello_world`)
- **`services/`** — Output formatting utilities
- **`v1/`** — REST API for task CRUD (`/api/v1/tasks/`)

### Task Groups and Feature Flags

`task_groups.py` defines four groups:

- **`SYSTEM_TASKS_GROUP`** — Always enabled. Runs `cleanup_old_tasks` (daily 5 AM) and `hello_world` (hourly).
- **`METRICS_COLLECTION_GROUP`** — Always enabled (no feature flag). Contains all hourly/daily collection tasks, `daily_metrics_rollup`, and `cleanup_metrics_data`. Local metrics are collected regardless of the opt-out flag to prevent data gaps.
- **`ANONYMIZATION_GROUP`** — Controlled by `ANONYMIZED_DATA_COLLECTION` feature flag (default: enabled, customer opt-out). Contains only `daily_anonymize_and_prepare` and `send_anonymized_to_segment` — the tasks that transmit data to Red Hat.
- **`DASHBOARD_COLLECTION_GROUP`** — Controlled by `DASHBOARD_COLLECTION` feature flag (default: disabled). Runs `collect_dashboard_reports_data` every 6 hours (configurable) and `cleanup_dashboard_reports_old_data` daily. Powers the `dashboard_reports` API.

Feature flags are defined in per-app `feature_flags.yaml` files (e.g., `apps/tasks/feature_flags.yaml`, `apps/bi_connector/feature_flags.yaml`). Values are seeded into the DB via `init-default-settings` and can be overridden at runtime without restart.

```bash
# Toggle at runtime without restart
METRICS_SERVICE_FEATURE_ENABLED__ANONYMIZED_DATA_COLLECTION=false
METRICS_SERVICE_FEATURE_ENABLED__DASHBOARD_COLLECTION=true
METRICS_SERVICE_FEATURE_ENABLED__BI_CONNECTOR=true
```

### API Structure

Each app exposes its own versioned API under a `v1/` subdirectory:
- `apps/tasks/v1/` — Task management endpoints (`/api/v1/tasks/`)
- `apps/core/v1/` — Core resource endpoints
- `apps/dynamic_settings/v1/` — Settings API
- `apps/dashboard_reports/` — Reporting endpoints for automation-reports UI
- `apps/bi_connector/v1/` — Read-only BI tool endpoints (disabled by default, token auth)

All viewsets use `BaseViewSet` / `UserManagementMixin` base classes. OpenAPI docs at `/api/docs/`.

### BI Connector (`apps/bi_connector/`)

Disabled by default — enable via `FEATURE_ENABLED__BI_CONNECTOR`. When disabled, all endpoints return 404 (`BiConnectorEnabledMixin` hides the surface entirely).

Uses token auth (`rest_framework.authtoken`) for long-lived service account tokens. Generate with:
```bash
python manage.py drf_create_token <username>
```

Two endpoint layers:
- **Layer 1** (`metrics_views.py`, `dashboard_views.py`) — pre-aggregated data from metrics-service DB (synchronous, fast)
- **Layer 2** (`controller_views.py`) — live queries direct to AWX DB (asynchronous for time-series)

The async pattern: `GET ?since=&until=` → `202 Accepted + {"task_id": N, "status_url": "/api/v1/tasks/N/"}`. Poll the task until `status == "completed"`, then read `result_data.data`. A second identical in-flight request returns the existing `task_id` (deduplication). Snapshot endpoints remain synchronous.

Date windows are enforced via `DateRangeRequiredMixin` to protect the AWX DB:
- `BI_CONNECTOR_MAX_DAYS_DEFAULT` (default: 7) — most endpoints
- `BI_CONNECTOR_MAX_DAYS_EVENTS` (default: 3) — events endpoint (largest AWX table)

Per-user throttle: 30 req/hour (`bi_connector` scope), overridable via `METRICS_SERVICE_REST_FRAMEWORK__DEFAULT_THROTTLE_RATES__BI_CONNECTOR`.

### Dynamic Settings (`apps/dynamic_settings/`)

Provides a DB-backed `Setting` model for runtime configuration. Feature flags checked here at task execution time — no restart needed when toggling. Managed via:
- `python manage.py metrics_service init-default-settings` — seed defaults
- `python manage.py metrics_service remove-default-settings` — remove unmodified defaults
- `python manage.py dynamic_settings reload_config` — reload config from DB

## Key Development Patterns

### Adding a New Background Task

1. Implement the function in `apps/tasks/collectors/`, `apps/tasks/cleanup/`, or `apps/tasks/simple/`
2. Add to `TASK_FUNCTIONS` dict in `apps/tasks/tasks.py`
3. Add a task config entry to the appropriate `TaskGroup` in `apps/tasks/task_groups.py`
4. Run `python manage.py metrics_service init-system-tasks` to sync to DB

### Code Style

- Line length: 120 characters
- Ruff rules include security (bandit), complexity (mccabe/pylint), and style checks
- All new code requires type hints and docstrings on public methods
- Migrations excluded from linting

### Test Organization

- `tests/unit/` and `apps/core/tests/` — unit tests (both are testpaths)
- `tests/integration/` — integration tests
- `apps/dynamic_settings/tests/` — app-local tests
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
