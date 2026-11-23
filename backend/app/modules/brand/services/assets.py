"""Brand asset library: signed direct-to-storage uploads, server-side verification, signed downloads.

Flow
1. ``start_upload`` checks permission, kind, extension and declared size, creates a ``pending`` row with a
   server-generated key under ``tenants/{tenant_id}/brands/{brand_id}/`` and returns a signed upload form whose
   policy pins that key, the content type and the maximum size.
2. The browser posts the file straight to storage.
3. ``complete_upload`` re-reads the object from storage: size within limits, magic bytes on the kind's allowlist,
   images fully decoded (dimensions, decompression-bomb guard), SHA-256 recorded. Anything else is ``rejected``
   and the object is deleted.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import set_rls_context, utcnow
from app.core.errors import AppError, NotFound
from app.modules.brand.models import BrandAsset, BrandProfile, Product
from app.modules.brand.services import STORAGE_DELETE_EVENT, BrandBase, to_db
from app.modules.brand.services.rules import INLINE_PREFIXES, RULES, canonical_type
from app.modules.tenant.services.context import TenantContext
from app.shared.files import SNIFF_BYTES, InvalidImage, inspect_image, sniff_mime
from app.shared.outbox import enqueue_event
from app.shared.storage import Storage, UploadTarget, get_storage, safe_filename, tenant_prefix

MAX_PENDING_PER_TENANT = 50
log = structlog.get_logger("xploads.assets")


class AssetService(BrandBase):
    def __init__(self, session: AsyncSession, meta: Any = None, storage: Storage | None = None):
        super().__init__(session, meta)
        self.storage = storage or get_storage()

    # --- reads ----------------------------------------------------------------------------------------------

    async def get_asset(self, ctx: TenantContext, asset_id: uuid.UUID) -> BrandAsset:
        a = (await self.s.execute(select(BrandAsset).where(
            BrandAsset.id == asset_id, BrandAsset.tenant_id == ctx.tenant_id, BrandAsset.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if a is None:
            raise NotFound("Asset not found")
        return a

    async def list_assets(self, ctx: TenantContext, brand_id: uuid.UUID, *, kind: str | None, status: str | None,
                          limit: int, offset: int) -> tuple[list[BrandAsset], int]:
        ctx.require("brands.read")
        await self.get_brand(ctx, brand_id)
        base = select(BrandAsset).where(BrandAsset.tenant_id == ctx.tenant_id, BrandAsset.brand_id == brand_id,
                                        BrandAsset.deleted_at.is_(None))
        base = base.where(BrandAsset.status == status) if status else base.where(BrandAsset.status == "ready")
        if kind:
            base = base.where(BrandAsset.kind == kind)
        total = (await self.s.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.s.execute(base.order_by(BrandAsset.created_at.desc()).limit(limit).offset(offset)))
        return list(rows.scalars()), total

    def signed_url(self, a: BrandAsset) -> str | None:
        if a.status != "ready" or not a.mime_type:
            return None
        inline = a.mime_type.startswith(INLINE_PREFIXES)
        return self.storage.download_url(a.storage_key, filename=a.original_filename, content_type=a.mime_type,
                                         inline=inline)

    async def urls_for(self, ctx: TenantContext, asset_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
        ids = [i for i in asset_ids if i]
        if not ids:
            return {}
        rows = (await self.s.execute(select(BrandAsset).where(
            BrandAsset.tenant_id == ctx.tenant_id, BrandAsset.id.in_(ids), BrandAsset.deleted_at.is_(None),
        ))).scalars()
        return {a.id: url for a in rows if (url := self.signed_url(a))}

    # --- upload ---------------------------------------------------------------------------------------------

    async def start_upload(self, ctx: TenantContext, data: dict[str, Any]) -> tuple[BrandAsset, UploadTarget]:
        ctx.require("brands.manage")
        brand = await self.get_brand(ctx, data["brand_id"])
        kind = data["kind"]
        rule = RULES[kind]
        filename = data["filename"].strip()
        mime = canonical_type(kind, filename)
        if mime is None:
            allowed = ", ".join(sorted(rule.extensions))
            raise AppError(f"This file type is not allowed for {kind} assets. Allowed: {allowed}",
                           code="file_type_not_allowed", details={"allowed_extensions": sorted(rule.extensions)})
        if data["size_bytes"] > rule.max_bytes:
            raise AppError(f"File is too large. The limit for {kind} assets is {rule.max_bytes // (1024 * 1024)} MB",
                           code="file_too_large", details={"max_bytes": rule.max_bytes}, status_code=413)
        pending = (await self.s.execute(select(func.count()).select_from(BrandAsset).where(
            BrandAsset.tenant_id == ctx.tenant_id, BrandAsset.status == "pending",
            BrandAsset.upload_expires_at > utcnow()))).scalar_one()
        if pending >= MAX_PENDING_PER_TENANT:
            raise AppError("Too many uploads in progress. Wait for them to finish and try again.",
                           code="too_many_pending_uploads", status_code=429)

        asset_id = uuid.uuid4()
        key = f"{tenant_prefix(ctx.tenant_id)}brands/{brand.id}/assets/{asset_id}/{safe_filename(filename)}"
        ttl = get_settings().storage_upload_url_ttl_seconds
        extra = to_db({k: data.get(k) for k in ("title", "rights_notes")})
        asset = BrandAsset(
            id=asset_id, tenant_id=ctx.tenant_id, brand_id=brand.id, kind=kind, status="pending", storage_key=key,
            original_filename=filename[:255], declared_mime_type=data["content_type"][:100],
            rights_source=data.get("rights_source") or "owned", uploaded_by=ctx.user.id,
            upload_expires_at=utcnow() + timedelta(seconds=ttl), tags=[],
            **{k: v for k, v in extra.items() if v is not None},
        )
        self.s.add(asset)
        await self.s.flush()
        target = self.storage.create_upload(key, content_type=mime, max_bytes=rule.max_bytes)
        return asset, target

    async def complete_upload(self, ctx: TenantContext, asset_id: uuid.UUID) -> BrandAsset:
        ctx.require("brands.manage")
        a = await self.get_asset(ctx, asset_id)
        if a.status == "ready":
            return a  # idempotent
        if a.status != "pending":
            raise AppError("This upload was rejected; start a new upload", code="upload_rejected")
        rule = RULES[a.kind]
        info = await self.storage.head(a.storage_key)
        if info is None:
            if a.upload_expires_at < utcnow():
                return await self._reject(ctx, a, "The upload expired before the file arrived")
            raise AppError("The file has not been uploaded yet", code="upload_incomplete")

        reason: str | None = None
        detected: str | None = None
        if info.size <= 0:
            reason = "The file is empty"
        elif info.size > rule.max_bytes:
            reason = "The file is larger than allowed"
        else:
            head = await self.storage.read(a.storage_key, max_bytes=SNIFF_BYTES)
            detected = sniff_mime(head)
            if detected not in rule.mime_types:
                reason = "The file content does not match an allowed type"
        if reason:
            return await self._reject(ctx, a, reason)

        assert detected is not None
        a.mime_type, a.size_bytes = detected, info.size
        if rule.decode_image or rule.hash_content:
            data = await self.storage.read(a.storage_key, max_bytes=rule.max_bytes)
            a.checksum_sha256 = hashlib.sha256(data).hexdigest()
            if rule.decode_image:
                try:
                    img = inspect_image(data)
                except InvalidImage as e:
                    return await self._reject(ctx, a, str(e))
                a.width, a.height = img.width, img.height
        a.status, a.completed_at = "ready", utcnow()
        await self._audit(ctx, "asset.uploaded", "brand_asset", a.id,
                          {"brand_id": str(a.brand_id), "kind": a.kind, "size": a.size_bytes, "mime": a.mime_type})
        return a

    async def _reject(self, ctx: TenantContext, a: BrandAsset, reason: str) -> BrandAsset:
        a.status, a.rejection_reason, a.completed_at = "rejected", reason[:300], utcnow()
        enqueue_event(self.s, STORAGE_DELETE_EVENT, {"key": a.storage_key}, tenant_id=ctx.tenant_id)
        await self._audit(ctx, "asset.rejected", "brand_asset", a.id, {"reason": reason, "kind": a.kind})
        return a

    # --- metadata & delete ----------------------------------------------------------------------------------

    async def update_asset(self, ctx: TenantContext, asset_id: uuid.UUID, data: dict[str, Any]) -> BrandAsset:
        ctx.require("brands.manage")
        a = await self.get_asset(ctx, asset_id)
        data = to_db(data)
        if "tags" in data and data["tags"] is not None:
            data["tags"] = sorted({t.strip().lower() for t in data["tags"] if t.strip()})
        for k, v in data.items():
            if v is None and k in ("tags", "rights_source"):
                continue
            setattr(a, k, v)
        await self._audit(ctx, "asset.updated", "brand_asset", a.id, {"fields": sorted(data)})
        return a

    async def delete_asset(self, ctx: TenantContext, asset_id: uuid.UUID) -> None:
        ctx.require("brands.manage")
        a = await self.get_asset(ctx, asset_id)
        a.deleted_at = utcnow()
        for model, col in ((BrandProfile, BrandProfile.logo_asset_id), (Product, Product.image_asset_id)):
            rows = (await self.s.execute(select(model).where(
                model.tenant_id == ctx.tenant_id, col == a.id))).scalars()  # type: ignore[attr-defined]
            for r in rows:
                setattr(r, col.key, None)
        enqueue_event(self.s, STORAGE_DELETE_EVENT, {"key": a.storage_key}, tenant_id=ctx.tenant_id)
        await self._audit(ctx, "asset.deleted", "brand_asset", a.id, {"filename": a.original_filename})

    async def download_url(self, ctx: TenantContext, asset_id: uuid.UUID) -> str:
        ctx.require("brands.read")
        a = await self.get_asset(ctx, asset_id)
        url = self.signed_url(a)
        if url is None:
            raise AppError("This asset is not available for download", code="asset_not_ready")
        return url


async def cleanup_stale_uploads(session: AsyncSession, storage: Storage | None = None, batch: int = 200) -> int:
    """Reject uploads that never completed and remove any partial object. Runs from Celery beat.

    The cross-tenant lookup goes through a narrow SECURITY DEFINER function; each update runs under that tenant's
    RLS context.
    """
    from sqlalchemy import text

    storage = storage or get_storage()
    rows = (await session.execute(text("SELECT id, tenant_id, storage_key FROM stale_pending_assets(:n)"),
                                  {"n": batch})).all()
    for asset_id, tenant_id, key in rows:
        try:
            await storage.delete(key)
        except Exception:  # noqa: BLE001 - storage outage: leave the row for the next run
            log.warning("asset_cleanup_delete_failed", asset_id=str(asset_id), exc_info=True)
            continue
        await set_rls_context(session, tenant_id=tenant_id)
        a = (await session.execute(select(BrandAsset).where(BrandAsset.id == asset_id))).scalar_one_or_none()
        if a is not None and a.status == "pending":
            a.status, a.rejection_reason, a.deleted_at = "rejected", "Upload expired", utcnow()
    await session.flush()
    return len(rows)
