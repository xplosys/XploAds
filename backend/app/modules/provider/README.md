# `provider` module

**Status:** planned for Phase 3 — no code yet. See `docs/architecture/ROADMAP.md`.

AI provider registry, models, versioned pricing, platform-managed and BYOK credentials (envelope-encrypted), per-tenant task routing.

**Owns tables:** ai_providers, provider_models, provider_pricing, provider_credentials, tenant_provider_configs

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
