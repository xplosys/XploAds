# `creative_studio` module

**Status:** planned for Phase 4 — no code yet. See `docs/architecture/ROADMAP.md`.

Brief to copy, image, carousel and video variants via async workers; deterministic compositing for logos, prices and exact text; creative library and versions.

**Owns tables:** creative_projects, generation_jobs, creatives, creative_versions

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
