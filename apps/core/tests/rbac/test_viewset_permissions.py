import uuid

import pytest
from ansible_base.rbac.models import RoleDefinition
from rest_framework.test import APIClient


def make_user_data():
    unique_id = uuid.uuid4().hex[:8]
    return {"username": f"newuser-{unique_id}", "password": f"password-{unique_id}"}


@pytest.mark.django_db
class TestSuperuserAccess:
    """Superuser should have full CRUD on all resources."""

    @pytest.mark.parametrize(
        "endpoint,data_factory",
        [
            ("/api/v1/organizations/", lambda: {"name": "New Org"}),
            ("/api/v1/users/", make_user_data),
        ],
    )
    def test_superuser_can_create(self, admin_api_client, endpoint, data_factory):
        data = data_factory()
        r = admin_api_client.post(endpoint, data)
        assert r.status_code == 201

    def test_superuser_can_create_team(self, admin_api_client, organization):
        r = admin_api_client.post("/api/v1/teams/", {"name": "New Team", "organization": organization.id})
        assert r.status_code == 201

    def test_superuser_can_delete_user(self, admin_api_client, rando):
        r = admin_api_client.delete(f"/api/v1/users/{rando.id}/")
        assert r.status_code == 204


@pytest.mark.django_db
class TestNormalUserAccess:
    """Normal users without roles should have no access."""

    @pytest.mark.parametrize(
        "endpoint,data_factory",
        [
            ("/api/v1/organizations/", lambda: {"name": "New Org"}),
            ("/api/v1/users/", make_user_data),
        ],
    )
    def test_cannot_create(self, user_api_client, endpoint, data_factory):
        data = data_factory()
        r = user_api_client.post(endpoint, data)
        assert r.status_code == 403

    def test_cannot_create_team(self, user_api_client, organization):
        r = user_api_client.post("/api/v1/teams/", {"name": "Team", "organization": organization.id})
        assert r.status_code == 403

    @pytest.mark.parametrize("endpoint", ["/api/v1/organizations/", "/api/v1/teams/"])
    def test_sees_empty_list(self, user_api_client, organization, team, endpoint):
        r = user_api_client.get(endpoint)
        assert r.status_code == 200
        results = r.data["results"] if isinstance(r.data, dict) else r.data
        assert results == []

    def test_can_access_me_endpoint(self, user_api_client, rando):
        r = user_api_client.get("/api/v1/users/me/")
        assert r.status_code == 200
        assert r.data["username"] == rando.username


@pytest.mark.django_db
class TestOrgAdminAccess:
    """Org Admin can manage their org and create teams in it."""

    def test_can_see_organization(self, user_api_client, rando, organization, org_admin_rd):
        org_admin_rd.give_permission(rando, organization)
        r = user_api_client.get("/api/v1/organizations/")
        assert r.status_code == 200
        results = r.data["results"] if isinstance(r.data, dict) else r.data
        assert len(results) == 1

    def test_can_update_organization(self, user_api_client, rando, organization, org_admin_rd):
        org_admin_rd.give_permission(rando, organization)
        r = user_api_client.patch(f"/api/v1/organizations/{organization.id}/", {"description": "Updated"})
        assert r.status_code == 200

    def test_cannot_create_organization(self, user_api_client, rando, organization, org_admin_rd):
        org_admin_rd.give_permission(rando, organization)
        r = user_api_client.post("/api/v1/organizations/", {"name": "Another Org"})
        assert r.status_code == 403

    def test_can_create_team_in_org(self, user_api_client, rando, organization, org_admin_rd):
        org_admin_rd.give_permission(rando, organization)
        r = user_api_client.post("/api/v1/teams/", {"name": "New Team", "organization": organization.id})
        assert r.status_code == 201


@pytest.mark.django_db
class TestTeamRoleAccess:
    """Team Admin vs Team Member permissions."""

    def test_team_admin_can_update_team(self, user_api_client, rando, team, team_admin_rd):
        team_admin_rd.give_permission(rando, team)
        r = user_api_client.patch(f"/api/v1/teams/{team.id}/", {"description": "Updated"})
        assert r.status_code == 200

    def test_team_member_cannot_update_team(self, user_api_client, rando, team, team_member_rd):
        team_member_rd.give_permission(rando, team)
        r = user_api_client.patch(f"/api/v1/teams/{team.id}/", {"description": "Fail"})
        assert r.status_code == 403

    def test_team_member_can_see_team(self, user_api_client, rando, team, team_member_rd):
        team_member_rd.give_permission(rando, team)
        r = user_api_client.get("/api/v1/teams/")
        assert r.status_code == 200
        results = r.data["results"] if isinstance(r.data, dict) else r.data
        assert len(results) == 1


# ---------------------------------------------------------------------------
# AAP-74790: activitystream, feature_flags_state, and users RBAC enforcement
# ---------------------------------------------------------------------------


@pytest.fixture
def platform_auditor(db, rando):
    """Assign the Platform Auditor global role to rando and return the user."""
    auditor_rd = RoleDefinition.objects.get(name="Platform Auditor")
    auditor_rd.give_global_permission(rando)
    return rando


@pytest.fixture
def auditor_api_client(platform_auditor):
    """API client authenticated as a Platform Auditor."""
    client = APIClient()
    client.force_authenticate(user=platform_auditor)
    return client


@pytest.mark.django_db
class TestUsersEndpointRBAC:
    """Users list/retrieve must require at least Platform Auditor (AAP-74790)."""

    def test_basic_user_cannot_list_users(self, user_api_client):
        r = user_api_client.get("/api/v1/users/")
        assert r.status_code == 403

    def test_platform_auditor_can_list_users(self, auditor_api_client):
        r = auditor_api_client.get("/api/v1/users/")
        assert r.status_code == 200

    def test_superuser_can_list_users(self, admin_api_client):
        r = admin_api_client.get("/api/v1/users/")
        assert r.status_code == 200

    def test_basic_user_can_access_me_endpoint(self, user_api_client, rando):
        """The /me action must remain accessible to any authenticated user."""
        r = user_api_client.get("/api/v1/users/me/")
        assert r.status_code == 200
        assert r.data["username"] == rando.username

    def test_unauthenticated_user_cannot_list_users(self):
        client = APIClient()
        r = client.get("/api/v1/users/")
        assert r.status_code in (401, 403)


@pytest.mark.django_db
class TestActivityStreamRBAC:
    """Activity stream must require at least Platform Auditor (AAP-74790)."""

    def test_basic_user_cannot_access_activitystream(self, user_api_client):
        r = user_api_client.get("/api/v1/activitystream/")
        assert r.status_code == 403

    def test_platform_auditor_can_access_activitystream(self, auditor_api_client):
        r = auditor_api_client.get("/api/v1/activitystream/")
        assert r.status_code == 200

    def test_superuser_can_access_activitystream(self, admin_api_client):
        r = admin_api_client.get("/api/v1/activitystream/")
        assert r.status_code == 200

    def test_unauthenticated_user_cannot_access_activitystream(self):
        client = APIClient()
        r = client.get("/api/v1/activitystream/")
        assert r.status_code in (401, 403)


@pytest.mark.django_db
class TestFeatureFlagsStateRBAC:
    """Old feature_flags_state endpoint must require at least Platform Auditor (AAP-74790)."""

    def test_basic_user_cannot_access_feature_flags_state(self, user_api_client):
        r = user_api_client.get("/api/v1/feature_flags_state/")
        assert r.status_code == 403

    def test_platform_auditor_can_access_feature_flags_state(self, auditor_api_client):
        r = auditor_api_client.get("/api/v1/feature_flags_state/")
        assert r.status_code == 200

    def test_superuser_can_access_feature_flags_state(self, admin_api_client):
        r = admin_api_client.get("/api/v1/feature_flags_state/")
        assert r.status_code == 200

    def test_unauthenticated_user_cannot_access_feature_flags_state(self):
        client = APIClient()
        r = client.get("/api/v1/feature_flags_state/")
        assert r.status_code in (401, 403)
