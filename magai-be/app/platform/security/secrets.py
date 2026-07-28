"""Reversible encryption for third-party credentials held on a customer's behalf.

Passwords are hashed because we never need them back. An integration's API key is
different: we have to present it to HubSpot on every delivery, so it must be
recoverable — which makes "store it in a column" the wrong answer and hashing an
impossible one. This is the narrow middle: authenticated symmetric encryption, so
a leaked database dump is not a leaked set of customer CRM keys.

The key is derived from ``MAGAI_SECRET_KEY`` rather than configured separately.
That is a deliberate trade-off, documented in SECURITY.md: one secret to rotate
instead of two, at the cost of tying credential recovery to the JWT signing key.
Rotating that key therefore invalidates stored credentials, which surface as
integrations needing reconnection rather than as silent delivery failures.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.platform.config.settings import settings


class SecretDecryptionError(Exception):
    """The stored ciphertext cannot be read with the current key."""


def _fernet() -> Fernet:
    # Built per call rather than cached at import: settings.secret_key is patched
    # by tests, and a module-level cipher would freeze the first value it saw.
    digest = hashlib.sha256(f"magnit-credentials:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a credential for storage. Returns URL-safe base64 text."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Recover a stored credential.

    Raises ``SecretDecryptionError`` rather than returning a partial value, so a
    key rotation produces a clear "reconnect this integration" rather than an
    authorization failure at the provider that looks like their outage.
    """
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise SecretDecryptionError("credential could not be decrypted") from exc


def mask_secret(plaintext: str) -> str:
    """A safe echo of a credential: last four characters only.

    Enough for someone to recognise which key they pasted, useless to anyone who
    intercepts it.
    """
    cleaned = plaintext.strip()
    if len(cleaned) <= 4:
        return "••••"
    return f"••••{cleaned[-4:]}"
