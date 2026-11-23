"""Tables owned by the tenant module. Schema (incl. RLS policies) is defined in Alembic migrations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, utcnow

TENANT_TYPES = ("business", "agency", "client", "enterprise")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    tenant_type: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    industry: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(500))
    country_code: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="tenant")
    description: Mapped[str] = mapped_column(String(300), nullable=False)


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"))
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id"), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class TenantUser(TimestampMixin, Base):
    __tablename__ = "tenant_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    invited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
