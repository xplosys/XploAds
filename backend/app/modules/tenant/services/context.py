"""Tenant context resolution — the single place where the active tenant is established.

The requested tenant id is never trusted: it is accepted only if the user has an active membership in it,
or (for agency client tenants) an active membership in the parent agency holding ``agency.clients.access``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_rls_context
from app.core.errors import NotFound, PermissionDenied
from app.modules.identity.models import User
from app.modules.tenant.models import Tenant, TenantUser
from app.modules.tenant.permissions.catalog import AGENCY_ONLY
from app.modules.tenant.repositories import MembershipRepository, TenantRepository


@dataclass
class TenantContext:
    tenant: Tenant
    user: User
    access: Literal["member", "agency"]
    permissions: set[str] = field(default_factory=set)
    membership: TenantUser | None = None

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.tenant.id

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, *permissions: str) -> None:
        missing = [p for p in permissions if p not in self.permissions]
        if missing:
            raise PermissionDenied("You do not have permission to perform this action",
                                   details={"required": missing})


NOT_FOUND = "Organization not found"


async def resolve_tenant_context(db: AsyncSession, user: User, tenant_id: uuid.UUID) -> TenantContext:
    ctx = await _resolve(db, user, tenant_id)
    if ctx.tenant.status != "active":
        raise PermissionDenied("This organization is not active", code="tenant_inactive")
    return ctx


async def _resolve(db: AsyncSession, user: User, tenant_id: uuid.UUID) -> TenantContext:
    tenants, members = TenantRepository(db), MembershipRepository(db)

    await set_rls_context(db, user_id=user.id, tenant_id=tenant_id)
    tenant = await tenants.get(tenant_id)
    if tenant is None:
        raise NotFound(NOT_FOUND)
    membership = await members.get_for_user(tenant.id, user.id)
    if membership is not None and membership.status == "active":
        perms = await members.tenant_permissions(membership.id)
        return TenantContext(tenant=tenant, user=user, access="member", permissions=perms, membership=membership)

    if tenant.tenant_type == "client" and tenant.parent_tenant_id:
        parent_id = tenant.parent_tenant_id
        await set_rls_context(db, user_id=user.id, tenant_id=parent_id)
        parent_membership = await members.get_for_user(parent_id, user.id)
        agency_perms: set[str] = set()
        if parent_membership is not None and parent_membership.status == "active":
            agency_perms = await members.tenant_permissions(parent_membership.id)
        await set_rls_context(db, user_id=user.id, tenant_id=tenant.id)
        if "agency.clients.access" in agency_perms:
            return TenantContext(tenant=tenant, user=user, access="agency", permissions=agency_perms - AGENCY_ONLY)

    # 404 rather than 403: do not reveal whether another organization exists.
    raise NotFound(NOT_FOUND)
