"""Redis fixed-window rate limiting for sensitive endpoints.

Fails open (logs a warning) if Redis is unavailable, so an outage of the cache does not lock every user out;
account lockout in the identity module still protects against password guessing.
"""

from __future__ import annotations

import hashlib

import structlog
from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.errors import RateLimited

log = structlog.get_logger(__name__)
_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def client_ip(request: Request) -> str:
    # Nginx sets X-Real-IP; it overwrites any client-supplied value.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


async def hit(bucket: str, identity: str, *, limit: int, window_seconds: int) -> None:
    if not get_settings().rate_limit_enabled:
        return
    digest = hashlib.sha256(identity.encode()).hexdigest()[:32]
    key = f"rl:{bucket}:{digest}"
    try:
        r = get_redis()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
    except RedisError:
        log.warning("rate_limit_unavailable", bucket=bucket)
        return
    if count > limit:
        raise RateLimited("Too many requests. Please try again later.", details={"retry_after": window_seconds})


def limiter(bucket: str, *, limit: int, window_seconds: int):
    """FastAPI dependency factory limiting by client IP."""

    async def _dep(request: Request) -> None:
        await hit(bucket, client_ip(request), limit=limit, window_seconds=window_seconds)

    return _dep
