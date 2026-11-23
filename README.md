# XploAds

AI-powered advertising automation for Facebook and Instagram, by **Xplosys**. Businesses and agencies plan
campaigns, generate on-brand creatives, publish through the Meta Marketing API after explicit approval, capture
leads and WhatsApp enquiries into a CRM, and optimize — while staying in control of every publish and every spend
decision.

> **Status:** Phase 1 (Foundation) is complete: accounts, MFA, organizations, agency clients, workspaces, team
> invitations, RBAC, audit log, tenant isolation with PostgreSQL RLS, async outbox, Docker stack.
> See [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) and the [roadmap](docs/architecture/ROADMAP.md).

## Quick start

```bash
cp .env.example .env
docker compose up -d --build
# open http://localhost:8080  — emails (verification links etc.) appear in: docker compose logs -f worker
```

Running services on the host, tests and VPS deployment: [`docs/deployment/DEPLOYMENT.md`](docs/deployment/DEPLOYMENT.md).

## Stack

| Layer | Technology |
|---|---|
| Web | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui-style components, TanStack Query, React Hook Form + Zod |
| API | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 (async), Alembic |
| Jobs | Celery 5 on Redis 7, transactional outbox |
| Data | PostgreSQL 16 with Row-Level Security (pgvector later), S3/R2 object storage (Phase 2) |
| Ops | Docker Compose, Nginx, structured JSON logs, Sentry; Prometheus/Grafana in Phase 9 |
| Quality | pytest (real Postgres), Playwright, Ruff, ESLint, GitHub Actions |

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md) · [Roadmap](docs/architecture/ROADMAP.md) ·
  [Risks & decisions](docs/architecture/RISKS_AND_DECISIONS.md) · [Repository structure](docs/architecture/REPOSITORY_STRUCTURE.md)
- [Database design](docs/database/SCHEMA.md) · [API](docs/api/API.md) · [Security](docs/security/SECURITY.md) ·
  [Integrations](docs/integrations/INTEGRATIONS.md)
- [Deployment](docs/deployment/DEPLOYMENT.md) · [Environment variables](docs/deployment/ENVIRONMENT.md)
- Source design documents: `Documents/`

## Principles

1. Tenant isolation is enforced by the database, not just the code.
2. AI proposes; people approve anything that publishes or spends money.
3. Money uses NUMERIC and an immutable double-entry ledger.
4. Every AI call goes through one gateway; BYOK never silently becomes platform-paid.
5. Mocked integrations are labelled as mocked. Nothing is called production-ready until verified.
