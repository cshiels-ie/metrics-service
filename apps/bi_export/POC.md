# BYO-BI Export — POC (ANSTRAT-1587)

Customer-facing analytics export API for connecting BI tools (Looker, Power BI, Grafana)
directly to local AAP automation data without data leaving the environment.

## Endpoints

All endpoints are under `/api/metrics/v1/export/` and require **system admin or platform auditor** auth.
Pagination is standard (`?page=&page_size=`). All responses are raw JSON.

### Dashboard collection data

Sourced from the metrics-service local database — data collected from the AWX DB on the
dashboard collection schedule (default every 6 hours).

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/export/jobs/` | Paginated job execution records: template, org, project, status, started, finished, elapsed, num_hosts, launched_by |
| `GET /api/v1/export/jobs/{id}/` | Single job record |
| `GET /api/v1/export/job_host_summaries/` | Per-host results for each job: host_id, host_name, job reference |
| `GET /api/v1/export/job_host_summaries/{id}/` | Single host summary |

**Filters on `jobs/`:** `?start_date=`, `?end_date=`, `?organization_id=`, `?template_id=`, `?project_id=`, `?status=`

**Filters on `job_host_summaries/`:** `?job_data_id=`, `?job_id=`, `?host_name=`

### Daily aggregated metrics

Sourced from the metrics-service local database — pre-aggregated daily rollups from the
anonymized metrics pipeline. Contains jobs by type/launch_type/ansible_version, module
usage stats, collection stats, EE counts, and table metadata. Real collection/module names
are present (this is the pre-anonymization rollup).

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/export/daily_metrics/` | List of daily summaries (date, status, collection count) |
| `GET /api/v1/export/daily_metrics/{id}/` | Full daily summary including the complete `aggregated_metrics` JSON |

**Filters on `daily_metrics/`:** `?start_date=`, `?end_date=`, `?status=`

### Controller data (direct AWX DB)

Sourced by querying the AWX PostgreSQL database directly — the same read-only connection
metrics-service already uses for dashboard collection. No HTTP passthrough, no Gateway
routing, no additional configuration required.

| Endpoint | AWX table | Description |
|----------|-----------|-------------|
| `GET /api/v1/export/controller/host_metrics/` | `main_hostmetric` | Per-host lifetime automation tracking: hostname, first/last automation, automated_counter, deleted_counter, used_in_inventories |
| `GET /api/v1/export/controller/host_metrics/{id}/` | | Single host record |
| `GET /api/v1/export/controller/host_metric_summary/` | `main_hostmetricsummarymonthly` | Monthly license consumption: date, license_capacity, license_consumed, hosts_added, hosts_deleted, indirectly_managed_hosts |
| `GET /api/v1/export/controller/host_metric_summary/{id}/` | | Single monthly summary |
| `GET /api/v1/export/controller/instances/` | `main_instance` | Controller node topology: hostname, node_type, capacity, consumed_capacity, remaining_capacity, cpu, memory, version, node_state |
| `GET /api/v1/export/controller/instances/{id}/` | | Single instance |
| `GET /api/v1/export/controller/instance_groups/` | `main_instancegroup` | Instance group capacity: name, capacity, consumed_capacity |
| `GET /api/v1/export/controller/instance_groups/{id}/` | | Single instance group |

## Historical data depth

Not all endpoints have the same historical reach. This is a hard constraint of the underlying
data sources, not a limitation of the export API itself.

| Endpoint group | Available history | Reason |
|----------------|------------------|--------|
| `controller/host_metrics/` | Full lifetime | `main_hostmetric` is a cumulative lifetime table — one row per hostname ever seen, never cleaned up |
| `controller/host_metric_summary/` | Full lifetime | Monthly summary rows accumulate since AWX ~2.4; 36 rows = 3 years |
| `controller/instances/` | Current state only | Snapshot of live nodes — no historical record |
| `controller/instance_groups/` | Current state only | Snapshot — no historical record |
| `jobs/` | AWX retention window + time since install | See below |
| `job_host_summaries/` | Same as `jobs/` | Linked to job records |
| `daily_metrics/` | Since metrics-service install | Rollup only exists from first collection run |

### The `jobs/` and `main_unifiedjob` limitation

The job execution data in `jobs/` is sourced from `dashboard_job_data`, which is a local mirror
of `main_unifiedjob` (the AWX Controller jobs table). Two constraints bound the available history:

**1. AWX cleanup schedule**

AWX runs a `cleanup_jobs` system task that deletes records from `main_unifiedjob` older than
a configured number of days (default: 90 days). Even if a customer has been running Controller
for five years, job records older than ~90 days are already deleted from the source table.
The export API can only surface what AWX still holds.

**2. Metrics-service installation date**

`dashboard_job_data` is populated from the point metrics-service was installed (plus the initial
backfill, which itself is bounded by the AWX retention window). A customer who installs
metrics-service today starts accumulating job history from today.

In practice: a customer asking for 3 years of job execution trends will receive at most
90 days of data (or less, depending on their Controller cleanup configuration).

### The events gap

`main_jobevent` — the task-level Ansible event table (module calls, host outcomes, ok/failed/changed
per task) — is not exposed by any endpoint in this POC. This table:

- Is the largest table in any AWX deployment (often billions of rows)
- Is subject to aggressive cleanup (default: 30 days)
- Requires heavy pre-processing to be useful for BI (raw events are not human-readable without joining
  to job, template, and host records)

The metrics-service `hourly_job_events` collector exists in the codebase but is disabled by default
for the same performance reasons. Exposing event-level data — task counts, module usage, host
outcomes per task — would require enabling this collector and adding dedicated rollup tables.
This is identified as a stretch goal in ANSTRAT-1587.

## Configuration

No additional configuration is required for the POC. The AWX DB connection (`METRICS_SERVICE_DATABASES__awx__*`)
is already required for existing dashboard collection and is reused by the controller endpoints.

## Architecture decisions

- **No HTTP passthrough to Controller API**: all controller data is read directly from the AWX
  PostgreSQL database. This avoids Gateway WIT token complexity, Envoy routing constraints, and
  adds no dependency on Controller API availability.
- **On by default**: no feature flag gate. Endpoints are always available to authenticated
  system admins and platform auditors.
- **Raw JSON output**: no pre-processing or BI-specific formatting. BI tools consume and
  transform the data themselves.
- **Task-backing deferred**: the controller endpoints use direct SQL queries from the web
  container. For production/GA, `host_metrics` in particular should be moved to a scheduled
  collection task (like `dashboard_job_data`) to avoid live AWX DB load from BI polling.

## What comes next

- Enable `hourly_job_events` collector and add event-level rollup for module/task analytics
- Add `counts` snapshot collector (org/host/user/template counts — currently a gap vs CRC)
- Add `host_metric_table` incremental collector for richer host lifecycle data
- Task-back `host_metrics` endpoint before GA to remove live AWX DB dependency
- Validate with a real BI tool (Looker or Power BI) against a pilot customer environment
