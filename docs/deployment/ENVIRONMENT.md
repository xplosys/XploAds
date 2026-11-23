# Environment Variables

Backend settings are defined in `backend/app/core/config.py` (pydantic-settings, case-insensitive). Defaults suit local
development only; staging/production refuse to boot with insecure defaults.

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `local` | `local`, `test`, `staging`, `production`. Production disables OpenAPI docs and enforces safe config. |
| `LOG_LEVEL` | `INFO` | Log level. |
| `DATABASE_URL` | `postgresql+asyncpg://xploads_app:xploads_app@localhost:5432/xploads` | Runtime connection (non-owner, NOBYPASSRLS role). |
| `MIGRATION_DATABASE_URL` | `postgresql+psycopg://xploads_owner:xploads_owner@localhost:5432/xploads` | Alembic / owner connection. |
| `APP_DB_ROLE` | `xploads_app` | Role that migrations grant DML privileges to. |
| `DB_POOL_SIZE` | `10` | SQLAlchemy pool size per process. |
| `REDIS_URL` | `redis://localhost:6379/0` | Rate limits, Celery broker. |
| `CELERY_BROKER_URL` | = `REDIS_URL` | Override the Celery broker. |
| `JWT_SECRET` | dev value | HMAC key for access tokens and token hashing (≥ 32 chars). **Required in prod.** |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `xploads` / `xploads-api` | JWT claims. |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Access token lifetime. |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Session lifetime. |
| `EMAIL_VERIFICATION_TTL_HOURS` | `48` | Verification link lifetime. |
| `PASSWORD_RESET_TTL_MINUTES` | `30` | Reset link lifetime. |
| `MFA_CHALLENGE_TTL_MINUTES` | `5` | MFA login challenge lifetime. |
| `INVITATION_TTL_DAYS` | `7` | Invitation lifetime. |
| `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES` | `10` / `15` | Account lockout. |
| `DATA_ENCRYPTION_KEY` | dev value | Base64url 32-byte KEK for envelope encryption. Keep outside the DB; back it up. **Required in prod.** |
| `COOKIE_SECURE` | `false` | Secure flag on the refresh cookie. **Must be true in prod.** |
| `COOKIE_DOMAIN` | unset | Cookie domain if API and app use different subdomains. |
| `REFRESH_COOKIE_NAME` | `xploads_refresh` | Cookie name. |
| `FRONTEND_URL` | `http://localhost:3000` | Used to build links in emails. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins. |
| `EMAIL_MODE` | `console` | `console` (prints emails; not allowed in prod) or `smtp`. |
| `EMAIL_FROM` | `XploAds <no-reply@xploads.local>` | Sender. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_STARTTLS` | — / 587 / — / — / true | SMTP delivery. |
| `RATE_LIMIT_ENABLED` | `true` | Disable only in tests. |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | API request body limit. |
| `SENTRY_DSN` | unset | Enables Sentry. |
| `STORAGE_BACKEND` | `local` | `s3` (AWS S3, Cloudflare R2, SeaweedFS, MinIO) or `local` (files on disk; dev/tests only, refused in prod). Docker Compose sets `s3`. |
| `STORAGE_BUCKET` | `xploads-assets` | Private bucket for brand assets. `python -m app.cli ensure-storage` creates it. |
| `STORAGE_LOCAL_PATH` | `./var/storage` | Folder for the local backend. |
| `S3_ENDPOINT_URL` | unset (AWS) | S3 API endpoint the API uses. Compose: `http://storage:8333`. R2: `https://<account>.r2.cloudflarestorage.com`. |
| `S3_PUBLIC_ENDPOINT_URL` | = `S3_ENDPOINT_URL` | Endpoint written into signed URLs the browser uses. Compose: `http://localhost:8333`. |
| `S3_REGION` | `us-east-1` | Region (`auto` for R2). |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | — | Storage credentials. In Compose they also create the SeaweedFS identity. **Required in prod.** |
| `S3_FORCE_PATH_STYLE` | `true` | Path-style addressing (needed for SeaweedFS/MinIO; fine for R2). |
| `STORAGE_UPLOAD_URL_TTL_SECONDS` / `STORAGE_DOWNLOAD_URL_TTL_SECONDS` | `900` / `300` | Lifetime of signed upload forms and download links. |
| `API_PUBLIC_URL` | empty | Base URL for the local backend's signed URLs; empty means same origin. |

Docker Compose only:

| Variable | Purpose |
|---|---|
| `POSTGRES_DB`, `POSTGRES_SUPERUSER`, `POSTGRES_SUPERUSER_PASSWORD` | Postgres container bootstrap. |
| `XPLOADS_OWNER_PASSWORD`, `XPLOADS_APP_PASSWORD` | Passwords for the owner and runtime roles (created by `infrastructure/docker/postgres/01-roles.sh`). |
| `HTTP_PORT` | Host port for Nginx (default 8080). |
| `STORAGE_PORT` | Host port for the SeaweedFS S3 endpoint (default 8333); must match `S3_PUBLIC_ENDPOINT_URL`. |

Frontend:

| Variable | When | Purpose |
|---|---|---|
| `API_INTERNAL_URL` | build time | Where the Next.js server proxies `/api/*` (dev: `http://localhost:8000`; Docker: `http://api:8000`). |
| `NEXT_PUBLIC_API_BASE` | build time | API base path seen by the browser (default `/api/v1`). |
| `E2E_BASE_URL`, `PW_CHANNEL` | tests | Playwright target URL and browser channel. |
