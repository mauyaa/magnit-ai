from collections.abc import AsyncGenerator
from typing import Any, cast

from sqlalchemy import CursorResult
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.platform.config.settings import settings


def rows_affected(result: Result[Any]) -> int:
    """Number of rows a DML statement touched.

    ``AsyncSession.execute`` is typed as returning ``Result``, which has no
    ``rowcount`` — that lives on ``CursorResult``, which is what an INSERT/UPDATE
    /DELETE actually returns. This narrows it in one place instead of scattering
    casts across every call site that needs the count.
    """
    return cast("CursorResult[Any]", result).rowcount


engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
