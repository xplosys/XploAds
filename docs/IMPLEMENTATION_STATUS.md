# Implementation Status

Legend: ✅ implemented and tested · 🧪 mock/dev-only · 🔜 planned (see ROADMAP) · ⚠️ needs external setup

| Phase | Status |
|---|---|
| 1 Foundation | ✅ Complete (milestones M1.1–M1.7 below) |
| 2 Business & Brand | ✅ Complete (milestones M2.1–M2.5 below) |
| 3 AI Infrastructure | 🔜 Next |
| 4–9 | 🔜 Planned |

---

## Milestone: Phase 2 — Business & Brand (2026-11-23)

### 1. What has been implemented

- **Organization profile:** description, contact email, contact phone and address on top of the Phase 1 settings.
- **Brand profiles:** several brands per organization with one default; tagline, description, industry, website,
  tone of voice, target audience, value propositions, colour palette (hex + usage), fonts, social links, logo;
  archive, make default, delete.
- **Brand guidelines:** categorised rules (voice, visual, messaging, do, don't, legal, other) with ordering.
- **Products & services:** kind, SKU (unique per brand), NUMERIC price with currency and unit, product URL,
  benefits list, image, archive; search and filters with pagination.
- **Asset library:** logos, images, videos, documents (PDF) and fonts. Direct-to-storage uploads with signed
  policies; server-side verification by magic bytes, size and full image decode (dimensions, SHA-256); rejected
  files are deleted; usage-rights metadata (source, notes, expiry), title, alt text and tags; signed downloads;
  hourly cleanup of abandoned uploads.
- **Object storage:** provider-neutral S3 adapter (Cloudflare R2, AWS S3, SeaweedFS, MinIO) plus a local
  development backend with HMAC-signed URLs. Docker Compose now runs SeaweedFS and creates the bucket.
- **Agency UX:** client organizations show a "Back to {agency}" link; agency staff manage client brand kits with
  `via: agency` audit entries; the organization switcher already groups agency clients.
- **Dark mode (added on request):** a single moon/sun button in the app sidebar, on sign-in pages and on the
  landing page; follows the OS setting until clicked, then remembered per browser, applied before first paint (no
  flash) and synced across tabs. Dark tokens in `app/globals.css`; logic in `features/theme/theme.tsx`.
- **Frontend:** Brands list, brand workspace with Profile / Guidelines / Products & services / Assets tabs,
  drag-and-drop uploader with progress and per-file results, asset detail dialog, organization profile fields,
  "Create your brand kit" onboarding step on the dashboard.

### 2. Files created or modified

- Backend new: `app/modules/brand/{models,schemas,services/__init__.py,services/assets.py,services/rules.py,api/routes.py}`,
  `app/shared/{storage.py,storage_routes.py,files.py}`, `alembic/versions/0002_business_brand.py`,
  `tests/{test_brand.py,test_assets.py}`.
- Backend modified: `app/core/config.py` (storage settings, production guard), `app/main.py` (routers, upload body
  limit), `app/cli.py` (`ensure-storage`), `app/workers/{handlers.py,celery_app.py}` (object deletion, cleanup job),
  `app/modules/tenant/{models,schemas,services}` (organization profile fields), `tests/conftest.py`,
  `requirements/{base,dev}.txt` (boto3, python-multipart, Pillow, moto).
- Frontend new: `app/app/[orgId]/brands/**` (list, layout, profile, guidelines, products, assets),
  `features/brands/{api.ts,components.tsx}`, `e2e/brand.spec.ts`, `e2e/fixtures/*`.
- Frontend modified: `components/app-shell.tsx`, `app/app/[orgId]/{page,settings/page}.tsx`, `types/api.ts`.
- Platform/docs: `docker-compose.yml` (storage service, migrate creates the bucket), `.env.example`, `README.md`,
  `docs/{api/API.md,database/SCHEMA.md,security/SECURITY.md,deployment/*,architecture/{ROADMAP,RISKS_AND_DECISIONS}.md}`,
  `backend/app/modules/brand/README.md`.

### 3. Database changes

Migration `0002_business_brand` (reversible): adds `tenants.{description,contact_email,contact_phone,address}`;
creates `brand_profiles`, `brand_guidelines`, `products`, `brand_assets` with RLS ENABLE + FORCE, tenant
isolation policies, `updated_at` triggers, composite `(tenant_id, …)` foreign keys, partial unique indexes (slug,
single default brand, SKU), CHECK constraints (status, kind, rights, JSON shapes, non-negative price, storage key
under the tenant prefix) and the `stale_pending_assets()` security-definer function for the cleanup job. Upgrade,
downgrade and re-upgrade verified.

### 4. APIs created

23 endpoints: brands (6), guidelines (4), products (5), assets (8, incl. `/assets/rules`, `/assets/uploads`,
`/assets/{id}/complete`, `/assets/{id}/download`); `PATCH /organizations/{id}` accepts the new profile fields.
Local-backend-only signed endpoints under `/storage/local/*`. Reference: `docs/api/API.md`.

### 5. Tests executed and results

| Suite | Result |
|---|---|
| Backend pytest against PostgreSQL 16 + Redis: Phase 1 (42) + brand (14) + assets (8) | **64 passed** |
| Ruff lint (backend incl. migrations) | passed |
| ESLint + TypeScript type-check + `next build` | passed |
| Playwright E2E on the full Docker Compose stack through Nginx (Phase 1 flow + brand-kit flow: profile, guideline, logo upload to SeaweedFS, spoofed file rejected, signed image served, logo set, priced service + dark-mode toggle/persistence/system preference) | **3 passed** |
| Docker Compose stack (8 services incl. storage) | all running; worker processed the storage-deletion events |
| S3 path | presigned POST policy (key, type, size), CORS and signed GET verified against SeaweedFS; unit test against moto |

New coverage: CRUD and validation, default/archive rules, SKU conflicts, literal search, permissions for viewer,
member, manager, sales and billing admin, foreign-tenant access through header and through own tenant (404), RLS
on all new tables, composite FK blocks cross-tenant links even as owner, agency audit trail, tampered/expired upload
policies and download links, wrong content type, oversize and empty files, spoofed and truncated images, stale
upload cleanup, worker refuses to delete outside the tenant prefix.

### 6. Security considerations

See `docs/security/SECURITY.md` §4a. Signed, expiring upload policies pin key, type and size; keys are server
generated under the tenant prefix (enforced by a CHECK); content is verified by magic bytes and full image decode;
SVG refused; private bucket with 5-minute signed downloads; per-tenant pending-upload cap and per-user upload rate
limit; production refuses `STORAGE_BACKEND=local` and the example storage secret.

### 7. Configuration required

- Local Docker: nothing new beyond `.env` (new keys are in `.env.example`); port **8333** must be free for
  signed upload/download URLs. Existing `.env` files need the new `S3_*` / `STORAGE_*` lines from `.env.example`.
- Production: a private R2 or S3 bucket, a scoped access key, bucket CORS for the app origin, and the `S3_*`
  variables (`docs/deployment/DEPLOYMENT.md`). ⚠️ Decision D11.

### 8. Known limitations

- No malware scanning for PDFs and videos yet (decision D12); videos are type-checked but not probed (FFmpeg arrives
  in Phase 4).
- Workspace-scoped permissions are still stored but not enforced; brands are organization-wide. Enforcement moves to
  Phases 4–5 when creatives and campaigns belong to workspaces.
- No image thumbnails/resizing; the library shows originals through signed URLs.
- The bundled SeaweedFS is meant for local use; production should use R2/S3 or SeaweedFS behind TLS.
- Asset upload verification runs inside the request (fine up to the 20–25 MB image/document limits); large-scale
  use should move it to a worker.
- Docker images in the sandbox were again built with an injected proxy CA; the committed Dockerfiles are unchanged.

### 9. Next milestone

**Phase 3 — AI Infrastructure:** provider registry and models, versioned pricing, envelope-encrypted credentials
(platform and BYOK), tenant provider configuration, the AI Gateway (reservation → execution → settlement), usage
events and costs, wallet and double-entry ledger skeleton, budgets and concurrency limits. Needs test API keys for
Gemini / OpenAI / DeepSeek (or mock mode first) and decisions D2 (currency/tax) and D4 (allowances).

---

## Milestone: Phase 1 — Foundation (2026-11-22)

### 1. What has been implemented

- **Architecture package:** technical architecture, roadmap with dependencies, ER diagrams and schema design for all
  phases, repository structure, risks / open decisions / external dependencies / third-party costs.
- **Identity:** registration, email verification, login with lockout, TOTP MFA with recovery codes, refresh-token
  rotation with reuse detection, logout, password reset and change, profile, session list/revoke.
- **Tenancy & RBAC:** business, agency and enterprise organizations; agency client organizations (isolated child
  tenants with audited agency access); workspaces; members; email-bound invitations; 7 system roles + custom roles
  (no privilege escalation); 34-permission catalog covering all planned modules; last-owner protection.
- **Multi-tenant isolation:** PostgreSQL RLS (ENABLE + FORCE) with a non-owner `NOBYPASSRLS` runtime role,
  transaction-local tenant context derived from membership, composite tenant foreign keys.
- **Audit:** append-only `audit_logs` (app role cannot update/delete), API with pagination and filtering.
- **Async foundation:** Celery app with all planned queues, transactional outbox with retry/backoff/dead-letter,
  email notifications (verification, reset, invitation) through the outbox.
- **Frontend:** landing page, sign-in (incl. MFA step), registration, forgot/reset password, email verification,
  invitation accept, onboarding (business/agency/enterprise), app shell with organization switcher, dashboard,
  team & invitations, workspaces, agency clients, organization settings, audit log, account & security
  (profile, MFA setup with QR, password, sessions). Loading, empty, error and confirmation states throughout.
- **Platform:** Dockerfiles (API/workers, web), Docker Compose (postgres, redis, migrate, api, worker, beat, web,
  nginx), Nginx reverse proxy with auth rate limiting and JSON logs, production overrides, CI workflow.

### 2. Files created or modified

New repository. Main areas: `backend/app/{core,shared,modules/identity,modules/tenant,workers}`,
`backend/alembic/versions/0001_foundation_identity_tenancy.py`, `backend/tests/*`, `frontend/{app,components,features,
services,hooks,types,e2e}`, `infrastructure/{docker,nginx,monitoring}`, `docs/**`, `docker-compose*.yml`,
`.env.example`, `.github/workflows/ci.yml`. Planned modules contain a README only.

### 3. Database changes

Migration `0001_foundation`: `users`, `sessions`, `auth_tokens`, `mfa_recovery_codes`, `tenants`, `workspaces`,
`permissions`, `roles`, `role_permissions`, `tenant_users`, `user_roles`, `invitations`, `audit_logs`,
`outbox_events`; RLS helper functions and policies; `updated_at` triggers; grants for `xploads_app`; seeded
permission catalog and system roles.

### 4. APIs created

`/api/v1/auth/*` (17 endpoints), `/api/v1/organizations/*` (19 endpoints), `/api/v1/invitations/{preview,accept}`,
`/api/v1/permissions`, `/health/{live,ready}`. Reference: `docs/api/API.md`.

### 5. Tests executed and results

| Suite | Result |
|---|---|
| Backend pytest against PostgreSQL 16 + Redis (auth 13, tenancy 8, isolation 15, platform 6) | **42 passed** |
| Ruff lint (backend) | passed |
| ESLint + TypeScript type-check (frontend) | passed |
| `next build` (production) | passed |
| Playwright E2E — register → agency onboarding → add client → agency access → workspace → sign out/in → reload session | **passed** against `next start` and against the full Docker Compose stack through Nginx |
| Docker Compose stack (7 services) | all healthy; outbox → Celery worker delivered the verification email |

Isolation tests cover: foreign-tenant reads/writes via API (404), cross-referenced ids, foreign workspace in
invitations, app role attributes (not superuser, no BYPASSRLS, owns no tables, RLS forced), zero rows without
context, blocked cross-tenant UPDATE/INSERT, append-only audit log, immutable system roles and permissions.

### 6. Security considerations

See `docs/security/SECURITY.md`. Notable: Argon2id; in-memory access tokens; HttpOnly/SameSite=Strict rotating
refresh cookie; MFA secrets envelope-encrypted; one-time tokens hashed and single-use; log redaction; outbox purges
one-time links after delivery; production boot guard against dev secrets.

### 7. Configuration required

- Local: none beyond `cp .env.example .env` (Docker) or the role setup in `docs/deployment/DEPLOYMENT.md` (host).
- Staging/production: strong secrets, `DATA_ENCRYPTION_KEY`, `COOKIE_SECURE=true`, SMTP provider (⚠️ decision D10),
  domain + TLS, Sentry DSN.

### 8. Known limitations

- Emails are printed by the worker in `console` mode; a real provider must be configured before external users.
- KEK comes from an environment variable; move to a KMS/secret manager before storing third-party credentials.
- Workspace-scoped role assignments are stored and validated but do not yet narrow permissions (used from Phase 2).
- No organization deletion/closure, data export or account deletion yet (Phase 6 privacy work, decision D7).
- No super-admin portal yet (Phase 9); platform admins are created via `python -m app.cli make-platform-admin`.
- No Prometheus metrics yet (Phase 9). OAuth (Google/Facebook) login not implemented (decision D9).
- Docker images were built and run in the development sandbox with an injected proxy CA (sandbox-specific); the
  committed Dockerfiles contain no such workaround and build normally on a standard network.

### 9. Next milestone

**Phase 2 — Business & Brand:** organization settings polish, agency client workspace UX, brand profiles and
guidelines, products and services (NUMERIC prices), brand asset upload to S3/R2 with tenant prefixes, signed URLs,
type/size validation; workspace-scoped permissions. Needs: object-storage bucket and decisions D1 (confirm), D9.
