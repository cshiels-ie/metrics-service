# AWX Mock Database - Implementation Status

## ✅ Completed

### Infrastructure

- ✅ Docker Compose setup with PostgreSQL 15 on port 5555
- ✅ Custom Dockerfile with Python 3 and required dependencies (psycopg2-binary, faker)
- ✅ Automatic initialization on first startup
- ✅ Volume persistence for database data

### Schema Generation

- ✅ Schema parser that converts `Schema.sql` INSERT statements to CREATE TABLE DDL
- ✅ Support for 191 AWX tables
- ✅ Auto-increment ID columns (SERIAL/BIGSERIAL)
- ✅ SQL reserved keyword quoting (e.g., "limit")
- ✅ Foreign key index creation
- ✅ Generated schema: `init/01-create-schema.sql` (122KB, 2,700+ lines)

### Mock Data Generator

- ✅ Python script with Faker library for realistic data
- ✅ Unix socket connection for Docker init phase
- ✅ Relationship-aware data generation
- ✅ Working generation for:
  - Django framework tables (content types)
  - Users (10 users with admin)
  - Organizations (5 orgs with max_hosts)
  - Teams (10 teams)
  - Credential types (6 types)
  - Credentials (15 credentials)

### Documentation

- ✅ Comprehensive README.md with usage instructions
- ✅ Connection details and examples
- ✅ Query examples
- ✅ Troubleshooting guide

## ⚠️ Partial Implementation

### Data Generation

The mock data generator successfully creates data for core tables but needs AWX-specific column mappings for full table coverage:

**Working:**

- ✅ auth_user
- ✅ main_organization
- ✅ main_team
- ✅ main_credentialtype
- ✅ main_credential

**Needs Column Mapping:**

- ⚠️ main_project (uses different column names)
- ⚠️ main_inventory
- ⚠️ main_host
- ⚠️ main_jobtemplate
- ⚠️ main_job
- ⚠️ Other AWX-specific tables

## 🔧 To Complete Full Implementation

To generate mock data for ALL tables, you would need to:

1. **Query actual AWX schema** to get exact column names and requirements
2. **Update data generator** with AWX-specific field names:
   ```python
   # Example: AWX uses 'unified_job_template_id' not 'template_id'
   # Example: Some tables don't have 'name' but use 'summary' or 'title'
   ```
3. **Add required fields** that have NOT NULL constraints
4. **Handle AWX-specific relationships** (e.g., unified jobs, polymorphic associations)

## 📋 Usage

### Start the Database

```bash
cd tools/mock-awx-db
docker-compose up -d
```

### Connect

```bash
psql -h localhost -p 5555 -U awx -d awx_mock
# Password: awxpass
```

### Check Current Data

```sql
SELECT COUNT(*) FROM auth_user;          -- Should show 10
SELECT COUNT(*) FROM main_organization;   -- Should show 5
SELECT COUNT(*) FROM main_team;          -- Should show 10
SELECT COUNT(*) FROM main_credential;     -- Should show 15
```

## 🎯 Current State

**The framework is complete and operational:**

- ✅ All 191 tables are created with proper schema
- ✅ Database is accessible on port 5555
- ✅ Partial mock data generation works
- ✅ Easy to extend with AWX-specific column mappings

**What you can do now:**

- Use the database structure for testing schema queries
- Manually insert data for specific use cases
- Extend the data generator with correct AWX field names
- Query the table structure to understand AWX schema

## 📝 Next Steps

If you need full mock data generation:

1. Compare generated schema with actual AWX database schema
2. Create a column mapping file (`awx_column_mappings.py`)
3. Update `MockDataGenerator` methods with actual column names
4. Add missing required fields for each table type

The foundation is solid - it just needs AWX-specific details!
