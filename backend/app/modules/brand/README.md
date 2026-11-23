# `brand` module — implemented (Phase 2)

Brand kits: profiles, guidelines, products and services, and the brand asset library.

| | |
|---|---|
| Owns tables | `brand_profiles`, `brand_guidelines`, `products`, `brand_assets` (migration `0002_business_brand`) |
| API | `/api/v1/brands/*`, `/api/v1/products/*`, `/api/v1/assets/*` (tenant from `X-Tenant-ID`) |
| Permissions | `brands.read`, `brands.manage` |
| Events emitted | `storage.object_delete_requested` (outbox; handled in `app/workers/handlers.py`) |
| Jobs | `brand.cleanup_stale_uploads` (Celery beat, hourly) |
| Depends on | `app.core`, `app.shared` (storage, files, audit, outbox), `app.modules.tenant` (tenant context) |

Key rules
- Every query filters by the active tenant and runs under RLS; composite `(tenant_id, …)` foreign keys stop
  cross-tenant references even for the owner role. Foreign ids return 404.
- One default brand per tenant; the default cannot be archived. Deleting a brand soft-deletes its products and
  assets and queues the objects for deletion.
- Uploads: `services/rules.py` lists each kind's extensions, MIME types and size limit. Files go straight to storage
  with a signed policy; `complete_upload` verifies size, magic bytes and (for images) a full decode before the asset
  becomes `ready`. SVG is not accepted.
- Product prices are NUMERIC(20,6) with a currency (defaults to the organization's); SKU is unique per brand.

Public interface for later phases (creative studio, campaigns): `BrandService.get_brand`, `BrandBase.get_ready_image`,
`AssetService.signed_url`.
