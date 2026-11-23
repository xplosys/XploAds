"""Transactional outbox.

Business code calls :func:`enqueue_event` inside its own transaction, so the event is persisted if and only if
the business change commits. The relay (Celery beat → :func:`relay_batch`) claims pending rows with
``FOR UPDATE SKIP LOCKED``, runs the registered handler, and retries with exponential backoff. Rows that exhaust
their attempts move to ``dead`` for operator review (dead-letter).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 8
# Payload keys removed after successful delivery (e.g. one-time links in emails).
SENSITIVE_PAYLOAD_KEYS = {"token", "link"}


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def enqueue_event(
    session: AsyncSession, event_type: str, payload: dict[str, Any], *, tenant_id: uuid.UUID | None = None
) -> OutboxEvent:
    event = OutboxEvent(event_type=event_type, payload=payload, tenant_id=tenant_id)
    session.add(event)
    return event


Handler = Callable[[OutboxEvent], Awaitable[None]]
_handlers: dict[str, Handler] = {}


def handles(event_type: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _handlers[event_type] = fn
        return fn

    return deco


def backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(2**attempt * 5, 3600))


async def relay_batch(sessionmaker: async_sessionmaker[AsyncSession], *, limit: int = 50) -> int:
    """Process up to ``limit`` due events. Returns the number of events handled successfully."""
    done = 0
    async with sessionmaker() as session, session.begin():
        rows = (
            await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending", OutboxEvent.available_at <= utcnow())
                .order_by(OutboxEvent.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for event in rows:
            handler = _handlers.get(event.event_type)
            event.attempts += 1
            try:
                if handler is None:
                    raise LookupError(f"no handler for {event.event_type}")
                await handler(event)
            except Exception as exc:  # noqa: BLE001 - every failure is recorded and retried
                event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if event.attempts >= MAX_ATTEMPTS:
                    event.status = "dead"
                    log.error("outbox_dead_letter", event_id=str(event.id), event_type=event.event_type)
                else:
                    event.available_at = utcnow() + backoff(event.attempts)
                    log.warning("outbox_retry", event_id=str(event.id), attempts=event.attempts)
                continue
            event.status = "done"
            event.processed_at = utcnow()
            event.payload = {k: v for k, v in event.payload.items() if k not in SENSITIVE_PAYLOAD_KEYS}
            done += 1
    return done
