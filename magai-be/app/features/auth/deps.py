"""FastAPI dependencies for authenticated routes.

``CurrentUser`` is the annotated type every protected endpoint should depend on::

    async def handler(user: CurrentUser): ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.service import get_active_user
from app.features.users.models import User
from app.platform.db.session import get_async_session
from app.platform.security.revocation import is_revoked
from app.platform.security.tokens import TokenError, decode_token

# auto_error=False so a missing header produces our own 401 with a
# WWW-Authenticate challenge rather than FastAPI's bare 403.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="not_authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED

    try:
        claims = decode_token(credentials.credentials, expected_type="access")
    except TokenError:
        raise _UNAUTHENTICATED from None

    if await is_revoked(claims.jti):
        raise _UNAUTHENTICATED

    user = await get_active_user(db, claims.subject)
    if user is None:
        raise _UNAUTHENTICATED

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
