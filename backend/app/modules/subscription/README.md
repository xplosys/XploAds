# `subscription` module

**Status:** planned for Phase 7 — no code yet. See `docs/architecture/ROADMAP.md`.

Plans, entitlements, subscriptions, trials, wallets, double-entry ledger, invoices, payments (Razorpay/Stripe adapters with verified webhooks).

**Owns tables:** plans, plan_entitlements, subscriptions, wallets, ledger_transactions, ledger_entries, credit_reservations, invoices, payments, billing_adjustments

Follows the standard module layout (`api/ schemas/ models/ repositories/ services/ integrations/ events/ permissions/`)
described in `docs/architecture/ARCHITECTURE.md` §3.1. Permission codes for this module are already declared in
`app/modules/tenant/permissions/catalog.py`.
