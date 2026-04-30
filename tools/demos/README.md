# Metrics Service — Demo Environment

A self-contained Docker Compose environment that starts a fully functional
metrics-service stack alongside a seeded AWX controller database and Grafana.

## What's included

| Service | Container | URL / Port |
|---|---|---|
| PostgreSQL (both DBs) | `demo-postgres` | `localhost:5432` |
| Metrics Service API | `demo-metrics-web` | http://localhost:8000 |
| Metrics Service dispatcher | `demo-metrics-dispatcher` | — |
| Metrics Service scheduler | `demo-metrics-scheduler` | — |
| Grafana | `demo-grafana` | http://localhost:3000 |

### Database layout (single PostgreSQL instance)

| Database | User | Password | Contents |
|---|---|---|---|
| `awx` | `awx` | `awx` | Full AWX controller schema + sample jobs, hosts, credentials, instances |
| `metrics_service` | `metrics_service` | `metrics_service` | Metrics service application data |

### Sample AWX data (seeded on first boot)

- **5 controller instances** — versions 4.7.2, 1.0, 24.1.0, 24.2.0, 23.5.0
- **Unified jobs** — 3 jobs per hour for 2 hours (2025-06-13 10:00 and 11:00)
- **Job events** — partitioned `main_jobevent` table with events per job
- **Job host summaries** — 2 hosts × 3 jobs per hour
- **Credentials** — 5 types, linked to jobs
- **Host metrics** — 3 inventories × 10 hosts
- **Feature flags** — 3 DAB feature flags

## Quick start

```bash
cd tools/demos

# Optional: copy and edit port overrides
cp .env.example .env

# Build and start everything
docker compose up --build
```

After the `demo-metrics-init` container exits successfully it will print:

```
=== BI Connector Token ===
  Authorization: Token <token>

  curl -H "Authorization: Token <token>" http://localhost:8000/api/v1/bi/metrics/daily/
```

## Access

### Metrics Service

```bash
# API root
curl http://localhost:8000/api/v1/

# Interactive API docs
open http://localhost:8000/api/docs/

# Login: demo_admin / demo_password
```

### Grafana

Open http://localhost:3000 — login with **admin / admin**.

A pre-built **Metrics Service — Overview** dashboard is available under the
_Metrics Service_ folder. It shows:

- Task status distribution and counts
- Daily metrics summaries
- Hourly collection breakdown by collector type
- Recent tasks table
- Live AWX job and instance tables (queried directly from the AWX DB)

Two datasources are pre-provisioned:

| Name | Type | Database |
|---|---|---|
| Metrics Service DB | PostgreSQL | `metrics_service` |
| AWX Controller DB | PostgreSQL | `awx` |

### BI Connector (Infinity datasource)

The BI connector feature flag is enabled automatically. To use it with
the Grafana Infinity datasource:

1. Copy the token printed by `demo-metrics-init` at startup, or retrieve it:

```bash
docker logs demo-metrics-init 2>&1 | grep "Token "
```

2. In Grafana → Connections → Data sources → **Metrics Service BI Connector**:
   - Add a Custom HTTP Header: `Authorization` = `Token <your-token>`
   - Save & test

3. Example panels you can build:
   - **URL:** `http://demo-metrics-web:8000/api/v1/bi/metrics/daily/`  
     Parser: JSON, Rows root: `results`
   - **URL:** `http://demo-metrics-web:8000/api/v1/bi/controller/snapshot/`  
     Parser: JSON

## Stopping and cleaning up

```bash
# Stop (keep data volumes)
docker compose down

# Stop and delete data volumes (fresh start)
docker compose down -v
```

## Re-seeding the AWX database

The AWX schema and sample data are loaded from `awx-db/init-*.sql` **only on
first boot** (when the `demo_metrics_service_postgres` volume is empty).

To reload:

```bash
docker compose down -v   # delete volumes
docker compose up --build
```

## Adding more AWX data

Edit the SQL files in `awx-db/` and restart with a fresh volume:

```bash
docker compose down -v && docker compose up --build
```

The SQL files are sourced from `metrics-utility/tools/docker/` — see that
repo for the full schema reference (`init-1-schema.sql` = AWX `latest.sql`).

## Useful commands

```bash
# Tail all logs
docker compose logs -f

# Tail a single service
docker compose logs -f demo-metrics-web

# Run a Django management command
docker exec demo-metrics-web python manage.py shell

# Connect to Metrics Service DB
docker exec -it demo-postgres psql -U metrics_service -d metrics_service

# Connect to AWX DB
docker exec -it demo-postgres psql -U awx -d awx

# Re-generate BI connector token
docker exec demo-metrics-web python manage.py drf_create_token demo_admin
```
