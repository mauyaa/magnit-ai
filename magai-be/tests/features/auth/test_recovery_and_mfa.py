"""Account recovery (verification, password reset) and MFA."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.features.auth.recovery import (
    InvalidToken,
    _hash_token,
    purge_expired_tokens,
    request_password_reset,
    reset_password,
    send_verification_email,
    verify_email,
)
from app.features.users.models import AuthToken
from app.platform.security.passwords import verify_password
from app.platform.security.totp import (
    current_code,
    generate_recovery_codes,
    generate_secret,
    normalize_recovery_code,
    provisioning_uri,
    verify_code,
)
from tests.conftest import TEST_PASSWORD


async def _token_for(db, user, purpose: str) -> AuthToken:
    result = await db.execute(
        select(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose)
    )
    return result.scalars().first()


class TestEmailVerification:
    async def test_sending_issues_a_hashed_token(self, db, unverified_user):
        await send_verification_email(db, unverified_user)
        await db.commit()

        token = await _token_for(db, unverified_user, "verify_email")
        assert token is not None
        # Only the hash is stored, so a database leak yields nothing replayable.
        assert len(token.token_hash) == 64
        assert token.used_at is None

    async def test_verification_marks_the_account_verified(self, db, unverified_user, monkeypatch):
        captured: dict[str, str] = {}

        async def fake_send(to, subject, text, html_body=None):
            captured["text"] = text

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await send_verification_email(db, unverified_user)
        await db.commit()

        raw = captured["text"].split("token=")[1].split()[0]
        user = await verify_email(db, raw)
        await db.commit()

        assert user.email_verified
        assert user.email_verified_at is not None

    async def test_token_is_single_use(self, db, unverified_user, monkeypatch):
        captured: dict[str, str] = {}

        async def fake_send(to, subject, text, html_body=None):
            captured["text"] = text

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await send_verification_email(db, unverified_user)
        await db.commit()
        raw = captured["text"].split("token=")[1].split()[0]

        await verify_email(db, raw)
        await db.commit()

        # Replaying a spent link must fail.
        with pytest.raises(InvalidToken):
            await verify_email(db, raw)

    async def test_unknown_token_is_rejected(self, db):
        with pytest.raises(InvalidToken):
            await verify_email(db, "not-a-real-token")

    async def test_expired_token_is_rejected(self, db, unverified_user):
        raw = "expired-token-value"
        db.add(
            AuthToken(
                user_id=unverified_user.id,
                purpose="verify_email",
                token_hash=_hash_token(raw),
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        await db.commit()

        with pytest.raises(InvalidToken):
            await verify_email(db, raw)

    async def test_reissuing_invalidates_the_previous_link(self, db, unverified_user, monkeypatch):
        sent: list[str] = []

        async def fake_send(to, subject, text, html_body=None):
            sent.append(text)

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await send_verification_email(db, unverified_user)
        await db.commit()
        first = sent[0].split("token=")[1].split()[0]

        await send_verification_email(db, unverified_user)
        await db.commit()

        # An older email must stop being a live key to the account.
        with pytest.raises(InvalidToken):
            await verify_email(db, first)


class TestPasswordReset:
    async def test_reset_changes_the_password(self, db, user, monkeypatch):
        captured: dict[str, str] = {}

        async def fake_send(to, subject, text, html_body=None):
            if "reset" in subject.lower():
                captured["text"] = text

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await request_password_reset(db, user.email)
        await db.commit()

        raw = captured["text"].split("token=")[1].split()[0]
        updated = await reset_password(db, raw, "brand-new-passw0rd-42")
        await db.commit()

        assert verify_password("brand-new-passw0rd-42", updated.password_hash)
        assert not verify_password(TEST_PASSWORD, updated.password_hash)

    async def test_unknown_address_is_silently_ignored(self, db):
        # Must not raise and must not reveal that the address is unregistered.
        await request_password_reset(db, "nobody@example.com")
        await db.commit()

        result = await db.execute(select(AuthToken))
        assert result.scalars().all() == []

    async def test_disabled_account_gets_no_reset_link(self, db, user):
        user.is_active = False
        await db.commit()
        await request_password_reset(db, user.email)
        await db.commit()
        assert await _token_for(db, user, "reset_password") is None

    async def test_reset_token_is_single_use(self, db, user, monkeypatch):
        captured: dict[str, str] = {}

        async def fake_send(to, subject, text, html_body=None):
            if "reset" in subject.lower():
                captured["text"] = text

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await request_password_reset(db, user.email)
        await db.commit()
        raw = captured["text"].split("token=")[1].split()[0]

        await reset_password(db, raw, "brand-new-passw0rd-42")
        await db.commit()

        with pytest.raises(InvalidToken):
            await reset_password(db, raw, "another-passw0rd-9999")

    async def test_completing_a_reset_also_verifies_the_email(
        self, db, unverified_user, monkeypatch
    ):
        captured: dict[str, str] = {}

        async def fake_send(to, subject, text, html_body=None):
            if "reset" in subject.lower():
                captured["text"] = text

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await request_password_reset(db, unverified_user.email)
        await db.commit()
        raw = captured["text"].split("token=")[1].split()[0]

        updated = await reset_password(db, raw, "brand-new-passw0rd-42")
        await db.commit()

        # Completing the reset proves control of the mailbox.
        assert updated.email_verified

    async def test_weak_new_password_is_rejected(self, db, user, monkeypatch):
        from app.platform.security.passwords import PasswordPolicyError

        captured: dict[str, str] = {}

        async def fake_send(to, subject, text, html_body=None):
            if "reset" in subject.lower():
                captured["text"] = text

        monkeypatch.setattr("app.features.auth.recovery.send_email", fake_send)
        await request_password_reset(db, user.email)
        await db.commit()
        raw = captured["text"].split("token=")[1].split()[0]

        with pytest.raises(PasswordPolicyError):
            await reset_password(db, raw, "weak")


class TestTokenPurposeSeparation:
    async def test_a_verification_token_cannot_reset_a_password(self, db, unverified_user):
        raw = "cross-purpose-token"
        db.add(
            AuthToken(
                user_id=unverified_user.id,
                purpose="verify_email",
                token_hash=_hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await db.commit()

        # Purpose confusion would turn a verification link into a takeover.
        with pytest.raises(InvalidToken):
            await reset_password(db, raw, "brand-new-passw0rd-42")


class TestTokenPurge:
    async def test_purges_expired_and_spent_tokens(self, db, user):
        now = datetime.now(UTC)
        db.add_all(
            [
                AuthToken(
                    user_id=user.id,
                    purpose="reset_password",
                    token_hash=_hash_token("expired"),
                    expires_at=now - timedelta(hours=1),
                ),
                AuthToken(
                    user_id=user.id,
                    purpose="verify_email",
                    token_hash=_hash_token("used"),
                    expires_at=now + timedelta(hours=1),
                    used_at=now,
                ),
                AuthToken(
                    user_id=user.id,
                    purpose="reset_password",
                    token_hash=_hash_token("live"),
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
        await db.commit()

        removed = await purge_expired_tokens(db)
        await db.commit()

        assert removed == 2
        remaining = (await db.execute(select(AuthToken))).scalars().all()
        assert len(remaining) == 1


class TestTotp:
    def test_generated_secret_is_valid_base32(self):
        secret = generate_secret()
        assert len(secret) == 32
        assert set(secret) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")

    def test_current_code_verifies(self):
        secret = generate_secret()
        assert verify_code(secret, current_code(secret))

    def test_wrong_code_fails(self):
        secret = generate_secret()
        assert not verify_code(secret, "000000")

    def test_code_from_a_different_secret_fails(self):
        assert not verify_code(generate_secret(), current_code(generate_secret()))

    @pytest.mark.parametrize("skew", [-30, 30])
    def test_tolerates_one_step_of_clock_skew(self, skew):
        # Phone/server clock drift is the most common cause of rejected codes.
        secret = generate_secret()
        now = 1_700_000_000
        assert verify_code(secret, current_code(secret, at=now + skew), at=now)

    def test_rejects_codes_beyond_the_skew_window(self):
        secret = generate_secret()
        now = 1_700_000_000
        assert not verify_code(secret, current_code(secret, at=now + 300), at=now)

    @pytest.mark.parametrize("bad", ["", "abc", "12345", "1234567", None])
    def test_rejects_malformed_input(self, bad):
        assert not verify_code(generate_secret(), bad)

    def test_provisioning_uri_is_scannable(self):
        uri = provisioning_uri("ABCDEFGHIJKLMNOP", "user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "secret=ABCDEFGHIJKLMNOP" in uri
        assert "issuer=MagnetAI" in uri
        assert "digits=6" in uri and "period=30" in uri


class TestRecoveryCodes:
    def test_generates_distinct_readable_codes(self):
        codes = generate_recovery_codes(8)
        assert len(set(codes)) == 8
        assert all(len(c) == 11 and c[5] == "-" for c in codes)

    def test_excludes_lookalike_characters(self):
        joined = "".join(generate_recovery_codes(20)).replace("-", "")
        # 0/O and 1/I/L are indistinguishable when read off a screen.
        assert not (set(joined) & set("01OIL"))

    def test_normalization_is_forgiving(self):
        assert normalize_recovery_code("abcde-fghjk") == "ABCDEFGHJK"
        assert normalize_recovery_code(" ABCDE FGHJK ") == "ABCDEFGHJK"


class TestMfaFlow:
    async def test_enrollment_requires_confirmation_before_activating(self, db, user):
        from app.features.auth.mfa import begin_enrollment

        secret, uri = await begin_enrollment(db, user)
        await db.commit()

        # A mis-scanned QR must not be able to lock the user out.
        assert user.mfa_secret == secret
        assert user.mfa_enabled is False
        assert uri.startswith("otpauth://")

    async def test_confirmation_enables_mfa_and_returns_recovery_codes(self, db, user):
        from app.features.auth.mfa import begin_enrollment, confirm_enrollment

        secret, _ = await begin_enrollment(db, user)
        codes = await confirm_enrollment(db, user, current_code(secret))
        await db.commit()

        assert user.mfa_enabled
        assert len(codes) == 8
        # Only hashes are persisted, so a leak yields no usable second factor.
        assert all(code not in str(user.mfa_recovery_codes) for code in codes)

    async def test_confirmation_rejects_a_wrong_code(self, db, user):
        from app.features.auth.mfa import InvalidMfaCode, begin_enrollment, confirm_enrollment

        await begin_enrollment(db, user)
        with pytest.raises(InvalidMfaCode):
            await confirm_enrollment(db, user, "000000")

    async def test_recovery_code_works_once_then_is_spent(self, db, user):
        from app.features.auth.mfa import (
            begin_enrollment,
            confirm_enrollment,
            verify_second_factor,
        )

        secret, _ = await begin_enrollment(db, user)
        codes = await confirm_enrollment(db, user, current_code(secret))
        await db.commit()

        assert await verify_second_factor(db, user, codes[0])
        await db.commit()
        # Single use: a code that stayed valid would be a permanent bypass.
        assert not await verify_second_factor(db, user, codes[0])
        assert len(user.mfa_recovery_codes) == 7

    async def test_disable_requires_a_valid_code(self, db, user):
        from app.features.auth.mfa import (
            InvalidMfaCode,
            begin_enrollment,
            confirm_enrollment,
            disable_mfa,
        )

        secret, _ = await begin_enrollment(db, user)
        await confirm_enrollment(db, user, current_code(secret))
        await db.commit()

        # Otherwise a stolen access token could strip the second factor.
        with pytest.raises(InvalidMfaCode):
            await disable_mfa(db, user, "000000")

        await disable_mfa(db, user, current_code(secret))
        await db.commit()
        assert user.mfa_enabled is False
        assert user.mfa_secret is None
