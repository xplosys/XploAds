# `analytics` module

**Status:** planned for Phase 8 — no code yet. See `docs/architecture/ROADMAP.md`.

Campaign, business, AI-usage and agency analytics from synced Meta insights, with attribution caveats.

**Owns tables:** metric_snapshots, conversion_events, report_jobs

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
