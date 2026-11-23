"""Database engine, declarative base and tenant-context helpers.

Every request/job runs in one transaction. Before any tenant data is touched, the transaction-local settings
``app.user_id`` and ``app.tenant_id`` are set; PostgreSQL RLS policies compare rows against them.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url, pool_size=settings.db_pool_size, pool_pre_ping=True
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def set_rls_context(
    session: AsyncSession, *, user_id: uuid.UUID | None = None, tenant_id: uuid.UUID | None = None
) -> None:
    """Set transaction-local RLS context. Passing ``None`` clears the value for the rest of the transaction."""
    await session.execute(
        text("SELECT set_config('app.user_id', :u, true), set_config('app.tenant_id', :t, true)"),
        {"u": str(user_id) if user_id else "", "t": str(tenant_id) if tenant_id else ""},
    )


async def session_scope() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request, committed on success, rolled back on error."""
    async with get_sessionmaker()() as session:
        async with session.begin():
            yield session


async def run_in_independent_transaction(fn) -> None:  # type: ignore[no-untyped-def]
    """Run ``await fn(session)`` in its own committed transaction.

    Used for security bookkeeping (failed-login counters, refresh-token reuse revocation) that must persist even
    though the surrounding request transaction is rolled back because the request fails.
    """
    async with get_sessionmaker()() as session, session.begin():
        await fn(session)
