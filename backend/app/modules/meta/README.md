# `meta` module

**Status:** planned for Phase 5 — no code yet. See `docs/architecture/ROADMAP.md`.

Meta OAuth, asset discovery (Pages, Instagram, ad accounts), token storage, Graph/Marketing API adapter with mock mode, Lead Ads webhooks, insights sync.

**Owns tables:** social_connections, meta_assets, oauth_grants, webhook_receipts

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
