# Repository Structure

```
XploAds/
├── backend/                     Python 3.12 · FastAPI modular monolith + Celery workers
│   ├── app/
│   │   ├── core/                Config, DB engine + RLS context, security primitives, errors, logging, rate limiting
│   │   ├── shared/              Cross-cutting infrastructure only: audit writer, outbox, notifications, DTO base
│   │   ├── modules/             One package per business module (see table below)
│   │   ├── workers/             Celery app, queue declarations, outbox event handlers
│   │   ├── cli.py               Operational commands (make-platform-admin, relay-outbox, sync-permissions)
│   │   └── main.py              FastAPI app factory, middleware, health checks, router registration
│   ├── alembic/versions/        Hand-written migrations incl. RLS policies and grants (run as xploads_owner)
│   ├── tests/                   pytest suite against real PostgreSQL + Redis (incl. cross-tenant tests)
│   └── requirements/            base.txt (runtime, pinned) · dev.txt (tests, lint)
│
├── frontend/                    Next.js 16 (App Router) · React 19 · TypeScript · Tailwind 4 · shadcn/ui-style components
│   ├── app/                     Routes: (marketing) landing, (auth) pages, onboarding, app/[orgId]/*, account/security
│   ├── components/              App shell, logo, ui/ primitives (button, input, card, dialog, …)
│   ├── features/<module>/       Feature code mirroring backend modules (auth provider, org queries/mutations)
│   ├── services/api-client.ts   Typed fetch wrapper, in-memory access token, single-flight refresh
│   ├── hooks/ lib/ types/       Shared hooks, utilities, API response types
│   └── e2e/                     Playwright end-to-end tests
│
├── database/                    Seeds and operational SQL (schema itself lives in backend/alembic)
├── infrastructure/
│   ├── docker/                  backend.Dockerfile (API + workers), frontend.Dockerfile, postgres init (roles)
│   ├── nginx/                   Reverse proxy config (/ → web, /api → api), JSON access logs, auth rate limit
│   └── monitoring/              Monitoring notes (Prometheus/Grafana arrive in Phase 9)
├── docs/
│   ├── architecture/            ARCHITECTURE, ROADMAP, RISKS_AND_DECISIONS, this file
│   ├── database/                SCHEMA (ER diagrams, table ownership, RLS rules)
│   ├── api/                     API reference and conventions
│   ├── integrations/            Meta, WhatsApp, AI providers, payments — plans and mock-mode rules
│   ├── security/                Security controls and threat model
│   ├── deployment/              Local, VPS deployment, environment variables, backups, rollback
│   └── IMPLEMENTATION_STATUS.md Milestone log (updated after every milestone)
├── Documents/                   Product owner's source documents (HLD/LLD PDF, diagrams) — not modified by code
├── .github/workflows/ci.yml     Lint, tests, build, full-stack E2E
├── docker-compose.yml           Local / single-VPS stack · docker-compose.prod.yml production overrides
├── .env.example                 Every environment variable, documented
├── CLAUDE.md                    Working notes for AI coding agents on this repo
└── README.md
```

## Backend modules

| Module | Status | Responsibility |
|---|---|---|
| `identity` | **Implemented** | Users, auth, sessions, MFA, verification, password reset |
| `tenant` | **Implemented** | Organizations, agency clients, workspaces, members, invitations, RBAC |
| `brand` | Phase 2 | Brand profiles, assets, products |
| `provider`, `ai_gateway` | Phase 3 | AI provider registry, BYOK, metering, reservations |
| `ai_agents`, `creative_studio`, `templates` | Phase 4 | Agents, generation pipeline, creative library |
| `meta`, `campaigns`, `audience`, `approvals` | Phase 5 | Meta integration, campaign builder, approval-gated publishing |
| `crm`, `whatsapp` | Phase 6 | Leads CRM, WhatsApp Cloud API |
| `subscription` | Phase 7 | Plans, ledger, payments |
| `analytics`, `automation` | Phase 8 | Dashboards, workflows, recommendations |
| `administration` | Phase 9 | Super-admin portal |

Planned modules contain only a `README.md` describing ownership and scope, so nothing appears implemented that is not.
