"""
Unit tests for the SubscriptionCost API endpoint.

Covers:
- SubscriptionCostViewSet: list and update endpoints
- SubscriptionCostSerializer: field validation
- Permission enforcement via IsSystemAdminOrAuditor
- SubscriptionCost.get_subscription_cost_by_id classmethod
"""

import decimal

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.dashboard_reports.models import SubscriptionCost
from apps.dashboard_reports.serializers import SubscriptionCostSerializer
from apps.dashboard_reports.viewsets.subscription_cost import SubscriptionCostViewSet
from tests.test_utils import get_test_password

# =============================================================================
# SubscriptionCostViewSet Tests - List and Update
# =============================================================================


@pytest.mark.unit
class TestSubscriptionCostViewSet(APITestCase):
    """Test SubscriptionCostViewSet list and update endpoints."""

    def setUp(self) -> None:
        """Set up test data."""
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.client.force_authenticate(user=self.user)
        self.subscription_cost = SubscriptionCost.get()
        # Snapshot original values so tearDown can restore them
        self._original_monthly = self.subscription_cost.monthly_subscription_cost
        self._original_rate = self.subscription_cost.engineer_avg_hourly_rate
        self._original_include = self.subscription_cost.include_template_creation_time_in_costs

    def tearDown(self) -> None:
        """Restore SubscriptionCost to its original default values."""
        self.subscription_cost.monthly_subscription_cost = self._original_monthly
        self.subscription_cost.engineer_avg_hourly_rate = self._original_rate
        self.subscription_cost.include_template_creation_time_in_costs = self._original_include
        self.subscription_cost.save()

    # ------------------------------------------------------------------
    # List Tests
    # ------------------------------------------------------------------

    def test_list_returns_200(self) -> None:
        """Test GET /api/v1/dashboard_reports/subscription_costs/ returns 200."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_subscription_cost_entries(self) -> None:
        """Test list endpoint returns the existing SubscriptionCost entries."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) >= 1

    def test_list_response_contains_expected_fields(self) -> None:
        """Test list response contains all expected serializer fields."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        entry = response.data[0]
        expected_fields = {
            "id",
            "monthly_subscription_cost",
            "engineer_avg_hourly_rate",
            "include_template_creation_time_in_costs",
        }
        assert expected_fields.issubset(set(entry.keys()))

    def test_list_pagination_is_disabled(self) -> None:
        """Test list endpoint returns a plain list, not a paginated response."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        # Pagination would wrap results in a dict with a 'results' key
        assert isinstance(response.data, list)

    def test_list_auto_creates_singleton_on_empty_db(self) -> None:
        """Test GET /subscription_costs/ returns a record even when the DB table is empty.

        Regression test: get_queryset() must trigger singleton creation so admins
        see a record to configure before the report endpoint has been called.
        """
        SubscriptionCost.objects.all().delete()
        assert SubscriptionCost.objects.count() == 0

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) == 1
        assert decimal.Decimal(response.data[0]["monthly_subscription_cost"]) == decimal.Decimal("5000.00")
        assert decimal.Decimal(response.data[0]["engineer_avg_hourly_rate"]) == decimal.Decimal("60.00")

    # ------------------------------------------------------------------
    # Update Tests
    # ------------------------------------------------------------------

    def test_update_returns_200(self) -> None:
        """Test PUT /api/v1/dashboard_reports/subscription_costs/{id}/ returns 200."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "1500.00",
            "engineer_avg_hourly_rate": "75.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

    def test_update_persists_monthly_subscription_cost(self) -> None:
        """Test updating monthly_subscription_cost persists the new value."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "2000.00",
            "engineer_avg_hourly_rate": self.subscription_cost.engineer_avg_hourly_rate,
            "include_template_creation_time_in_costs": self.subscription_cost.include_template_creation_time_in_costs,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert decimal.Decimal(response.data["monthly_subscription_cost"]) == decimal.Decimal("2000.00")

        self.subscription_cost.refresh_from_db()
        assert self.subscription_cost.monthly_subscription_cost == decimal.Decimal("2000.00")

    def test_update_persists_engineer_avg_hourly_rate(self) -> None:
        """Test updating engineer_avg_hourly_rate persists the new value."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": self.subscription_cost.monthly_subscription_cost,
            "engineer_avg_hourly_rate": "99.50",
            "include_template_creation_time_in_costs": self.subscription_cost.include_template_creation_time_in_costs,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert decimal.Decimal(response.data["engineer_avg_hourly_rate"]) == decimal.Decimal("99.50")

        self.subscription_cost.refresh_from_db()
        assert self.subscription_cost.engineer_avg_hourly_rate == decimal.Decimal("99.50")

    def test_update_persists_include_template_creation_time_in_costs(self) -> None:
        """Test toggling include_template_creation_time_in_costs persists correctly."""
        self.client.force_authenticate(user=self.user)

        original = self.subscription_cost.include_template_creation_time_in_costs
        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": self.subscription_cost.monthly_subscription_cost,
            "engineer_avg_hourly_rate": self.subscription_cost.engineer_avg_hourly_rate,
            "include_template_creation_time_in_costs": not original,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["include_template_creation_time_in_costs"] == (not original)

        self.subscription_cost.refresh_from_db()
        assert self.subscription_cost.include_template_creation_time_in_costs == (not original)

    def test_update_falls_back_to_existing_values_for_missing_fields(self) -> None:
        """Test that omitting a field in the request body keeps the existing value."""
        self.client.force_authenticate(user=self.user)

        original_rate = self.subscription_cost.engineer_avg_hourly_rate
        original_include = self.subscription_cost.include_template_creation_time_in_costs
        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        # Only send monthly_subscription_cost; the other two fields are omitted entirely
        data = {
            "monthly_subscription_cost": "500.00",
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert decimal.Decimal(response.data["engineer_avg_hourly_rate"]) == original_rate
        assert response.data["include_template_creation_time_in_costs"] == original_include

    def test_update_with_nonexistent_id_returns_404(self) -> None:
        """Test PUT with a non-existent PK returns 404."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": 999999})
        data = {
            "monthly_subscription_cost": "100.00",
            "engineer_avg_hourly_rate": "50.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_with_partial_data_preserves_other_fields(self) -> None:
        """Test that omitting fields in the request body keeps existing DB values,
        i.e. the viewset falls back to the instance values for missing fields."""
        self.client.force_authenticate(user=self.user)

        # Set known starting values
        self.subscription_cost.monthly_subscription_cost = decimal.Decimal("1000.00")
        self.subscription_cost.engineer_avg_hourly_rate = decimal.Decimal("50.00")
        self.subscription_cost.include_template_creation_time_in_costs = True
        self.subscription_cost.save()

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        # Only send monthly_subscription_cost, omit the other two fields entirely
        data = {
            "monthly_subscription_cost": "1234.00",
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert decimal.Decimal(response.data["monthly_subscription_cost"]) == decimal.Decimal("1234.00")
        # These were not sent — they should be unchanged
        assert decimal.Decimal(response.data["engineer_avg_hourly_rate"]) == decimal.Decimal("50.00")
        assert response.data["include_template_creation_time_in_costs"] is True

        self.subscription_cost.refresh_from_db()
        assert self.subscription_cost.monthly_subscription_cost == decimal.Decimal("1234.00")
        assert self.subscription_cost.engineer_avg_hourly_rate == decimal.Decimal("50.00")
        assert self.subscription_cost.include_template_creation_time_in_costs is True

    def test_update_rejects_negative_monthly_subscription_cost(self) -> None:
        """Test updating monthly_subscription_cost with a negative value returns 400."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "-100.00",
            "engineer_avg_hourly_rate": "50.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_rejects_negative_engineer_avg_hourly_rate(self) -> None:
        """Test updating engineer_avg_hourly_rate with a negative value returns 400."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "100.00",
            "engineer_avg_hourly_rate": "-50.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_response_includes_id(self) -> None:
        """Test the update response includes the id field."""
        self.client.force_authenticate(user=self.user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "300.00",
            "engineer_avg_hourly_rate": "40.00",
            "include_template_creation_time_in_costs": False,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "id" in response.data
        assert response.data["id"] == self.subscription_cost.pk

    # ------------------------------------------------------------------
    # ViewSet introspection
    # ------------------------------------------------------------------

    def test_get_serializer_class_for_list_action(self) -> None:
        """Test get_serializer_class returns SubscriptionCostSerializer for list."""
        viewset = SubscriptionCostViewSet()
        viewset.action = "list"
        assert viewset.get_serializer_class() == SubscriptionCostSerializer

    def test_get_queryset_returns_all_subscription_costs(self) -> None:
        """Test get_queryset returns all SubscriptionCost objects."""
        viewset = SubscriptionCostViewSet()
        qs = viewset.get_queryset()
        assert qs.model == SubscriptionCost


# =============================================================================
# Permission Tests
# =============================================================================


@pytest.mark.unit
class TestSubscriptionCostPermissions(APITestCase):
    """Test permission enforcement on the SubscriptionCost endpoints."""

    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password=get_test_password()
        )
        self.subscription_cost = SubscriptionCost.get()
        self._original_monthly = self.subscription_cost.monthly_subscription_cost
        self._original_rate = self.subscription_cost.engineer_avg_hourly_rate
        self._original_include = self.subscription_cost.include_template_creation_time_in_costs

    def tearDown(self) -> None:
        self.subscription_cost.monthly_subscription_cost = self._original_monthly
        self.subscription_cost.engineer_avg_hourly_rate = self._original_rate
        self.subscription_cost.include_template_creation_time_in_costs = self._original_include
        self.subscription_cost.save()

    def test_list_denied_for_unauthenticated_user(self) -> None:
        """Test list is forbidden for unauthenticated requests."""
        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_denied_for_non_admin_user(self) -> None:
        """Test list is forbidden for a regular authenticated (non-superuser) user."""
        self.client.force_authenticate(user=self.regular_user)

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_accessible_for_superuser(self) -> None:
        """Test list is accessible for a superuser."""
        self.client.force_authenticate(user=self.admin)

        url = reverse("v1:subscription_costs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_update_denied_for_unauthenticated_user(self) -> None:
        """Test update is forbidden for unauthenticated requests."""
        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "100.00",
            "engineer_avg_hourly_rate": "50.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_denied_for_non_admin_user(self) -> None:
        """Test update is forbidden for a regular authenticated (non-superuser) user."""
        self.client.force_authenticate(user=self.regular_user)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "100.00",
            "engineer_avg_hourly_rate": "50.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_accessible_for_superuser(self) -> None:
        """Test update is accessible for a superuser."""
        self.client.force_authenticate(user=self.admin)

        url = reverse("v1:subscription_costs-detail", kwargs={"pk": self.subscription_cost.pk})
        data = {
            "monthly_subscription_cost": "100.00",
            "engineer_avg_hourly_rate": "50.00",
            "include_template_creation_time_in_costs": True,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# Serializer Tests
# =============================================================================


@pytest.mark.unit
class TestSubscriptionCostSerializer(TestCase):
    """Test SubscriptionCostSerializer field validation."""

    def setUp(self) -> None:
        self.instance = SubscriptionCost.get()
        self._original_monthly = self.instance.monthly_subscription_cost
        self._original_rate = self.instance.engineer_avg_hourly_rate
        self._original_include = self.instance.include_template_creation_time_in_costs

    def tearDown(self) -> None:
        self.instance.monthly_subscription_cost = self._original_monthly
        self.instance.engineer_avg_hourly_rate = self._original_rate
        self.instance.include_template_creation_time_in_costs = self._original_include
        self.instance.save()

    def test_valid_data_is_accepted(self) -> None:
        """Test serializer accepts a fully valid payload."""
        data = {
            "monthly_subscription_cost": "1200.00",
            "engineer_avg_hourly_rate": "60.00",
            "include_template_creation_time_in_costs": True,
        }
        serializer = SubscriptionCostSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_negative_monthly_subscription_cost_is_rejected(self) -> None:
        """Test serializer rejects negative monthly_subscription_cost."""
        data = {
            "monthly_subscription_cost": "-1.00",
            "engineer_avg_hourly_rate": "60.00",
            "include_template_creation_time_in_costs": True,
        }
        serializer = SubscriptionCostSerializer(data=data)
        assert not serializer.is_valid()
        assert "monthly_subscription_cost" in serializer.errors

    def test_negative_engineer_avg_hourly_rate_is_rejected(self) -> None:
        """Test serializer rejects negative engineer_avg_hourly_rate."""
        data = {
            "monthly_subscription_cost": "500.00",
            "engineer_avg_hourly_rate": "-10.00",
            "include_template_creation_time_in_costs": True,
        }
        serializer = SubscriptionCostSerializer(data=data)
        assert not serializer.is_valid()
        assert "engineer_avg_hourly_rate" in serializer.errors

    def test_zero_values_are_accepted(self) -> None:
        """Test serializer accepts 0.00 for cost fields (boundary value)."""
        data = {
            "monthly_subscription_cost": "0.00",
            "engineer_avg_hourly_rate": "0.00",
            "include_template_creation_time_in_costs": True,
        }
        serializer = SubscriptionCostSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_include_template_creation_time_preserves_existing_when_omitted(self) -> None:
        """When include_template_creation_time_in_costs is omitted from a PUT request,
        validated_data should not contain the key so that update() falls back to the
        existing instance value rather than silently overwriting False with True."""
        data = {
            "monthly_subscription_cost": "100.00",
            "engineer_avg_hourly_rate": "50.00",
            # include_template_creation_time_in_costs intentionally omitted
        }
        serializer = SubscriptionCostSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert "include_template_creation_time_in_costs" not in serializer.validated_data

    def test_update_method_persists_changes(self) -> None:
        """Test serializer update() saves all fields to the instance."""
        data = {
            "monthly_subscription_cost": "750.00",
            "engineer_avg_hourly_rate": "85.00",
            "include_template_creation_time_in_costs": False,
        }
        serializer = SubscriptionCostSerializer(instance=self.instance, data=data)
        assert serializer.is_valid(), serializer.errors

        updated = serializer.save()

        assert updated.monthly_subscription_cost == decimal.Decimal("750.00")
        assert updated.engineer_avg_hourly_rate == decimal.Decimal("85.00")
        assert updated.include_template_creation_time_in_costs is False

    def test_id_field_is_read_only(self) -> None:
        """Test the id field is read-only and cannot be set via input."""
        serializer = SubscriptionCostSerializer(instance=self.instance)
        assert serializer.fields["id"].read_only is True

    def test_serializer_exposes_expected_fields(self) -> None:
        """Test serializer data contains all expected fields."""
        serializer = SubscriptionCostSerializer(instance=self.instance)
        data = serializer.data
        expected_fields = {
            "id",
            "monthly_subscription_cost",
            "engineer_avg_hourly_rate",
            "include_template_creation_time_in_costs",
        }
        assert expected_fields == set(data.keys())


# =============================================================================
# Import Tests
# =============================================================================


@pytest.mark.unit
class TestSubscriptionCostImports(TestCase):
    """Smoke tests: verify all new symbols can be imported."""

    def test_viewset_is_importable(self) -> None:
        """Test SubscriptionCostViewSet can be imported."""
        assert callable(SubscriptionCostViewSet)

    def test_serializer_is_importable(self) -> None:
        """Test SubscriptionCostSerializer can be imported."""
        assert callable(SubscriptionCostSerializer)
