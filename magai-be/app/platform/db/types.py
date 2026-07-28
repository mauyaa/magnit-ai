"""Dialect-portable column types.

Production runs on PostgreSQL and wants native ``JSONB``/``UUID``. The test suite
runs on in-memory SQLite (the ``aiosqlite`` dev dependency), which has neither.
These decorators compile to the native Postgres types where available and fall
back to portable equivalents elsewhere, so the same models back both.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CHAR, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


class JSONType(TypeDecorator):
    """``JSONB`` on PostgreSQL, generic ``JSON`` elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UUIDType(TypeDecorator):
    """Native ``UUID`` on PostgreSQL, 36-char string elsewhere.

    Always yields ``uuid.UUID`` instances to Python regardless of backend so
    application and test code can treat the value identically.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
