"""Shared test fixtures.

Design notes:

* The database is in-memory SQLite driven through the async engine. The models use
  the dialect-portable types in ``app.platform.db.types``, so the same mappings
  that run on PostgreSQL back the tests without a live server.
* Redis-backed behaviour (rate limits, revocation, locks) is stubbed by default so
  the suite needs no running Redis. Tests that exercise those paths patch them
  explicitly.
* Environment variables are set before ``app.*`` is imported so ``settings`` picks
  up test values at import time.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

# Must precede any app import: Settings reads the environment on construction.
os.environ.update(
    {
        "MAGAI_ENVIRONMENT": "development",
        "MAGAI_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256-signing",
        "MAGAI_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "MAGAI_RATE_LIMIT_ENABLED": "false",
        "MAGAI_LOG_FORMAT": "text",
        "MAGAI_METRICS_ENABLED": "false",
        "MAGAI_SELF_HEAL_ENABLED": "false",
        "MAGAI_PASSWORD_MIN_LENGTH": "12",
        "MAGAI_CORS_ALLOW_ORIGINS": "http://localhost:3000",
        "MAGAI_STRIPE_WEBHOOK_SECRET": "whsec_test_secret",
        "MAGAI_VERCEL_API_TOKEN": "test-vercel-token",
    }
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.platform.db.models
from app.features.auth.deps import get_current_user
from app.features.users.models import User
from app.platform.db.base import Base
from app.platform.db.session import get_async_session
from app.platform.http.app import create_app
from app.platform.security.passwords import hash_password

TEST_PASSWORD = "correct-horse-battery-99"


@pytest.fixture
async def engine():
    """One in-memory database per test, shared across connections.

    StaticPool keeps a single connection alive so ``:memory:`` persists for the
    duration of the test instead of vanishing between checkouts.
    """
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db(session_factory) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
async def stub_redis(monkeypatch):
    """Replace Redis-backed helpers with in-process equivalents."""
    revoked: set[str] = set()

    async def fake_revoke(jti: str, _expires_at) -> None:
        revoked.add(jti)

    async def fake_is_revoked(jti: str) -> bool:
        return jti in revoked

    for module in ("app.platform.security.revocation", "app.features.auth.deps"):
        monkeypatch.setattr(f"{module}.is_revoked", fake_is_revoked, raising=False)
    monkeypatch.setattr("app.features.auth.routes.is_revoked", fake_is_revoked, raising=False)
    monkeypatch.setattr("app.features.auth.routes.revoke", fake_revoke, raising=False)
    monkeypatch.setattr("app.platform.security.revocation.revoke", fake_revoke, raising=False)
    return revoked


@pytest.fixture
async def app(session_factory, stub_redis):
    """The FastAPI app with the test database injected."""
    application = create_app()

    async def override_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_async_session] = override_session
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient]:
    """HTTP client bound to the test app.

    ``raise_app_exceptions=False`` so the registered exception handlers run and
    tests can assert on the 500 response body instead of the exception propagating
    out of the transport.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def _make_user(db, email: str, *, verified: bool = True) -> User:
    account = User(
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
        role="owner",
        # Verified by default: most tests exercise behaviour *after* onboarding, and
        # an unverified fixture would trip the build gate before the assertion under
        # test. The gate itself has dedicated tests.
        email_verified=verified,
        email_verified_at=datetime.now(UTC) if verified else None,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@pytest.fixture
async def user(db) -> User:
    return await _make_user(db, "owner@example.com")


@pytest.fixture
async def other_user(db) -> User:
    return await _make_user(db, "intruder@example.com")


@pytest.fixture
async def unverified_user(db) -> User:
    """A freshly signed-up account that has not confirmed its email yet."""
    return await _make_user(db, "unverified@example.com", verified=False)


@pytest.fixture
def auth_headers():
    """Build an Authorization header for a given user."""
    from app.platform.security.tokens import create_access_token

    def _headers(account: User) -> dict[str, str]:
        token, _ = create_access_token(str(account.id))
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def as_user(app, client):
    """Bypass token verification and pin the request identity to ``account``.

    For route tests that are about authorization logic rather than token plumbing;
    token handling itself is covered in ``test_auth.py``.
    """

    def _apply(account: User) -> AsyncClient:
        app.dependency_overrides[get_current_user] = lambda: account
        return client

    return _apply
