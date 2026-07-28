from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.platform.security.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)


class IncorrectPassword(Exception):
    pass


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    """Rotate a user's password after verifying the current one.

    Password strength is enforced by :func:`hash_password`, which raises
    ``PasswordPolicyError`` for the route to translate.
    """
    if not verify_password(current_password, user.password_hash):
        raise IncorrectPassword()

    user.password_hash = hash_password(new_password)
    await db.flush()
    logger.info("Password changed for user %s", user.id)


async def delete_account(db: AsyncSession, user: User, current_password: str) -> None:
    """Permanently delete a user and everything they own.

    Widgets, leads, heal events and deployment history all cascade from the
    ``users`` row, so this is a full erasure — which is what a GDPR/CCPA deletion
    request requires.
    """
    if not verify_password(current_password, user.password_hash):
        raise IncorrectPassword()

    user_id = user.id
    await db.delete(user)
    await db.flush()
    logger.info("Deleted account %s and all owned data", user_id)
