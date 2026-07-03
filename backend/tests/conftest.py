"""Shared test fixtures.

Integration tests run against an in-memory SQLite database (via aiosqlite) so the full
persistence + service + sync stack is exercised with zero external services. The ORM
models are portable, so the same code runs on PostgreSQL in production.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.db.all_models  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base
from app.domain.clock import FixedClock

TEST_USER = uuid.UUID("00000000-0000-7000-8000-000000000001")
OTHER_USER = uuid.UUID("00000000-0000-7000-8000-0000000000ff")
CLOCK = FixedClock(dt.datetime(2026, 7, 3, 12, 0, tzinfo=dt.UTC))


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as sess:
        yield sess
