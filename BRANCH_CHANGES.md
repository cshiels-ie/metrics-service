# Dashboard-Support Branch Changes

## Branch Information

- **Branch Name**: Dashboard-Support
- **Base Branch**: devel
- **Total Commits**: 3
- **Files Changed**: 32 files
- **Lines Added**: 4,340+ lines
- **Lines Removed**: 2 lines

## Summary

This branch introduces comprehensive dashboard reporting capabilities for the automation-reports and aap-ui frontend integration. The implementation adds a complete REST API for managing dashboard metrics, filter options, user preferences, and settings, with robust caching mechanisms for optimal performance.

## Commits Overview

### 1. Add dashboard_reports app for automation-reports integration (5dc69b5)

**Core Implementation:**

- Introduced the `dashboard_reports` Django app as the foundation for automation-reports integration
- Implemented `DashboardReportCache` model to store pre-calculated metrics data, enhancing API response times
- Created comprehensive API endpoints for retrieving dashboard reports with pagination and date range filtering
- Added background tasks for collecting dashboard data from the database with scheduled execution capabilities
- Updated project settings to include the new app and its feature flag for customer opt-in

**Key Features:**

- **Models**: `DashboardReportCache` for caching job templates, top projects, and top users data
- **Tasks**: Automated collection tasks for populating cache with metrics data
- **API Views**: RESTful endpoints for dashboard data retrieval
- **Serializers**: Data transformation layer for frontend consumption

**Purpose:** Improve efficiency of dashboard data retrieval and enhance user experience in the automation-reports frontend

---

### 2. Add AWX query functions and dashboard models for filter options (2dd11e6)

**Database Integration:**

- Introduced `awx_queries.py` module with functions to fetch real-time filter options from the AWX database:
  - Organizations lookup
  - Projects lookup
  - Labels/tags lookup
  - Instance/execution environment lookup
  - Cluster information

**New Models:**

- **`Currency`**: Manage currency options for cost calculations in dashboards
- **`UserPreference`**: Store user-specific settings and preferences
- **`FilterSet`**: Manage saved filter views for users
- **`TemplateMetadata`**: Template metadata overrides for customization

**API Enhancements:**

- Implemented serializers for all new models to ensure API compatibility
- Updated URL routing to include new endpoints for template options and user preferences
- Enhanced views to support dynamic filter options and OAuth settings for AAP integration
- Added cost settings update endpoints

**Purpose:** Enable dynamic filter options and user-specific settings, improving the overall user experience

---

### 3. Added additional Changes (4ac3599)

**Refinements:**

- Enhanced serializers in `apps/dashboard_reports/serializers.py` (12 lines modified)
- Updated URL routing in `apps/dashboard_reports/urls.py` (8 lines modified)
- Significant view enhancements in `apps/dashboard_reports/views.py` (82 lines added, 4 removed)

**Improvements:**

- Refined API endpoint behavior
- Enhanced error handling and validation
- Improved response formatting
- Additional edge case handling

---

## New Files and Directories

### Dashboard Reports App (`apps/dashboard_reports/`)

```
apps/dashboard_reports/
├── README.md                     # Comprehensive API documentation (413 lines)
├── __init__.py
├── admin.py                      # Django admin configuration
├── apps.py                       # App configuration
├── awx_queries.py               # AWX database query functions (258 lines)
├── models.py                     # Database models (371 lines)
├── serializers.py               # DRF serializers (338 lines)
├── tasks.py                      # Background collection tasks (171 lines)
├── tests.py                      # Test suite placeholder
├── urls.py                       # API URL routing (78 lines)
├── views.py                      # API view implementations (1,116 lines)
└── migrations/
    ├── 0001_initial.py
    ├── 0002_add_currency_filterset_templatemetadata_userpreference.py
    ├── 0003_initialize_currencies.py
    └── 0004_initialize_dashboard_settings.py
```

### Test Suite (`tests/`)

```
tests/
├── integration/dashboard_reports/
│   ├── __init__.py
│   └── test_api_endpoints.py    # Integration tests (394 lines)
└── unit/dashboard_reports/
    ├── __init__.py
    └── test_serializers.py       # Unit tests (325 lines)
```

### Task System Updates

- `apps/tasks/migrations/0002_dashboardreportcache.py` - Cache model migration
- `apps/tasks/task_groups.py` - Task group definitions (20 lines)
- `apps/tasks/tasks.py` - Task function implementations (29 lines)
- `apps/tasks/tasks_collector.py` - Collector updates (6 lines)
- `apps/tasks/v1/serializers.py` - Task serializers (112 lines)
- `apps/tasks/v1/views.py` - Task API views (215 lines)

### Configuration and Settings

- `apps/settings/defaults.py` - Dashboard settings defaults (43 lines)
- `local_settings.py` - Local development settings
- `test_dashboard_api.py` - Standalone API tests (120 lines)
- `pyproject.toml` - Updated dependencies

---

## API Endpoints Implemented

### Critical Endpoints (Week 1)

1. **`GET /api/v1/template_options/`** - Master filter options aggregation
   - Returns all filter dropdowns, settings, currencies, saved views
   - Combines data from Settings model, AWX database, and user preferences

2. **`POST /api/v1/common/settings/`** - User preferences management
   - Save currency selection and custom preferences
   - Per-user settings storage

### Data Management Endpoints (Week 2)

**Template Metadata:**

3. `GET /api/v1/templates/` - List template metadata
4. `GET /api/v1/templates/{template_id}/` - Get specific template metadata
5. `PUT /api/v1/templates/{template_id}/` - Update template overrides
6. `POST /api/v1/templates/` - Create template metadata
7. `DELETE /api/v1/templates/{template_id}/` - Delete template metadata

**Saved Views:**

8. `GET /api/v1/common/filter_set/` - List saved filter views
9. `POST /api/v1/common/filter_set/` - Create saved view
10. `PUT /api/v1/common/filter_set/{id}/` - Update saved view
11. `DELETE /api/v1/common/filter_set/{id}/` - Delete saved view

### Individual Filter Endpoints

12. `GET /api/v1/template_options/organizations/` - Organizations list
13. `GET /api/v1/template_options/projects/` - Projects list
14. `GET /api/v1/template_options/labels/` - Labels list

---

## Database Schema Changes

### New Models

1. **DashboardReportCache** (`dashboard_report_cache` table)
   - `cache_key` (CharField, unique, indexed)
   - `report_type` (CharField, choices: job_templates, top_projects, top_users)
   - `data` (JSONField)
   - `date_range_start` (DateTimeField, indexed)
   - `date_range_end` (DateTimeField, indexed)
   - Indexes: `report_type + modified`, `cache_key + modified`

2. **Currency** (currency management for cost calculations)
3. **UserPreference** (user-specific settings storage)
4. **FilterSet** (saved filter views)
5. **TemplateMetadata** (template customization overrides)

### Migrations Applied

- `0001_initial.py` - Initial DashboardReportCache model
- `0002_add_currency_filterset_templatemetadata_userpreference.py` - Additional models
- `0003_initialize_currencies.py` - Seed default currency data
- `0004_initialize_dashboard_settings.py` - Initialize dashboard configuration
- `apps/tasks/migrations/0002_dashboardreportcache.py` - Task system integration

---

## Background Tasks Added

### Dashboard Collection Tasks

**Task Function:** `collect_dashboard_reports()`

**Purpose:** Periodic collection of dashboard metrics from the database

**Features:**
- Scheduled execution via cron or manual trigger
- Populates DashboardReportCache with pre-calculated data
- Supports date range filtering
- Task-driven cache invalidation (no TTL)

**Integration:** Integrated with existing task management system in `apps/tasks/`

---

## Architecture Overview

```
automation-reports Frontend (TypeScript/React)
            ↓
    REST API (Django REST Framework)
            ↓
    ┌─────────────────┬─────────────────┐
    │                 │                 │
DashboardReportCache  AWX Database    Settings
(Cached Metrics)    (Real-time Filters) (Config)
```

### Data Flow

1. **Frontend Request** → API endpoint (e.g., `/api/v1/template_options/`)
2. **API Layer** → Aggregates data from:
   - `DashboardReportCache` (pre-calculated metrics)
   - AWX Database (real-time filter options via `awx_queries.py`)
   - Settings/UserPreference models (configuration)
3. **Response** → JSON formatted for TypeScript interfaces

### Caching Strategy

- **Cache Population**: Background tasks run periodically to update cache
- **Cache Retrieval**: API endpoints read from cache for fast responses
- **Real-time Data**: Filter options fetched directly from AWX for freshness
- **No TTL**: Task-driven updates ensure data consistency

---

## Feature Flags and Settings

### New Settings Added

- `DASHBOARD_REPORTS_ENABLED` - Feature flag for dashboard reports functionality
- Dashboard-specific configuration in `apps/settings/defaults.py`
- OAuth settings for AAP integration
- Cost calculation settings

### Environment Variables

- `METRICS_SERVICE_DASHBOARD_REPORTS` - Control dashboard reports feature
- Integration with existing `FEATURE_ENABLED` system

---

## Testing Coverage

### Integration Tests (`tests/integration/dashboard_reports/`)

- API endpoint integration tests (394 lines)
- End-to-end workflow testing
- Database interaction validation

### Unit Tests (`tests/unit/dashboard_reports/`)

- Serializer validation tests (325 lines)
- Model behavior verification
- Edge case handling

### Additional Test Files

- `test_dashboard_api.py` - Standalone API testing suite (120 lines)

---

## Dependencies and Configuration

### Updated Files

- **`pyproject.toml`**: Updated version or dependencies
- **`apps/settings/defaults.py`**: Added dashboard defaults (43 lines)

### New Modules

- **`apps/dashboard_reports/awx_queries.py`**: AWX database integration (258 lines)
- **`apps/tasks/task_groups.py`**: Task organization (20 lines)

---

## Breaking Changes

None. This branch adds new functionality without modifying existing APIs.

---

## Migration Path

### For Developers

1. Pull the Dashboard-Support branch
2. Run migrations: `.venv/bin/python manage.py migrate`
3. Initialize system tasks: `.venv/bin/python manage.py metrics_service init-system-tasks`
4. Run the service: `.venv/bin/python manage.py metrics_service run`

### For Testing

1. Run test suite: `.venv/bin/python -m pytest tests/unit/dashboard_reports/ tests/integration/dashboard_reports/`
2. Test API endpoints: `python test_dashboard_api.py`

---

## Documentation Added

- **`apps/dashboard_reports/README.md`** (413 lines)
  - Complete API documentation
  - Endpoint descriptions and examples
  - TypeScript interface definitions
  - Implementation timeline and status

---

## Next Steps

### Before Merge to Devel

1. **Code Review**: Thorough review of 4,340+ lines of new code
2. **Testing**: Ensure all tests pass with 80%+ coverage
3. **Documentation**: Verify README.md accuracy
4. **Performance**: Load testing of cached endpoints
5. **Security**: Review AWX query functions for SQL injection protection

### Post-Merge

1. **Frontend Integration**: Connect automation-reports React app to new endpoints
2. **Monitoring**: Add metrics for cache hit rates and API performance
3. **Documentation**: Update main project docs with dashboard features

---

## Contributors

- Ciaran Shiels <cas.ireland@Gmail.com>

---

## Related Issues and PRs

- Integration with automation-reports frontend
- AAP dashboard metrics requirements
- Performance optimization for dashboard queries

---

**Generated**: 2026-02-03
**Branch**: Dashboard-Support
**Base**: devel
