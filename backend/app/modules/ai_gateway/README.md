# `ai_gateway` module

**Status:** planned for Phase 3 — no code yet. See `docs/architecture/ROADMAP.md`.

The only path to AI providers: routing, credential selection, usage reservation, execution, cost calculation, settlement. Never falls back from BYOK to platform credentials.

**Owns tables:** usage_events, usage_costs, usage_reservations

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
