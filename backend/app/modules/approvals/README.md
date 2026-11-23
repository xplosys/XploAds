# `approvals` module

**Status:** planned for Phase 5 — no code yet. See `docs/architecture/ROADMAP.md`.

Approval requests for creatives, campaign publishing and budget changes, bound to the exact version approved. (The shared audit log already exists in app/shared/audit.py.)

**Owns tables:** approvals

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
