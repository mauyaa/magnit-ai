"""Email verification and password reset.

Token design: a 256-bit URL-safe random value is emailed to the user, and only its
SHA-256 hash is stored. Verification hashes the presented token and looks up that
hash, so a database leak yields nothing replayable. (SHA-256 rather than Argon2 is
correct here — unlike a password these tokens are full-entropy and short-lived, so
there is nothing to brute-force and the lookup must be indexable.)

Enumeration safety: ``request_password_reset`` behaves identically for a registered
and an unregistered address. The caller always reports success.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import AuthToken, User
from app.platform.config.settings import settings
from app.platform.db.session import rows_affected
from app.platform.email.sender import EmailDeliveryError, send_email
from app.platform.email.templates import (
    password_changed_email,
    password_reset_email,
    verification_email,
)
from app.platform.security.passwords import hash_password

logger = logging.getLogger(__name__)

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"


class InvalidToken(Exception):
    """The token is unknown, expired, already used, or of the wrong purpose."""


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _issue_token(db: AsyncSession, user: User, purpose: str, ttl: timedelta) -> str:
    """Invalidate any outstanding tokens of this purpose, then mint a new one.

    Single outstanding token per purpose: requesting a second reset link must make
    the first one dead, or an old email remains a live key to the account.
    """
    now = datetime.now(UTC)
    await db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_hash_token(raw),
            expires_at=now + ttl,
        )
    )
    await db.flush()
    return raw


async def _consume_token(db: AsyncSession, raw: str, purpose: str) -> User:
    """Atomically spend a token and return its user, or raise :class:`InvalidToken`.

    The UPDATE is the claim: marking ``used_at`` conditionally on it still being
    null means two concurrent requests cannot both redeem the same token.
    """
    token_hash = _hash_token(str(raw or ""))
    now = datetime.now(UTC)

    claimed = await db.execute(
        update(AuthToken)
        .where(
            AuthToken.token_hash == token_hash,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > now,
        )
        .values(used_at=now)
    )
    if rows_affected(claimed) == 0:
        raise InvalidToken(purpose)

    result = await db.execute(
        select(User)
        .join(AuthToken, AuthToken.user_id == User.id)
        .where(AuthToken.token_hash == token_hash)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise InvalidToken(purpose)
    return user


# --------------------------------------------------------------------------- #
# Email verification
# --------------------------------------------------------------------------- #


async def send_verification_email(db: AsyncSession, user: User) -> None:
    """Issue and email a verification link.

    A mail-transport failure is logged but not raised: signup must still succeed,
    and the user can request a new link.
    """
    if user.email_verified:
        return

    ttl_hours = settings.email_verification_ttl_hours
    raw = await _issue_token(db, user, VERIFY_EMAIL, timedelta(hours=ttl_hours))
    subject, text, html_body = verification_email(raw, ttl_hours)

    try:
        await send_email(user.email, subject, text, html_body)
    except EmailDeliveryError:
        logger.warning("Verification email to %s could not be delivered", user.id)


async def verify_email(db: AsyncSession, raw_token: str) -> User:
    user = await _consume_token(db, raw_token, VERIFY_EMAIL)
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(UTC)
    await db.flush()
    logger.info("Verified email for user %s", user.id)
    return user


# --------------------------------------------------------------------------- #
# Password reset
# --------------------------------------------------------------------------- #


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Email a reset link if the address belongs to an active account.

    Returns ``None`` either way and never signals which case occurred, so the
    endpoint cannot be used to discover who has an account.
    """
    normalized = str(email or "").strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == normalized))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        logger.info("Password reset requested for a non-account address")
        return

    ttl_minutes = settings.password_reset_ttl_minutes
    raw = await _issue_token(db, user, RESET_PASSWORD, timedelta(minutes=ttl_minutes))
    subject, text, html_body = password_reset_email(raw, ttl_minutes)

    try:
        await send_email(user.email, subject, text, html_body)
    except EmailDeliveryError:
        logger.warning("Password reset email to %s could not be delivered", user.id)


async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> User:
    """Set a new password from a valid reset token.

    Strength is enforced by :func:`hash_password`, which raises
    ``PasswordPolicyError`` for the route to translate.
    """
    user = await _consume_token(db, raw_token, RESET_PASSWORD)
    user.password_hash = hash_password(new_password)

    # Completing a reset proves control of the mailbox, so the address is verified.
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(UTC)

    await db.flush()
    logger.info("Password reset completed for user %s", user.id)

    # Notify out-of-band: if this reset was an account takeover, this mail is how
    # the real owner finds out.
    subject, text, html_body = password_changed_email()
    try:
        await send_email(user.email, subject, text, html_body)
    except EmailDeliveryError:
        logger.warning("Password-changed notice to %s could not be delivered", user.id)

    return user


async def purge_expired_tokens(db: AsyncSession) -> int:
    """Delete spent and expired tokens. Returns how many rows were removed."""
    from sqlalchemy import delete, or_

    now = datetime.now(UTC)
    result = await db.execute(
        delete(AuthToken).where(or_(AuthToken.expires_at < now, AuthToken.used_at.is_not(None)))
    )
    return rows_affected(result)
