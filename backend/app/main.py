"""FastAPI application factory."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings
from app.core.database import dispose_engine, get_sessionmaker
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import close_redis, get_redis
from app.modules.identity.api.routes import router as auth_router
from app.modules.tenant.api.routes import router as tenant_router

log = structlog.get_logger("xploads.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.state.request_id = request_id
        limit = get_settings().max_request_body_bytes
        if int(request.headers.get("content-length") or 0) > limit:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=413, content={"error": {
                "code": "payload_too_large", "message": "Request body too large", "request_id": request_id,
                "details": None}})
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        log.info("request", method=request.method, path=request.url.path, status=response.status_code,
                 duration_ms=round((time.perf_counter() - start) * 1000, 1), request_id=request_id,
                 tenant_id=getattr(request.state, "tenant_id", None))
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.assert_safe_for_environment()
    configure_logging(settings.log_level, json_logs=settings.environment != "local")
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, send_default_pii=False,
                        traces_sample_rate=0.05)

    app = FastAPI(
        title="XploAds API", version="0.1.0", lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/api/docs",
        openapi_url=None if settings.environment == "production" else "/api/openapi.json",
    )
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth_router)
    v1.include_router(tenant_router)
    app.include_router(v1)

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> Response:
        checks: dict[str, str] = {}
        try:
            async with get_sessionmaker()() as s:
                await s.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            checks["database"] = "unavailable"
        try:
            await get_redis().ping()
            checks["redis"] = "ok"
        except Exception:  # noqa: BLE001
            checks["redis"] = "unavailable"
        ok = all(v == "ok" for v in checks.values())
        import json

        return Response(json.dumps({"status": "ok" if ok else "degraded", "checks": checks}),
                        status_code=200 if ok else 503, media_type="application/json")

    return app


app = create_app()
