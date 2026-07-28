"""TOTP multi-factor enrolment and verification.

Enrolment is two-phase on purpose. ``begin_enrollment`` stores a secret but leaves
``mfa_enabled`` false; only ``confirm_enrollment`` — which requires a code the user
read from their authenticator — turns it on. Without that, a mis-scanned QR code
would lock the user out of their own account.

Recovery codes are stored as Argon2 hashes and consumed on use, so a leaked
database yields no usable second factor.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.platform.security.passwords import hash_secret, verify_secret
from app.platform.security.totp import (
    generate_recovery_codes,
    generate_secret,
    normalize_recovery_code,
    provisioning_uri,
    verify_code,
)

logger = logging.getLogger(__name__)


class MfaAlreadyEnabled(Exception):
    pass


class MfaNotEnrolled(Exception):
    pass


class InvalidMfaCode(Exception):
    pass


async def begin_enrollment(db: AsyncSession, user: User) -> tuple[str, str]:
    """Generate a secret and return ``(secret, otpauth_uri)``.

    MFA stays *disabled* until :func:`confirm_enrollment` succeeds.
    """
    if user.mfa_enabled:
        raise MfaAlreadyEnabled()

    secret = generate_secret()
    user.mfa_secret = secret
    await db.flush()
    return secret, provisioning_uri(secret, user.email)


async def confirm_enrollment(db: AsyncSession, user: User, code: str) -> list[str]:
    """Activate MFA after verifying a code. Returns the plaintext recovery codes.

    The plaintext is returned exactly once — only hashes are persisted, so it
    cannot be shown again.
    """
    if user.mfa_enabled:
        raise MfaAlreadyEnabled()
    if not user.mfa_secret:
        raise MfaNotEnrolled()
    if not verify_code(user.mfa_secret, code):
        raise InvalidMfaCode()

    codes = generate_recovery_codes()
    # hash_secret, not hash_password: these are system-generated and would fail the
    # user-password policy (10 characters, no digit guaranteed).
    user.mfa_recovery_codes = [hash_secret(normalize_recovery_code(c)) for c in codes]
    user.mfa_enabled = True
    await db.flush()
    logger.info("MFA enabled for user %s", user.id)
    return codes


async def disable_mfa(db: AsyncSession, user: User, code: str) -> None:
    """Turn MFA off, requiring a valid current code or recovery code.

    Re-authentication matters here: otherwise a stolen access token could strip the
    second factor and make the takeover permanent.
    """
    if not user.mfa_enabled:
        raise MfaNotEnrolled()
    if not await verify_second_factor(db, user, code):
        raise InvalidMfaCode()

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_codes = None
    await db.flush()
    logger.info("MFA disabled for user %s", user.id)


async def verify_second_factor(db: AsyncSession, user: User, code: str) -> bool:
    """Verify a TOTP code, or spend a recovery code. False if neither matches."""
    if not user.mfa_enabled or not user.mfa_secret:
        return False

    if verify_code(user.mfa_secret, code):
        return True

    return await _consume_recovery_code(db, user, code)


async def _consume_recovery_code(db: AsyncSession, user: User, code: str) -> bool:
    """Match and permanently remove a recovery code."""
    stored = list(user.mfa_recovery_codes or [])
    if not stored:
        return False

    candidate = normalize_recovery_code(code)
    # Recovery codes are 10 alphanumerics; skip the hash comparisons otherwise.
    if len(candidate) < 8:
        return False

    for index, code_hash in enumerate(stored):
        if verify_secret(candidate, code_hash):
            remaining = stored[:index] + stored[index + 1 :]
            # Reassign rather than mutate: SQLAlchemy does not track in-place edits
            # to a JSON column, so an in-place pop would silently not persist.
            user.mfa_recovery_codes = remaining
            await db.flush()
            logger.warning("Recovery code used for user %s (%d remaining)", user.id, len(remaining))
            return True

    return False


def remaining_recovery_codes(user: User) -> int:
    return len(user.mfa_recovery_codes or [])
