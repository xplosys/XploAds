"""Tenant-scoped persistence. All queries run under RLS; callers must have set the tenant context."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant.models import (
    Invitation,
    Permission,
    Role,
    RolePermission,
    Tenant,
    TenantUser,
    UserRole,
    Workspace,
)


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        q = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
        return (await self.s.execute(q)).scalar_one_or_none()

    async def list_visible(self) -> list[Tenant]:
        """Tenants visible under the current RLS context (memberships + agency clients)."""
        q = select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.name)
        return list((await self.s.execute(q)).scalars())

    async def list_clients(self, agency_id: uuid.UUID) -> list[Tenant]:
        q = (select(Tenant).where(Tenant.parent_tenant_id == agency_id, Tenant.deleted_at.is_(None))
             .order_by(Tenant.name))
        return list((await self.s.execute(q)).scalars())

    def add(self, obj: object) -> None:
        self.s.add(obj)


class MembershipRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantUser | None:
        q = select(TenantUser).where(TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id)
        return (await self.s.execute(q)).scalar_one_or_none()

    async def get(self, membership_id: uuid.UUID) -> TenantUser | None:
        return await self.s.get(TenantUser, membership_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[TenantUser]:
        q = select(TenantUser).where(TenantUser.user_id == user_id, TenantUser.status == "active")
        return list((await self.s.execute(q)).scalars())

    async def list_in_tenant(self, tenant_id: uuid.UUID) -> list[TenantUser]:
        q = select(TenantUser).where(TenantUser.tenant_id == tenant_id).order_by(TenantUser.joined_at)
        return list((await self.s.execute(q)).scalars())

    async def tenant_permissions(self, membership_id: uuid.UUID) -> set[str]:
        """Permission codes granted by tenant-wide role assignments of a membership."""
        q = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.membership_id == membership_id, UserRole.workspace_id.is_(None))
        )
        return set((await self.s.execute(q)).scalars())

    async def role_assignments(self, tenant_id: uuid.UUID) -> list[tuple[uuid.UUID, str, uuid.UUID | None]]:
        q = (
            select(UserRole.membership_id, Role.key, UserRole.workspace_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.tenant_id == tenant_id)
        )
        return [(m, k, w) for m, k, w in (await self.s.execute(q)).all()]

    async def count_owners(self, tenant_id: uuid.UUID, *, excluding_membership: uuid.UUID | None = None) -> int:
        q = (
            select(func.count(func.distinct(UserRole.membership_id)))
            .join(Role, Role.id == UserRole.role_id)
            .join(TenantUser, TenantUser.id == UserRole.membership_id)
            .where(UserRole.tenant_id == tenant_id, Role.key == "owner", Role.tenant_id.is_(None),
                   UserRole.workspace_id.is_(None), TenantUser.status == "active")
        )
        if excluding_membership:
            q = q.where(UserRole.membership_id != excluding_membership)
        return int((await self.s.execute(q)).scalar_one())

    async def clear_roles(self, membership_id: uuid.UUID) -> None:
        await self.s.execute(delete(UserRole).where(UserRole.membership_id == membership_id))

    def add(self, obj: object) -> None:
        self.s.add(obj)


class RoleRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def by_key(self, key: str) -> Role | None:
        """Custom role of the current tenant takes precedence over a system role with the same key."""
        q = select(Role).where(Role.key == key).order_by(Role.tenant_id.is_(None))
        return (await self.s.execute(q)).scalars().first()

    async def get(self, role_id: uuid.UUID) -> Role | None:
        return await self.s.get(Role, role_id)

    async def list_with_permissions(self) -> list[tuple[Role, list[str]]]:
        roles = list((await self.s.execute(select(Role).order_by(Role.is_system.desc(), Role.name))).scalars())
        q = select(RolePermission.role_id, Permission.code).join(
            Permission, Permission.id == RolePermission.permission_id)
        perms: dict[uuid.UUID, list[str]] = {}
        for role_id, code in (await self.s.execute(q)).all():
            perms.setdefault(role_id, []).append(code)
        return [(r, sorted(perms.get(r.id, []))) for r in roles]

    async def permissions_by_code(self, codes: list[str]) -> list[Permission]:
        q = select(Permission).where(Permission.code.in_(codes))
        return list((await self.s.execute(q)).scalars())

    async def all_permissions(self) -> list[Permission]:
        return list((await self.s.execute(select(Permission).order_by(Permission.module, Permission.code))).scalars())

    async def is_assigned(self, role_id: uuid.UUID) -> bool:
        q = select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
        q2 = select(func.count()).select_from(Invitation).where(Invitation.role_id == role_id,
                                                                Invitation.status == "pending")
        return bool((await self.s.execute(q)).scalar_one() or (await self.s.execute(q2)).scalar_one())

    def add(self, obj: object) -> None:
        self.s.add(obj)


class WorkspaceRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def list_all(self, tenant_id: uuid.UUID) -> list[Workspace]:
        q = select(Workspace).where(Workspace.tenant_id == tenant_id, Workspace.deleted_at.is_(None)).order_by(
            Workspace.is_default.desc(), Workspace.name)
        return list((await self.s.execute(q)).scalars())

    async def get(self, tenant_id: uuid.UUID, workspace_id: uuid.UUID) -> Workspace | None:
        q = select(Workspace).where(Workspace.id == workspace_id, Workspace.tenant_id == tenant_id,
                                    Workspace.deleted_at.is_(None))
        return (await self.s.execute(q)).scalar_one_or_none()

    async def slug_exists(self, tenant_id: uuid.UUID, slug: str) -> bool:
        q = select(func.count()).select_from(Workspace).where(Workspace.tenant_id == tenant_id, Workspace.slug == slug)
        return bool((await self.s.execute(q)).scalar_one())

    def add(self, obj: object) -> None:
        self.s.add(obj)


class InvitationRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def by_token_hash(self, token_hash: str) -> Invitation | None:
        q = select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
        return (await self.s.execute(q)).scalar_one_or_none()

    async def pending_for_email(self, tenant_id: uuid.UUID, email: str) -> Invitation | None:
        q = select(Invitation).where(Invitation.tenant_id == tenant_id, Invitation.email == email,
                                     Invitation.status == "pending")
        return (await self.s.execute(q)).scalar_one_or_none()

    async def list_all(self, tenant_id: uuid.UUID) -> list[Invitation]:
        q = select(Invitation).where(Invitation.tenant_id == tenant_id).order_by(Invitation.created_at.desc())
        return list((await self.s.execute(q)).scalars())

    async def get(self, tenant_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation | None:
        q = select(Invitation).where(Invitation.id == invitation_id, Invitation.tenant_id == tenant_id)
        return (await self.s.execute(q)).scalar_one_or_none()

    def add(self, obj: object) -> None:
        self.s.add(obj)
