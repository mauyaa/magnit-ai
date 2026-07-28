"""Password hashing and strength policy.

Argon2id via ``argon2-cffi`` — the OWASP-recommended default. Verification
transparently reports when a stored hash used weaker parameters so callers can
re-hash on successful login.
"""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.platform.config.settings import settings

# Defaults follow argon2-cffi's RFC 9106 low-memory profile.
_hasher = PasswordHasher()

# Deliberately short: the top credential-stuffing passwords. Real deployments
# should layer a breached-password API on top; this is a floor, not a ceiling.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "123456789",
        "1234567890",
        "qwertyuiop",
        "letmein123",
        "welcome123",
        "admin12345",
        "iloveyou123",
        "changeme123",
        "magnitai123",
    }
)


class PasswordPolicyError(ValueError):
    """Raised when a candidate password fails the strength policy."""


def validate_password_strength(password: str) -> None:
    """Raise :class:`PasswordPolicyError` if ``password`` is too weak.

    Length-first policy (per NIST SP 800-63B) rather than forced symbol classes,
    plus a character-variety floor and a common-password check.
    """
    minimum = settings.password_min_length
    if len(password) < minimum:
        raise PasswordPolicyError(f"Password must be at least {minimum} characters long")
    if len(password) > 1024:
        raise PasswordPolicyError("Password must be at most 1024 characters long")
    if password.lower() in _COMMON_PASSWORDS:
        raise PasswordPolicyError("Password is too common — choose something less predictable")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise PasswordPolicyError("Password must contain both letters and numbers")


def hash_password(password: str) -> str:
    """Validate then hash. Always call this rather than the hasher directly."""
    validate_password_strength(password)
    return _hasher.hash(password)


def hash_secret(secret: str) -> str:
    """Hash a system-generated secret, bypassing the human-password policy.

    For values this application generates itself — MFA recovery codes, for example.
    They are already high-entropy and were never chosen by a person, so the
    length/variety rules for user passwords do not apply and would reject them.
    """
    if not secret:
        raise ValueError("cannot hash an empty secret")
    return _hasher.hash(secret)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


# Verification is identical either way; the alias exists so call sites read
# correctly and pair with hash_secret().
verify_secret = verify_password


def needs_rehash(password_hash: str) -> bool:
    """True when a valid hash used parameters weaker than the current policy."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return False
