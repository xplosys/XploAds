"""/api/v1/organizations, /api/v1/invitations, /api/v1/permissions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.core.rate_limit import limiter
from app.modules.identity.api.deps import Auth, DbSession, Meta
from app.modules.tenant.api.deps import OrgContext
from app.modules.tenant.models import Tenant
from app.modules.tenant.repositories import MembershipRepository, RoleRepository
from app.modules.tenant.schemas import (
    AcceptInvitation,
    AuditLogOut,
    ClientCreate,
    InvitationCreate,
    InvitationOut,
    InvitationPreview,
    MemberOut,
    MemberRolesUpdate,
    OrganizationAccess,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
    PermissionOut,
    RoleCreate,
    RoleOut,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.modules.tenant.services import TenantService
from app.shared.audit import AuditLog
from app.shared.schemas import Message, Page

router = APIRouter(tags=["organizations"])


def _org(t: Tenant) -> OrganizationOut:
    return OrganizationOut.model_validate(t)


def _access(t: Tenant, access: str, roles: list[str], perms: set[str]) -> OrganizationAccess:
    return OrganizationAccess(**_org(t).model_dump(), access=access, roles=roles,  # type: ignore[arg-type]
                              permissions=sorted(perms))


@router.get("/organizations", response_model=list[OrganizationAccess])
async def list_organizations(auth: Auth, db: DbSession) -> list[OrganizationAccess]:
    rows = await TenantService(db).list_accessible(auth.user)
    return [_access(t, a, r, p) for t, a, r, p in rows]


@router.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(body: OrganizationCreate, auth: Auth, db: DbSession, meta: Meta) -> OrganizationOut:
    return _org(await TenantService(db, meta).create_organization(auth.user, body.model_dump()))


@router.get("/organizations/{org_id}", response_model=OrganizationAccess)
async def get_organization(ctx: OrgContext, db: DbSession) -> OrganizationAccess:
    ctx.require("organization.read")
    roles: list[str] = []
    if ctx.membership is not None:
        assignments = await MembershipRepository(db).role_assignments(ctx.tenant_id)
        roles = sorted({k for m, k, w in assignments if m == ctx.membership.id and w is None})
    return _access(ctx.tenant, ctx.access, roles, ctx.permissions)


@router.patch("/organizations/{org_id}", response_model=OrganizationOut)
async def update_organization(body: OrganizationUpdate, ctx: OrgContext, db: DbSession, meta: Meta) -> OrganizationOut:
    data = body.model_dump(exclude_unset=True)
    return _org(await TenantService(db, meta).update_organization(ctx, data))


# --- agency clients ------------------------------------------------------------------------------------------


@router.get("/organizations/{org_id}/clients", response_model=list[OrganizationOut])
async def list_clients(ctx: OrgContext, db: DbSession) -> list[OrganizationOut]:
    return [_org(t) for t in await TenantService(db).list_clients(ctx)]


@router.post("/organizations/{org_id}/clients", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_client(body: ClientCreate, ctx: OrgContext, db: DbSession, meta: Meta) -> OrganizationOut:
    return _org(await TenantService(db, meta).create_client(ctx, body.model_dump()))


# --- workspaces ----------------------------------------------------------------------------------------------


@router.get("/organizations/{org_id}/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(ctx: OrgContext, db: DbSession) -> list[WorkspaceOut]:
    return [WorkspaceOut.model_validate(w) for w in await TenantService(db).list_workspaces(ctx)]


@router.post("/organizations/{org_id}/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceCreate, ctx: OrgContext, db: DbSession, meta: Meta) -> WorkspaceOut:
    ws = await TenantService(db, meta).create_workspace(ctx, body.name, body.description)
    return WorkspaceOut.model_validate(ws)


@router.patch("/organizations/{org_id}/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(workspace_id: uuid.UUID, body: WorkspaceUpdate, ctx: OrgContext, db: DbSession,
                           meta: Meta) -> WorkspaceOut:
    ws = await TenantService(db, meta).update_workspace(ctx, workspace_id, body.model_dump(exclude_unset=True))
    return WorkspaceOut.model_validate(ws)


# --- members & invitations -----------------------------------------------------------------------------------


@router.get("/organizations/{org_id}/members", response_model=list[MemberOut])
async def list_members(ctx: OrgContext, db: DbSession) -> list[MemberOut]:
    return [MemberOut.model_validate(m) for m in await TenantService(db).list_members(ctx)]


@router.put("/organizations/{org_id}/members/{membership_id}/roles", response_model=Message)
async def set_member_roles(membership_id: uuid.UUID, body: MemberRolesUpdate, ctx: OrgContext, db: DbSession,
                           meta: Meta) -> Message:
    await TenantService(db, meta).set_member_roles(ctx, membership_id, [r.model_dump() for r in body.roles])
    return Message(message="Roles updated")


@router.delete("/organizations/{org_id}/members/{membership_id}", response_model=Message)
async def remove_member(membership_id: uuid.UUID, ctx: OrgContext, db: DbSession, meta: Meta) -> Message:
    await TenantService(db, meta).remove_member(ctx, membership_id)
    return Message(message="Member removed")


@router.post("/organizations/{org_id}/members", response_model=InvitationOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(limiter("invite", limit=50, window_seconds=3600))])
@router.post("/organizations/{org_id}/invitations", response_model=InvitationOut,
             status_code=status.HTTP_201_CREATED, include_in_schema=False,
             dependencies=[Depends(limiter("invite", limit=50, window_seconds=3600))])
async def invite_member(body: InvitationCreate, ctx: OrgContext, db: DbSession, meta: Meta) -> InvitationOut:
    """Invite a person by email. Existing users accept from their account; new users register first."""
    inv, _ = await TenantService(db, meta).invite(ctx, body.email, body.role_key, body.workspace_id)
    return InvitationOut(id=inv.id, email=inv.email, role_key=body.role_key, workspace_id=inv.workspace_id,
                         status=inv.status, expires_at=inv.expires_at, created_at=inv.created_at)


@router.get("/organizations/{org_id}/invitations", response_model=list[InvitationOut])
async def list_invitations(ctx: OrgContext, db: DbSession) -> list[InvitationOut]:
    rows = await TenantService(db).list_invitations(ctx)
    return [InvitationOut(id=i.id, email=i.email, role_key=k, workspace_id=i.workspace_id, status=i.status,
                          expires_at=i.expires_at, created_at=i.created_at) for i, k in rows]


@router.delete("/organizations/{org_id}/invitations/{invitation_id}", response_model=Message)
async def revoke_invitation(invitation_id: uuid.UUID, ctx: OrgContext, db: DbSession, meta: Meta) -> Message:
    await TenantService(db, meta).revoke_invitation(ctx, invitation_id)
    return Message(message="Invitation revoked")


@router.get("/invitations/preview", response_model=InvitationPreview,
            dependencies=[Depends(limiter("invite_preview", limit=30, window_seconds=600))])
async def preview_invitation(db: DbSession, token: str = Query(min_length=10, max_length=300)) -> InvitationPreview:
    return InvitationPreview(**await TenantService(db).preview_invitation(token))


@router.post("/invitations/accept", response_model=OrganizationOut,
             dependencies=[Depends(limiter("invite_accept", limit=20, window_seconds=600))])
async def accept_invitation(body: AcceptInvitation, auth: Auth, db: DbSession, meta: Meta) -> OrganizationOut:
    return _org(await TenantService(db, meta).accept_invitation(auth.user, body.token))


# --- roles & permissions -------------------------------------------------------------------------------------


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(auth: Auth, db: DbSession) -> list[PermissionOut]:
    return [PermissionOut.model_validate(p) for p in await RoleRepository(db).all_permissions()]


@router.get("/organizations/{org_id}/roles", response_model=list[RoleOut])
async def list_roles(ctx: OrgContext, db: DbSession) -> list[RoleOut]:
    rows = await TenantService(db).list_roles(ctx)
    return [RoleOut(id=r.id, key=r.key, name=r.name, description=r.description, is_system=r.is_system,
                    permissions=p) for r, p in rows]


@router.post("/organizations/{org_id}/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(body: RoleCreate, ctx: OrgContext, db: DbSession, meta: Meta) -> RoleOut:
    r, p = await TenantService(db, meta).create_role(ctx, body.key, body.name, body.description, body.permissions)
    return RoleOut(id=r.id, key=r.key, name=r.name, description=r.description, is_system=r.is_system, permissions=p)


@router.delete("/organizations/{org_id}/roles/{role_id}", response_model=Message)
async def delete_role(role_id: uuid.UUID, ctx: OrgContext, db: DbSession, meta: Meta) -> Message:
    await TenantService(db, meta).delete_role(ctx, role_id)
    return Message(message="Role deleted")


# --- audit ---------------------------------------------------------------------------------------------------


@router.get("/organizations/{org_id}/audit-logs", response_model=Page[AuditLogOut])
async def list_audit_logs(ctx: OrgContext, db: DbSession, limit: int = Query(50, ge=1, le=200),
                          offset: int = Query(0, ge=0), action: str | None = Query(None, max_length=100)
                          ) -> Page[AuditLogOut]:
    ctx.require("audit.read")
    base = select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id)
    if action:
        base = base.where(AuditLog.action == action)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(AuditLog.occurred_at.desc()).limit(limit).offset(offset))).scalars()
    items = [AuditLogOut(id=a.id, actor_user_id=a.actor_user_id, actor_type=a.actor_type, action=a.action,
                         resource_type=a.resource_type, resource_id=a.resource_id, ip_address=a.ip_address,
                         metadata=a.metadata_, occurred_at=a.occurred_at) for a in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)
