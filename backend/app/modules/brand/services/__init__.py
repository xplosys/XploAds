"""Brand kit: brand profiles, guidelines, products and services.

Every query is filtered by the active tenant explicitly *and* by RLS. Foreign or missing ids return 404.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.errors import AppError, Conflict, NotFound
from app.modules.brand.models import BrandAsset, BrandGuideline, BrandProfile, Product
from app.modules.tenant.services.context import TenantContext
from app.shared.audit import RequestMeta, record_audit
from app.shared.outbox import enqueue_event

STORAGE_DELETE_EVENT = "storage.object_delete_requested"


def slugify(value: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:max_len].strip("-")
    return slug or "brand"


def to_db(data: dict[str, Any]) -> dict[str, Any]:
    """Pydantic output -> column values (URLs to str, nested models to plain JSON)."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k in ("website", "url") and v is not None:
            v = str(v)
        elif k == "social_links" and v is not None:
            v = {p: str(u) for p, u in v.items()}
        elif k in ("description", "tagline", "industry", "tone_of_voice", "target_audience", "sku", "price_unit",
                   "rights_notes", "title", "alt_text") and isinstance(v, str):
            v = v or None
        out[k] = v
    return out


class BrandBase:
    def __init__(self, session: AsyncSession, meta: RequestMeta | None = None):
        self.s = session
        self.meta = meta or RequestMeta()

    async def _audit(self, ctx: TenantContext, action: str, resource_type: str, resource_id: Any,
                     metadata: dict[str, Any] | None = None) -> None:
        md = dict(metadata or {})
        if ctx.access == "agency":
            md["via"] = "agency"
        await record_audit(self.s, action=action, actor_user_id=ctx.user.id, tenant_id=ctx.tenant_id,
                           resource_type=resource_type, resource_id=resource_id, meta=self.meta, metadata=md)

    async def get_brand(self, ctx: TenantContext, brand_id: uuid.UUID) -> BrandProfile:
        brand = (await self.s.execute(select(BrandProfile).where(
            BrandProfile.id == brand_id, BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if brand is None:
            raise NotFound("Brand not found")
        return brand

    async def get_ready_image(self, ctx: TenantContext, brand_id: uuid.UUID, asset_id: uuid.UUID,
                              kinds: tuple[str, ...] = ("logo", "image")) -> BrandAsset:
        asset = (await self.s.execute(select(BrandAsset).where(
            BrandAsset.id == asset_id, BrandAsset.tenant_id == ctx.tenant_id, BrandAsset.brand_id == brand_id,
            BrandAsset.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if asset is None:
            raise NotFound("Asset not found")
        if asset.status != "ready" or asset.kind not in kinds:
            raise AppError("Choose an uploaded logo or image from this brand", code="asset_not_usable")
        return asset


class BrandService(BrandBase):
    # --- brands ---------------------------------------------------------------------------------------------

    async def list_brands(self, ctx: TenantContext, include_archived: bool = False) -> list[BrandProfile]:
        ctx.require("brands.read")
        q = select(BrandProfile).where(BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.deleted_at.is_(None))
        if not include_archived:
            q = q.where(BrandProfile.status == "active")
        return list((await self.s.execute(q.order_by(BrandProfile.is_default.desc(), BrandProfile.name))).scalars())

    async def brand_detail(self, ctx: TenantContext, brand_id: uuid.UUID) -> tuple[BrandProfile, dict[str, int]]:
        ctx.require("brands.read")
        brand = await self.get_brand(ctx, brand_id)
        counts: dict[str, int] = {}
        for name, model in (("guidelines", BrandGuideline), ("products", Product), ("assets", BrandAsset)):
            q = select(func.count()).select_from(model).where(model.tenant_id == ctx.tenant_id,
                                                              model.brand_id == brand.id)
            if model is not BrandGuideline:
                q = q.where(model.deleted_at.is_(None))  # type: ignore[attr-defined]
            if model is BrandAsset:
                q = q.where(BrandAsset.status == "ready")
            counts[name] = (await self.s.execute(q)).scalar_one()
        return brand, counts

    async def create_brand(self, ctx: TenantContext, data: dict[str, Any]) -> BrandProfile:
        ctx.require("brands.manage")
        data = to_db(data)
        base = slugify(data["name"])
        slug, n = base, 1
        while (await self.s.execute(select(BrandProfile.id).where(
                BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.slug == slug,
                BrandProfile.deleted_at.is_(None)))).first():
            n += 1
            slug = f"{base}-{n}"
        has_default = (await self.s.execute(select(BrandProfile.id).where(
            BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.is_default, BrandProfile.deleted_at.is_(None),
        ))).first()
        fields = {k: v for k, v in data.items() if v is not None}
        brand = BrandProfile(id=uuid.uuid4(), tenant_id=ctx.tenant_id, slug=slug, is_default=not has_default,
                             created_by=ctx.user.id, **fields)
        self.s.add(brand)
        await self.s.flush()
        await self._audit(ctx, "brand.created", "brand", brand.id, {"name": brand.name})
        return brand

    async def update_brand(self, ctx: TenantContext, brand_id: uuid.UUID, data: dict[str, Any]) -> BrandProfile:
        ctx.require("brands.manage")
        brand = await self.get_brand(ctx, brand_id)
        data = to_db(data)
        if data.get("logo_asset_id"):
            await self.get_ready_image(ctx, brand.id, data["logo_asset_id"])
        list_fields = {"value_propositions", "colors", "fonts", "social_links"}
        for k, v in data.items():
            if v is None and k in list_fields | {"name", "status"}:
                continue  # these columns are NOT NULL; omit to keep, send [] / {} to clear
            setattr(brand, k, v)
        if brand.status == "archived" and brand.is_default:
            raise AppError("Make another brand the default before archiving this one", code="brand_is_default")
        await self._audit(ctx, "brand.updated", "brand", brand.id, {"fields": sorted(data)})
        return brand

    async def set_default(self, ctx: TenantContext, brand_id: uuid.UUID) -> BrandProfile:
        ctx.require("brands.manage")
        brand = await self.get_brand(ctx, brand_id)
        if brand.status != "active":
            raise AppError("Only an active brand can be the default", code="brand_archived")
        await self.s.execute(update(BrandProfile).where(
            BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.is_default, BrandProfile.id != brand.id,
        ).values(is_default=False))
        await self.s.flush()
        brand.is_default = True
        await self._audit(ctx, "brand.default_changed", "brand", brand.id)
        return brand

    async def delete_brand(self, ctx: TenantContext, brand_id: uuid.UUID) -> None:
        ctx.require("brands.manage")
        brand = await self.get_brand(ctx, brand_id)
        now = utcnow()
        brand.deleted_at, brand.is_default, brand.logo_asset_id = now, False, None
        assets = (await self.s.execute(select(BrandAsset).where(
            BrandAsset.tenant_id == ctx.tenant_id, BrandAsset.brand_id == brand.id, BrandAsset.deleted_at.is_(None),
        ))).scalars()
        for a in assets:
            a.deleted_at = now
            enqueue_event(self.s, STORAGE_DELETE_EVENT, {"key": a.storage_key}, tenant_id=ctx.tenant_id)
        await self.s.execute(update(Product).where(
            Product.tenant_id == ctx.tenant_id, Product.brand_id == brand.id, Product.deleted_at.is_(None),
        ).values(deleted_at=now))
        await self.s.flush()
        # Promote another active brand to default so the tenant keeps one.
        nxt = (await self.s.execute(select(BrandProfile).where(
            BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.deleted_at.is_(None),
            BrandProfile.status == "active").order_by(BrandProfile.created_at).limit(1))).scalar_one_or_none()
        if nxt is not None and not (await self.s.execute(select(BrandProfile.id).where(
                BrandProfile.tenant_id == ctx.tenant_id, BrandProfile.is_default,
                BrandProfile.deleted_at.is_(None)))).first():
            nxt.is_default = True
        await self._audit(ctx, "brand.deleted", "brand", brand.id, {"name": brand.name})

    # --- guidelines -----------------------------------------------------------------------------------------

    async def list_guidelines(self, ctx: TenantContext, brand_id: uuid.UUID) -> list[BrandGuideline]:
        ctx.require("brands.read")
        await self.get_brand(ctx, brand_id)
        q = select(BrandGuideline).where(BrandGuideline.tenant_id == ctx.tenant_id,
                                         BrandGuideline.brand_id == brand_id)
        return list((await self.s.execute(q.order_by(BrandGuideline.sort_order, BrandGuideline.created_at))).scalars())

    async def _guideline(self, ctx: TenantContext, brand_id: uuid.UUID, guideline_id: uuid.UUID) -> BrandGuideline:
        g = (await self.s.execute(select(BrandGuideline).where(
            BrandGuideline.id == guideline_id, BrandGuideline.brand_id == brand_id,
            BrandGuideline.tenant_id == ctx.tenant_id))).scalar_one_or_none()
        if g is None:
            raise NotFound("Guideline not found")
        return g

    async def create_guideline(self, ctx: TenantContext, brand_id: uuid.UUID, data: dict[str, Any]) -> BrandGuideline:
        ctx.require("brands.manage")
        await self.get_brand(ctx, brand_id)
        count = (await self.s.execute(select(func.count()).select_from(BrandGuideline).where(
            BrandGuideline.tenant_id == ctx.tenant_id, BrandGuideline.brand_id == brand_id))).scalar_one()
        if count >= 200:
            raise Conflict("A brand can have at most 200 guidelines", code="limit_reached")
        g = BrandGuideline(id=uuid.uuid4(), tenant_id=ctx.tenant_id, brand_id=brand_id, created_by=ctx.user.id,
                           **data)
        self.s.add(g)
        await self.s.flush()
        await self._audit(ctx, "brand.guideline_created", "brand_guideline", g.id, {"brand_id": str(brand_id)})
        return g

    async def update_guideline(self, ctx: TenantContext, brand_id: uuid.UUID, guideline_id: uuid.UUID,
                               data: dict[str, Any]) -> BrandGuideline:
        ctx.require("brands.manage")
        await self.get_brand(ctx, brand_id)
        g = await self._guideline(ctx, brand_id, guideline_id)
        for k, v in data.items():
            if v is not None:
                setattr(g, k, v)
        await self._audit(ctx, "brand.guideline_updated", "brand_guideline", g.id, {"fields": sorted(data)})
        return g

    async def delete_guideline(self, ctx: TenantContext, brand_id: uuid.UUID, guideline_id: uuid.UUID) -> None:
        ctx.require("brands.manage")
        await self.get_brand(ctx, brand_id)
        g = await self._guideline(ctx, brand_id, guideline_id)
        await self.s.delete(g)
        await self._audit(ctx, "brand.guideline_deleted", "brand_guideline", guideline_id)

    # --- products & services --------------------------------------------------------------------------------

    async def list_products(self, ctx: TenantContext, brand_id: uuid.UUID, *, kind: str | None, status: str | None,
                            q: str | None, limit: int, offset: int) -> tuple[list[Product], int]:
        ctx.require("brands.read")
        await self.get_brand(ctx, brand_id)
        base = select(Product).where(Product.tenant_id == ctx.tenant_id, Product.brand_id == brand_id,
                                     Product.deleted_at.is_(None))
        if kind:
            base = base.where(Product.kind == kind)
        if status:
            base = base.where(Product.status == status)
        if q:
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            base = base.where(Product.name.ilike(pattern, escape="\\") | Product.sku.ilike(pattern, escape="\\"))
        total = (await self.s.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.s.execute(base.order_by(Product.name).limit(limit).offset(offset))).scalars()
        return list(rows), total

    async def get_product(self, ctx: TenantContext, product_id: uuid.UUID) -> Product:
        p = (await self.s.execute(select(Product).where(
            Product.id == product_id, Product.tenant_id == ctx.tenant_id, Product.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if p is None:
            raise NotFound("Product not found")
        return p

    async def _sku_taken(self, ctx: TenantContext, brand_id: uuid.UUID, sku: str | None,
                         exclude: uuid.UUID | None = None) -> bool:
        if not sku:
            return False
        q = select(Product.id).where(Product.tenant_id == ctx.tenant_id, Product.brand_id == brand_id,
                                     Product.sku == sku, Product.deleted_at.is_(None))
        if exclude:
            q = q.where(Product.id != exclude)
        return (await self.s.execute(q)).first() is not None

    @staticmethod
    def _check_price(price: Any, currency: str | None) -> None:
        if price is not None and not currency:
            raise AppError("Choose a currency for the price", code="validation_error",
                           details=[{"loc": ["body", "currency"], "msg": "Choose a currency for the price"}])

    async def create_product(self, ctx: TenantContext, brand_id: uuid.UUID, data: dict[str, Any]) -> Product:
        ctx.require("brands.manage")
        brand = await self.get_brand(ctx, brand_id)
        data = to_db(data)
        if data.get("price") is not None and not data.get("currency"):
            data["currency"] = ctx.tenant.default_currency
        self._check_price(data.get("price"), data.get("currency"))
        if data.get("image_asset_id"):
            await self.get_ready_image(ctx, brand.id, data["image_asset_id"])
        if await self._sku_taken(ctx, brand.id, data.get("sku")):
            raise Conflict("Another product in this brand already uses that SKU", code="sku_taken")
        fields = {k: v for k, v in data.items() if v is not None}
        p = Product(id=uuid.uuid4(), tenant_id=ctx.tenant_id, brand_id=brand.id, created_by=ctx.user.id, **fields)
        self.s.add(p)
        await self.s.flush()
        await self._audit(ctx, "product.created", "product", p.id, {"brand_id": str(brand.id), "kind": p.kind})
        return p

    async def update_product(self, ctx: TenantContext, product_id: uuid.UUID, data: dict[str, Any]) -> Product:
        ctx.require("brands.manage")
        p = await self.get_product(ctx, product_id)
        data = to_db(data)
        if data.get("image_asset_id"):
            await self.get_ready_image(ctx, p.brand_id, data["image_asset_id"])
        if "sku" in data and await self._sku_taken(ctx, p.brand_id, data["sku"], exclude=p.id):
            raise Conflict("Another product in this brand already uses that SKU", code="sku_taken")
        for k, v in data.items():
            if v is None and k in ("name", "kind", "status", "features"):
                continue
            setattr(p, k, v)
        if p.price is not None and not p.currency:
            p.currency = ctx.tenant.default_currency
        await self._audit(ctx, "product.updated", "product", p.id, {"fields": sorted(data)})
        return p

    async def delete_product(self, ctx: TenantContext, product_id: uuid.UUID) -> None:
        ctx.require("brands.manage")
        p = await self.get_product(ctx, product_id)
        p.deleted_at = utcnow()
        await self._audit(ctx, "product.deleted", "product", p.id, {"name": p.name})
