"""Create the local development schema.

Uses `metadata.create_all` rather than Alembic for the same reason `seed_dev.py`
does: the initial migration relies on `server_default=now()`, which is
Postgres-only, so `alembic upgrade head` cannot run against SQLite. Production
schema changes still go through Alembic — never through this script.

Produces an empty schema; use `seed_dev.py` instead when you also want content.
"""

import asyncio
import logging

import app.platform.db.models  # noqa: F401  (registers mappers before create_all)
from app.platform.db.base import Base
from app.platform.db.session import engine

logger = logging.getLogger("init_db")


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
