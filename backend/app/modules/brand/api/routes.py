"""/api/v1/brands, /api/v1/products, /api/v1/assets. The tenant comes from the ``X-Tenant-ID`` header."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.modules.brand.models import BrandAsset, BrandProfile, Product
from app.modules.brand.schemas import (
    AssetKind,
    AssetOut,
    AssetRules,
    AssetUpdate,
    AssetUploadCreate,
    AssetUploadOut,
    BrandCreate,
    BrandOut,
    BrandSummary,
    BrandUpdate,
    DownloadUrl,
    GuidelineCreate,
    GuidelineOut,
    GuidelineUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    UploadTargetOut,
)
from app.modules.brand.services import BrandService
from app.modules.brand.services.assets import AssetService
from app.modules.brand.services.rules import RULES
from app.modules.identity.api.deps import DbSession, Meta
from app.modules.tenant.api.deps import CurrentTenant
from app.modules.tenant.services.context import TenantContext
from app.shared.schemas import Message, Page

router = APIRouter(tags=["brands"])


def _asset(a: BrandAsset, svc: AssetService) -> AssetOut:
    return AssetOut.model_validate(a).model_copy(update={"url": svc.signed_url(a)})


async def _brand_summaries(ctx: TenantContext, db: DbSession, brands: list[BrandProfile]) -> list[BrandSummary]:
    urls = await AssetService(db).urls_for(ctx, [b.logo_asset_id for b in brands])
    return [BrandSummary.model_validate(b).model_copy(update={"logo_url": urls.get(b.logo_asset_id)})  # type: ignore[arg-type]
            for b in brands]


async def _brand_out(ctx: TenantContext, db: DbSession, brand: BrandProfile, counts: dict[str, int]) -> BrandOut:
    urls = await AssetService(db).urls_for(ctx, [brand.logo_asset_id])
    return BrandOut.model_validate(brand).model_copy(
        update={"logo_url": urls.get(brand.logo_asset_id), "counts": counts})  # type: ignore[arg-type]


async def _products(ctx: TenantContext, db: DbSession, products: list[Product]) -> list[ProductOut]:
    urls = await AssetService(db).urls_for(ctx, [p.image_asset_id for p in products])
    return [ProductOut.model_validate(p).model_copy(update={"image_url": urls.get(p.image_asset_id)})  # type: ignore[arg-type]
            for p in products]


# --- brands --------------------------------------------------------------------------------------------------


@router.get("/brands", response_model=list[BrandSummary])
async def list_brands(ctx: CurrentTenant, db: DbSession, include_archived: bool = False) -> list[BrandSummary]:
    return await _brand_summaries(ctx, db, await BrandService(db).list_brands(ctx, include_archived))


@router.post("/brands", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def create_brand(body: BrandCreate, ctx: CurrentTenant, db: DbSession, meta: Meta) -> BrandOut:
    brand = await BrandService(db, meta).create_brand(ctx, body.model_dump(exclude_unset=True))
    return await _brand_out(ctx, db, brand, {"guidelines": 0, "products": 0, "assets": 0})


@router.get("/brands/{brand_id}", response_model=BrandOut)
async def get_brand(brand_id: uuid.UUID, ctx: CurrentTenant, db: DbSession) -> BrandOut:
    brand, counts = await BrandService(db).brand_detail(ctx, brand_id)
    return await _brand_out(ctx, db, brand, counts)


@router.patch("/brands/{brand_id}", response_model=BrandOut)
async def update_brand(brand_id: uuid.UUID, body: BrandUpdate, ctx: CurrentTenant, db: DbSession,
                       meta: Meta) -> BrandOut:
    svc = BrandService(db, meta)
    await svc.update_brand(ctx, brand_id, body.model_dump(exclude_unset=True))
    await db.flush()
    brand, counts = await svc.brand_detail(ctx, brand_id)
    return await _brand_out(ctx, db, brand, counts)


@router.post("/brands/{brand_id}/default", response_model=BrandSummary)
async def make_default(brand_id: uuid.UUID, ctx: CurrentTenant, db: DbSession, meta: Meta) -> BrandSummary:
    brand = await BrandService(db, meta).set_default(ctx, brand_id)
    return (await _brand_summaries(ctx, db, [brand]))[0]


@router.delete("/brands/{brand_id}", response_model=Message)
async def delete_brand(brand_id: uuid.UUID, ctx: CurrentTenant, db: DbSession, meta: Meta) -> Message:
    await BrandService(db, meta).delete_brand(ctx, brand_id)
    return Message(message="Brand deleted")


# --- guidelines ----------------------------------------------------------------------------------------------


@router.get("/brands/{brand_id}/guidelines", response_model=list[GuidelineOut])
async def list_guidelines(brand_id: uuid.UUID, ctx: CurrentTenant, db: DbSession) -> list[GuidelineOut]:
    return [GuidelineOut.model_validate(g) for g in await BrandService(db).list_guidelines(ctx, brand_id)]


@router.post("/brands/{brand_id}/guidelines", response_model=GuidelineOut, status_code=status.HTTP_201_CREATED)
async def create_guideline(brand_id: uuid.UUID, body: GuidelineCreate, ctx: CurrentTenant, db: DbSession,
                           meta: Meta) -> GuidelineOut:
    return GuidelineOut.model_validate(await BrandService(db, meta).create_guideline(ctx, brand_id, body.model_dump()))


@router.patch("/brands/{brand_id}/guidelines/{guideline_id}", response_model=GuidelineOut)
async def update_guideline(brand_id: uuid.UUID, guideline_id: uuid.UUID, body: GuidelineUpdate, ctx: CurrentTenant,
                           db: DbSession, meta: Meta) -> GuidelineOut:
    g = await BrandService(db, meta).update_guideline(ctx, brand_id, guideline_id, body.model_dump(exclude_unset=True))
    return GuidelineOut.model_validate(g)


@router.delete("/brands/{brand_id}/guidelines/{guideline_id}", response_model=Message)
async def delete_guideline(brand_id: uuid.UUID, guideline_id: uuid.UUID, ctx: CurrentTenant, db: DbSession,
                           meta: Meta) -> Message:
    await BrandService(db, meta).delete_guideline(ctx, brand_id, guideline_id)
    return Message(message="Guideline deleted")


# --- products & services -------------------------------------------------------------------------------------


@router.get("/brands/{brand_id}/products", response_model=Page[ProductOut])
async def list_products(brand_id: uuid.UUID, ctx: CurrentTenant, db: DbSession,
                        kind: Literal["product", "service"] | None = None,
                        status_: Literal["active", "archived"] | None = Query(None, alias="status"),
                        q: str | None = Query(None, max_length=100), limit: int = Query(50, ge=1, le=200),
                        offset: int = Query(0, ge=0)) -> Page[ProductOut]:
    rows, total = await BrandService(db).list_products(ctx, brand_id, kind=kind, status=status_, q=q, limit=limit,
                                                       offset=offset)
    return Page(items=await _products(ctx, db, rows), total=total, limit=limit, offset=offset)


@router.post("/brands/{brand_id}/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(brand_id: uuid.UUID, body: ProductCreate, ctx: CurrentTenant, db: DbSession,
                         meta: Meta) -> ProductOut:
    p = await BrandService(db, meta).create_product(ctx, brand_id, body.model_dump(exclude_unset=True))
    return (await _products(ctx, db, [p]))[0]


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, ctx: CurrentTenant, db: DbSession) -> ProductOut:
    ctx.require("brands.read")
    return (await _products(ctx, db, [await BrandService(db).get_product(ctx, product_id)]))[0]


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, body: ProductUpdate, ctx: CurrentTenant, db: DbSession,
                         meta: Meta) -> ProductOut:
    p = await BrandService(db, meta).update_product(ctx, product_id, body.model_dump(exclude_unset=True))
    return (await _products(ctx, db, [p]))[0]


@router.delete("/products/{product_id}", response_model=Message)
async def delete_product(product_id: uuid.UUID, ctx: CurrentTenant, db: DbSession, meta: Meta) -> Message:
    await BrandService(db, meta).delete_product(ctx, product_id)
    return Message(message="Product deleted")


# --- assets --------------------------------------------------------------------------------------------------


@router.get("/assets/rules", response_model=list[AssetRules])
async def asset_rules() -> list[AssetRules]:
    """What each asset kind accepts, so the UI can validate before uploading."""
    return [AssetRules(kind=k, mime_types=sorted(r.mime_types), extensions=sorted(r.extensions),
                       max_bytes=r.max_bytes) for k, r in RULES.items()]


@router.get("/brands/{brand_id}/assets", response_model=Page[AssetOut])
async def list_assets(brand_id: uuid.UUID, ctx: CurrentTenant, db: DbSession, kind: AssetKind | None = None,
                      status_: Literal["ready", "pending", "rejected"] | None = Query(None, alias="status"),
                      limit: int = Query(60, ge=1, le=200), offset: int = Query(0, ge=0)) -> Page[AssetOut]:
    svc = AssetService(db)
    rows, total = await svc.list_assets(ctx, brand_id, kind=kind, status=status_, limit=limit, offset=offset)
    return Page(items=[_asset(a, svc) for a in rows], total=total, limit=limit, offset=offset)


@router.post("/assets/uploads", response_model=AssetUploadOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(limiter("asset_upload", limit=120, window_seconds=3600))])
async def start_upload(body: AssetUploadCreate, ctx: CurrentTenant, db: DbSession, meta: Meta) -> AssetUploadOut:
    """Create a pending asset and return a signed form to post the file directly to storage."""
    svc = AssetService(db, meta)
    asset, target = await svc.start_upload(ctx, body.model_dump())
    return AssetUploadOut(asset=_asset(asset, svc), upload=UploadTargetOut(
        url=target.url, method=target.method, fields=target.fields, expires_in=target.expires_in))


@router.post("/assets/{asset_id}/complete", response_model=AssetOut)
async def complete_upload(asset_id: uuid.UUID, ctx: CurrentTenant, db: DbSession, meta: Meta) -> AssetOut:
    """Verify the uploaded file. Returns the asset with status ``ready`` or ``rejected`` (with a reason)."""
    svc = AssetService(db, meta)
    return _asset(await svc.complete_upload(ctx, asset_id), svc)


@router.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: uuid.UUID, ctx: CurrentTenant, db: DbSession) -> AssetOut:
    ctx.require("brands.read")
    svc = AssetService(db)
    return _asset(await svc.get_asset(ctx, asset_id), svc)


@router.patch("/assets/{asset_id}", response_model=AssetOut)
async def update_asset(asset_id: uuid.UUID, body: AssetUpdate, ctx: CurrentTenant, db: DbSession,
                       meta: Meta) -> AssetOut:
    svc = AssetService(db, meta)
    return _asset(await svc.update_asset(ctx, asset_id, body.model_dump(exclude_unset=True)), svc)


@router.delete("/assets/{asset_id}", response_model=Message)
async def delete_asset(asset_id: uuid.UUID, ctx: CurrentTenant, db: DbSession, meta: Meta) -> Message:
    await AssetService(db, meta).delete_asset(ctx, asset_id)
    return Message(message="Asset deleted")


@router.get("/assets/{asset_id}/download", response_model=DownloadUrl)
async def download_asset(asset_id: uuid.UUID, ctx: CurrentTenant, db: DbSession) -> DownloadUrl:
    url = await AssetService(db).download_url(ctx, asset_id)
    return DownloadUrl(url=url, expires_in=get_settings().storage_download_url_ttl_seconds)
