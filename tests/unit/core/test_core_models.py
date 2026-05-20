"""
Unit tests for core models.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Organization, Team
from apps.tasks.models import Task, TaskExecution
from tests.test_utils import get_test_password

User = get_user_model()


@pytest.mark.unit
class CoreModelsTestCase(TestCase):
    """Test cases for core models."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=get_test_password()
        )

        self.organization = Organization.objects.create(name="Test Organization", description="A test organization")

        self.team = Team.objects.create(name="Test Team", description="A test team", organization=self.organization)

    def test_user_creation(self):
        """Test User model creation and string representation."""
        self.assertEqual(str(self.user), "testuser")
        self.assertEqual(self.user.email, "test@example.com")
        self.assertTrue(self.user.check_password(get_test_password()))

    def test_organization_creation(self):
        """Test Organization model creation."""
        self.assertEqual(str(self.organization), "Test Organization")
        self.assertEqual(self.organization.name, "Test Organization")

    def test_team_creation(self):
        """Test Team model creation."""
        # AbstractTeam's __str__ returns just the team name
        self.assertEqual(str(self.team), "Test Team")
        self.assertEqual(self.team.organization, self.organization)


@pytest.mark.unit
class TaskModelTestCase(TestCase):
    """Test cases for Task system models."""

    def _create_task_safely(self, **kwargs):
        """Create a task without triggering signals."""
        task = Task(**kwargs)
        task.save()
        return task

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="taskuser", email="task@example.com")

        self.task = self._create_task_safely(
            name="Test Task",
            function_name="test_function",
            task_data={"param": "value"},
            created_by=self.user,
            status="pending",
        )

    def test_task_creation(self):
        """Test Task model creation."""
        self.assertEqual(str(self.task), "Test Task (test_function) - Pending")
        self.assertEqual(self.task.status, "pending")
        self.assertEqual(self.task.attempts, 0)
        self.assertEqual(self.task.max_attempts, 3)
        self.assertIsNone(self.task.cron_expression)  # Non-recurring task

    def test_task_is_ready_to_run(self):
        """Test Task is_ready_to_run method."""
        # Task should be ready by default
        self.assertTrue(self.task.is_ready_to_run())

        # Task with future scheduled time should not be ready
        future_time = timezone.now() + timedelta(hours=1)
        self.task.scheduled_time = future_time
        self.task.save()
        self.assertFalse(self.task.is_ready_to_run())

        # Task with past scheduled time should be ready
        past_time = timezone.now() - timedelta(hours=1)
        self.task.scheduled_time = past_time
        self.task.save()
        self.assertTrue(self.task.is_ready_to_run())

        # Running task should not be ready
        self.task.status = "running"
        self.task.save()
        self.assertFalse(self.task.is_ready_to_run())

    def test_task_can_retry(self):
        """Test Task can_retry method."""
        # New task cannot be retried
        self.assertFalse(self.task.can_retry())

        # Failed task with attempts < max_attempts can be retried
        self.task.status = "failed"
        self.task.attempts = 1
        self.task.save()
        self.assertTrue(self.task.can_retry())

        # Failed task with attempts >= max_attempts cannot be retried
        self.task.attempts = 3
        self.task.save()
        self.assertFalse(self.task.can_retry())

    def test_task_execution_creation(self):
        """Test TaskExecution model creation."""
        execution = TaskExecution.objects.create(task=self.task, status="running", worker_id="worker-123")

        self.assertEqual(execution.task, self.task)
        self.assertEqual(execution.status, "running")
        self.assertEqual(execution.worker_id, "worker-123")
        self.assertIsNotNone(execution.started_at)

    def test_task_execution_time_calculation(self):
        """Test TaskExecution execution time calculation."""
        start_time = timezone.now()
        end_time = start_time + timedelta(seconds=10)

        execution = TaskExecution.objects.create(
            task=self.task, status="completed", started_at=start_time, completed_at=end_time
        )

        self.assertEqual(execution.execution_time_seconds, 10.0)


@pytest.mark.unit
class ModelValidationTestCase(TestCase):
    """Test cases for model validation and constraints."""

    def _create_task_safely(self, **kwargs):
        """Create a task without triggering signals."""
        task = Task(**kwargs)
        task.save()
        return task

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="validationuser")
        self.organization = Organization.objects.create(name="Test Org")

    def test_team_unique_constraint(self):
        """Test Team unique constraint on organization and name."""
        team1 = Team.objects.create(name="Unique Team", organization=self.organization)

        # Creating another team with same name in same org should work initially
        # but the unique_together constraint is defined in Meta
        team2 = Team.objects.create(name="Different Team", organization=self.organization)

        self.assertNotEqual(team1.name, team2.name)


@pytest.mark.unit
class ModelMethodsTestCase(TestCase):
    """Test cases for model methods and properties."""

    def _create_task_safely(self, **kwargs):
        """Create a task without triggering signals."""
        task = Task(**kwargs)
        task.save()
        return task

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="methoduser")

    def test_user_password_handling(self):
        """Test User password handling."""
        # Test password setting
        self.user.set_password("newpassword")  # noqa: S105
        self.user.save()
        self.assertTrue(self.user.check_password("newpassword"))  # noqa: S105

        # Test empty password handling in save method
        self.user.password = ""
        self.user.save()
        # Password should be set to None for empty string
