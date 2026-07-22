import uuid

import pytest


def make_user_data():
    unique_id = uuid.uuid4().hex[:8]
    return {"username": f"newuser-{unique_id}", "password": f"password-{unique_id}"}


@pytest.mark.django_db
class TestSuperuserAccess:
    """Superuser should have full CRUD on all resources."""

    def test_superuser_can_create_user(self, admin_api_client):
        """Superusers can create users."""
        data = make_user_data()
        r = admin_api_client.post("/api/v1/users/", data)
        assert r.status_code == 201

    def test_superuser_cannot_create_organization(self, admin_api_client):
        """POST to /organizations/ returns 405 — orgs are synced from the gateway, not created here.

        Organizations are managed by the AAP resource server (is_provider=False in resource_api.py).
        Creating them directly causes a DAB signal crash when a resource server is configured (AAP-74775).
        """
        r = admin_api_client.post("/api/v1/organizations/", {"name": "New Org"})
        assert r.status_code == 405

    def test_superuser_can_create_team(self, admin_api_client, organization):
        r = admin_api_client.post("/api/v1/teams/", {"name": "New Team", "organization": organization.id})
        assert r.status_code == 201

    def test_superuser_can_delete_user(self, admin_api_client, rando):
        r = admin_api_client.delete(f"/api/v1/users/{rando.id}/")
        assert r.status_code == 204


@pytest.mark.django_db
class TestNormalUserAccess:
    """Normal users without roles should have no access."""

    def test_cannot_create_user(self, user_api_client):
        """Normal users cannot create users (403 Forbidden)."""
        data = make_user_data()
        r = user_api_client.post("/api/v1/users/", data)
        assert r.status_code == 403

    def test_cannot_create_organization(self, user_api_client):
        """Normal users are denied before reaching the 405 method guard (RBAC fires first)."""
        r = user_api_client.post("/api/v1/organizations/", {"name": "New Org"})
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
        """Org admins cannot create organizations — RBAC denies (403) before the method guard fires."""
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
