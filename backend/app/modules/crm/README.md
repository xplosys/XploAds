# `crm` module

**Status:** planned for Phase 6 — no code yet. See `docs/architecture/ROADMAP.md`.

Leads and contacts, normalization, dedupe, scoring, AI qualification, assignment, pipeline stages, activities, export.

**Owns tables:** leads, contacts, lead_sources, lead_assignments, lead_activities, pipeline_stages

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
