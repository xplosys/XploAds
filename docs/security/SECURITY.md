# Security Architecture

Status column: ✅ implemented in Phase 1 · 🔜 designed, arrives with the module that needs it.

## 1. Identity and sessions

| Control | Status | Implementation |
|---|---|---|
| Password hashing | ✅ | Argon2id (m=19 MiB, t=2, p=1), transparent rehash on login (`app/core/security.py`). |
| Password policy | ✅ | 10–128 chars, not trivially repetitive, must not contain the email local part. |
| Account enumeration | ✅ | Identical errors for unknown user / wrong password; forgot-password always returns 202; dummy hash equalizes timing. |
| Brute force | ✅ | Redis rate limits (per IP and per email) + account lockout after 10 failures for 15 min + Nginx `limit_req` on `/api/v1/auth/`. |
| Access tokens | ✅ | HS256 JWT, 15 min, `iss`/`aud`/`exp`/`sid` required; each request re-checks the server-side session (logout is immediate). |
| Refresh tokens | ✅ | Opaque, HMAC-hashed at rest, HttpOnly + Secure + SameSite=Strict cookie scoped to `/api/v1/auth`; rotated on each use; replay after the 20 s multi-tab grace window revokes the session. |
| Token storage in browser | ✅ | Access token only in memory; nothing in `localStorage`/`sessionStorage` except the non-secret active org id. |
| CSRF | ✅ | API uses `Authorization: Bearer` (not cookies) for state-changing calls; the only cookie-authenticated endpoint (`/auth/refresh`) is SameSite=Strict and path-scoped. |
| MFA | ✅ | TOTP (RFC 6238, ±1 step), envelope-encrypted secret, 10 hashed single-use recovery codes, short-lived single-use login challenge. |
| Email verification / reset | ✅ | Single-use HMAC-hashed tokens (48 h / 30 min); reset revokes all sessions; change-password revokes other sessions. |
| OAuth login | 🔜 | Google / Facebook login (decision D9). |

## 2. Multi-tenant isolation

| Control | Status | Implementation |
|---|---|---|
| Tenant context | ✅ | Derived only from verified membership (or audited agency access). Foreign / unknown tenants return 404. |
| PostgreSQL RLS | ✅ | `ENABLE` + `FORCE` RLS on all tenant-owned tables; policies use transaction-local `app.tenant_id` / `app.user_id`. |
| Least-privilege DB role | ✅ | API/workers connect as `xploads_app` (NOSUPERUSER, NOBYPASSRLS, not owner). Tested in `tests/test_isolation.py`. |
| Composite tenant FKs | ✅ | e.g. `user_roles (membership_id, tenant_id, user_id)` and `(workspace_id, tenant_id)` — rows cannot reference another tenant's records. |
| Cross-tenant tests | ✅ | API-level (reads, writes, cross-referenced ids) and DB-level (no context → 0 rows, foreign writes rejected). |
| Tenant-scoped storage / cache / jobs | ✅ design · 🔜 code | Keys `tenants/{tenant_id}/…`, `t:{tenant_id}:…`; jobs carry `tenant_id` and re-establish context. |

## 3. Authorization

- RBAC with permission codes (`app/modules/tenant/permissions/catalog.py`), checked in services via
  `TenantContext.require()` — never in the frontend alone, never in prompts.
- Owner safeguards: at least one owner; only owners grant/remove owner.
- No privilege escalation through custom roles (cannot grant permissions you do not hold).
- Platform admin (`users.is_platform_admin`) is separate from tenant roles; granted only via CLI.
- Financially consequential actions (`campaigns.publish`, `campaigns.budget`, `billing.manage`) are distinct
  permissions so they can be restricted independently. 🔜 Approval workflow in Phase 5.

## 4. Data protection

| Control | Status | Implementation |
|---|---|---|
| Secret encryption | ✅ | AES-256-GCM envelope encryption: per-secret data key wrapped by a KEK from `DATA_ENCRYPTION_KEY` (outside the DB), AAD binds ciphertext to its owner. Move the KEK to a KMS/secret manager in production. |
| Log redaction | ✅ | structlog processor redacts keys matching password/secret/token/cookie/api key/otp. |
| Outbox payload hygiene | ✅ | One-time links/tokens are purged from outbox rows after delivery. |
| Audit trail | ✅ | `audit_logs` append-only for the app role (no UPDATE/DELETE grant). |
| Error hygiene | ✅ | Consistent envelope; 500s never leak internals; request id for support. |
| Security headers | ✅ | nosniff, frame DENY, referrer policy, permissions policy; HSTS once TLS is enabled. |
| Request limits | ✅ | Body size limit (FastAPI middleware 1 MiB, Nginx 2 MiB). |
| Prod config guard | ✅ | API refuses to start in staging/production with dev JWT secret/KEK, insecure cookies or console email. |
| Upload validation, SSRF guard, webhook signatures, OAuth state | 🔜 | Phases 2 and 5 (designs in ARCHITECTURE §9–10). |
| GDPR / DPDP: export, deletion, retention, consent | 🔜 | Phase 6 (decision D7). |

## 5. AI-specific controls (designed, Phases 3–4)

Untrusted-content delimiting; tool allowlists per agent version; JSON-schema validation of outputs; authorization in
services, not prompts; no secrets in prompts or run history; agents can only create proposals that humans approve;
BYOK never silently falls back to platform credentials.

## 6. Reporting

Report suspected vulnerabilities privately to the Xplosys security contact (to be defined before launch).
