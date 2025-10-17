# Implement ADR 0014 Phase 2: Dynamic Preferences

## Overview

Add runtime configuration management with database-backed storage, caching, access hooks, and APIs following ADR 0014 Phase 2 specifications.

## Implementation Steps

### 1. Database Models - Create Setting Model

**Replace** `ConfigurationChange` audit model with proper versioned `Setting` model:

**File**: `apps/core/models.py`

```python
class Setting(models.Model):
    """
    Database-backed key-value storage for dynamic preferences.
    Immutable versioned records - new version created on each change.
    """
    # What
    key = models.CharField(max_length=255, db_index=True)
    value = models.TextField()  # JSON serialized
    version = models.IntegerField(default=1)
    
    # Metadata
    category = models.CharField(max_length=50, blank=True)  # e.g., 'security', 'features'
    is_secret = models.BooleanField(default=False)
    is_encrypted = models.BooleanField(default=False)
    
    # Auditing
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50)  # 'api', 'management_command', etc.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        unique_together = [['key', 'version']]
        ordering = ['-version']
        indexes = [
            models.Index(fields=['key', '-version']),  # Fast lookup of latest version
        ]
    
    @classmethod
    def get_latest(cls, key):
        """Get latest version of a setting."""
        return cls.objects.filter(key=key).first()
```

Keep `ConfigurationChange` for backward compatibility but mark deprecated.

**Migration**: Create `0008_setting_model.py`

### 2. Custom Model Manager with Locking

**File**: `apps/core/models.py`

Add custom manager to `Setting` model:

```python
class SettingManager(models.Manager):
    """Custom manager with transaction locking and cache updates."""
    
    def create_or_update(self, key, value, user=None, source='api', ip_address=None):
        """Create new version with locking."""
        from django.db import transaction
        from django.core.cache import cache
        import redis
        
        redis_client = cache._cache.get_client() if hasattr(cache, '_cache') else None
        lock_key = f"setting_lock:{key}"
        
        with transaction.atomic():
            # Acquire Redis lock
            lock = redis_client.lock(lock_key, timeout=10) if redis_client else None
            if lock:
                lock.acquire()
            
            try:
                # Get current latest version
                latest = self.filter(key=key).first()
                new_version = (latest.version + 1) if latest else 1
                
                # Validate value
                self._validate_setting(key, value)
                
                # Create new version
                setting = self.create(
                    key=key,
                    value=value,
                    version=new_version,
                    changed_by=user,
                    source=source,
                    ip_address=ip_address
                )
                
                # Update cache
                cache.set(f"setting:{key}", value, timeout=None)
                
                return setting
            finally:
                if lock:
                    lock.release()
```

### 3. Access Hooks - Dynamic Settings Loader

**File**: `apps/core/dynamic_settings.py` (new)

Create access hook that checks cache → database → defaults:

```python
from django.core.cache import cache
from dynaconf import Dynaconf

# Define which keys can be dynamically changed
DYNAMIC_KEYS = {
    'DEBUG',
    'FEATURE_FLAGS',
    'CORS_ALLOW_ALL_ORIGINS',
    'LOG_LEVEL',
    # Add more as needed
}

def dynamic_settings_loader(settings_obj: Dynaconf, key: str, *args, **kwargs):
    """
    Access hook that loads dynamic settings from cache/database.
    
    Execution flow:
    1. Check if key is in DYNAMIC_KEYS
    2. Try cache first (fastest)
    3. Fall back to database if cache miss
    4. Fall back to static defaults if database unavailable
    """
    if key not in DYNAMIC_KEYS:
        # Not a dynamic key, skip hook
        return None
    
    # Try cache first
    cache_key = f"setting:{key}"
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return _deserialize_value(cached_value)
    
    # Cache miss - try database
    try:
        from apps.core.models import Setting
        setting = Setting.get_latest(key)
        if setting:
            value = _deserialize_value(setting.value)
            # Update cache
            cache.set(cache_key, setting.value, timeout=None)
            return value
    except Exception as e:
        logger.warning(f"Failed to load {key} from database: {e}")
    
    # Fall back to static defaults (already in settings_obj)
    return None
```

### 4. Integrate Access Hooks into Settings

**File**: `metrics_service/settings/__init__.py`

Update to register access hooks:

```python
from ansible_base.lib.dynamic_config import export, factory, load_envvars, load_standard_settings_files
from apps.core.dynamic_settings import dynamic_settings_loader, DYNAMIC_KEYS

# ... existing factory setup ...

# Register access hooks for dynamic keys
for key in DYNAMIC_KEYS:
    DYNACONF.register_hook(key, dynamic_settings_loader)

# Export with access hooks enabled
export(__name__, DYNACONF, validation=not is_development, enable_hooks=True)
```

### 5. REST API Endpoints

**File**: `apps/api/v1/settings/` (new directory)

Create viewset for settings management:

**`apps/api/v1/settings/views.py`**:

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.models import Setting
from apps.api.v1.settings.serializers import SettingSerializer

class SettingViewSet(viewsets.ModelViewSet):
    """
    API endpoints for dynamic settings management.
    
    list: Get all current settings (latest versions)
    retrieve: Get specific setting with version history
    create: Create/update a setting (creates new version)
    """
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    
    def get_queryset(self):
        """Return only latest versions by default."""
        if self.action == 'retrieve':
            # Show all versions for specific key
            return Setting.objects.filter(key=self.kwargs['pk'])
        # Latest versions only
        from django.db.models import Max
        latest_versions = Setting.objects.values('key').annotate(
            max_version=Max('version')
        )
        # ... construct queryset ...
    
    def create(self, request):
        """Create new version of a setting."""
        key = request.data.get('key')
        value = request.data.get('value')
        
        setting = Setting.objects.create_or_update(
            key=key,
            value=value,
            user=request.user,
            source='api',
            ip_address=self.get_client_ip(request)
        )
        
        serializer = self.get_serializer(setting)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def revert(self, request, pk=None):
        """Revert setting to specific version."""
        # Implementation
```

**`apps/api/v1/settings/serializers.py`**:

```python
class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ['key', 'value', 'version', 'changed_by', 'changed_at', 'source']
        read_only_fields = ['version', 'changed_at']
```

**Update** `apps/api/v1/urls.py`:

```python
from apps.api.v1.settings.views import SettingViewSet

router.register(r'settings', SettingViewSet, basename='setting')
```

### 6. Management Commands

**File**: `apps/core/management/commands/manage_settings.py` (new)

```python
class Command(BaseCommand):
    """Manage dynamic settings from command line."""
    
    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='subcommand')
        
        # Get setting
        get_parser = subparsers.add_parser('get')
        get_parser.add_argument('key')
        
        # Set setting
        set_parser = subparsers.add_parser('set')
        set_parser.add_argument('key')
        set_parser.add_argument('value')
        
        # List all settings
        subparsers.add_parser('list')
        
        # Revert to version
        revert_parser = subparsers.add_parser('revert')
        revert_parser.add_argument('key')
        revert_parser.add_argument('version', type=int)
    
    def handle(self, *args, **options):
        # Implementation
```

### 7. Redis Cache Configuration

**File**: `metrics_service/settings/defaults.py`

Update cache configuration to use Redis:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "metrics_service",
        "TIMEOUT": None,  # Dynamic settings don't expire
    }
}
```

**File**: `config/settings.yaml`

```yaml
default:
  CACHES:
    default:
      BACKEND: django.core.cache.backends.redis.RedisCache
      LOCATION: redis://localhost:6379/1
```

Add `django-redis` to `pyproject.toml` dependencies.

### 8. Signals for Cache Updates

**File**: `apps/core/signals.py`

Add signal handlers to update cache when settings change:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

@receiver(post_save, sender=Setting)
def update_cache_on_setting_change(sender, instance, created, **kwargs):
    """Update cache when setting is created/updated."""
    if created:
        cache_key = f"setting:{instance.key}"
        cache.set(cache_key, instance.value, timeout=None)
```

### 9. Update Docker Compose

**File**: `docker-compose.yml`

Add Redis service:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  redis_data:
```

### 10. Documentation

**File**: `metrics_service/settings/README.md`

Add Phase 2 section:

````markdown
## Phase 2: Dynamic Preferences (Runtime Configuration)

Dynamic settings can be changed at runtime without restarting the service.

### Dynamic Keys

The following settings support runtime changes:
- `DEBUG`
- `FEATURE_FLAGS`
- `CORS_ALLOW_ALL_ORIGINS`
- `LOG_LEVEL`

### Usage

**Via Management Command:**
```bash
python manage.py manage_settings set DEBUG false
python manage.py manage_settings get DEBUG
python manage.py manage_settings list
````

**Via REST API:**

```bash
# Get all settings
curl http://localhost:8000/api/v1/settings/

# Update a setting
curl -X POST http://localhost:8000/api/v1/settings/ \
  -H "Content-Type: application/json" \
  -d '{"key": "DEBUG", "value": "false"}'

# Revert to previous version
curl -X POST http://localhost:8000/api/v1/settings/DEBUG/revert/ \
  -d '{"version": 3}'
```



````

### 11. Testing

**File**: `tests/unit/core/test_dynamic_settings.py` (new)

Comprehensive tests for Phase 2:

```python
class TestDynamicSettings:
    def test_setting_creation_with_versioning(self):
        """Test creating setting versions."""
        
    def test_access_hook_reads_from_cache(self):
        """Test access hook checks cache first."""
        
    def test_access_hook_fallback_to_database(self):
        """Test fallback when cache misses."""
        
    def test_transaction_locking(self):
        """Test concurrent writes are locked."""
        
    def test_cache_invalidation_on_write(self):
        """Test cache updates when setting changes."""
````

## Files to Create/Modify

**New Files:**

- `apps/core/dynamic_settings.py` - Access hooks
- `apps/api/v1/settings/views.py` - API endpoints
- `apps/api/v1/settings/serializers.py` - API serializers
- `apps/api/v1/settings/urls.py` - URL routing
- `apps/core/management/commands/manage_settings.py` - CLI
- `apps/core/migrations/0008_setting_model.py` - Migration
- `tests/unit/core/test_dynamic_settings.py` - Tests
- `DYNAMIC_PREFERENCES.md` - Usage documentation

**Modified Files:**

- `apps/core/models.py` - Add Setting model, update ConfigurationChange
- `metrics_service/settings/__init__.py` - Register access hooks
- `metrics_service/settings/defaults.py` - Redis cache config
- `config/settings.yaml` - Redis configuration
- `docker-compose.yml` - Add Redis service
- `pyproject.toml` - Add django-redis dependency
- `apps/api/v1/urls.py` - Register settings endpoints
- `metrics_service/settings/README.md` - Document Phase 2

## Dependencies to Add

- `django-redis>=5.4.0` - Redis cache backend
- `redis>=5.0.0` - Python Redis client with locking support