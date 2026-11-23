"""Tables owned by the brand module. Schema, RLS policies and composite tenant foreign keys live in migration 0002."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

GUIDELINE_CATEGORIES = ("voice", "visual", "messaging", "do", "dont", "legal", "other")
ASSET_KINDS = ("logo", "image", "video", "document", "font")
RIGHTS_SOURCES = ("owned", "licensed", "stock", "user_generated", "ai_generated")


class BrandProfile(TimestampMixin, Base):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(500))
    tone_of_voice: Mapped[str | None] = mapped_column(Text)
    target_audience: Mapped[str | None] = mapped_column(Text)
    value_propositions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    colors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    fonts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    social_links: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BrandGuideline(TimestampMixin, Base):
    __tablename__ = "brand_guidelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="product")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    price_unit: Mapped[str | None] = mapped_column(String(50))
    url: Mapped[str | None] = mapped_column(String(500))
    features: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BrandAsset(TimestampMixin, Base):
    __tablename__ = "brand_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    storage_key: Mapped[str] = mapped_column(String(600), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(200))
    alt_text: Mapped[str | None] = mapped_column(String(500))
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rights_source: Mapped[str] = mapped_column(String(30), nullable=False, default="owned")
    rights_notes: Mapped[str | None] = mapped_column(Text)
    rights_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(300))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    upload_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
