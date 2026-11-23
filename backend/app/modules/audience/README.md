# `audience` module

**Status:** planned for Phase 5 — no code yet. See `docs/architecture/ROADMAP.md`.

Targeting, saved/custom/lookalike audiences, AI audience recommendations validated against Meta policy.

**Owns tables:** audiences

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
