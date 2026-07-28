"""JWT issuing and verification for access and refresh tokens.

Tokens carry a ``typ`` claim so a refresh token can never be replayed as an
access token, and a ``jti`` so individual tokens can be revoked (see
:mod:`app.platform.security.revocation`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.platform.config.settings import settings

TokenType = Literal["access", "refresh"]

ISSUER = "magnitai"


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    token_type: TokenType
    jti: str
    expires_at: datetime


def _encode(subject: str, token_type: TokenType, ttl: timedelta) -> tuple[str, TokenClaims]:
    now = datetime.now(UTC)
    expires_at = now + ttl
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "jti": jti,
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, TokenClaims(
        subject=subject, token_type=token_type, jti=jti, expires_at=expires_at
    )


def create_access_token(subject: str) -> tuple[str, TokenClaims]:
    return _encode(subject, "access", timedelta(minutes=settings.access_token_ttl_minutes))


def create_refresh_token(subject: str) -> tuple[str, TokenClaims]:
    return _encode(subject, "refresh", timedelta(days=settings.refresh_token_ttl_days))


def decode_token(token: str, expected_type: TokenType) -> TokenClaims:
    """Decode and validate ``token``, or raise :class:`TokenError`.

    Signature, expiry, issuer, and the ``typ`` claim are all enforced.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=ISSUER,
            options={"require": ["exp", "sub", "typ", "jti", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid_token") from exc

    token_type = payload.get("typ")
    if token_type != expected_type:
        raise TokenError("wrong_token_type")

    return TokenClaims(
        subject=str(payload["sub"]),
        token_type=expected_type,
        jti=str(payload["jti"]),
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
