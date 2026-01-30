"""
Unit tests for dashboard_reports serializers.

Tests verify that serializers match TypeScript interfaces exactly
and properly serialize/deserialize data.
"""

import pytest
from apps.dashboard_reports.serializers import (
    ClusterOptionSerializer,
    CurrencySerializer,
    FilterOptionResponseSerializer,
    FilterOptionSerializer,
    FilterSetSerializer,
    TemplateMetadataSerializer,
    UserPreferenceSerializer,
)


@pytest.mark.unit
class TestCurrencySerializer:
    """Test CurrencySerializer matches TypeScript interface: {id: number; name: string; symbol: string;}"""

    def test_serialization(self):
        """Test currency serialization returns correct fields."""
        data = {'id': 1, 'name': 'US Dollar', 'symbol': '$'}
        serializer = CurrencySerializer(data=data)
        assert serializer.is_valid()
        assert serializer.data == data

    def test_required_fields(self):
        """Test all required fields are present."""
        # Missing name
        data = {'id': 1, 'symbol': '$'}
        serializer = CurrencySerializer(data=data)
        assert not serializer.is_valid()
        assert 'name' in serializer.errors

    def test_typescript_interface_match(self):
        """Test serialized data matches TypeScript interface exactly."""
        data = {'id': 1, 'name': 'Euro', 'symbol': '€'}
        serializer = CurrencySerializer(data=data)
        assert serializer.is_valid()

        # Verify exact field match
        result = serializer.data
        assert set(result.keys()) == {'id', 'name', 'symbol'}
        assert isinstance(result['id'], int)
        assert isinstance(result['name'], str)
        assert isinstance(result['symbol'], str)


@pytest.mark.unit
class TestFilterSetSerializer:
    """Test FilterSetSerializer matches TypeScript interface: {id: number; name: string; filters: any;}"""

    def test_serialization(self):
        """Test filter set serialization with JSON filters."""
        data = {
            'id': 1,
            'name': 'My Saved View',
            'filters': {'organizations': [1, 2], 'projects': [3], 'date_range': {'start': '2025-01-01'}},
        }
        serializer = FilterSetSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.data['name'] == 'My Saved View'
        assert serializer.data['filters']['organizations'] == [1, 2]

    def test_filters_json_field(self):
        """Test filters field accepts any JSON structure."""
        test_cases = [
            {'filters': {}},  # Empty object
            {'filters': {'key': 'value'}},  # Simple object
            {'filters': {'nested': {'deep': {'value': 123}}}},  # Nested
            {'filters': {'array': [1, 2, 3]}},  # Arrays
        ]

        for case in test_cases:
            data = {'id': 1, 'name': 'Test', **case}
            serializer = FilterSetSerializer(data=data)
            assert serializer.is_valid(), f"Failed for {case}: {serializer.errors}"


@pytest.mark.unit
class TestFilterOptionSerializer:
    """Test FilterOptionSerializer matches TypeScript interface: {id: number; name: string;}"""

    def test_simple_option(self):
        """Test basic filter option serialization."""
        data = {'id': 5, 'name': 'Production'}
        serializer = FilterOptionSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.data == data

    def test_field_types(self):
        """Test field types match TypeScript."""
        data = {'id': 10, 'name': 'Test Organization'}
        serializer = FilterOptionSerializer(data=data)
        assert serializer.is_valid()
        assert isinstance(serializer.data['id'], int)
        assert isinstance(serializer.data['name'], str)


@pytest.mark.unit
class TestClusterOptionSerializer:
    """Test ClusterOptionSerializer matches TypeScript interface: {id: number; name: string; type: string;}"""

    def test_cluster_with_type(self):
        """Test cluster option includes type field."""
        data = {'id': 1, 'name': 'Default EE', 'type': 'execution_environment'}
        serializer = ClusterOptionSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.data == data

    def test_typescript_match(self):
        """Test serialized data has exactly 3 fields."""
        data = {'id': 2, 'name': 'Custom EE', 'type': 'execution_environment'}
        serializer = ClusterOptionSerializer(data=data)
        assert serializer.is_valid()
        assert set(serializer.data.keys()) == {'id', 'name', 'type'}


@pytest.mark.unit
class TestFilterOptionResponseSerializer:
    """
    Test FilterOptionResponseSerializer matches TypeScript FilterOptionResponse interface.

    This is the CRITICAL master aggregation serializer.
    """

    def test_all_required_fields(self):
        """Test all required fields are present in serialization."""
        data = {
            # Global settings
            'automated_process_cost_per_minute': '0.50',
            'manual_cost_automation_per_hour': '50.00',
            'enable_template_creation_time': True,
            'max_pdf_job_templates': 100,
            # User preference
            'currency': 1,
            # Arrays
            'currencies': [],
            'filter_sets': [],
            'organizations': [],
            'projects': [],
            'labels': [],
            'instances': [],
            'clusters': [],
            'date_ranges': [],
        }

        serializer = FilterOptionResponseSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_typescript_interface_complete_match(self):
        """Test complete serialization matches TypeScript interface."""
        data = {
            'automated_process_cost_per_minute': '0.75',
            'manual_cost_automation_per_hour': '60.00',
            'enable_template_creation_time': False,
            'max_pdf_job_templates': 150,
            'currency': 2,
            'currencies': [{'id': 1, 'name': 'USD', 'symbol': '$'}],
            'filter_sets': [{'id': 1, 'name': 'My View', 'filters': {}}],
            'organizations': [{'id': 1, 'name': 'Default'}],
            'projects': [{'id': 5, 'name': 'Demo'}],
            'labels': [{'id': 1, 'name': 'prod'}],
            'instances': [{'id': 1, 'name': 'awx-1'}],
            'clusters': [{'id': 1, 'name': 'Default EE', 'type': 'execution_environment'}],
            'date_ranges': [{'id': 1, 'name': 'Last 7 days'}],
        }

        serializer = FilterOptionResponseSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        # Verify all expected fields present
        expected_fields = {
            'automated_process_cost_per_minute',
            'manual_cost_automation_per_hour',
            'enable_template_creation_time',
            'max_pdf_job_templates',
            'currency',
            'currencies',
            'filter_sets',
            'organizations',
            'projects',
            'labels',
            'instances',
            'clusters',
            'date_ranges',
        }
        assert set(serializer.data.keys()) == expected_fields


@pytest.mark.unit
class TestTemplateMetadataSerializer:
    """Test TemplateMetadataSerializer for template override functionality."""

    def test_create_metadata(self):
        """Test creating new template metadata."""
        data = {
            'template_name': 'Deploy Production',
            'time_taken_manually_execute_minutes': 120,
            'time_taken_create_automation_minutes': 240,
            'custom_cost_per_minute': '1.50',
            'notes': 'Complex deployment',
        }

        serializer = TemplateMetadataSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_optional_fields(self):
        """Test that override fields are optional."""
        # Minimal valid data
        data = {'template_name': 'Test Template'}

        serializer = TemplateMetadataSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_nullable_overrides(self):
        """Test null values for override fields."""
        data = {
            'template_name': 'Test',
            'time_taken_manually_execute_minutes': None,
            'time_taken_create_automation_minutes': None,
            'custom_cost_per_minute': None,
        }

        serializer = TemplateMetadataSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.unit
class TestUserPreferenceSerializer:
    """Test UserPreferenceSerializer for user settings."""

    def test_currency_preference(self):
        """Test saving currency preference."""
        data = {'currency': 2}

        serializer = UserPreferenceSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.data['currency'] == 2

    def test_preferences_data_json(self):
        """Test preferences_data accepts JSON."""
        data = {'currency': 1, 'preferences_data': {'theme': 'dark', 'notifications': True}}

        serializer = UserPreferenceSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.data['preferences_data']['theme'] == 'dark'

    def test_all_fields_optional(self):
        """Test that all fields are optional."""
        data = {}

        serializer = UserPreferenceSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.unit
class TestTypeScriptInterfaceCompatibility:
    """
    Integration tests verifying complete TypeScript interface compatibility.

    These tests ensure zero frontend code changes are required.
    """

    def test_currency_type_compatibility(self):
        """Verify Currency matches: {id: number; name: string; symbol: string;}"""
        data = {'id': 1, 'name': 'US Dollar', 'symbol': '$'}
        serializer = CurrencySerializer(data=data)
        assert serializer.is_valid()

        # Check exact type match
        result = serializer.data
        assert type(result['id']) in [int]
        assert type(result['name']) in [str]
        assert type(result['symbol']) in [str]

    def test_filter_set_type_compatibility(self):
        """Verify FilterSet matches: {id: number; name: string; filters: any;}"""
        data = {'id': 1, 'name': 'View', 'filters': {'any': 'value'}}
        serializer = FilterSetSerializer(data=data)
        assert serializer.is_valid()

        result = serializer.data
        assert type(result['id']) in [int]
        assert type(result['name']) in [str]
        assert type(result['filters']) in [dict]

    def test_complete_filter_response_compatibility(self):
        """Verify FilterOptionResponse matches complete TypeScript interface."""
        data = {
            'automated_process_cost_per_minute': '0.50',
            'manual_cost_automation_per_hour': '50.00',
            'enable_template_creation_time': True,
            'max_pdf_job_templates': 100,
            'currency': 1,
            'currencies': [],
            'filter_sets': [],
            'organizations': [],
            'projects': [],
            'labels': [],
            'instances': [],
            'clusters': [],
            'date_ranges': [],
        }

        serializer = FilterOptionResponseSerializer(data=data)
        assert serializer.is_valid()

        result = serializer.data
        # String fields
        assert type(result['automated_process_cost_per_minute']) in [str]
        assert type(result['manual_cost_automation_per_hour']) in [str]
        # Boolean field
        assert type(result['enable_template_creation_time']) in [bool]
        # Number fields
        assert type(result['max_pdf_job_templates']) in [int]
        assert type(result['currency']) in [int]
        # Array fields
        assert type(result['currencies']) in [list]
        assert type(result['filter_sets']) in [list]
        assert type(result['organizations']) in [list]
