from datetime import UTC, datetime, timedelta

import pytest

from app.platform.security.passwords import (
    PasswordPolicyError,
    hash_password,
    verify_password,
)
from app.platform.security.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestPasswordHashing:
    def test_hash_is_not_reversible_and_verifies(self):
        password = "a-long-enough-passw0rd"
        hashed = hash_password(password)
        assert password not in hashed
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("a-long-enough-passw0rd")
        assert not verify_password("a-long-enough-passw0rc", hashed)

    def test_same_password_gets_distinct_hashes(self):
        # Distinct salts: identical passwords must not produce identical hashes.
        assert hash_password("a-long-enough-passw0rd") != hash_password("a-long-enough-passw0rd")

    def test_verify_rejects_garbage_hash_without_raising(self):
        assert not verify_password("anything", "not-a-real-hash")


class TestPasswordPolicy:
    @pytest.mark.parametrize(
        "password",
        [
            "short1",  # too short
            "password123",  # common
            "aaaaaaaaaaaaaaaa",  # no digits
            "1234567890123456",  # no letters
        ],
    )
    def test_rejects_weak_passwords(self, password):
        with pytest.raises(PasswordPolicyError):
            hash_password(password)

    def test_accepts_a_reasonable_password(self):
        assert hash_password("correct-horse-battery-99")

    def test_rejects_absurdly_long_password(self):
        # Unbounded input would let a caller burn CPU in the hasher.
        with pytest.raises(PasswordPolicyError):
            hash_password("a1" * 1000)


class TestTokens:
    def test_access_token_round_trips(self):
        token, claims = create_access_token("user-123")
        decoded = decode_token(token, expected_type="access")
        assert decoded.subject == "user-123"
        assert decoded.jti == claims.jti

    def test_refresh_token_cannot_be_used_as_access_token(self):
        # Type confusion here would make long-lived refresh tokens API keys.
        refresh, _ = create_refresh_token("user-123")
        with pytest.raises(TokenError, match="wrong_token_type"):
            decode_token(refresh, expected_type="access")

    def test_access_token_cannot_be_used_as_refresh_token(self):
        access, _ = create_access_token("user-123")
        with pytest.raises(TokenError, match="wrong_token_type"):
            decode_token(access, expected_type="refresh")

    def test_tampered_signature_is_rejected(self):
        token, _ = create_access_token("user-123")
        header, payload, _ = token.split(".")
        forged = f"{header}.{payload}.bm90LWEtc2lnbmF0dXJl"
        with pytest.raises(TokenError):
            decode_token(forged, expected_type="access")

    def test_token_signed_with_another_secret_is_rejected(self):
        import jwt

        foreign = jwt.encode(
            {
                "sub": "user-123",
                "typ": "access",
                "jti": "x",
                "iss": "magnitai",
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            # At least 32 bytes, so PyJWT does not emit an insecure-key-length
            # warning while we are testing signature rejection.
            "a-completely-different-secret-of-sufficient-length",
            algorithm="HS256",
        )
        with pytest.raises(TokenError):
            decode_token(foreign, expected_type="access")

    def test_expired_token_is_rejected(self, monkeypatch):
        from app.platform.config.settings import settings

        # Negative TTL yields an already-expired token.
        monkeypatch.setattr(settings, "access_token_ttl_minutes", -1)
        token, _ = create_access_token("user-123")
        with pytest.raises(TokenError, match="token_expired"):
            decode_token(token, expected_type="access")

    def test_unsigned_alg_none_token_is_rejected(self):
        import jwt

        # The classic "alg: none" downgrade attack.
        unsigned = jwt.encode(
            {"sub": "user-123", "typ": "access", "jti": "x", "iss": "magnitai", "exp": 9999999999},
            key="",
            algorithm="none",
        )
        with pytest.raises(TokenError):
            decode_token(unsigned, expected_type="access")

    def test_each_token_has_a_unique_jti(self):
        _, first = create_access_token("user-123")
        _, second = create_access_token("user-123")
        assert first.jti != second.jti
