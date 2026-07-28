from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.platform.config.settings import settings


class GoogleAuthNotConfigured(Exception):
    pass


class InvalidGoogleCredential(Exception):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str


def _verify(credential: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        id_token.verify_oauth2_token(
            credential,
            Request(),
            settings.google_client_id,
        ),
    )


async def verify_google_credential(credential: str) -> GoogleIdentity:
    """Verify a Google Identity Services ID token and return its stable identity."""
    if not settings.google_client_id:
        raise GoogleAuthNotConfigured()

    try:
        claims = await asyncio.to_thread(_verify, credential)
    except (GoogleAuthError, ValueError, TypeError):
        raise InvalidGoogleCredential() from None

    subject = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified")
    if (
        not isinstance(subject, str)
        or not subject
        or len(subject) > 255
        or not isinstance(email, str)
        or not email
        or email_verified not in (True, "true")
    ):
        raise InvalidGoogleCredential()

    return GoogleIdentity(subject=subject, email=email)
