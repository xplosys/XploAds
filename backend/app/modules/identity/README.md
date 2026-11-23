# `identity` module — implemented (Phase 1)

Authentication and user accounts.

| | |
|---|---|
| Owns tables | `users`, `sessions`, `auth_tokens`, `mfa_recovery_codes` |
| API | `/api/v1/auth/*` (register, login, mfa/verify, refresh, logout, me, verify-email, resend-verification, forgot-password, reset-password, change-password, mfa/setup, mfa/enable, mfa/disable, sessions) |
| Public interface | `app.modules.identity.api.deps` — `Auth`, `VerifiedAuth`, `DbSession`, `Meta`, `require_platform_admin` |
| Events emitted | `identity.email_verification_requested`, `identity.password_reset_requested` (via outbox) |
| Depends on | `app.core`, `app.shared` only |

Key rules
- Argon2id hashing; constant-time handling of unknown accounts; lockout after `MAX_FAILED_LOGINS`.
- Access JWT (15 min) bound to a server-side session; every request checks the session is not revoked.
- Refresh token `"{session_id}.{secret}"` in an HttpOnly, SameSite=Strict cookie scoped to `/api/v1/auth`;
  rotated on every use; replaying an old token after the 20-second multi-tab grace window revokes the session.
- One-time tokens (verification, reset, MFA challenge) are stored as HMAC-SHA256 hashes and are single-use.
- TOTP secrets are envelope-encrypted with AAD bound to the user id; 10 hashed single-use recovery codes.
