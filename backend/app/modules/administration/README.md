# `administration` module

**Status:** planned for Phase 9 — no code yet. See `docs/architecture/ROADMAP.md`.

Super-admin portal APIs: tenants, users, plans, providers, pricing, feature flags, job and error monitoring. Separate from tenant administration.

**Owns tables:** feature_flags, platform_settings

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
