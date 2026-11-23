# `campaigns` module

**Status:** planned for Phase 5 — no code yet. See `docs/architecture/ROADMAP.md`.

Campaign / ad set / ad builder mapped to Meta Marketing API capabilities, validation, final review, approval-gated publishing, pause/resume.

**Owns tables:** campaigns, ad_sets, ads, campaign_schedules

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
