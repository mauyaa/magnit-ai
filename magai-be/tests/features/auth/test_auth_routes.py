"""End-to-end auth flows through the HTTP layer."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.features.auth.google import GoogleIdentity, InvalidGoogleCredential
from app.features.users.models import User
from tests.conftest import TEST_PASSWORD

SIGNUP = "/api/auth/signup"
LOGIN = "/api/auth/login"
REFRESH = "/api/auth/refresh"
LOGOUT = "/api/auth/logout"
ME = "/api/auth/me"
GOOGLE = "/api/auth/google"


class TestSignup:
    async def test_signup_returns_usable_tokens(self, client):
        response = await client.post(
            SIGNUP, json={"email": "new@example.com", "password": "correct-horse-battery-99"}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

        me = await client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me.status_code == 200
        assert me.json()["email"] == "new@example.com"

    async def test_duplicate_email_is_rejected(self, client):
        payload = {"email": "dup@example.com", "password": "correct-horse-battery-99"}
        assert (await client.post(SIGNUP, json=payload)).status_code == 201
        second = await client.post(SIGNUP, json=payload)
        assert second.status_code == 409

    async def test_email_is_normalized_to_lowercase(self, client):
        await client.post(
            SIGNUP, json={"email": "MiXeD@Example.COM", "password": "correct-horse-battery-99"}
        )
        # Same address in different case must not create a second account.
        duplicate = await client.post(
            SIGNUP, json={"email": "mixed@example.com", "password": "correct-horse-battery-99"}
        )
        assert duplicate.status_code == 409

    async def test_weak_password_is_rejected_with_reason(self, client):
        response = await client.post(SIGNUP, json={"email": "weak@example.com", "password": "abc1"})
        assert response.status_code == 422

    async def test_invalid_email_is_rejected(self, client):
        response = await client.post(
            SIGNUP, json={"email": "not-an-email", "password": "correct-horse-battery-99"}
        )
        assert response.status_code == 422

    async def test_password_is_never_echoed_back(self, client):
        secret = "correct-horse-battery-99"
        response = await client.post(
            SIGNUP, json={"email": "quiet@example.com", "password": secret}
        )
        assert secret not in response.text


class TestLogin:
    async def test_login_with_correct_password(self, client, user):
        response = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_login_with_wrong_password_is_401(self, client, user):
        response = await client.post(
            LOGIN, json={"email": user.email, "password": "wrong-passw0rd"}
        )
        assert response.status_code == 401

    async def test_unknown_email_and_wrong_password_are_indistinguishable(self, client, user):
        unknown = await client.post(
            LOGIN, json={"email": "nobody@example.com", "password": TEST_PASSWORD}
        )
        wrong = await client.post(LOGIN, json={"email": user.email, "password": "wrong-passw0rd"})
        # Identical status and body: no user enumeration through the login endpoint.
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["detail"] == wrong.json()["detail"]

    async def test_disabled_account_cannot_log_in(self, client, db, user):
        user.is_active = False
        await db.commit()
        response = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 403


class TestGoogleLogin:
    async def test_google_creates_a_verified_user_and_returns_usable_tokens(
        self, client, db, monkeypatch
    ):
        monkeypatch.setattr(
            "app.features.auth.routes.verify_google_credential",
            AsyncMock(
                return_value=GoogleIdentity(
                    subject="google-user-123",
                    email="google.owner@example.com",
                )
            ),
        )

        response = await client.post(GOOGLE, json={"credential": "credential-" * 4})

        assert response.status_code == 200
        body = response.json()
        me = await client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me.status_code == 200
        assert me.json()["email"] == "google.owner@example.com"
        assert me.json()["email_verified"] is True

        result = await db.execute(select(User).where(User.email == "google.owner@example.com"))
        created = result.scalar_one()
        assert created.google_subject == "google-user-123"

    async def test_google_links_an_existing_verified_email(self, client, db, user, monkeypatch):
        monkeypatch.setattr(
            "app.features.auth.routes.verify_google_credential",
            AsyncMock(return_value=GoogleIdentity(subject="google-linked-456", email=user.email)),
        )

        response = await client.post(GOOGLE, json={"credential": "credential-" * 4})

        assert response.status_code == 200
        await db.refresh(user)
        assert user.google_subject == "google-linked-456"
        assert user.email_verified is True

    async def test_google_rejects_an_invalid_id_token(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.features.auth.routes.verify_google_credential",
            AsyncMock(side_effect=InvalidGoogleCredential()),
        )

        response = await client.post(GOOGLE, json={"credential": "credential-" * 4})

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_google_credential"

    async def test_google_does_not_relink_an_email_to_another_subject(
        self, client, db, user, monkeypatch
    ):
        user.google_subject = "original-google-subject"
        await db.commit()
        monkeypatch.setattr(
            "app.features.auth.routes.verify_google_credential",
            AsyncMock(return_value=GoogleIdentity(subject="different-subject", email=user.email)),
        )

        response = await client.post(GOOGLE, json={"credential": "credential-" * 4})

        assert response.status_code == 409
        assert response.json()["detail"] == "google_identity_conflict"


class TestProtectedAccess:
    async def test_missing_token_is_401_with_challenge(self, client):
        response = await client.get(ME)
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    @pytest.mark.parametrize(
        "header",
        ["Bearer not-a-token", "Bearer ", "Basic dXNlcjpwYXNz", "garbage"],
    )
    async def test_malformed_credentials_are_401(self, client, header):
        response = await client.get(ME, headers={"Authorization": header})
        assert response.status_code == 401

    async def test_token_for_deleted_user_is_rejected(self, client, db, user, auth_headers):
        headers = auth_headers(user)
        await db.delete(user)
        await db.commit()
        # A validly signed token must stop working once the account is gone.
        assert (await client.get(ME, headers=headers)).status_code == 401

    async def test_token_for_deactivated_user_is_rejected(self, client, db, user, auth_headers):
        headers = auth_headers(user)
        user.is_active = False
        await db.commit()
        assert (await client.get(ME, headers=headers)).status_code == 401


class TestRefreshAndLogout:
    async def test_refresh_issues_a_new_pair(self, client, user):
        login = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        original = login.json()

        refreshed = await client.post(REFRESH, json={"refresh_token": original["refresh_token"]})
        assert refreshed.status_code == 200
        assert refreshed.json()["access_token"]

    async def test_refresh_token_is_single_use(self, client, user):
        login = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        token = login.json()["refresh_token"]

        assert (await client.post(REFRESH, json={"refresh_token": token})).status_code == 200
        # Rotation: replaying the consumed token must fail.
        assert (await client.post(REFRESH, json={"refresh_token": token})).status_code == 401

    async def test_access_token_cannot_be_used_to_refresh(self, client, user):
        login = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        access = login.json()["access_token"]
        assert (await client.post(REFRESH, json={"refresh_token": access})).status_code == 401

    async def test_logout_revokes_the_refresh_token(self, client, user):
        login = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        tokens = login.json()

        logout = await client.post(
            LOGOUT,
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert logout.status_code == 200
        assert (
            await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
        ).status_code == 401

    async def test_logout_requires_authentication(self, client, user):
        login = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        response = await client.post(LOGOUT, json={"refresh_token": login.json()["refresh_token"]})
        assert response.status_code == 401

    async def test_user_cannot_revoke_another_users_token(self, client, user, other_user):
        victim = await client.post(LOGIN, json={"email": user.email, "password": TEST_PASSWORD})
        attacker = await client.post(
            LOGIN, json={"email": other_user.email, "password": TEST_PASSWORD}
        )

        await client.post(
            LOGOUT,
            json={"refresh_token": victim.json()["refresh_token"]},
            headers={"Authorization": f"Bearer {attacker.json()['access_token']}"},
        )
        # The victim's session must survive an attacker's logout attempt.
        still_valid = await client.post(
            REFRESH, json={"refresh_token": victim.json()["refresh_token"]}
        )
        assert still_valid.status_code == 200
