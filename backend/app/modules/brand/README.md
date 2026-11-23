# `brand` module

**Status:** planned for Phase 2 — no code yet. See `docs/architecture/ROADMAP.md`.

Brand profiles, guidelines, products and services, brand assets in tenant-scoped object storage.

**Owns tables:** brand_profiles, brand_assets, brand_guidelines, products

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
