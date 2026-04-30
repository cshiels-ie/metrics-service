"""
Tests for BI connector dashboard API endpoints.

Covers JobDataViewSet and TemplateMetadataViewSet:
- Authentication enforcement
- Feature flag disabled → 404
- Flat serialization with inlined template metadata
- job_id used as lookup field for detail view
- Detail includes label_ids and host_summaries
- Filtering by date range, status, template, organization, project
- Read-only enforcement
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from tests.test_utils import get_test_password

_FLAG_PATCH = "apps.tasks.task_groups.get_feature_enabled_from_db"


def _make_job(
    job_id,
    template_name="Deploy App",
    template_id=10,
    org_id=1,
    org_name="Org A",
    project_id=5,
    project_name="Project X",
    job_status="successful",
    finished_offset_hours=1,
    elapsed=Decimal("30.000"),
    num_hosts=3,
    template_metadata=None,
):
    from apps.dashboard_reports.models import JobData

    now = timezone.now().replace(second=0, microsecond=0)
    finished = now - timedelta(hours=finished_offset_hours)
    return JobData.objects.create(
        job_id=job_id,
        template_name=template_name,
        template_id=template_id,
        organization_id=org_id,
        organization_name=org_name,
        project_id=project_id,
        project_name=project_name,
        status=job_status,
        started=finished - timedelta(seconds=float(elapsed)),
        finished=finished,
        elapsed=elapsed,
        num_hosts=num_hosts,
        template_metadata=template_metadata,
        awx_created=finished,
        awx_modified=finished,
    )


def _make_template_metadata(template_id, template_name="Deploy App", manual_minutes=60, automation_minutes=120):
    from apps.dashboard_reports.models import TemplateMetadata

    return TemplateMetadata.objects.create(
        template_id=template_id,
        template_name=template_name,
        time_taken_manually_execute_minutes=manual_minutes,
        time_taken_create_automation_minutes=automation_minutes,
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestJobDataViewSet(APITestCase):
    """Tests for GET /api/v1/dashboard/jobs/ and /api/v1/dashboard/jobs/<job_id>/"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = patcher.start()
        self.addCleanup(patcher.stop)

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_list_requires_authentication(self):
        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    # --- Serialization ---

    def test_list_inlines_template_metadata_fields(self):
        self.client.force_authenticate(user=self.user)
        tm = _make_template_metadata(template_id=10, manual_minutes=60, automation_minutes=120)
        _make_job(job_id=1001, template_id=10, template_metadata=tm)

        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["template_time_manual_minutes"] == 60
        assert result["template_time_automation_minutes"] == 120

    def test_list_returns_null_for_missing_template_metadata(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=1002, template_metadata=None)

        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["template_time_manual_minutes"] is None
        assert result["template_time_automation_minutes"] is None

    def test_list_does_not_include_label_ids_or_host_summaries(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=1003)

        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url)

        result = response.data["results"][0]
        assert "label_ids" not in result
        assert "host_summaries" not in result

    def test_detail_uses_job_id_as_lookup_field(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=2001)

        url = reverse("bi_connector:dashboard:dashboard-jobs-detail", kwargs={"job_id": 2001})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["job_id"] == 2001

    def test_detail_includes_label_ids(self):
        self.client.force_authenticate(user=self.user)
        from apps.dashboard_reports.models import JobLabel

        job = _make_job(job_id=2002)
        JobLabel.objects.create(job_data=job, label_id=11)
        JobLabel.objects.create(job_data=job, label_id=22)

        url = reverse("bi_connector:dashboard:dashboard-jobs-detail", kwargs={"job_id": 2002})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert sorted(response.data["label_ids"]) == [11, 22]

    def test_detail_includes_host_summaries(self):
        self.client.force_authenticate(user=self.user)
        from apps.dashboard_reports.models import JobHostSummary

        job = _make_job(job_id=2003)
        JobHostSummary.objects.create(job_data=job, host_summary_id=501, host_id=201, host_name="host-a")

        url = reverse("bi_connector:dashboard:dashboard-jobs-detail", kwargs={"job_id": 2003})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["host_summaries"]) == 1
        assert response.data["host_summaries"][0]["host_name"] == "host-a"

    def test_detail_not_found_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:dashboard:dashboard-jobs-detail", kwargs={"job_id": 99999})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Filtering ---

    def test_filter_by_status(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=3001, job_status="successful", finished_offset_hours=2)
        _make_job(job_id=3002, job_status="failed", finished_offset_hours=3)

        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url, {"status": "successful"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "successful"

    def test_filter_by_template_id(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=3003, template_id=10, finished_offset_hours=2)
        _make_job(job_id=3004, template_id=20, finished_offset_hours=3)

        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url, {"template_id": 10})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["template_id"] == 10

    def test_filter_by_organization_id(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=3005, org_id=1, finished_offset_hours=2)
        _make_job(job_id=3006, org_id=2, finished_offset_hours=3)

        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.get(url, {"organization_id": 1})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    # --- Read-only enforcement ---

    def test_post_returns_405(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:dashboard:dashboard-jobs-list")
        response = self.client.post(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self):
        self.client.force_authenticate(user=self.user)
        _make_job(job_id=4001)
        url = reverse("bi_connector:dashboard:dashboard-jobs-detail", kwargs={"job_id": 4001})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.unit
@pytest.mark.django_db
class TestTemplateMetadataViewSet(APITestCase):
    """Tests for GET /api/v1/dashboard/templates/ and /api/v1/dashboard/templates/<template_id>/"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=get_test_password()
        )
        patcher = patch(_FLAG_PATCH, return_value=True)
        self.flag_mock = patcher.start()
        self.addCleanup(patcher.stop)

    # --- Feature flag ---

    def test_flag_disabled_returns_404(self):
        self.client.force_authenticate(user=self.user)
        self.flag_mock.return_value = False
        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Authentication ---

    def test_list_requires_authentication(self):
        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated_returns_200(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    # --- Serialization ---

    def test_list_includes_time_estimate_fields(self):
        self.client.force_authenticate(user=self.user)
        _make_template_metadata(template_id=10, manual_minutes=45, automation_minutes=90)

        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert result["time_taken_manually_execute_minutes"] == 45
        assert result["time_taken_create_automation_minutes"] == 90

    def test_detail_uses_template_id_as_lookup_field(self):
        self.client.force_authenticate(user=self.user)
        _make_template_metadata(template_id=42, template_name="Patch Hosts")

        url = reverse("bi_connector:dashboard:dashboard-templates-detail", kwargs={"template_id": 42})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["template_id"] == 42
        assert response.data["template_name"] == "Patch Hosts"

    # --- Filtering ---

    def test_filter_by_template_id(self):
        self.client.force_authenticate(user=self.user)
        _make_template_metadata(template_id=10, template_name="Deploy App")
        _make_template_metadata(template_id=20, template_name="Patch Hosts")

        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.get(url, {"template_id": 10})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["template_name"] == "Deploy App"

    def test_filter_by_template_name_icontains(self):
        self.client.force_authenticate(user=self.user)
        _make_template_metadata(template_id=10, template_name="Deploy App")
        _make_template_metadata(template_id=20, template_name="Patch Hosts")

        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.get(url, {"template_name__icontains": "deploy"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    # --- Read-only enforcement ---

    def test_post_returns_405(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("bi_connector:dashboard:dashboard-templates-list")
        response = self.client.post(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
