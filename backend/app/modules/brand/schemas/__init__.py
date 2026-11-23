from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, field_validator

from app.shared.schemas import APIModel

GuidelineCategory = Literal["voice", "visual", "messaging", "do", "dont", "legal", "other"]
AssetKind = Literal["logo", "image", "video", "document", "font"]
RightsSource = Literal["owned", "licensed", "stock", "user_generated", "ai_generated"]
SocialPlatform = Literal["facebook", "instagram", "linkedin", "x", "youtube", "tiktok", "whatsapp", "website"]

ShortText = Annotated[str, Field(min_length=1, max_length=300)]
Tag = Annotated[str, Field(min_length=1, max_length=40)]


class BrandColor(APIModel):
    name: str = Field(min_length=1, max_length=60)
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    usage: Literal["primary", "secondary", "accent", "neutral", "background", "text"] = "primary"

    @field_validator("hex")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class BrandFont(APIModel):
    family: str = Field(min_length=1, max_length=100)
    usage: Literal["heading", "body", "accent"] = "body"
    weight: str | None = Field(default=None, max_length=40)


class BrandFields(APIModel):
    tagline: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    industry: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None
    tone_of_voice: str | None = Field(default=None, max_length=3000)
    target_audience: str | None = Field(default=None, max_length=3000)
    value_propositions: list[ShortText] | None = Field(default=None, max_length=20)
    colors: list[BrandColor] | None = Field(default=None, max_length=12)
    fonts: list[BrandFont] | None = Field(default=None, max_length=6)
    social_links: dict[SocialPlatform, HttpUrl] | None = None


class BrandCreate(BrandFields):
    name: str = Field(min_length=2, max_length=200)


class BrandUpdate(BrandFields):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    status: Literal["active", "archived"] | None = None
    logo_asset_id: uuid.UUID | None = None


class BrandSummary(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    tagline: str | None
    industry: str | None
    status: str
    is_default: bool
    logo_asset_id: uuid.UUID | None
    logo_url: str | None = None
    created_at: datetime
    updated_at: datetime


class BrandOut(BrandSummary):
    description: str | None
    website: str | None
    tone_of_voice: str | None
    target_audience: str | None
    value_propositions: list[str]
    colors: list[BrandColor]
    fonts: list[BrandFont]
    social_links: dict[str, str]
    counts: dict[str, int] = Field(default_factory=dict)


class GuidelineCreate(APIModel):
    category: GuidelineCategory
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    sort_order: int = Field(default=0, ge=0, le=10_000)


class GuidelineUpdate(APIModel):
    category: GuidelineCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


class GuidelineOut(APIModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    category: str
    title: str
    content: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ProductFields(APIModel):
    description: str | None = Field(default=None, max_length=5000)
    sku: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.99"), decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    price_unit: str | None = Field(default=None, max_length=50)
    url: HttpUrl | None = None
    features: list[ShortText] | None = Field(default=None, max_length=30)
    image_asset_id: uuid.UUID | None = None


class ProductCreate(ProductFields):
    kind: Literal["product", "service"] = "product"
    name: str = Field(min_length=1, max_length=200)


class ProductUpdate(ProductFields):
    kind: Literal["product", "service"] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "archived"] | None = None


class ProductOut(APIModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    kind: str
    name: str
    description: str | None
    sku: str | None
    price: Decimal | None
    currency: str | None
    price_unit: str | None
    url: str | None

    @field_validator("price")
    @classmethod
    def _two_places(cls, v: Decimal | None) -> Decimal | None:
        # Stored as NUMERIC(20,6) (project money convention); list prices are entered and shown with 2 decimals.
        return v.quantize(Decimal("0.01")) if v is not None else None
    features: list[str]
    image_asset_id: uuid.UUID | None
    image_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class AssetUploadCreate(APIModel):
    brand_id: uuid.UUID
    kind: AssetKind
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=200)
    rights_source: RightsSource = "owned"
    rights_notes: str | None = Field(default=None, max_length=2000)


class UploadTargetOut(APIModel):
    url: str
    method: str
    fields: dict[str, str]
    expires_in: int


class AssetUpdate(APIModel):
    title: str | None = Field(default=None, max_length=200)
    alt_text: str | None = Field(default=None, max_length=500)
    tags: list[Tag] | None = Field(default=None, max_length=20)
    rights_source: RightsSource | None = None
    rights_notes: str | None = Field(default=None, max_length=2000)
    rights_expires_at: datetime | None = None


class AssetOut(APIModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    kind: str
    status: str
    original_filename: str
    mime_type: str | None
    size_bytes: int | None
    checksum_sha256: str | None
    width: int | None
    height: int | None
    title: str | None
    alt_text: str | None
    tags: list[str]
    rights_source: str
    rights_notes: str | None
    rights_expires_at: datetime | None
    rejection_reason: str | None
    url: str | None = None
    created_at: datetime
    completed_at: datetime | None


class AssetUploadOut(APIModel):
    asset: AssetOut
    upload: UploadTargetOut


class AssetRules(APIModel):
    kind: str
    mime_types: list[str]
    extensions: list[str]
    max_bytes: int


class DownloadUrl(APIModel):
    url: str
    expires_in: int
