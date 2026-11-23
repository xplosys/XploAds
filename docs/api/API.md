# API Reference (v1)

Interactive OpenAPI docs: `http://localhost:8000/api/docs` (disabled when `ENVIRONMENT=production`).

## Conventions

- Base path `/api/v1`, JSON, UTC ISO-8601 timestamps, UUID ids.
- Auth: `Authorization: Bearer <access_token>`. Refresh via the HttpOnly cookie on `POST /auth/refresh`.
- Tenant: organization routes take it from the path (`/organizations/{org_id}/…`); later modules use `X-Tenant-ID`.
  Membership is always verified server-side.
- Errors: `{"error": {"code", "message", "request_id", "details"}}`. Every response carries `X-Request-ID`.
- Pagination: `limit` (≤200) and `offset`; paged responses return `{items, total, limit, offset}`.
- Rate limits: auth endpoints are limited per IP and per email/user (429 `rate_limited`).

## Auth — `/api/v1/auth`

| Method | Path | Notes |
|---|---|---|
| POST | `/register` | `{email, password, full_name}` → 201 `{access_token, expires_in}` + refresh cookie; sends verification email |
| POST | `/login` | `{email, password}` → tokens, or `{mfa_required: true, mfa_token}` |
| POST | `/mfa/verify` | `{mfa_token, code}` (TOTP or recovery code) → tokens |
| POST | `/refresh` | Uses cookie; rotates it → tokens. `refresh_conflict` = retry (another tab refreshed) |
| POST | `/logout` | Revokes the session, clears cookie |
| GET / PATCH | `/me` | Current user / update `full_name` |
| POST | `/verify-email` | `{token}` |
| POST | `/resend-verification` | Authenticated |
| POST | `/forgot-password` | `{email}` → always 202 |
| POST | `/reset-password` | `{token, new_password}`; revokes all sessions |
| POST | `/change-password` | `{current_password, new_password}`; revokes other sessions |
| POST | `/mfa/setup` | → `{secret, otpauth_uri}` |
| POST | `/mfa/enable` | `{code}` → `{recovery_codes}` (shown once) |
| POST | `/mfa/disable` | `{password, code}` |
| GET | `/sessions` | Active sessions (`current` flag) |
| DELETE | `/sessions/{id}` | Revoke one session |

## Organizations — `/api/v1`

| Method | Path | Permission |
|---|---|---|
| GET | `/organizations` | — (lists own memberships + accessible agency clients, with roles and permissions) |
| POST | `/organizations` | — `{name, tenant_type: business|agency|enterprise, industry?, website?, country_code?, timezone?, default_currency?}`; caller becomes owner |
| GET | `/organizations/{id}` | `organization.read` |
| PATCH | `/organizations/{id}` | `organization.update` |
| GET / POST | `/organizations/{id}/clients` | `agency.clients.access` / `agency.clients.create` (agency tenants only) |
| GET / POST | `/organizations/{id}/workspaces` | `workspaces.read` / `workspaces.manage` |
| PATCH | `/organizations/{id}/workspaces/{wid}` | `workspaces.manage` |
| GET | `/organizations/{id}/members` | `members.read` |
| POST | `/organizations/{id}/members` | `members.invite` + verified email — `{email, role_key, workspace_id?}` creates an invitation |
| PUT | `/organizations/{id}/members/{mid}/roles` | `members.manage` — `{roles: [{role_key, workspace_id?}]}` |
| DELETE | `/organizations/{id}/members/{mid}` | `members.manage` (or self, to leave) |
| GET | `/organizations/{id}/invitations` | `members.read` |
| DELETE | `/organizations/{id}/invitations/{iid}` | `members.invite` |
| GET | `/invitations/preview?token=` | public |
| POST | `/invitations/accept` | authenticated; email must match |
| GET | `/permissions` | authenticated |
| GET / POST | `/organizations/{id}/roles` | `roles.read` / `roles.manage` |
| DELETE | `/organizations/{id}/roles/{rid}` | `roles.manage` (custom, unassigned roles only) |
| GET | `/organizations/{id}/audit-logs?limit&offset&action` | `audit.read` |

## Health

`GET /health/live` (process up) · `GET /health/ready` (database + Redis; 503 when degraded).
