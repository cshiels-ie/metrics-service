# AWX Mock Database

A standalone Docker Compose environment that provides a PostgreSQL database with AWX-like schema and realistic mock data.

## Overview

This tool creates a complete AWX-compatible database with:

- **191 tables** from AWX schema (auth, organizations, teams, inventories, hosts, jobs, workflows, etc.)
- **Realistic mock data** with proper relationships and foreign keys
- **PostgreSQL 15** running on port **5555** (to avoid conflicts with other services)
- **Automatic initialization** on first startup

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Port 5555 available (or modify `docker-compose.yml` to use a different port)

### Start the Database

```bash
cd tools/mock-awx-db
docker-compose up -d
```

The first startup will:

1. Create the PostgreSQL container
2. Initialize the `awx_mock` database
3. Create all 191 tables from the AWX schema
4. Generate and insert realistic mock data (~2000-3000 records)

This process takes approximately 2-5 minutes on the first run.

### Check Logs

```bash
docker-compose logs -f postgres
```

Look for the message "Mock data generation completed successfully!" to confirm initialization is complete.

### Connection Details

```
Host: localhost
Port: 5555
Database: awx_mock
User: awx
Password: awxpass
```

### Connect to the Database

#### Using psql

```bash
psql -h localhost -p 5555 -U awx -d awx_mock
# Password: awxpass
```

#### Using Python

```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5555,
    database="awx_mock",
    user="awx",
    password="awxpass"
)
```

#### Connection String

```
postgresql://awx:awxpass@localhost:5555/awx_mock
```

## Database Schema

The database contains 191 tables organized into these categories:

### Core Tables

- `auth_user` - User accounts (10 users including admin)
- `main_organization` - Organizations (5 orgs)
- `main_team` - Teams (10 teams)
- `django_content_type` - Content types for Django

### Inventory Management

- `main_inventory` - Inventories (10 inventories)
- `main_group` - Inventory groups (25 groups)
- `main_host` - Managed hosts (50 hosts with IP addresses)
- `main_inventorysource` - Dynamic inventory sources

### Job Management

- `main_jobtemplate` - Job templates (15 templates)
- `main_job` - Job executions (100 jobs with various statuses)
- `main_jobevent` - Job events (500+ events)
- `main_jobhostsummary` - Job execution summaries per host (200 summaries)

### Project Management

- `main_project` - Projects (8 projects)
- `main_projectupdate` - Project update history
- `main_projectupdateevent` - Project update events

### Credentials

- `main_credentialtype` - Credential types (SSH, AWS, GCE, etc.)
- `main_credential` - Stored credentials (15 credentials)

### Workflows

- `main_workflowjobtemplate` - Workflow templates (5 workflows)
- `main_workflowjob` - Workflow executions (20 workflow jobs)
- `main_workflowjobnode` - Workflow nodes

### RBAC (Role-Based Access Control)

- `dab_rbac_*` - Django-Ansible-Base RBAC tables
- `main_rbac_*` - AWX RBAC tables

### Activity Stream

- `main_activitystream` - Audit log of all changes
- `main_activitystream_*` - Activity stream relations

## Mock Data Details

### Data Volume

- **Core tables**: 5-10 rows each
- **Junction tables**: 10-30 rows
- **Event tables**: 50-100 rows per table
- **Total**: ~2000-3000 records

### Data Characteristics

#### Users

- 10 users with realistic names and emails
- First user is `admin` (superuser)
- Mixed staff/non-staff users

#### Organizations & Teams

- 5 organizations with company names
- 10 teams distributed across organizations
- Proper creator/modifier relationships

#### Inventories & Hosts

- 10 inventories
- 25 groups
- 50 hosts with:
  - Realistic hostnames (e.g., `server-001.example.com`)
  - IP addresses
  - Variables (ansible_host, ansible_port)

#### Jobs

- 100 job executions with:
  - Various statuses: successful (60%), failed (20%), running (10%), pending (5%), etc.
  - Realistic timestamps (last 60 days)
  - Started/finished times
  - Elapsed time calculations
- 500+ job events per job
- 200 host summaries with task statistics

#### Projects

- 8 projects with:
  - SCM URLs (Git/SVN)
  - Branch names
  - SCM revisions
  - Various statuses

#### Workflows

- 5 workflow templates
- 20 workflow job executions
- Realistic workflow execution times

## Management Commands

### Stop the Database

```bash
docker-compose down
```

**Note**: This preserves data in the `awx_mock_data` volume.

### Stop and Remove Data

```bash
docker-compose down -v
```

This will delete the volume and all data. Next startup will regenerate everything.

### Restart the Database

```bash
docker-compose restart
```

### View Database Logs

```bash
docker-compose logs postgres
```

### Execute SQL Directly

```bash
docker-compose exec postgres psql -U awx -d awx_mock -c "SELECT COUNT(*) FROM main_job;"
```

## Development and Customization

### Regenerate Schema from Schema.sql

If the Schema.sql file is updated:

```bash
cd scripts
python3 parse-schema.py
```

This regenerates `init/01-create-schema.sql`.

### Modify Mock Data Generation

Edit `init/02-insert-data.py` to customize:

- Number of records per table
- Data patterns and relationships
- Status distributions
- Timestamp ranges

After modifying, rebuild:

```bash
docker-compose down -v
docker-compose up -d
```

### Add Additional Tables

1. Update `Schema.sql` with new table definitions
2. Run `scripts/parse-schema.py` to regenerate DDL
3. Add data generation logic to `init/02-insert-data.py`
4. Rebuild the database

## Querying the Mock Data

### Example Queries

#### List all organizations

```sql
SELECT id, name, description, created
FROM main_organization
ORDER BY created DESC;
```

#### Count jobs by status

```sql
SELECT status, COUNT(*) as count
FROM main_job
GROUP BY status
ORDER BY count DESC;
```

#### Find recently failed jobs

```sql
SELECT j.id, j.name, j.status, j.started, j.finished, jt.name as template
FROM main_job j
JOIN main_jobtemplate jt ON j.job_template_id = jt.id
WHERE j.status = 'failed'
ORDER BY j.finished DESC
LIMIT 10;
```

#### Host inventory summary

```sql
SELECT i.name as inventory, COUNT(h.id) as host_count
FROM main_inventory i
LEFT JOIN main_host h ON h.inventory_id = i.id
GROUP BY i.id, i.name
ORDER BY host_count DESC;
```

#### Job success rate per template

```sql
SELECT
    jt.name,
    COUNT(*) as total_jobs,
    SUM(CASE WHEN j.status = 'successful' THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN j.status = 'successful' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM main_jobtemplate jt
LEFT JOIN main_job j ON j.job_template_id = jt.id
GROUP BY jt.id, jt.name
HAVING COUNT(*) > 0
ORDER BY success_rate DESC;
```

## Troubleshooting

### Port 5555 Already in Use

Edit `docker-compose.yml` and change the port mapping:

```yaml
ports:
  - "5556:5432"  # Change 5555 to any available port
```

### Data Generation Takes Too Long

The first initialization can take 2-5 minutes. If it's stuck:

1. Check logs: `docker-compose logs -f postgres`
2. Verify the container is running: `docker-compose ps`
3. If initialization fails, restart: `docker-compose down -v && docker-compose up -d`

### Connection Refused

Wait for the database to fully initialize. Check status:

```bash
docker-compose exec postgres pg_isready -U awx -d awx_mock
```

### Reset Everything

To completely reset and start fresh:

```bash
docker-compose down -v
docker system prune -f
docker-compose up -d
```

## Architecture

### Initialization Flow

1. **Docker Compose starts** → PostgreSQL 15 container
2. **Container initialization** → Database `awx_mock` created
3. **01-create-schema.sql** → All 191 tables created with indexes
4. **02-insert-data.sh** → Installs Python dependencies
5. **02-insert-data.py** → Generates and inserts mock data
6. **Database ready** → Available on port 5555

### Files Structure

```
tools/mock-awx-db/
├── docker-compose.yml          # Docker Compose configuration
├── requirements.txt            # Python dependencies for local development
├── README.md                   # This file
├── init/
│   ├── 01-create-schema.sql    # Generated DDL (191 tables)
│   ├── 02-insert-data.sh       # Shell wrapper for data generation
│   └── 02-insert-data.py       # Mock data generator
└── scripts/
    └── parse-schema.py         # Schema parser (Schema.sql → DDL)
```

## Integration with Metrics Service

While this is a standalone tool, you can use it to test metrics collection:

```python
# In your metrics service code
from sqlalchemy import create_engine

# Connect to mock AWX database
engine = create_engine('postgresql://awx:awxpass@localhost:5555/awx_mock')

# Query job metrics
result = engine.execute("""
    SELECT status, COUNT(*)
    FROM main_job
    WHERE finished > NOW() - INTERVAL '7 days'
    GROUP BY status
""")
```

## Performance Notes

- **Initial startup**: 2-5 minutes (first time only)
- **Subsequent startups**: 5-10 seconds
- **Database size**: ~50-100 MB with mock data
- **Memory usage**: ~100-200 MB
- **Queries**: Indexed for common patterns (foreign keys)

## Security Notes

⚠️ **This is for development/testing only!**

- Default credentials are hardcoded
- No SSL/TLS encryption
- No backup strategy
- Not suitable for production use
- Data is randomly generated and not secure

## License

This tool is part of the metrics-service project. See the main repository for license information.
