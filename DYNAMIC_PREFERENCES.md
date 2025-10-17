# Dynamic Preferences (Phase 2)

This document describes the Phase 2 dynamic preferences implementation following [ADR 0014: Django Settings](https://handbook.eng.ansible.com/proposals/0014-Django-Settings).

## Overview

Dynamic preferences allow runtime configuration changes without restarting the service. Settings are:

- **Versioned**: Each change creates a new immutable version
- **Audited**: Full history of who changed what and when
- **Cached**: Database cache for fast access
- **Validated**: Only approved keys can be changed
- **API-driven**: REST API and management command interfaces

## Architecture

### Storage

- **Database**: PostgreSQL stores all versions with full audit trail
- **Cache**: Django database cache for fast access (no Redis needed)
- **Locking**: Database `select_for_update()` prevents concurrent modifications

### Access Flow

```
1. Application accesses setting via django.conf.settings
2. Access hook checks if key is in DYNAMIC_KEYS
3. If dynamic:
   a. Check cache first (fastest)
   b. If cache miss, query database
   c. Update cache with database value
   d. Return value
4. If not dynamic or not found, use static default
```

### Write Flow

```
1. User creates/updates setting via API or management command
2. Validate key is in DYNAMIC_KEYS
3. Validate value is JSON-serializable
4. Acquire database lock with select_for_update()
5. Create new version (increment version number)
6. Update cache automatically via signal
7. Return new setting version
```

## Available Dynamic Keys

The following settings can be changed at runtime:

| Key                      | Type    | Description                                 |
| ------------------------ | ------- | ------------------------------------------- |
| `DEBUG`                  | boolean | Enable/disable debug mode                   |
| `FEATURE_FLAGS`          | object  | Feature flag configuration                  |
| `CORS_ALLOW_ALL_ORIGINS` | boolean | CORS allow all origins                      |
| `LOG_LEVEL`              | string  | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DISPATCHERD_ENABLED`    | boolean | Enable/disable background task dispatcher   |

To add more dynamic keys, edit `apps/core/dynamic_settings.py`:

```python
DYNAMIC_KEYS = {
    "DEBUG",
    "FEATURE_FLAGS",
    # Add your key here
    "MY_NEW_SETTING",
}
```

## Usage

### REST API

#### List All Settings

```bash
curl http://localhost:8000/api/v1/settings/ \
  -H "Authorization: Token YOUR_TOKEN"
```

#### Get Specific Setting

```bash
curl http://localhost:8000/api/v1/settings/DEBUG/ \
  -H "Authorization: Token YOUR_TOKEN"
```

#### Create/Update Setting

```bash
curl -X POST http://localhost:8000/api/v1/settings/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "DEBUG",
    "value": false,
    "category": "security"
  }'
```

#### Get Setting History

```bash
curl http://localhost:8000/api/v1/settings/DEBUG/history/ \
  -H "Authorization: Token YOUR_TOKEN"
```

#### Revert to Previous Version

```bash
curl -X POST http://localhost:8000/api/v1/settings/DEBUG/revert/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"version": 3}'
```

#### List Available Dynamic Keys

```bash
curl http://localhost:8000/api/v1/settings/available_keys/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### Management Command

#### Get Current Value

```bash
python manage.py manage_settings get DEBUG
```

Output:

```
Key: DEBUG
Value: false
Version: 5
Changed by: admin
Changed at: 2025-10-17 14:30:00
Source: api
```

#### Set New Value

```bash
# Set simple value
python manage.py manage_settings set DEBUG 'false'

# Set complex value (JSON)
python manage.py manage_settings set FEATURE_FLAGS '{"new_feature": true, "beta_mode": false}'

# Set with category
python manage.py manage_settings set DEBUG 'false' --category security
```

#### List All Settings

```bash
# Latest versions only
python manage.py manage_settings list

# All versions
python manage.py manage_settings list --all-versions
```

#### Show Available Keys

```bash
python manage.py manage_settings keys
```

Output:

```
Available dynamic keys:

  ✓ set  CORS_ALLOW_ALL_ORIGINS
  ✓ set  DEBUG
  ✓ set  FEATURE_FLAGS
    not set  DISPATCHERD_ENABLED
    not set  LOG_LEVEL

Total: 5 dynamic keys
```

#### Show Version History

```bash
python manage.py manage_settings history DEBUG
```

#### Revert to Previous Version

```bash
python manage.py manage_settings revert DEBUG 3
```

### Programmatic Access

```python
from apps.core.dynamic_settings import get_dynamic_setting, set_dynamic_setting

# Get value
debug_mode = get_dynamic_setting('DEBUG', default=False)

# Set value
set_dynamic_setting('DEBUG', False, source='script')
```

### Django Settings Access

```python
from django.conf import settings

# Access dynamic settings like any other setting
if settings.DEBUG:
    print("Debug mode is enabled")

# Values automatically loaded from cache/database if dynamic
feature_flags = settings.FEATURE_FLAGS
```

## Database Schema

### Setting Model

```sql
CREATE TABLE core_setting (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    version INTEGER NOT NULL,
    category VARCHAR(50),
    is_secret BOOLEAN DEFAULT FALSE,
    is_encrypted BOOLEAN DEFAULT FALSE,
    changed_by_id INTEGER REFERENCES core_user(id),
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source VARCHAR(50) NOT NULL,
    ip_address INET,
    UNIQUE (key, version)
);

CREATE INDEX idx_setting_key_version ON core_setting(key, version DESC);
CREATE INDEX idx_setting_changed_at ON core_setting(changed_at);
CREATE INDEX idx_setting_category ON core_setting(category);
```

### Cache Table

```sql
CREATE TABLE cache_table (
    cache_key VARCHAR(255) PRIMARY KEY,
    value TEXT,
    expires TIMESTAMP WITH TIME ZONE
);
```

## Setup

### 1. Run Migrations

```bash
python manage.py migrate
```

### 2. Create Cache Table

```bash
python manage.py createcachetable
```

### 3. Configure Dynamic Keys

Edit `apps/core/dynamic_settings.py` to add/remove dynamic keys.

### 4. Test the System

```bash
# Set a value
python manage.py manage_settings set DEBUG 'false'

# Get the value
python manage.py manage_settings get DEBUG

# Verify it works without restart
python manage.py shell
>>> from django.conf import settings
>>> settings.DEBUG  # Should show False
```

## Security Considerations

### Secret Settings

Settings marked as `is_secret=True` are redacted in API responses:

```python
{
    "key": "SECRET_KEY",
    "value_json": "***REDACTED***",
    "is_secret": true
}
```

### Permissions

- All settings API endpoints require authentication
- Use Django's permission system to control access
- Audit trail tracks who changed what

### Validation

- Only keys in `DYNAMIC_KEYS` can be changed
- Values must be JSON-serializable
- Custom validators can be added in `SettingManager._validate_setting()`

## Performance

### Caching Strategy

- **First access**: Cache miss → database query → cache update
- **Subsequent accesses**: Cache hit → instant return
- **Cache invalidation**: Automatic via Django signals on setting change

### Database Locking

- `select_for_update()` ensures only one transaction modifies a key at a time
- Lock is released when transaction commits
- Prevents race conditions on version numbers

## Troubleshooting

### Setting Not Updating

1. Check if key is in `DYNAMIC_KEYS`:

   ```bash
   python manage.py manage_settings keys
   ```

2. Clear cache manually:

   ```python
   from django.core.cache import cache
   cache.delete('setting:DEBUG')
   ```

3. Check database:
   ```python
   from apps.core.models import Setting
   Setting.get_latest('DEBUG')
   ```

### Cache Issues

Verify cache is working:

```bash
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')  # Should return 'value'
```

If cache fails, check:

- Cache table exists: `python manage.py createcachetable`
- Database permissions
- Cache configuration in settings

### Version Conflicts

If you see version conflicts, it means concurrent updates occurred.
The system will handle this automatically by incrementing the version.

## Monitoring

### View Recent Changes

```bash
python manage.py shell
>>> from apps.core.models import Setting
>>> Setting.objects.order_by('-changed_at')[:10]
```

### Track Setting Usage

```python
# Get all versions of a setting
Setting.get_history('DEBUG')

# See who made the most changes
Setting.objects.values('changed_by__username').annotate(
    count=Count('id')
).order_by('-count')
```

## Integration with Phase 1

Phase 2 builds on Phase 1 static settings:

1. **Phase 1**: Settings loaded at startup from files/env vars
2. **Phase 2**: Dynamic settings override static defaults at runtime
3. **Precedence**: Dynamic (cache/DB) > Static (Phase 1)

To use a setting dynamically:

1. Add key to `DYNAMIC_KEYS`
2. Set initial value via API or management command
3. Access normally via `django.conf.settings`

## Migration from Static to Dynamic

To convert a static setting to dynamic:

1. Add key to `DYNAMIC_KEYS` in `apps/core/dynamic_settings.py`
2. Set initial value:
   ```bash
   python manage.py manage_settings set MY_SETTING '"current_value"'
   ```
3. Test access:
   ```python
   from django.conf import settings
   print(settings.MY_SETTING)
   ```
4. Update at runtime:
   ```bash
   python manage.py manage_settings set MY_SETTING '"new_value"'
   ```

## Future Enhancements (Phase 3)

The current implementation is Phase 2. Future enhancements may include:

- **Centralized settings service**: Share settings across multiple services
- **gRPC API**: For language-agnostic access
- **Settings encryption**: Encrypt sensitive values at rest
- **Settings validation hooks**: Custom validation per key
- **Settings UI**: Web-based settings management interface
- **Settings backup/restore**: Export/import settings configurations

## References

- [ADR 0014: Django Settings](https://handbook.eng.ansible.com/proposals/0014-Django-Settings)
- [Dynaconf Documentation](https://www.dynaconf.com/)
- [Django Settings Documentation](https://docs.djangoproject.com/en/stable/topics/settings/)
- [metrics_service/settings/README.md](metrics_service/settings/README.md) - Phase 1 documentation
