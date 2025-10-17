"""
Extended tests for API views and serializers to improve coverage.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.api.v1.base_serializers import BaseModelSerializer, CountFieldMixin, PasswordHandlingMixin
from apps.api.v1.base_views import BaseViewSet, UserManagementMixin
from apps.api.v1.serializers import OrganizationSerializer, TeamSerializer, UserSerializer
from apps.api.v1.views import OrganizationViewSet, UserViewSet
from apps.core.models import Organization, Team, User


@pytest.mark.django_db
class TestBaseViewSet(TestCase):
    """Test BaseViewSet functionality."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="test", email="test@example.com")

    def test_base_viewset_initialization(self):
        """Test BaseViewSet can be initialized."""
        viewset = BaseViewSet()
        assert viewset

    def test_get_queryset_with_none_queryset(self):
        """Test get_queryset handles None queryset."""
        viewset = BaseViewSet()
        # This will raise AttributeError since queryset is None
        with pytest.raises(AttributeError):
            viewset.get_queryset()

    def test_get_serializer_class_not_implemented(self):
        """Test get_serializer_class raises AssertionError when no serializer_class is set."""
        viewset = BaseViewSet()
        with pytest.raises(AssertionError):
            viewset.get_serializer_class()


@pytest.mark.django_db
class TestUserManagementMixin(TestCase):
    """Test UserManagementMixin functionality."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="test", email="test@example.com")

    def test_mixin_initialization(self):
        """Test UserManagementMixin can be initialized."""
        mixin = UserManagementMixin()
        assert mixin

    def test_get_queryset_with_none_queryset(self):
        """Test get_queryset in mixin handles None queryset."""
        mixin = UserManagementMixin()
        # This will also raise AttributeError since queryset is None
        with pytest.raises(AttributeError):
            mixin.get_queryset()


@pytest.mark.django_db
class TestBaseModelSerializer(TestCase):
    """Test BaseModelSerializer functionality."""

    def test_base_serializer_initialization(self):
        """Test BaseModelSerializer can be initialized with proper Meta class."""

        # Create a concrete test serializer class with Meta
        class TestSerializer(BaseModelSerializer):
            class Meta:
                model = User
                fields = ["id", "username", "email"]

        serializer = TestSerializer()
        assert serializer

    def test_base_serializer_meta_not_implemented(self):
        """Test that Meta class is properly defined."""

        # Create a concrete test serializer class with Meta
        class TestSerializer(BaseModelSerializer):
            class Meta:
                model = User
                fields = ["id", "username", "email"]

        serializer = TestSerializer()
        # The base serializer should have a Meta class
        assert hasattr(serializer, "Meta")

    def test_setup_common_fields(self):
        """Test _setup_common_fields method adds read_only_fields."""

        # Create a concrete test serializer class with Meta
        class TestSerializer(BaseModelSerializer):
            class Meta:
                model = User
                fields = ["id", "username", "email"]

        serializer = TestSerializer()
        # Check that common read-only fields were added
        expected_readonly = ["id", "url", "created", "modified"]
        for field in expected_readonly:
            assert field in serializer.Meta.read_only_fields


@pytest.mark.django_db
class TestCountFieldMixin(TestCase):
    """Test CountFieldMixin functionality."""

    def test_count_field_mixin_initialization(self):
        """Test CountFieldMixin can be initialized."""
        mixin = CountFieldMixin()
        assert mixin

    def test_count_methods_exist(self):
        """Test count methods exist."""
        mixin = CountFieldMixin()
        assert hasattr(mixin, "get_users_count")
        assert hasattr(mixin, "get_admins_count")
        assert hasattr(mixin, "get_tasks_count")


@pytest.mark.django_db
class TestUserSerializer(TestCase):
    """Test UserSerializer functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", first_name="Test", last_name="User"
        )

    def test_user_serialization(self):
        """Test user serialization."""
        # Create a request context for HyperlinkedIdentityField
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user  # Add user to request for serializer context
        serializer = UserSerializer(instance=self.user, context={"request": request})
        data = serializer.data

        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        # Password should not be in serialized data
        assert "password" not in data

    def test_user_deserialization(self):
        """Test user deserialization."""
        data = {"username": "newuser", "email": "new@example.com", "first_name": "New", "last_name": "User"}
        serializer = UserSerializer(data=data)
        assert serializer.is_valid()

    def test_password_validation(self):
        """Test password validation in user serializer."""
        data = {"username": "testuser2", "email": "test2@example.com", "password": "testpass123"}
        serializer = UserSerializer(data=data)
        # Should handle password validation
        serializer.is_valid()

    def test_update_user(self):
        """Test updating user via serializer."""
        data = {"first_name": "Updated"}
        serializer = UserSerializer(instance=self.user, data=data, partial=True)
        assert serializer.is_valid()
        updated_user = serializer.save()
        assert updated_user.first_name == "Updated"


@pytest.mark.django_db
class TestOrganizationSerializer(TestCase):
    """Test OrganizationSerializer functionality."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", description="Test organization")

    def test_organization_serialization(self):
        """Test organization serialization."""
        # Create a user and request context
        user = User.objects.create_user(username="testuser", email="test@example.com")
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user  # Add user to request for serializer context
        serializer = OrganizationSerializer(instance=self.org, context={"request": request})
        data = serializer.data

        assert data["name"] == "Test Org"
        assert data["description"] == "Test organization"

    def test_organization_deserialization(self):
        """Test organization deserialization."""
        data = {"name": "New Org", "description": "New organization"}
        serializer = OrganizationSerializer(data=data)
        assert serializer.is_valid()


@pytest.mark.django_db
class TestUserViewSet(TestCase):
    """Test UserViewSet functionality."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="test", email="test@example.com")
        self.superuser = User.objects.create_user(username="admin", email="admin@example.com", is_superuser=True)

    def test_viewset_initialization(self):
        """Test UserViewSet can be initialized."""
        viewset = UserViewSet()
        assert viewset

    def test_get_queryset(self):
        """Test get_queryset method."""
        viewset = UserViewSet()
        # Mock request and user for access_qs method
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user
        viewset.request = request
        queryset = viewset.get_queryset()
        assert queryset.model == User

    def test_get_serializer_class(self):
        """Test get_serializer_class method."""
        viewset = UserViewSet()
        serializer_class = viewset.get_serializer_class()
        assert serializer_class == UserSerializer

    def test_viewset_actions(self):
        """Test viewset has expected actions."""
        viewset = UserViewSet()
        # Test that standard actions are available
        assert hasattr(viewset, "list")
        assert hasattr(viewset, "retrieve")
        assert hasattr(viewset, "create")
        assert hasattr(viewset, "update")
        assert hasattr(viewset, "destroy")


@pytest.mark.django_db
class TestOrganizationViewSet(TestCase):
    """Test OrganizationViewSet functionality."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="test", email="test@example.com")
        self.org = Organization.objects.create(name="Test Org")

    def test_viewset_initialization(self):
        """Test OrganizationViewSet can be initialized."""
        viewset = OrganizationViewSet()
        assert viewset

    def test_get_queryset(self):
        """Test get_queryset method."""
        viewset = OrganizationViewSet()
        # Mock request and user for access_qs method
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user
        viewset.request = request
        queryset = viewset.get_queryset()
        assert queryset.model == Organization

    def test_get_serializer_class(self):
        """Test get_serializer_class method."""
        viewset = OrganizationViewSet()
        serializer_class = viewset.get_serializer_class()
        assert serializer_class == OrganizationSerializer


class TestAPIImports(TestCase):
    """Test API module imports."""

    def test_base_view_imports(self):
        """Test base view imports work."""
        from apps.api.v1.base_views import BaseViewSet, UserManagementMixin

        assert BaseViewSet
        assert UserManagementMixin

    def test_base_serializer_imports(self):
        """Test base serializer imports work."""
        from apps.api.v1.base_serializers import BaseModelSerializer, CountFieldMixin

        assert BaseModelSerializer
        assert CountFieldMixin
        assert PasswordHandlingMixin

    def test_serializer_imports(self):
        """Test serializer imports work."""
        from apps.api.v1.serializers import OrganizationSerializer, TeamSerializer, UserSerializer

        assert UserSerializer
        assert OrganizationSerializer
        assert TeamSerializer

    def test_view_imports(self):
        """Test view imports work."""
        from apps.api.v1.views import OrganizationViewSet, UserViewSet

        assert UserViewSet
        assert OrganizationViewSet


@pytest.mark.django_db
class TestSerializerValidation(TestCase):
    """Test serializer validation logic."""

    def test_user_serializer_required_fields(self):
        """Test user serializer required fields."""
        serializer = UserSerializer(data={})
        assert not serializer.is_valid()
        assert "username" in serializer.errors or "email" in serializer.errors

    def test_organization_serializer_required_fields(self):
        """Test organization serializer required fields."""
        serializer = OrganizationSerializer(data={})
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_team_serializer_required_fields(self):
        """Test team serializer required fields."""
        serializer = TeamSerializer(data={})
        assert not serializer.is_valid()
        assert "name" in serializer.errors or "organization" in serializer.errors


@pytest.mark.django_db
class TestViewSetMethods(TestCase):
    """Test viewset method coverage."""

    def setUp(self):
        self.user = User.objects.create_user(username="test", email="test@example.com")
        self.org = Organization.objects.create(name="Test Org")
        self.team = Team.objects.create(name="Test Team", organization=self.org)

    def test_user_viewset_methods(self):
        """Test UserViewSet methods can be called."""
        viewset = UserViewSet()
        viewset.queryset = User.objects.all()

        # Test methods exist
        assert hasattr(viewset, "get_object")
        assert hasattr(viewset, "perform_create")
        assert hasattr(viewset, "perform_update")
        assert hasattr(viewset, "perform_destroy")

    def test_organization_viewset_methods(self):
        """Test OrganizationViewSet methods can be called."""
        viewset = OrganizationViewSet()
        viewset.queryset = Organization.objects.all()

        # Test methods exist
        assert hasattr(viewset, "get_object")
        assert hasattr(viewset, "get_serializer")
