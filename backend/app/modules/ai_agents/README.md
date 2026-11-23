# `ai_agents` module

**Status:** planned for Phase 4 — no code yet. See `docs/architecture/ROADMAP.md`.

Versioned agent definitions (instructions, model policy, tool allowlist, input/output schemas) and run history. Agents propose; services decide.

**Owns tables:** agent_definitions, agent_versions, agent_runs

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
