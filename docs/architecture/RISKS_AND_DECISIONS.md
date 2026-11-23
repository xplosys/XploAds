# Technical Risks, Open Decisions, External Dependencies and Costs

## 1. Technical risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **Meta API access** — Marketing API Standard/Advanced Access, App Review, Business Verification can take weeks and may be refused for some permissions (`ads_management`, `leads_retrieval`, `pages_manage_ads`, `business_management`, `whatsapp_business_messaging`). | Blocks Phase 5–6 in production. | Start App Review early; build against mock adapter + Meta test ad accounts; keep feature flags per capability. |
| R2 | **Meta policy and API churn** — Graph API versions deprecate ~every 2 years; targeting options (e.g. detailed interests, special ad categories for housing/employment/credit/health) change. | Broken publishing, rejected ads. | Pin Graph API version in config; contract tests against recorded responses; validation layer per objective; special-ad-category handling. |
| R3 | **Generated-media accuracy** — models hallucinate text, logos, product details. | Misleading ads, brand damage, policy rejections. | Deterministic compositing for exact text/logos/prices; use real product photos; claim validation; mandatory human approval. |
| R4 | **AI/media cost overruns** — video generation is expensive and slow. | Margin loss. | Reservation before execution, per-tenant budgets & concurrency caps, tier limits, price ceilings in routing, alerts. |
| R5 | **Cross-tenant data leakage** | Severe (security, legal). | RLS with non-owner `NOBYPASSRLS` role + `FORCE RLS`, membership-derived context, dedicated isolation tests in CI, tenant-scoped storage and cache keys. |
| R6 | **Financial correctness** (double charges, drift). | Customer disputes. | NUMERIC money, idempotency keys, immutable double-entry ledger, reconciliation jobs, webhook-only payment activation. |
| R7 | **Prompt injection via customer content/websites.** | Data exfiltration, bad actions. | Untrusted-content delimiting, tool allowlists, authorization in services not prompts, no secrets in prompts, output schema validation. |
| R8 | **Webhook reliability** (bursts, retries, duplicates). | Lost or duplicate leads. | Verify → store receipt (unique provider+event id) → ack → async process; dead-letter + replay tooling. |
| R9 | **Single-VPS topology** — one host failure takes everything down. | Downtime. | Managed Postgres or replicated volumes, off-site backups, documented restore; move to multi-node when SLOs require. |
| R10 | **Privacy & consent** (GDPR, India DPDP Act 2023, WhatsApp opt-in rules). | Legal exposure. | Consent records, retention policies, export/delete endpoints, DPA templates, data-region decision (D7). |

## 2. Unresolved decisions (need product owner input)

| # | Decision | Phase 1 default taken | Needed by |
|---|---|---|---|
| D1 | Agency hierarchy: client = child tenant vs. workspace inside agency tenant | **Child tenant** (`tenant_type='client'`, `parent_tenant_id`) — strongest isolation, client hand-over possible. | Implemented; revisit only if objections. |
| D2 | Launch geography, currencies, tax (GST/VAT), payment gateway (Razorpay vs Stripe) | Model supports multiple currencies; no gateway chosen. | Phase 7 |
| D3 | Initial image/video providers and quality targets | None hard-coded. | Phase 4 |
| D4 | Creative/video allowances per subscription tier | — | Phase 4/7 |
| D5 | MVP campaign objectives & placements (e.g. Leads, Traffic, Engagement, Messages/Click-to-WhatsApp, Sales) | — | Phase 5 |
| D6 | Approval policy: always required vs configurable by action/budget/risk | Initial publish **always** needs explicit approval; later policies narrowly scoped. | Phase 5 |
| D7 | Data residency, retention periods, privacy notice | — | Phase 6 |
| D8 | Expected tenant count, concurrent generation jobs, storage volume, SLOs | Sized for low hundreds of tenants on one VPS. | Phase 9 |
| D9 | Social login (Google/Facebook) at launch? | Email/password + TOTP MFA only; OAuth login slots reserved in `user_identities` design. | Phase 2 |
| D10 | Transactional email provider (SES, Postmark, SendGrid, SMTP) | Console adapter in dev; SMTP adapter ready. | Before first external user |

## 3. External dependencies

- Meta for Developers app (Business type), Business Verification, App Review, Marketing API access tier, test ad accounts.
- WhatsApp Business Platform (Cloud API) account, phone numbers, approved message templates.
- AI providers: Google Gemini, OpenAI, DeepSeek; at least one image provider and one video provider.
- Payment gateways: Razorpay and/or Stripe merchant accounts (eligibility depends on entity and region).
- Object storage: Cloudflare R2 or AWS S3.
- Email delivery provider; domain with SPF/DKIM/DMARC.
- Sentry project; domain + TLS (Let's Encrypt); Ubuntu VPS.

## 4. Potential third-party costs (indicative — verify current pricing before committing)

| Item | Cost driver | Who pays |
|---|---|---|
| Meta ad spend | Campaign budgets | **Customer, directly to Meta** from their own ad account. Never pooled by XploAds. |
| WhatsApp conversations/messages | Per-message pricing by category and country | Customer's WABA (or passed through if Xplosys hosts — decision needed). |
| LLM tokens (Gemini / OpenAI / DeepSeek) | Tokens per call | Xplosys (platform-managed) or customer (BYOK). |
| Image generation | Per image | Same as above. |
| Video generation | Per second/clip; highest unit cost | Same as above; tier-limited. |
| Object storage + egress | GB stored, requests (R2 has no egress fee) | Xplosys. |
| Email | Per 1k emails | Xplosys. |
| Payment gateway fees | % per transaction | Xplosys. |
| Sentry, monitoring, VPS, backups | Monthly plans | Xplosys. |
