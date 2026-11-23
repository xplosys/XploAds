from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import EmailStr, Field, HttpUrl

from app.shared.schemas import APIModel

OrgType = Literal["business", "agency", "enterprise"]


class OrganizationCreate(APIModel):
    name: str = Field(min_length=2, max_length=200)
    tenant_type: OrgType = "business"
    industry: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    timezone: str = Field(default="UTC", max_length=64)
    default_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class ClientCreate(APIModel):
    name: str = Field(min_length=2, max_length=200)
    industry: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    timezone: str = Field(default="UTC", max_length=64)
    default_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class OrganizationUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    industry: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    timezone: str | None = Field(default=None, max_length=64)
    default_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class OrganizationOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    tenant_type: str
    parent_tenant_id: uuid.UUID | None
    status: str
    industry: str | None
    website: str | None
    country_code: str | None
    timezone: str
    default_currency: str
    created_at: datetime


class OrganizationAccess(OrganizationOut):
    access: Literal["member", "agency"]
    roles: list[str]
    permissions: list[str]


class WorkspaceCreate(APIModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "archived"] | None = None


class WorkspaceOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_default: bool
    status: str
    created_at: datetime


class RoleAssignment(APIModel):
    role_key: str
    workspace_id: uuid.UUID | None = None


class MemberOut(APIModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    status: str
    joined_at: datetime
    roles: list[RoleAssignment]


class MemberRolesUpdate(APIModel):
    roles: list[RoleAssignment] = Field(min_length=1, max_length=20)


class InvitationCreate(APIModel):
    email: EmailStr
    role_key: str = Field(default="member", max_length=50)
    workspace_id: uuid.UUID | None = None


class InvitationOut(APIModel):
    id: uuid.UUID
    email: str
    role_key: str
    workspace_id: uuid.UUID | None
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationPreview(APIModel):
    organization_name: str
    email: str
    role_name: str
    inviter_name: str | None
    expires_at: datetime


class AcceptInvitation(APIModel):
    token: str = Field(min_length=10, max_length=300)


class PermissionOut(APIModel):
    code: str
    module: str
    description: str


class RoleOut(APIModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


class RoleCreate(APIModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    permissions: list[str] = Field(min_length=1, max_length=200)


class AuditLogOut(APIModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_type: str
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    metadata: dict[str, Any]
    occurred_at: datetime
