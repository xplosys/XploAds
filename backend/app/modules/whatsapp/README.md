# `whatsapp` module

**Status:** planned for Phase 6 — no code yet. See `docs/architecture/ROADMAP.md`.

WhatsApp Cloud API: accounts, numbers, webhooks, conversations, templates, opt-in/opt-out, 24-hour window rules.

**Owns tables:** whatsapp_accounts, conversations, messages, opt_ins

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
