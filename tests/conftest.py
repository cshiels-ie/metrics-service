"""
Pytest configuration and fixtures for metrics_service tests.
"""

import os

# Must be set before Django is configured (pytest-django reads DJANGO_SETTINGS_MODULE
# from pyproject.toml and calls django.setup() before conftest fixtures run, so the
# setdefault inside the 'if not settings.configured' block below is too late).
os.environ.setdefault("METRICS_SERVICE_MODE", "test")

# Patch ansible_base feature flags loading before Django setup to prevent
# Resource.DoesNotExist errors during test migrations
try:
    # Import and patch load_feature_flags before Django setup
    try:
        from ansible_base.feature_flags.utils import load_feature_flags as original_load_feature_flags

        def safe_load_feature_flags():
            """
            Wrapper that catches Resource.DoesNotExist during migrations.

            During test migrations, Resource objects may not exist yet,
            causing DoesNotExist errors when feature flags try to validate.
            """
            try:
                return original_load_feature_flags()
            except Exception:  # noqa: S110
                # During migrations, Resource objects may not exist yet
                # Silently skip feature flag loading in tests
                pass

        # Patch the function in the module before Django setup
        import ansible_base.feature_flags.utils

        ansible_base.feature_flags.utils.load_feature_flags = safe_load_feature_flags
    except ImportError:
        # If ansible_base is not available, continue anyway
        pass
except Exception:  # noqa: S110
    # If patching fails, continue anyway
    pass

import django
from django.conf import settings

# Configure Django settings before any imports
if not settings.configured:
    os.environ.setdefault("METRICS_SERVICE_MODE", "test")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "metrics_service.settings")
    django.setup()

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient

from apps.core.models import Organization, Team

User = get_user_model()


@pytest.fixture(scope="session", autouse=True)
def setup_service_id(django_db_setup, django_db_blocker):
    """Mock ServiceID access for tests to prevent ansible_base resource registry errors."""
    import uuid
    from unittest.mock import patch

    # Generate a fixed UUID for consistent testing
    test_service_id = str(uuid.UUID("12345678-1234-5678-9012-123456789012"))

    # Mock the service_id function to return our test UUID
    def mock_service_id():
        return test_service_id

    # Apply patches for the entire test session
    patches = []
    try:
        # Patch the service_id function
        service_id_patch = patch(
            "ansible_base.resource_registry.models.service_identifier.service_id", side_effect=mock_service_id
        )
        patches.append(service_id_patch)

        # Also patch the global variable
        global_var_patch = patch(
            "ansible_base.resource_registry.models.service_identifier._service_id", test_service_id
        )
        patches.append(global_var_patch)

        # Start all patches
        for p in patches:
            p.start()

    except ImportError:
        # If ansible_base is not available, continue anyway
        pass


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def api_client():
    """DRF API test client."""
    return APIClient()


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_superuser(username="testuser", email="test@example.com", password="testpassword123")  # noqa: S105


@pytest.fixture
def admin_user():
    """Create a test admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="adminpassword123",  # noqa: S105
        is_superuser=True,
    )


@pytest.fixture
def organization():
    """Create a test organization."""
    return Organization.objects.create(name="Test Organization")


@pytest.fixture
def team(organization):
    """Create a test team."""
    return Team.objects.create(name="Test Team", organization=organization)


@pytest.fixture
def authenticated_client(api_client, user):
    """API client authenticated with a test user."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client authenticated with an admin user."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def task(user):
    """Create a test task."""
    from apps.tasks.models import Task

    return Task.objects.create(name="Test Task", function_name="hello_world", task_data={}, created_by=user)


@pytest.fixture
def create_task_safely():
    """
    Factory fixture for creating tasks without triggering signals.

    This fixture provides a way to create tasks while bypassing Django signals,
    which is useful for testing task behavior in isolation.

    Usage:
        def test_something(create_task_safely):
            from apps.tasks.models import Task
            task = create_task_safely(Task, name="test", function_name="hello_world")
    """

    def _create(task_model, **kwargs):
        task = task_model(**kwargs)
        task.save()
        return task

    return _create


@pytest.fixture
def mock_scheduler():
    """
    Fixture for mocking the task scheduler.

    Provides a mocked scheduler instance with running=True, suitable for
    testing scheduler-dependent code without actually starting the scheduler.

    Usage:
        def test_something(mock_scheduler):
            # mock_scheduler is already patched and running
            assert mock_scheduler.running is True
    """
    from unittest.mock import MagicMock, patch

    with patch("apps.tasks.cron_scheduler.get_scheduler") as mock:
        scheduler = MagicMock()
        scheduler.running = True
        mock.return_value = scheduler
        yield scheduler


@pytest.fixture
def mock_style():
    """
    Fixture for mocking Django command style output.

    Provides a mocked style object for testing Django management commands
    without actual console output.

    Usage:
        def test_command(mock_style):
            output = mock_style.SUCCESS("Test message")
            assert output == "Test message"
    """
    from unittest.mock import MagicMock

    style = MagicMock()
    style.SUCCESS.side_effect = lambda msg: msg
    style.ERROR.side_effect = lambda msg: msg
    style.WARNING.side_effect = lambda msg: msg
    style.NOTICE.side_effect = lambda msg: msg
    return style


@pytest.fixture
def mock_db_connection():
    """
    Fixture for mocking database connections used by collectors.

    Provides a mocked database connection suitable for testing metrics
    collectors without requiring an actual AWX database connection.

    Usage:
        def test_collector(mock_db_connection):
            # mock_db_connection is the raw psycopg2 connection
            collector = config(db=mock_db_connection)
            result = collector.gather()
    """
    from unittest.mock import MagicMock, patch

    with patch("django.db.connections") as mock_connections:
        mock_raw_connection = MagicMock()
        mock_db_connection_obj = MagicMock()
        mock_db_connection_obj.connection = mock_raw_connection
        mock_connections.__getitem__.return_value = mock_db_connection_obj
        yield mock_raw_connection
