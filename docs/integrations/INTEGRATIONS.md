# Third-party Integrations

**Phase 1 status: no third-party integration is implemented.** Email is the only outbound channel, in `console`
mode locally (messages are printed by the worker) or `smtp` mode. Everything below is the plan; nothing here is
claimed to work until it is verified in an authorized test environment and marked in `IMPLEMENTATION_STATUS.md`.

## Rules for every integration

1. Vendor SDK/API calls live only in the owning module's `integrations/` adapter.
2. Each adapter has a `mock` implementation selected by an env flag (e.g. `META_MODE=mock|live`), and the UI shows a
   visible "Mock integration" badge while mocked.
3. Credentials are envelope-encrypted (`app/core/security.encrypt_secret`), never returned to the frontend, never logged.
4. Webhooks: verify signature → insert `webhook_receipts` (unique provider + event id) → acknowledge → process async
   on `webhook_processing` with retries and dead-lettering.
5. Respect rate limits with backoff; store external ids for idempotent retries.
6. Verify current vendor documentation and required permissions before building each endpoint.

## Meta (Phase 5)

- Facebook Login for Business with signed `state` (CSRF) and PKCE where supported.
- Permissions to request in App Review (verify current names): `ads_management`, `ads_read`, `business_management`,
  `pages_show_list`, `pages_read_engagement`, `pages_manage_ads`, `leads_retrieval`, `instagram_basic`,
  `instagram_manage_insights`; WhatsApp: `whatsapp_business_management`, `whatsapp_business_messaging`.
- Prerequisites: Business Verification, Marketing API Advanced Access, test ad accounts for staging.
- Campaigns are created **paused**, then activated only after the approval record for that exact version exists.
- Lead Ads webhook (`leadgen`) → fetch lead with Page token → normalize into CRM.
- Special Ad Categories (housing, employment, credit, social issues) restrict targeting — validate before publish.

## WhatsApp Cloud API (Phase 6)

Separate from the Marketing API. Inbound webhook for messages and statuses; 24-hour customer-service window;
template messages outside the window; opt-in records required; per-message pricing tracked separately from
XploAds charges.

## AI providers (Phases 3–4)

Gemini, OpenAI, DeepSeek behind the AI Gateway; image and video providers behind the same interface. Platform-managed
or BYOK credentials per tenant and task; usage reserved before and settled after each call.

## Payments (Phase 7)

Razorpay and/or Stripe adapters. Subscription state changes only from signature-verified webhooks.
