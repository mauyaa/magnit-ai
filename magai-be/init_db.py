"""Create — and bring up to date — the local development schema.

Uses `metadata.create_all` rather than Alembic for the same reason `seed_dev.py`
does: the initial migration relies on `server_default=now()`, which is
Postgres-only, so `alembic upgrade head` cannot run against SQLite. Production
schema changes still go through Alembic — never through this script.

`create_all` alone is not enough. It creates tables that do not exist and skips
tables that do, so a database made before a model gained a column keeps the old
columns forever. Nothing announces that: the app starts normally and then 500s
on the first request touching the new field, with a SQL error that reads like a
code bug rather than a stale local database. So this also adds any column the
models declare and the database is missing.

Deliberately additive only. Dropping a column, changing a type or adding a
constraint are migrations, and doing them here would let a local shortcut
diverge from what production will actually run.

Produces an empty schema; use `seed_dev.py` instead when you also want content.
"""

import asyncio
import logging

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

import app.platform.db.models  # noqa: F401  (registers mappers before create_all)
from app.platform.db.base import Base
from app.platform.db.session import engine

logger = logging.getLogger("init_db")


def _missing_columns(connection) -> list[tuple[str, str, str]]:
    """Returns ``(table, column, DDL)`` for every column the database lacks."""
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    dialect = connection.dialect

    pending: list[tuple[str, str, str]] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all just made it, with every column.
        present = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            # SQLite refuses ADD COLUMN for a NOT NULL column with no default,
            # and rightly: existing rows would have nothing to put in it. Say so
            # here rather than let the driver report it as a syntax error.
            if not column.nullable and column.server_default is None and column.default is None:
                raise RuntimeError(
                    f"{table.name}.{column.name} is NOT NULL with no default; "
                    "add a server_default or recreate the local database"
                )
            ddl = str(CreateColumn(column).compile(dialect=dialect))
            pending.append((table.name, column.name, ddl))
    return pending


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        pending = await conn.run_sync(_missing_columns)
        for table_name, column_name, ddl in pending:
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
            logger.info("Added %s.%s", table_name, column_name)

    logger.info(
        "Database schema is up to date (%d column%s added).",
        len(pending),
        "" if len(pending) == 1 else "s",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
