"""Account management: password change and account deletion."""

from sqlalchemy import select

from app.features.users.models import User
from app.features.widgets.models import Widget
from tests.conftest import TEST_PASSWORD


class TestChangePassword:
    async def test_password_can_be_changed_and_used(self, client, user, auth_headers):
        new_password = "brand-new-passw0rd-42"
        response = await client.patch(
            "/api/users/me/password",
            json={"current_password": TEST_PASSWORD, "new_password": new_password},
            headers=auth_headers(user),
        )
        assert response.status_code == 200

        login = await client.post(
            "/api/auth/login", json={"email": user.email, "password": new_password}
        )
        assert login.status_code == 200

    async def test_old_password_stops_working(self, client, user, auth_headers):
        await client.patch(
            "/api/users/me/password",
            json={"current_password": TEST_PASSWORD, "new_password": "brand-new-passw0rd-42"},
            headers=auth_headers(user),
        )
        login = await client.post(
            "/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        )
        assert login.status_code == 401

    async def test_wrong_current_password_is_rejected(self, client, user, auth_headers):
        # Without this check, a stolen access token could take over the account.
        response = await client.patch(
            "/api/users/me/password",
            json={"current_password": "not-the-password", "new_password": "brand-new-passw0rd-42"},
            headers=auth_headers(user),
        )
        assert response.status_code == 403

    async def test_weak_new_password_is_rejected(self, client, user, auth_headers):
        response = await client.patch(
            "/api/users/me/password",
            json={"current_password": TEST_PASSWORD, "new_password": "short1"},
            headers=auth_headers(user),
        )
        assert response.status_code == 422

    async def test_requires_authentication(self, client):
        response = await client.patch(
            "/api/users/me/password",
            json={"current_password": "a", "new_password": "brand-new-passw0rd-42"},
        )
        assert response.status_code == 401


class TestDeleteAccount:
    async def test_deletion_removes_the_user_and_their_widgets(
        self, client, db, user, auth_headers
    ):
        db.add(
            Widget(
                user_id=user.id,
                target_url="https://example.com",
                widget_type="roi_calculator",
                title="Calc",
                status="active",
            )
        )
        await db.commit()

        response = await client.request(
            "DELETE",
            "/api/users/me",
            json={"current_password": TEST_PASSWORD},
            headers=auth_headers(user),
        )
        assert response.status_code == 200

        # Cascade: a deletion request must not leave orphaned customer data behind.
        deleted = await db.execute(select(User).where(User.id == user.id))
        assert deleted.scalar_one_or_none() is None
        remaining = (
            (await db.execute(select(Widget).where(Widget.user_id == user.id))).scalars().all()
        )
        assert remaining == []

    async def test_wrong_password_prevents_deletion(self, client, db, user, auth_headers):
        response = await client.request(
            "DELETE",
            "/api/users/me",
            json={"current_password": "not-the-password"},
            headers=auth_headers(user),
        )
        assert response.status_code == 403
        assert (
            await db.execute(select(User).where(User.id == user.id))
        ).scalar_one_or_none() is not None
