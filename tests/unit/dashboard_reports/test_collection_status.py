"""Unit tests for the DashboardCollectionStatusViewSet."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from apps.dashboard_reports.urls import router
from apps.dashboard_reports.viewsets.collection_status import DashboardCollectionStatusViewSet

PATCH_FLAG = "apps.dashboard_reports.viewsets.collection_status.get_feature_enabled_from_db"
PATCH_TASK = "apps.dashboard_reports.viewsets.collection_status.Task"
PATCH_PERM = "ansible_base.rbac.api.permissions.IsSystemAdminOrAuditor.has_permission"

factory = APIRequestFactory()
view = DashboardCollectionStatusViewSet.as_view({"get": "list"})


@pytest.mark.unit
class TestDashboardCollectionStatusViewSet:
    """Tests for DashboardCollectionStatusViewSet.list()."""

    @pytest.fixture(autouse=True)
    def bypass_permissions(self):
        with patch(PATCH_PERM, return_value=True):
            yield

    def _get(self):
        request = factory.get("/api/v1/dashboard_reports/collection_status/")
        request.user = MagicMock()
        return view(request)

    @patch(PATCH_FLAG, return_value=False)
    @patch(PATCH_TASK)
    def test_flag_disabled_returns_nulls(self, mock_task_class, mock_flag):
        response = self._get()

        assert response.status_code == 200
        assert response.data == {
            "enabled": False,
            "next_run": None,
            "initial_collection_status": None,
        }
        mock_task_class.objects.filter.assert_not_called()

    @patch(PATCH_FLAG, return_value=True)
    @patch(PATCH_TASK)
    def test_flag_enabled_tasks_exist(self, mock_task_class, mock_flag):
        mock_data_task = MagicMock()
        mock_data_task.get_next_run_time.return_value = "2026-04-15T06:00:00+00:00"

        mock_initial_task = MagicMock()
        mock_initial_task.status = "completed"

        mock_task_class.objects.filter.return_value.first.side_effect = [
            mock_data_task,
            mock_initial_task,
        ]

        response = self._get()

        assert response.status_code == 200
        assert response.data == {
            "enabled": True,
            "next_run": "2026-04-15T06:00:00+00:00",
            "initial_collection_status": "completed",
        }

    @patch(PATCH_FLAG, return_value=True)
    @patch(PATCH_TASK)
    def test_flag_enabled_tasks_not_found(self, mock_task_class, mock_flag):
        mock_task_class.objects.filter.return_value.first.return_value = None

        response = self._get()

        assert response.status_code == 200
        assert response.data == {
            "enabled": True,
            "next_run": None,
            "initial_collection_status": None,
        }

    @patch(PATCH_FLAG, return_value=True)
    @patch(PATCH_TASK)
    def test_initial_status_running(self, mock_task_class, mock_flag):
        mock_data_task = MagicMock()
        mock_data_task.get_next_run_time.return_value = None

        mock_initial_task = MagicMock()
        mock_initial_task.status = "running"

        mock_task_class.objects.filter.return_value.first.side_effect = [
            mock_data_task,
            mock_initial_task,
        ]

        response = self._get()

        assert response.data["initial_collection_status"] == "running"

    @patch(PATCH_FLAG, return_value=True)
    @patch(PATCH_TASK)
    def test_initial_status_failed(self, mock_task_class, mock_flag):
        mock_data_task = MagicMock()
        mock_data_task.get_next_run_time.return_value = None

        mock_initial_task = MagicMock()
        mock_initial_task.status = "failed"

        mock_task_class.objects.filter.return_value.first.side_effect = [
            mock_data_task,
            mock_initial_task,
        ]

        response = self._get()

        assert response.data["initial_collection_status"] == "failed"

    @patch(PATCH_FLAG, return_value=True)
    @patch(PATCH_TASK)
    def test_queries_correct_tasks(self, mock_task_class, mock_flag):
        """next_run comes from hourly_unified_jobs (the hook driver), not the removed data task."""
        mock_task_class.objects.filter.return_value.first.return_value = None

        self._get()

        calls = mock_task_class.objects.filter.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs == {
            "name": "hourly_unified_jobs",
            "is_system_task": True,
        }
        assert calls[1].kwargs == {
            "function_name": "collect_dashboard_reports_initial_data",
            "is_system_task": True,
        }

    def test_permission_class(self):
        from ansible_base.rbac.api.permissions import IsSystemAdminOrAuditor

        assert IsSystemAdminOrAuditor in DashboardCollectionStatusViewSet.permission_classes


@pytest.mark.unit
class TestDashboardCollectionStatusURL:
    """Tests for URL registration and reversal."""

    def test_url_reverse(self):
        url = reverse("v1:collection_status-list")
        assert "collection_status" in url

    def test_viewset_registered_in_router(self):
        registered = [reg[1] for reg in router.registry]
        assert DashboardCollectionStatusViewSet in registered
