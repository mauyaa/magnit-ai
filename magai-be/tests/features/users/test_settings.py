"""Operational settings: persistence, access, domains, export and team sharing."""

from sqlalchemy import select

from app.features.users.models import ApiKey
from app.features.widgets.models import Widget


class TestPreferences:
    async def test_profile_workspace_notifications_and_labs_persist(self, user, as_user):
        client = as_user(user)
        assert (
            await client.patch("/api/users/me/profile", json={"display_name": "Maya Chen"})
        ).json()["display_name"] == "Maya Chen"
        workspace = await client.patch(
            "/api/users/me/workspace",
            json={"name": "Northstar Studio", "timezone": "Africa/Nairobi"},
        )
        assert workspace.json()["workspace_name"] == "Northstar Studio"
        assert workspace.json()["workspace_timezone"] == "Africa/Nairobi"

        notifications = await client.patch(
            "/api/users/me/notifications",
            json={"notify_weekly_summary": False, "notify_product_updates": True},
        )
        assert notifications.json()["notify_on_lead"] is True
        assert notifications.json()["notify_weekly_summary"] is False
        assert notifications.json()["notify_product_updates"] is True

        labs = await client.patch("/api/users/me/labs", json={"enabled": True})
        assert labs.json()["labs_enabled"] is True


class TestApiKeys:
    async def test_secret_is_returned_once_and_authenticates_developer_api(self, db, user, as_user):
        db.add(
            Widget(
                user_id=user.id,
                target_url="https://example.com",
                widget_type="roi_calculator",
                title="ROI calculator",
                status="active",
            )
        )
        await db.commit()

        client = as_user(user)
        created = await client.post(
            "/api/users/me/api-keys",
            json={"name": "Reporting", "expires_in_days": 30},
        )
        assert created.status_code == 201
        raw_key = created.json()["key"]
        assert raw_key.startswith("magai_")

        stored = (await db.scalars(select(ApiKey))).one()
        assert stored.key_hash != raw_key
        assert raw_key not in stored.key_hash

        listing = await client.get("/api/users/me/api-keys")
        assert listing.json()["keys"][0]["name"] == "Reporting"
        assert "key" not in listing.json()["keys"][0]

        tools = await client.get("/api/developer/tools", headers={"X-API-Key": raw_key})
        assert tools.status_code == 200
        assert tools.json()["tools"][0]["title"] == "ROI calculator"

    async def test_revoked_key_stops_authenticating(self, db, user, as_user):
        client = as_user(user)
        created = (
            await client.post(
                "/api/users/me/api-keys",
                json={"name": "Temporary", "expires_in_days": 30},
            )
        ).json()
        assert (await client.delete(f"/api/users/me/api-keys/{created['id']}")).status_code == 204
        denied = await client.get("/api/developer/tools", headers={"X-API-Key": created["key"]})
        assert denied.status_code == 401


class TestTeam:
    async def test_invitation_acceptance_shares_the_owner_workspace(
        self, monkeypatch, db, user, other_user, as_user
    ):
        raw = "known-invitation-token-with-more-than-thirty-two-characters"
        monkeypatch.setattr("app.features.users.routes.secrets.token_urlsafe", lambda _length: raw)
        owner_client = as_user(user)
        db.add(
            Widget(
                user_id=user.id,
                target_url="https://example.com",
                widget_type="roi_calculator",
                title="Shared ROI calculator",
                status="active",
            )
        )
        await db.commit()
        invitation = await owner_client.post(
            "/api/users/me/team/invitations",
            json={"email": other_user.email, "role": "admin"},
        )
        assert invitation.status_code == 201

        member_client = as_user(other_user)
        accepted = await member_client.post(
            "/api/users/me/team/invitations/accept",
            json={"token": raw},
        )
        assert accepted.status_code == 200
        assert accepted.json()["workspace_id"] == str(user.id)
        assert accepted.json()["role"] == "admin"

        team = await member_client.get("/api/users/me/team")
        assert {member["email"] for member in team.json()["members"]} == {
            user.email,
            other_user.email,
        }
        tools = await member_client.get("/api/widgets")
        assert tools.json()["widgets"][0]["title"] == "Shared ROI calculator"

    async def test_invitation_requires_the_matching_email(
        self, monkeypatch, user, other_user, as_user
    ):
        raw = "another-known-invitation-token-with-enough-characters"
        monkeypatch.setattr("app.features.users.routes.secrets.token_urlsafe", lambda _length: raw)
        await (as_user(user)).post(
            "/api/users/me/team/invitations",
            json={"email": "someone-else@example.com", "role": "member"},
        )
        response = await (as_user(other_user)).post(
            "/api/users/me/team/invitations/accept", json={"token": raw}
        )
        assert response.status_code == 403


class TestDomains:
    async def test_domain_uses_provider_verification_and_can_be_removed(
        self, monkeypatch, db, user, as_user
    ):
        widget = Widget(
            user_id=user.id,
            target_url="https://example.com",
            widget_type="roi_calculator",
            title="ROI calculator",
            status="active",
            deployment_url="https://magai-widget-example.vercel.app",
        )
        db.add(widget)
        await db.commit()
        await db.refresh(widget)

        async def add(_widget_id, hostname):
            assert hostname == "tools.example.com"
            return {
                "verified": False,
                "verification": [{"type": "CNAME", "domain": hostname, "value": "dns.vercel.com"}],
            }

        async def verify(_widget_id, _hostname):
            return {"verified": True}

        removed: list[str] = []

        async def remove(_widget_id, hostname):
            removed.append(hostname)

        monkeypatch.setattr("app.features.users.routes.add_project_domain", add)
        monkeypatch.setattr("app.features.users.routes.verify_project_domain", verify)
        monkeypatch.setattr("app.features.users.routes.remove_project_domain", remove)

        client = as_user(user)
        created = await client.post(
            "/api/users/me/domains",
            json={"widget_id": str(widget.id), "hostname": "https://tools.example.com/"},
        )
        assert created.status_code == 201
        assert created.json()["status"] == "pending"
        assert created.json()["verification"][0]["type"] == "CNAME"

        checked = await client.post(f"/api/users/me/domains/{created.json()['id']}/verify")
        assert checked.json()["status"] == "verified"
        assert (
            await client.delete(f"/api/users/me/domains/{created.json()['id']}")
        ).status_code == 204
        assert removed == ["tools.example.com"]


class TestDataExport:
    async def test_export_contains_owned_records_but_no_secrets(self, db, user, as_user):
        db.add(
            Widget(
                user_id=user.id,
                target_url="https://example.com",
                widget_type="roi_calculator",
                title="ROI calculator",
                status="active",
                delivery_webhook_secret="must-not-export",
            )
        )
        await db.commit()
        exported = await (as_user(user)).get("/api/users/me/export")
        assert exported.status_code == 200
        body = exported.json()
        assert body["tools"][0]["title"] == "ROI calculator"
        assert "must-not-export" not in exported.text
