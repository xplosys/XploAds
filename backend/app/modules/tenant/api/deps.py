"""Tenant-context dependencies (public interface used by every tenant-scoped module).

- Organization-management routes take the tenant from the ``{org_id}`` path parameter.
- Other modules' routes take it from the ``X-Tenant-ID`` header.
Either way, membership is verified before any tenant data is read.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request

from app.core.errors import AppError
from app.modules.identity.api.deps import Auth, DbSession
from app.modules.tenant.services.context import TenantContext, resolve_tenant_context


async def org_context(org_id: uuid.UUID, auth: Auth, db: DbSession, request: Request) -> TenantContext:
    ctx = await resolve_tenant_context(db, auth.user, org_id)
    request.state.tenant_id = str(ctx.tenant_id)
    return ctx


async def header_context(
    auth: Auth, db: DbSession, request: Request,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> TenantContext:
    if not x_tenant_id:
        raise AppError("X-Tenant-ID header is required", code="tenant_required")
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError:
        raise AppError("X-Tenant-ID must be a UUID", code="tenant_required") from None
    ctx = await resolve_tenant_context(db, auth.user, tenant_id)
    request.state.tenant_id = str(ctx.tenant_id)
    return ctx


OrgContext = Annotated[TenantContext, Depends(org_context)]
CurrentTenant = Annotated[TenantContext, Depends(header_context)]
