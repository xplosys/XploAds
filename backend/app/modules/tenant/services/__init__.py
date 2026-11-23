"""Tenant use cases: organizations, agency clients, workspaces, members, invitations, roles."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import set_rls_context, utcnow
from app.core.errors import AppError, Conflict, NotFound, PermissionDenied
from app.core.security import generate_token, hash_token
from app.modules.identity.models import User
from app.modules.identity.repositories import UserRepository
from app.modules.tenant.models import Invitation, Role, RolePermission, Tenant, TenantUser, UserRole, Workspace
from app.modules.tenant.permissions.catalog import AGENCY_ONLY
from app.modules.tenant.repositories import (
    InvitationRepository,
    MembershipRepository,
    RoleRepository,
    TenantRepository,
    WorkspaceRepository,
)
from app.modules.tenant.services.context import TenantContext
from app.shared.audit import RequestMeta, record_audit
from app.shared.outbox import enqueue_event


def slugify(value: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:max_len].strip("-")
    return slug or "org"


def _unique_slug(name: str) -> str:
    # Tenant slugs are globally unique but other tenants are invisible under RLS, so add a random suffix.
    return f"{slugify(name, 52)}-{secrets.token_hex(3)}"


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    return {k: (str(v) if k == "website" and v is not None else v) for k, v in data.items()}


class TenantService:
    def __init__(self, session: AsyncSession, meta: RequestMeta | None = None):
        self.s = session
        self.meta = meta or RequestMeta()
        self.tenants = TenantRepository(session)
        self.members = MembershipRepository(session)
        self.roles = RoleRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.invitations = InvitationRepository(session)
        self.users = UserRepository(session)

    async def _audit(self, ctx_or_tenant: TenantContext | uuid.UUID, user_id: uuid.UUID, action: str,
                     resource_type: str, resource_id: Any, metadata: dict[str, Any] | None = None) -> None:
        tenant_id = ctx_or_tenant.tenant_id if isinstance(ctx_or_tenant, TenantContext) else ctx_or_tenant
        md = dict(metadata or {})
        if isinstance(ctx_or_tenant, TenantContext) and ctx_or_tenant.access == "agency":
            md["via"] = "agency"
        await record_audit(self.s, action=action, actor_user_id=user_id, tenant_id=tenant_id,
                           resource_type=resource_type, resource_id=resource_id, meta=self.meta, metadata=md)

    # --- organizations --------------------------------------------------------------------------------------

    async def _create_tenant(self, user: User, *, tenant_type: str, parent: uuid.UUID | None,
                             data: dict[str, Any]) -> Tenant:
        tenant = Tenant(id=uuid.uuid4(), slug=_unique_slug(data["name"]), tenant_type=tenant_type,
                        parent_tenant_id=parent, created_by=user.id, **_clean(data))
        # Creating a tenant switches the transaction's RLS context to it (insert policy: id = app.tenant_id).
        await set_rls_context(self.s, user_id=user.id, tenant_id=tenant.id)
        self.tenants.add(tenant)
        await self.s.flush()
        self.workspaces.add(Workspace(tenant_id=tenant.id, name="General", slug="general", is_default=True))
        await self.s.flush()
        return tenant

    async def create_organization(self, user: User, data: dict[str, Any]) -> Tenant:
        tenant_type = data.pop("tenant_type")
        tenant = await self._create_tenant(user, tenant_type=tenant_type, parent=None, data=data)
        membership = TenantUser(id=uuid.uuid4(), tenant_id=tenant.id, user_id=user.id)
        self.members.add(membership)
        await self.s.flush()
        owner = await self.roles.by_key("owner")
        assert owner is not None, "system roles missing — run migrations"
        self.members.add(UserRole(tenant_id=tenant.id, membership_id=membership.id, user_id=user.id,
                                  role_id=owner.id))
        await self._audit(tenant.id, user.id, "organization.created", "tenant", tenant.id,
                          {"tenant_type": tenant_type})
        return tenant

    async def create_client(self, ctx: TenantContext, data: dict[str, Any]) -> Tenant:
        ctx.require("agency.clients.create")
        if ctx.tenant.tenant_type != "agency":
            raise AppError("Only agency organizations can create client organizations", code="not_an_agency")
        agency_id = ctx.tenant_id
        await self._audit(ctx, ctx.user.id, "agency.client_created", "tenant", None, {"name": data["name"]})
        client = await self._create_tenant(ctx.user, tenant_type="client", parent=agency_id, data=data)
        await self._audit(client.id, ctx.user.id, "organization.created", "tenant", client.id,
                          {"tenant_type": "client", "agency_id": str(agency_id)})
        return client

    async def list_clients(self, ctx: TenantContext) -> list[Tenant]:
        ctx.require("organization.read")
        if ctx.tenant.tenant_type != "agency":
            return []
        if not ctx.has("agency.clients.access"):
            raise PermissionDenied("You do not have access to client organizations")
        await set_rls_context(self.s, user_id=ctx.user.id, tenant_id=None)
        clients = await self.tenants.list_clients(ctx.tenant_id)
        await set_rls_context(self.s, user_id=ctx.user.id, tenant_id=ctx.tenant_id)
        return clients

    async def list_accessible(self, user: User) -> list[tuple[Tenant, str, list[str], set[str]]]:
        """Organizations the user can open: direct memberships plus agency clients (with access permission)."""
        await set_rls_context(self.s, user_id=user.id, tenant_id=None)
        visible = await self.tenants.list_visible()
        memberships = {m.tenant_id: m for m in await self.members.list_for_user(user.id)}
        result: list[tuple[Tenant, str, list[str], set[str]]] = []
        perms_cache: dict[uuid.UUID, tuple[list[str], set[str]]] = {}
        for tid, m in memberships.items():
            await set_rls_context(self.s, user_id=user.id, tenant_id=tid)
            roles = sorted({k for mid, k, w in await self.members.role_assignments(tid) if mid == m.id and w is None})
            perms_cache[tid] = (roles, await self.members.tenant_permissions(m.id))
        await set_rls_context(self.s, user_id=user.id, tenant_id=None)
        for t in visible:
            if t.status == "closed":
                continue
            if t.id in perms_cache:
                roles, perms = perms_cache[t.id]
                result.append((t, "member", roles, perms))
            elif t.parent_tenant_id in perms_cache and "agency.clients.access" in perms_cache[t.parent_tenant_id][1]:
                roles, perms = perms_cache[t.parent_tenant_id]
                result.append((t, "agency", roles, perms - AGENCY_ONLY))
        return result

    async def update_organization(self, ctx: TenantContext, data: dict[str, Any]) -> Tenant:
        ctx.require("organization.update")
        changes = {k: v for k, v in _clean(data).items()}
        for k, v in changes.items():
            setattr(ctx.tenant, k, v)
        await self._audit(ctx, ctx.user.id, "organization.updated", "tenant", ctx.tenant_id,
                          {"fields": sorted(changes)})
        return ctx.tenant

    # --- workspaces -----------------------------------------------------------------------------------------

    async def list_workspaces(self, ctx: TenantContext) -> list[Workspace]:
        ctx.require("workspaces.read")
        return await self.workspaces.list_all(ctx.tenant_id)

    async def create_workspace(self, ctx: TenantContext, name: str, description: str | None) -> Workspace:
        ctx.require("workspaces.manage")
        base = slugify(name)
        slug, n = base, 1
        while await self.workspaces.slug_exists(ctx.tenant_id, slug):
            n += 1
            slug = f"{base}-{n}"
        ws = Workspace(id=uuid.uuid4(), tenant_id=ctx.tenant_id, name=name, slug=slug, description=description)
        self.workspaces.add(ws)
        await self.s.flush()
        await self._audit(ctx, ctx.user.id, "workspace.created", "workspace", ws.id, {"name": name})
        return ws

    async def update_workspace(self, ctx: TenantContext, workspace_id: uuid.UUID, data: dict[str, Any]) -> Workspace:
        ctx.require("workspaces.manage")
        ws = await self.workspaces.get(ctx.tenant_id, workspace_id)
        if ws is None:
            raise NotFound("Workspace not found")
        if ws.is_default and data.get("status") == "archived":
            raise AppError("The default workspace cannot be archived", code="default_workspace")
        for k, v in data.items():
            setattr(ws, k, v)
        await self._audit(ctx, ctx.user.id, "workspace.updated", "workspace", ws.id, {"fields": sorted(data)})
        return ws

    # --- members --------------------------------------------------------------------------------------------

    async def list_members(self, ctx: TenantContext) -> list[dict[str, Any]]:
        ctx.require("members.read")
        memberships = await self.members.list_in_tenant(ctx.tenant_id)
        users = await self.users.get_many([m.user_id for m in memberships])
        assignments: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for mid, key, ws in await self.members.role_assignments(ctx.tenant_id):
            assignments.setdefault(mid, []).append({"role_key": key, "workspace_id": ws})
        return [
            {"membership_id": m.id, "user_id": m.user_id, "email": users[m.user_id].email,
             "full_name": users[m.user_id].full_name, "status": m.status, "joined_at": m.joined_at,
             "roles": assignments.get(m.id, [])}
            for m in memberships if m.user_id in users
        ]

    async def _resolve_role(self, ctx: TenantContext, key: str) -> Role:
        role = await self.roles.by_key(key)
        if role is None:
            raise AppError(f"Unknown role '{key}'", code="unknown_role")
        if key == "owner" and not (ctx.access == "member" and await self._is_owner(ctx)):
            raise PermissionDenied("Only owners can grant the owner role")
        return role

    async def _is_owner(self, ctx: TenantContext) -> bool:
        if ctx.membership is None:
            return False
        return any(mid == ctx.membership.id and k == "owner" and w is None
                   for mid, k, w in await self.members.role_assignments(ctx.tenant_id))

    async def _check_workspace(self, ctx: TenantContext, workspace_id: uuid.UUID | None) -> None:
        if workspace_id and await self.workspaces.get(ctx.tenant_id, workspace_id) is None:
            raise NotFound("Workspace not found")

    async def set_member_roles(self, ctx: TenantContext, membership_id: uuid.UUID,
                               roles: list[dict[str, Any]]) -> None:
        ctx.require("members.manage")
        m = await self.members.get(membership_id)
        if m is None or m.tenant_id != ctx.tenant_id:
            raise NotFound("Member not found")
        resolved = []
        for r in roles:
            await self._check_workspace(ctx, r.get("workspace_id"))
            resolved.append((await self._resolve_role(ctx, r["role_key"]), r.get("workspace_id")))
        keeps_owner = any(role.key == "owner" and role.is_system and ws is None for role, ws in resolved)
        current = {k for mid, k, w in await self.members.role_assignments(ctx.tenant_id) if mid == m.id and w is None}
        if "owner" in current and not keeps_owner:
            if not await self._is_owner(ctx):
                raise PermissionDenied("Only owners can change another owner's roles")
            if await self.members.count_owners(ctx.tenant_id, excluding_membership=m.id) == 0:
                raise Conflict("An organization must keep at least one owner", code="last_owner")
        await self.members.clear_roles(m.id)
        await self.s.flush()
        for role, ws in {(r.id, w): (r, w) for r, w in resolved}.values():
            self.members.add(UserRole(tenant_id=ctx.tenant_id, membership_id=m.id, user_id=m.user_id,
                                      role_id=role.id, workspace_id=ws))
        await self._audit(ctx, ctx.user.id, "member.roles_changed", "membership", m.id,
                          {"roles": [{"role": r.key, "workspace_id": str(w) if w else None} for r, w in resolved]})

    async def remove_member(self, ctx: TenantContext, membership_id: uuid.UUID) -> None:
        m = await self.members.get(membership_id)
        if m is None or m.tenant_id != ctx.tenant_id:
            raise NotFound("Member not found")
        if m.user_id != ctx.user.id:  # leaving yourself needs no permission
            ctx.require("members.manage")
        is_owner = any(mid == m.id and k == "owner" and w is None
                       for mid, k, w in await self.members.role_assignments(ctx.tenant_id))
        if is_owner:
            if m.user_id != ctx.user.id and not await self._is_owner(ctx):
                raise PermissionDenied("Only owners can remove another owner")
            if await self.members.count_owners(ctx.tenant_id, excluding_membership=m.id) == 0:
                raise Conflict("An organization must keep at least one owner", code="last_owner")
        await self.s.delete(m)
        await self._audit(ctx, ctx.user.id, "member.removed", "membership", m.id, {"user_id": str(m.user_id)})

    # --- invitations ----------------------------------------------------------------------------------------

    async def invite(self, ctx: TenantContext, email: str, role_key: str,
                     workspace_id: uuid.UUID | None) -> tuple[Invitation, str]:
        ctx.require("members.invite")
        if not ctx.user.email_verified:
            raise PermissionDenied("Verify your email address before inviting others", code="email_not_verified")
        email = email.lower()
        role = await self._resolve_role(ctx, role_key)
        await self._check_workspace(ctx, workspace_id)
        existing_user = await self.users.get_by_email(email)
        if existing_user and await self.members.get_for_user(ctx.tenant_id, existing_user.id):
            raise Conflict("This person is already a member", code="already_member")
        if prior := await self.invitations.pending_for_email(ctx.tenant_id, email):
            prior.status = "revoked"
            await self.s.flush()
        secret = generate_token()
        inv = Invitation(id=uuid.uuid4(), tenant_id=ctx.tenant_id, email=email, role_id=role.id,
                         workspace_id=workspace_id, token_hash=hash_token(secret), invited_by=ctx.user.id,
                         expires_at=utcnow() + timedelta(days=get_settings().invitation_ttl_days))
        self.invitations.add(inv)
        await self.s.flush()
        token = f"{ctx.tenant_id}.{secret}"
        enqueue_event(self.s, "tenant.invitation_created", {
            "invitation_id": str(inv.id), "email": email, "organization_name": ctx.tenant.name,
            "inviter_name": ctx.user.full_name, "role_name": role.name,
            "link": f"{get_settings().frontend_url}/invitations/accept?token={token}", "token": token,
        }, tenant_id=ctx.tenant_id)
        await self._audit(ctx, ctx.user.id, "invitation.created", "invitation", inv.id,
                          {"email": email, "role": role.key})
        return inv, token

    async def list_invitations(self, ctx: TenantContext) -> list[tuple[Invitation, str]]:
        ctx.require("members.read")
        invs = await self.invitations.list_all(ctx.tenant_id)
        now = utcnow()
        out = []
        for inv in invs:
            if inv.status == "pending" and inv.expires_at <= now:
                inv.status = "expired"
            role = await self.roles.get(inv.role_id)
            out.append((inv, role.key if role else "unknown"))
        return out

    async def revoke_invitation(self, ctx: TenantContext, invitation_id: uuid.UUID) -> None:
        ctx.require("members.invite")
        inv = await self.invitations.get(ctx.tenant_id, invitation_id)
        if inv is None:
            raise NotFound("Invitation not found")
        if inv.status == "pending":
            inv.status = "revoked"
            await self._audit(ctx, ctx.user.id, "invitation.revoked", "invitation", inv.id)

    async def _load_invitation(self, token: str, user_id: uuid.UUID | None) -> Invitation:
        try:
            tenant_part, secret = token.split(".", 1)
            tenant_id = uuid.UUID(tenant_part)
        except ValueError:
            raise NotFound("Invitation not found or no longer valid") from None
        await set_rls_context(self.s, user_id=user_id, tenant_id=tenant_id)
        inv = await self.invitations.by_token_hash(hash_token(secret))
        if inv is None or inv.status != "pending" or inv.expires_at <= utcnow():
            raise NotFound("Invitation not found or no longer valid")
        return inv

    async def preview_invitation(self, token: str) -> dict[str, Any]:
        inv = await self._load_invitation(token, None)
        tenant = await self.tenants.get(inv.tenant_id)
        role = await self.roles.get(inv.role_id)
        inviter = await self.users.get(inv.invited_by)
        assert tenant and role
        return {"organization_name": tenant.name, "email": inv.email, "role_name": role.name,
                "inviter_name": inviter.full_name if inviter else None, "expires_at": inv.expires_at}

    async def accept_invitation(self, user: User, token: str) -> Tenant:
        inv = await self._load_invitation(token, user.id)
        if inv.email != user.email:
            raise PermissionDenied("This invitation was sent to a different email address",
                                   code="invitation_email_mismatch")
        membership = await self.members.get_for_user(inv.tenant_id, user.id)
        if membership is None:
            membership = TenantUser(id=uuid.uuid4(), tenant_id=inv.tenant_id, user_id=user.id,
                                    invited_by=inv.invited_by)
            self.members.add(membership)
            await self.s.flush()
        else:
            membership.status = "active"
        if not any(mid == membership.id and rid == inv.role_id
                   for mid, rid in await self._assignment_ids(inv.tenant_id)):
            self.members.add(UserRole(tenant_id=inv.tenant_id, membership_id=membership.id, user_id=user.id,
                                      role_id=inv.role_id, workspace_id=inv.workspace_id))
        inv.status, inv.accepted_at, inv.accepted_by = "accepted", utcnow(), user.id
        # The token was delivered to this mailbox, which proves control of the address.
        user.email_verified_at = user.email_verified_at or utcnow()
        await self._audit(inv.tenant_id, user.id, "invitation.accepted", "invitation", inv.id)
        tenant = await self.tenants.get(inv.tenant_id)
        assert tenant is not None
        return tenant

    async def _assignment_ids(self, tenant_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        from sqlalchemy import select

        q = select(UserRole.membership_id, UserRole.role_id).where(UserRole.tenant_id == tenant_id)
        return [(a, b) for a, b in (await self.s.execute(q)).all()]

    # --- roles ----------------------------------------------------------------------------------------------

    async def list_roles(self, ctx: TenantContext) -> list[tuple[Role, list[str]]]:
        ctx.require("roles.read")
        return await self.roles.list_with_permissions()

    async def create_role(self, ctx: TenantContext, key: str, name: str, description: str | None,
                          permissions: list[str]) -> tuple[Role, list[str]]:
        ctx.require("roles.manage")
        codes = sorted(set(permissions))
        found = await self.roles.permissions_by_code(codes)
        unknown = set(codes) - {p.code for p in found}
        if unknown:
            raise AppError("Unknown permissions", code="unknown_permission", details=sorted(unknown))
        escalation = set(codes) - ctx.permissions
        if escalation:
            raise PermissionDenied("You cannot grant permissions you do not hold", details=sorted(escalation))
        if (existing := await self.roles.by_key(key)) is not None and existing.tenant_id == ctx.tenant_id:
            raise Conflict("A role with this key already exists", code="role_exists")
        if existing is not None and existing.is_system:
            raise Conflict("This key is reserved for a system role", code="role_exists")
        role = Role(id=uuid.uuid4(), tenant_id=ctx.tenant_id, key=key, name=name, description=description,
                    is_system=False)
        self.roles.add(role)
        await self.s.flush()
        for p in found:
            self.roles.add(RolePermission(role_id=role.id, permission_id=p.id, tenant_id=ctx.tenant_id))
        await self._audit(ctx, ctx.user.id, "role.created", "role", role.id, {"key": key, "permissions": codes})
        return role, codes

    async def delete_role(self, ctx: TenantContext, role_id: uuid.UUID) -> None:
        ctx.require("roles.manage")
        role = await self.roles.get(role_id)
        if role is None or role.tenant_id != ctx.tenant_id:
            raise NotFound("Role not found")
        if await self.roles.is_assigned(role.id):
            raise Conflict("This role is still assigned to members or pending invitations", code="role_in_use")
        await self.s.delete(role)
        await self._audit(ctx, ctx.user.id, "role.deleted", "role", role_id, {"key": role.key})
