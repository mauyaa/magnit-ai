from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.platform.security.passwords import (
    hash_password,
    needs_rehash,
    verify_password,
)

logger = logging.getLogger(__name__)

# A hash of a throwaway password, used to keep login timing roughly constant for
# unknown emails so the endpoint doesn't leak which addresses are registered.
_DUMMY_HASH = hash_password("timing-equalizer-placeholder-9f3c1")


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class AccountDisabled(Exception):
    pass


class GoogleIdentityConflict(Exception):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    """Create a user, or raise :class:`EmailAlreadyRegistered`.

    Password strength is enforced inside :func:`hash_password`, which raises
    ``PasswordPolicyError`` for the route layer to translate.
    """
    normalized = _normalize_email(email)

    existing = await db.execute(select(User.id).where(func.lower(User.email) == normalized))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyRegistered(normalized)

    user = User(email=normalized, password_hash=hash_password(password), role="owner")
    db.add(user)
    await db.flush()
    logger.info("Registered new user %s", user.id)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """Return the user for valid credentials, else raise.

    Raises :class:`InvalidCredentials` for both unknown emails and bad passwords
    so callers cannot distinguish the two, and :class:`AccountDisabled` only
    after the password has been verified.
    """
    normalized = _normalize_email(email)
    result = await db.execute(select(User).where(func.lower(User.email) == normalized))
    user = result.scalar_one_or_none()

    if user is None:
        # Spend comparable time so response latency doesn't reveal existence.
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials()

    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()

    if not user.is_active:
        raise AccountDisabled()

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(UTC)
    return user


async def authenticate_google_identity(
    db: AsyncSession,
    subject: str,
    email: str,
) -> User:
    """Create or link a Google identity, then return the active Magnitai user."""
    normalized = _normalize_email(email)
    by_subject = await db.execute(select(User).where(User.google_subject == subject))
    user = by_subject.scalar_one_or_none()

    if user is None:
        by_email = await db.execute(select(User).where(func.lower(User.email) == normalized))
        user = by_email.scalar_one_or_none()

        if user is not None:
            if user.google_subject is not None and user.google_subject != subject:
                raise GoogleIdentityConflict()
            user.google_subject = subject
        else:
            # Password login remains unavailable until the owner explicitly
            # creates one through password reset. The random secret is never
            # exposed and only satisfies the existing non-null database contract.
            user = User(
                email=normalized,
                password_hash=hash_password(f"{secrets.token_urlsafe(48)}A1"),
                google_subject=subject,
                role="owner",
            )
            db.add(user)
            await db.flush()

    if not user.is_active:
        raise AccountDisabled()

    now = datetime.now(UTC)
    user.email_verified = True
    user.email_verified_at = user.email_verified_at or now
    user.last_login_at = now
    return user


async def get_active_user(db: AsyncSession, user_id: str) -> User | None:
    """Look up an active user by id; returns ``None`` for missing or disabled."""
    try:
        result = await db.execute(select(User).where(User.id == user_id))
    except Exception:
        # Malformed subject in an otherwise well-signed token.
        logger.warning("Rejected token with unusable subject %r", user_id)
        return None
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user
