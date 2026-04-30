# BI Connector

This service exposes three sets of read-only REST API endpoints that BI tools can query directly.

- **Layer 1** — Pre-aggregated daily/hourly metrics from the metrics-service DB. Fast, no AWX load.
- **Layer 2** — Live data from the AWX DB. Async: returns a task ID immediately, collect result once complete.
- **Layer 3** — Job execution data collected by the DASHBOARD_COLLECTION task group. Ready to query, no AWX load.

---

## Setup

### 1. Enable the feature flag

The BI connector is disabled by default. Enable it at runtime — no restart required:

```bash
# Via environment variable
METRICS_SERVICE_FEATURE_ENABLED__BI_CONNECTOR=true

# Or toggle FEATURE_BI_CONNECTOR_ENABLED via the DAB feature flags admin UI
```

Layer 3 (dashboard data) additionally requires the DASHBOARD_COLLECTION flag:

```bash
METRICS_SERVICE_FEATURE_ENABLED__DASHBOARD_COLLECTION=true
```

All endpoints return `404 Not Found` while the flag is off.

### 2. Create a service account token

```bash
uv run ./manage.py drf_create_token <username>
```

Pass the token in every request:

```
Authorization: Token <your-token>
```

---

## Rate Limits

Authenticated users are throttled to **30 requests per hour** across all BI connector endpoints. Exceeding the limit returns `429 Too Many Requests`.

Layer 2 endpoints use an async poll pattern — budget your 30 requests across both the initial collection trigger and the status polls. A single collection typically requires 2–5 polls before completing.

---

## Endpoints

### Layer 1 — Pre-aggregated metrics (metrics-service DB)

These return data already collected and rolled up by the metrics pipeline. Fast, no AWX DB load.

| Endpoint | Description | Key filters |
|---|---|---|
| `GET /api/v1/bi/metrics/daily/` | List daily summaries | `summary_date`, `summary_date__gte`, `summary_date__lte`, `status` |
| `GET /api/v1/bi/metrics/daily/<date>/` | Single day detail (e.g. `2025-06-13`) | — |
| `GET /api/v1/bi/metrics/hourly/` | List hourly collections | `collector_type`, `collection_timestamp__gte`, `collection_timestamp__lte`, `status` |
| `GET /api/v1/bi/metrics/hourly/<id>/` | Single hourly record with raw data | — |

The daily list endpoint flattens `aggregated_metrics` into top-level fields per collector type:

- `metrics_unified_jobs`
- `metrics_job_host_summary_service`
- `metrics_credentials_service`
- `metrics_main_jobevent_service`
- `metrics_execution_environments`
- `metrics_controller_version_service`
- `metrics_table_metadata`

The detail endpoint (`/daily/<date>/`) additionally includes `aggregated_metrics` (the raw blob) and `hourly_collection_ids`.

#### Pagination

List endpoints are paginated. The response envelope:

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/bi/metrics/daily/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

#### Example daily summary response

```json
{
  "id": 1,
  "summary_date": "2025-06-13",
  "status": "aggregated",
  "hourly_collections_count": 24,
  "missing_hours": [],
  "aggregation_completed_at": "2025-06-14T01:05:32Z",
  "error_message": "",
  "config_data": {},
  "metrics_unified_jobs": { "jobs_total": 1200, "jobs_successful": 1150 },
  "metrics_job_host_summary_service": { "hosts_total": 340 },
  "metrics_credentials_service": { "usage_count": 88 },
  "metrics_main_jobevent_service": {},
  "metrics_execution_environments": { "ee_count": 5 },
  "metrics_controller_version_service": { "version": "4.5.0" },
  "metrics_table_metadata": { "unified_job_count": 12400 },
  "created": "2025-06-14T01:05:32Z",
  "modified": "2025-06-14T01:05:32Z"
}
```

---

### Layer 2 — Live Controller data (AWX DB) — async

These query the AWX database directly. Because a 7-day collection can take tens of seconds, the endpoints are **asynchronous**: the initial request returns `202 Accepted` immediately with a task ID, and the BI tool polls until the collection completes.

#### Time-series endpoints (async)

| Endpoint | Collector | Max window |
|---|---|---|
| `GET /api/v1/bi/controller/jobs/` | Unified jobs | 7 days |
| `GET /api/v1/bi/controller/hosts/` | Job host summaries | 7 days |
| `GET /api/v1/bi/controller/credentials/` | Credentials usage | 7 days |
| `GET /api/v1/bi/controller/events/` | Job events (event modules) | **3 days** |

`since` and `until` must be ISO 8601 datetimes. Requests exceeding the max window return `400`.

**202 response:**

```json
{
  "task_id": 42,
  "status": "pending",
  "collector_type": "unified_jobs",
  "results_url": "/api/v1/tasks/42/"
}
```

**Deduplication:** if an identical collection (same endpoint + same `since`/`until`) is already running, the existing `task_id` is returned — no duplicate AWX query is started.

**Polling:** `GET /api/v1/tasks/<task_id>/` returns the task status and, once complete, the result data:

```json
{
  "id": 42,
  "status": "completed",
  "result_data": {
    "status": "success",
    "collector_type": "unified_jobs",
    "since": "2025-03-01T00:00:00+00:00",
    "until": "2025-03-07T23:59:59+00:00",
    "data": [ ... ]
  }
}
```

If the task fails, `status` is `"failed"` and `result_data.error` contains the reason.

#### Snapshot endpoint (synchronous)

```
GET /api/v1/bi/controller/snapshot/
```

Point-in-time snapshot of execution environments, controller version, table metadata, and config. Remains synchronous — fast query, no date window.

Optional `?collectors=` query param to subset results:

```
GET /api/v1/bi/controller/snapshot/?collectors=config,controller_version_service
```

**Response:**

```json
{
  "collected_at": "2025-06-13T10:22:11.543210+00:00",
  "collectors": {
    "execution_environments": { ... },
    "controller_version_service": { "version": "4.5.0" },
    "table_metadata": { ... },
    "config": { ... }
  },
  "errors": {}
}
```

Returns `200` even when individual collectors fail — the failed key appears in `errors` and is absent from `collectors`.

---

### Layer 3 — Dashboard collected data (metrics-service DB)

Pre-collected AWX job execution data, synced incrementally every 6 hours by the `DASHBOARD_COLLECTION` task group. Query directly with no AWX DB load.

| Endpoint | Description | Key filters |
|---|---|---|
| `GET /api/v1/bi/dashboard/jobs/` | List job execution records | `finished__gte`, `finished__lte`, `status`, `template_id`, `organization_id`, `project_id` |
| `GET /api/v1/bi/dashboard/jobs/<job_id>/` | Single job with label IDs and host summaries | — |
| `GET /api/v1/bi/dashboard/templates/` | Template time estimates (manual/automation minutes) | `template_id`, `template_name__icontains` |
| `GET /api/v1/bi/dashboard/templates/<template_id>/` | Single template detail | — |

The job list response inlines template metadata as flat columns (`template_time_manual_minutes`, `template_time_automation_minutes`) so BI tools get a single joined row per job.

The job detail response adds `label_ids` (list of AWX label IDs) and `host_summaries` (list of `{host_summary_id, host_id, host_name}`).

Data availability depends on `DASHBOARD_COLLECTION` being enabled. Endpoints return empty results (not errors) if no data has been collected yet.

---

## Example requests

```bash
TOKEN="your-token-here"

# --- Layer 1 ---

# Daily summary list — last 30 days
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/metrics/daily/?summary_date__gte=2025-05-14"

# Single day detail
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/metrics/daily/2025-06-13/"

# Hourly collections for unified_jobs
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/metrics/hourly/?collector_type=unified_jobs"

# --- Layer 2 (async) ---

# Step 1 — kick off the collection
RESPONSE=$(curl -s -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/controller/jobs/?since=2025-03-01T00:00:00Z&until=2025-03-07T23:59:59Z")
TASK_ID=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

# Step 2 — poll until complete
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/tasks/$TASK_ID/"
# Repeat until "status": "completed", then read result_data.data

# Snapshot (synchronous, no polling needed)
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/controller/snapshot/?collectors=config,controller_version_service"

# --- Layer 3 ---

# Jobs finished in the last 7 days, failed only
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/dashboard/jobs/?status=failed&finished__gte=2025-06-06T00:00:00Z"

# Single job detail with labels and host summaries
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/dashboard/jobs/12345/"

# Template time estimates
curl -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/bi/dashboard/templates/?template_name__icontains=deploy"
```

---

## Troubleshooting

| Status | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | No or invalid token | Check `Authorization: Token <token>` header |
| `403 Forbidden` | Token valid but user lacks permission | Ensure the user has API access |
| `404 Not Found` | BI connector feature flag is disabled | Set `METRICS_SERVICE_FEATURE_ENABLED__BI_CONNECTOR=true` |
| `400 Bad Request` | Missing or invalid `since`/`until`, or range exceeds max window | Use ISO 8601 datetimes; check the `detail` field in the response |
| `429 Too Many Requests` | Rate limit exceeded (30 req/hour) | Reduce polling frequency; note each poll counts toward the limit |
| `202 Accepted` (Layer 2) | Collection started — not an error | Poll `results_url` until `status == "completed"` |
| `500 Internal Server Error` | Collector raised an exception (Layer 2: visible in `result_data.error` after task completes) | Check service logs |
| `503 Service Unavailable` | AWX DB connection failed (snapshot endpoint only) | Verify the AWX DB alias is configured and reachable |

---

## Testing with Grafana

[Grafana](https://grafana.com/) with the [Infinity datasource plugin](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) can call the REST endpoints directly — no database driver needed.

> **Note:** Grafana Infinity does not natively support the async poll pattern. Use Layer 1 or Layer 3 endpoints for live Grafana dashboards. For Layer 2 data, schedule a separate collection job and point Grafana at the task result URL once complete.

### Install

```bash
brew install grafana

# Install the Infinity plugin
sudo chown -R $(whoami) /usr/local/var/lib/grafana/plugins
grafana cli plugins install yesoreyeram-infinity-datasource
brew services restart grafana
```

Open `http://localhost:3000` (default credentials: admin / admin).

### Add the datasource

1. **Connections → Add new connection → search "Infinity"**
2. Set base URL to `http://127.0.0.1:8000`
3. Under **Auth → Custom HTTP Headers**, add:
   - Header: `Authorization`
   - Value: `Token <your-token>`
4. Save and test

### Example panels

**Daily jobs trend (time series)**
- Type: Time series
- URL: `http://127.0.0.1:8000/api/v1/bi/metrics/daily/`
- Parser: JSON / Rows root: `results`
- Columns: `summary_date`, `metrics_unified_jobs.jobs_total`

**Dashboard job status breakdown (table)**
- URL: `http://127.0.0.1:8000/api/v1/bi/dashboard/jobs/?finished__gte=2025-06-01T00:00:00Z`
- Parser: JSON / Rows root: `results`
- Columns: `job_id`, `template_name`, `status`, `elapsed`, `finished`

**Current Controller state (stat panels)**
- URL: `http://127.0.0.1:8000/api/v1/bi/controller/snapshot/`
- Parser: JSON
- Extract from `collectors.controller_version_service`, `collectors.table_metadata`

---

## Alternative BI tools

### Metabase (connects to PostgreSQL directly)

```bash
docker run -d -p 3001:3000 --name metabase metabase/metabase
```

Connect to the metrics-service PostgreSQL database. Query `tasks_dailymetricssummary`, `tasks_hourlymetricscollection`, `dashboard_job_data`, and `dashboard_template_metadata` directly via SQL. JSON column extraction requires `->` / `->>` operators.

### Evidence (SQL-driven, code-based)

```bash
npx degit evidence-dev/template my-metrics-reports
cd my-metrics-reports && npm install && npm run dev
```

Write SQL in markdown files connected to the metrics-service PostgreSQL.

---

## Building a custom connector (.mez / .taco)

For enterprise BI tools (Tableau, Power BI) that require a native connector:

1. **Auth** — Use the token endpoint or configure OAuth2 (`ansible_base.oauth2_provider` is included)
2. **Layer 1 & 3** — Call with date range filters, handle the paginated `results` array; declare flat column schemas
3. **Layer 2 (async)** — Implement a request/poll loop:
   - `GET /api/v1/bi/controller/<type>/?since=...&until=...` → capture `task_id`
   - Poll `GET /api/v1/tasks/<task_id>/` until `status == "completed"`
   - Read rows from `result_data.data`
4. **Schema** — Map flat fields from Layer 1/3 and `result_data.data` from Layer 2 to typed columns

From the BI tool's perspective it is one data source. The split between layers is an implementation detail — Layer 1/3 are fast reads, Layer 2 is async and suitable for scheduled/nightly refreshes rather than interactive queries.
