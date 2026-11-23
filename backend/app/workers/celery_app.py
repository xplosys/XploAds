"""Celery application. Queues are declared up front so worker pools can be split by workload."""

from __future__ import annotations

import asyncio

from celery import Celery
from kombu import Queue
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.shared.outbox import relay_batch

QUEUES = [
    "default", "ai_generation", "image_generation", "video_generation", "creative_rendering", "meta_publishing",
    "webhook_processing", "lead_processing", "analytics_sync", "notifications", "billing_reconciliation",
]

settings = get_settings()
configure_logging(settings.log_level)

celery_app = Celery("xploads", broker=settings.broker_url, backend=None, include=["app.workers.handlers"])
celery_app.conf.update(
    task_queues=[Queue(q) for q in QUEUES],
    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "outbox-relay": {"task": "outbox.relay", "schedule": 5.0, "options": {"queue": "notifications"}},
        "asset-upload-cleanup": {"task": "brand.cleanup_stale_uploads", "schedule": 3600.0,
                                 "options": {"queue": "default"}},
    },
)


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


@celery_app.task(name="outbox.relay", ignore_result=True)
def outbox_relay() -> int:
    """Deliver due outbox events. Safe to run concurrently (rows are claimed with SKIP LOCKED)."""

    async def _go() -> int:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            return await relay_batch(async_sessionmaker(engine, expire_on_commit=False))
        finally:
            await engine.dispose()

    return _run(_go())


@celery_app.task(name="brand.cleanup_stale_uploads", ignore_result=True)
def cleanup_stale_uploads() -> int:
    """Reject asset uploads that were started but never completed, and delete any partial objects."""
    from app.modules.brand.services.assets import cleanup_stale_uploads as run

    async def _go() -> int:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
                return await run(session)
        finally:
            await engine.dispose()

    return _run(_go())
