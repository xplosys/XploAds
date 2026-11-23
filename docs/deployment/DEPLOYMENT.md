# Deployment

## 1. Local development

### Option A — everything in Docker

```bash
cp .env.example .env          # defaults work locally; DATA_ENCRYPTION_KEY may stay empty for local only
docker compose up -d --build
open http://localhost:8080    # Nginx → web + api
docker compose logs -f worker # emails (verification, reset, invitations) are printed here in console mode
```

Brand assets are stored in the bundled SeaweedFS container (S3-compatible). The browser uploads to and downloads
from it through signed URLs on `http://localhost:8333`, so keep that port free (or change `STORAGE_PORT` and
`S3_PUBLIC_ENDPOINT_URL` together). The `migrate` service creates the bucket.

### Option B — run API and web on the host (fast reload)

Prerequisites: Python 3.12, Node 22, PostgreSQL 16, Redis 7.

```bash
# one-time database setup (as a PostgreSQL superuser)
psql -U postgres -c "CREATE ROLE xploads_owner LOGIN PASSWORD 'xploads_owner' BYPASSRLS"
psql -U postgres -c "CREATE ROLE xploads_app LOGIN PASSWORD 'xploads_app' NOBYPASSRLS"
psql -U postgres -c "CREATE DATABASE xploads OWNER xploads_owner"
psql -U postgres -d xploads -c "ALTER SCHEMA public OWNER TO xploads_owner; GRANT CONNECT ON DATABASE xploads TO xploads_app"

cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
alembic upgrade head
uvicorn app.main:app --reload                      # http://localhost:8000/api/docs
celery -A app.workers.celery_app worker -B -Q default,notifications --loglevel=INFO   # (Windows: add --pool=solo)

cd ../frontend
npm install
npm run dev                                         # http://localhost:3000 (proxies /api to :8000)
```

The backend defaults (`app/core/config.py`) match these role passwords, so no `.env` is needed for Option B.
Uploaded assets go to `backend/var/storage` (`STORAGE_BACKEND=local`), served through signed API URLs.
Without a worker, deliver queued emails once with `python -m app.cli relay-outbox`.

### Tests

```bash
cd backend && pytest -q                 # needs PostgreSQL superuser access (TEST_PG_ADMIN_URL) and Redis
cd frontend && npm run lint && npm run typecheck && npm run build
cd frontend && E2E_BASE_URL=http://localhost:8080 npx playwright test   # against a running stack
```

## 2. Ubuntu VPS (staging / production)

1. **Server:** Ubuntu 24.04 LTS, 4 vCPU / 8 GB RAM minimum to start. Create a non-root sudo user, enable `ufw`
   (allow 22, 80, 443), disable SSH password login, enable unattended-upgrades.
2. **Docker:** install Docker Engine + Compose plugin from Docker's apt repository.
3. **Code:** `git clone` the repository to `/opt/xploads`.
4. **Secrets:** `cp .env.example .env`, set `ENVIRONMENT=production`, strong unique passwords, `JWT_SECRET`,
   `DATA_ENCRYPTION_KEY` (generate per the comments; store a copy in your password manager — losing it makes MFA
   secrets and future integration credentials unreadable), `COOKIE_SECURE=true`, `EMAIL_MODE=smtp` + SMTP settings,
   `FRONTEND_URL=https://app.example.com`, `CORS_ORIGINS=https://app.example.com`, `SENTRY_DSN`. `chmod 600 .env`.
   **Object storage:** use Cloudflare R2 or AWS S3 rather than the bundled SeaweedFS (or put SeaweedFS behind TLS on
   its own subdomain). Create a private bucket and an access key limited to it, then set `S3_ENDPOINT_URL` and
   `S3_PUBLIC_ENDPOINT_URL` (R2: `https://<account>.r2.cloudflarestorage.com`), `S3_REGION` (`auto` for R2),
   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `STORAGE_BUCKET`. Add a bucket CORS rule allowing `POST` and `GET`
   from the app origin with any header. When using R2/S3, remove the `storage` service (and its dependency in
   `migrate`) from your compose override.
5. **DNS:** A/AAAA record for the app domain to the VPS.
6. **TLS:** obtain certificates with certbot (webroot `/var/www/certbot` is served by Nginx), then add a `listen 443 ssl`
   server block to `infrastructure/nginx/nginx.conf` using `/etc/letsencrypt/live/<domain>/`, redirect 80 → 443, and
   enable the HSTS header. Renew with a systemd timer running `certbot renew` and `docker compose exec nginx nginx -s reload`.
7. **Start:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
   The API refuses to start if production secrets are still development defaults.
8. **First admin:** register through the UI, then
   `docker compose exec api python -m app.cli make-platform-admin you@example.com`.

## 3. Releases and rollback

- Tag releases (`vX.Y.Z`); build images per tag.
- Deploy: `git fetch && git checkout vX.Y.Z && docker compose ... up -d --build`. The `migrate` service runs
  `alembic upgrade head` before the API starts.
- Migrations must be backward compatible with the previous release (expand → migrate → contract), so rolling the
  code back does not require a schema downgrade.
- Rollback: check out the previous tag and `up -d --build`. Use `alembic downgrade` only for migrations explicitly
  marked reversible, after a backup.

## 4. Backups and recovery

- Nightly logical backup: `docker compose exec -T postgres pg_dump -U postgres -Fc xploads > /backups/xploads-$(date +%F).dump`
  via cron; copy off-site (e.g. R2/S3 with object lock); keep 7 daily, 4 weekly, 12 monthly.
- For PITR use a managed PostgreSQL or WAL archiving (pgBackRest / WAL-G) — recommended before paying customers.
- Redis is not a source of truth (AOF enabled only to preserve queued jobs across restarts).
- Restore drill monthly: `pg_restore -U postgres -d xploads_restore /backups/<file>.dump`, run the test suite's
  isolation checks against it.
- Keep `DATA_ENCRYPTION_KEY` backed up separately from database backups.
- Object storage: enable versioning or replication on the R2/S3 bucket; with the bundled SeaweedFS, back up the
  `storagedata` volume alongside the database dump (asset rows and objects must be restored together).

## 5. Logging and monitoring

- API and Nginx write JSON logs with `request_id`; view with `docker compose logs`. Ship to a log store
  (Loki / CloudWatch / Better Stack) in production.
- Health: `/health/live`, `/health/ready`; container healthchecks for api, web, worker.
- Errors: Sentry via `SENTRY_DSN` (no PII sent).
- Metrics: Prometheus/Grafana in Phase 9.
