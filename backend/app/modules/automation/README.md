# `automation` module

**Status:** planned for Phase 8 — no code yet. See `docs/architecture/ROADMAP.md`.

Workflow engine: triggers, schedules, steps, run logs, consent-aware messaging.

**Owns tables:** workflows, workflow_versions, workflow_runs, workflow_steps

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
