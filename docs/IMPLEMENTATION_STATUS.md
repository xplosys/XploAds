# Implementation Status

Legend: ✅ implemented and tested · 🧪 mock/dev-only · 🔜 planned (see ROADMAP) · ⚠️ needs external setup

| Phase | Status |
|---|---|
| 1 Foundation | ✅ Complete (milestones M1.1–M1.7 below) |
| 2 Business & Brand | 🔜 Next |
| 3–9 | 🔜 Planned |

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
