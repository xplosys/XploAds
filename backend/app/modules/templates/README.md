# `templates` module

**Status:** planned for Phase 4 — no code yet. See `docs/architecture/ROADMAP.md`.

Platform and tenant creative templates with versions and previews.

**Owns tables:** templates, template_versions

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
