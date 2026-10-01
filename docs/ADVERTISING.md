# Advertising and Payments (Phase 8)

Phase 8 v1 is **sponsored medical-product campaigns**: a verified medical company
promotes one of its marketplace products to the providers it is meant for. The
whole commercial workflow — campaigns, backend pricing, payment records, payment
verification and targeting — is server-controlled. **There is no payment gateway,
no webhook and no seeded price**: the owner has not selected a gateway or set a
rate, so payment happens off-platform and an administrator verifies it.

Out of scope: generic banner ads, provider/hospital/job/real-estate ads, external
URLs, brand-only campaigns, image/video ads, receipts, analytics (impressions,
clicks, ROI — Phase 10), refunds, chat and notifications.

## Ownership and roles

Advertising belongs to the existing `MEDICAL_COMPANY` role (capability
`advertising.manage_own_campaigns`) and the existing `marketplace.MedicalCompany`
profile. No advertiser role or second company profile exists. The company is always
`request.user.medical_company`, never a client id. Payment itself is the commercial
gate: there is no advertising subscription, credit or entitlement key
(`billing.KNOWN_KEYS` is untouched), and `billing.PaymentRecord` (subscription
payments) is not reused or changed — `CampaignPayment` is advertising-specific.

## Entities (`apps/advertising`)

| Model | Notes |
| --- | --- |
| `AdvertisingRate` | `code`, bilingual name, `price_per_day` (> 0), `currency` (settings allow-list), `is_active`. **At most one active rate** (partial unique constraint). **No migration inserts a price**; administrators configure it in Django admin (activating a rate atomically retires the previous one; rates are never deleted). |
| `AdvertisingCampaign` | `company`, `product`, internal `name` (not ad copy — the ad shows the product), `starts_on`/`ends_on`, `status`, and the price snapshot `quoted_days`, `quoted_daily_rate`, `quoted_amount`, `quoted_currency`, `quoted_at` plus a protected `rate` FK. |
| `CampaignProviderType`, `CampaignSpecialty`, `CampaignGovernorate` | Normalized targets (FKs, never names), unique per campaign + target; written only while the campaign is locked. |
| `CampaignPayment` | One per campaign: `amount`, `currency` (copies of the quote), `status` PENDING/VERIFIED/REJECTED, `method` (BANK_TRANSFER, CASH, EXCHANGE_OFFICE, OTHER), `reference`, `verified_by`, `verified_at`, `admin_note`. No card numbers, secrets, receipts or credentials. |

Model guards: `company` can never change; once a campaign leaves DRAFT, its product,
name, dates and the whole quote snapshot can never change; a payment's campaign,
amount and currency can never change. Database checks: dates ordered, amounts
≥ 0, days > 0, **a submitted campaign must carry its full quote**, and a payment is
VERIFIED only with a verification time and a method. Migration `advertising/0001`.

## Campaign state machine

```
DRAFT --submit--> PENDING_PAYMENT --admin verifies--> ACTIVE --company cancels--> CANCELLED
                          \--admin rejects--> REJECTED
```

No other transition exists (no DRAFT → ACTIVE, nothing → ACTIVE from the client,
REJECTED/CANCELLED are final history — another attempt is a new campaign). The API
never accepts `status`. **Only DRAFT is editable**; after submission the product,
dates, targeting and price are frozen. A campaign whose end date has passed stays
stored `ACTIVE` but is not live and is not shown (server date, no worker).

## Pricing

`quoted_days = (ends_on - starts_on).days + 1` (inclusive);
`quoted_amount = quoted_days × the active rate's price_per_day` — `Decimal`,
2 places, no surcharge for type/specialty/geography/category.

- `POST advertising/company/quote` (`starts_on`, `ends_on`) is a **preview** from the
  current active rate (`days`, `daily_rate`, `total`, `currency`). No active rate →
  typed `pricing_unavailable` (409); the web then says pricing has not been
  configured and shows no number.
- **Submission never trusts the preview**: it recomputes under the rate row lock
  from the committed active rate and snapshots the result on the campaign and in
  its `CampaignPayment`. A later rate change never alters a submitted campaign
  (`test_a_rate_change_never_touches_a_snapshot…`, and a real concurrent test).
- **A total must fit the stored precision.** `_build_quote()` (used by the preview and by the authoritative submission) refuses a total above `MAX_CAMPAIGN_AMOUNT` — derived from the `quoted_amount` and `CampaignPayment.amount` field metadata (`Decimal(16, 2)` → `99999999999999.99`), which the quote response serializer mirrors — with the typed `quote_amount_too_large` (409). It is never truncated, clamped or left to fail as a database/serializer error; the campaign stays an untouched DRAFT (no snapshot, no payment). At the maximum daily rate `999999999999.99`, 100 days (`99999999999999.00`) fits and 101 days overflows. This is distinct from `payment_quote_mismatch`, which protects verification against a corrupted snapshot.
- Submission requires both dates, `ends_on >= starts_on`, `starts_on >= today` and
  `ends_on >= today` (no charging for elapsed days), active targeted
  governorates/specialties, and the company and product checks below.

## Submission and manual payment verification

`services.submit_campaign` (one transaction; lock order **company + account →
campaign → payment → product / rate**): company eligible (`MedicalCompany.can_publish`:
VERIFIED, active account, role MEDICAL_COMPANY — the marketplace's own rule) → campaign
is DRAFT → the company's own product is currently exposable (Phase 6) → dates and
targets valid → lock and read the active rate → snapshot → create the one PENDING
`CampaignPayment` → `PENDING_PAYMENT` → audit.

Payment is completed **outside the platform**. An administrator calls
`POST admin/advertising/campaigns/{id}/verify-payment` with only `method`,
`reference` and `note`; the amount is the campaign's own quote and can never be
sent. `services.verify_campaign_payment` locks company → campaign → payment →
product, then requires: campaign PENDING_PAYMENT and payment PENDING
(`invalid_transition` / `payment_not_pending` otherwise), **the locked financial
snapshot to be coherent** (`payment_quote_mismatch`, 409, see below), the company **currently**
eligible (`company_not_eligible`), the product **currently** exposable
(`product_unavailable`), targeted references still active, and the end date not
passed (`campaign_ended`). Only then are the payment VERIFIED and the campaign
ACTIVE, **in the same transaction** — never a verified payment with a non-active
campaign. A paid campaign never overrides marketplace safety.
`POST …/reject-payment` (`reason` required) atomically sets payment REJECTED and
campaign REJECTED. Verify twice, reject after verify and verify after reject are all
refused. Cancelling an ACTIVE campaign stops exposure immediately and changes
nothing financial: **no automatic refund, credit or payment edit**; refunds and
reconciliation stay manual until a provider/refund policy exists.

### Future gateway boundary

`verify_campaign_payment` is the single business transition for "this payment is
verified". A real provider integration will (1) authenticate the provider's
callback/signature, (2) resolve the `CampaignPayment`, (3) verify paid
amount/currency/reference, then (4) call this same locked service. A browser's
"payment succeeded" can never activate a campaign. Steps 1–3 are **not built**:
there is no fake webhook, test endpoint or placeholder secret.

### Payment ↔ quote coherence

Model guards can be bypassed by `QuerySet.update()`, SQL or a future integration, so
`verify_campaign_payment` itself proves, on the **locked** rows and before anything is
marked VERIFIED: the campaign has a rate reference, `quoted_days > 0`,
`quoted_daily_rate > 0`, `quoted_amount > 0` and a supported `quoted_currency`;
`quoted_amount == quantize(quoted_daily_rate × quoted_days)`; **`quoted_days` equals the inclusive day count of the locked dates** (`(ends_on − starts_on).days + 1`, which must be > 0), so a guard-bypassing change of the window cannot activate a different duration than the one priced; `payment.amount ==
campaign.quoted_amount`; `payment.currency == campaign.quoted_currency`; and the payment
belongs to this campaign. Any mismatch is `payment_quote_mismatch` (409): the payment stays
PENDING and the campaign PENDING_PAYMENT (an administrator can still reject it); nothing is
repaired automatically. The snapshot is deliberately **not** compared with the current
`AdvertisingRate`, which may legitimately have changed since submission, and nothing is recomputed or repaired. Shifting both dates while keeping the same duration stays financially coherent; the other verification rules (for example `campaign_ended`) still apply.

## Targeting and visibility

`AdvertisingCampaignQuerySet.visible_to(provider)` is the only exposure rule,
evaluated from **current database state** and the server date on every read:

1. campaign ACTIVE, payment VERIFIED, `starts_on <= today <= ends_on`;
2. the company is VERIFIED on an active MEDICAL_COMPANY account and owns the product;
3. **the product reaches this provider under the Phase 6 rule**
   (`ProductQuerySet.targeted_for`: active product, exposable category, matching
   `ProductAudience`, verified provider) — the campaign layer can only **narrow**
   that set, never widen it (`test_campaign_targeting_can_only_narrow…`);
4. the provider is an active PROVIDER with a VERIFIED profile, re-read here;
5. each configured narrowing matches the provider's current profile: provider types
   (none = no restriction), specialties (any one), governorates (current governorate
   must match one; a deactivated targeted governorate stops producing exposure). A
   campaign's targeted **specialty must itself still be active** to match: deactivating it
   (or all of a campaign's specialty targets) stops exposure at read time, while the
   campaign and its payment stay untouched — no automatic cancel, reject or refund.

The company/product-category dimension is the product's own current category and its
audience rules — there is no separate category selector. Nothing caches provider
identity; changing role, account state, verification, type, specialty or governorate,
or any company/product/category/audience state, hides the ad on the next request.
Queries are bounded (Exists/Subquery; target checks are not per row).

## API (`/api/v1/`)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| GET | `advertising/marketplace` | verified provider | sponsored campaigns visible to me (paginated, `ends_on`, `id`); every row `sponsored: true`; product + window only; no filters |
| GET | `advertising/company/dashboard` | company | backend counts (total, draft, pending_payment, active, live, ended, rejected, cancelled) |
| POST | `advertising/company/quote` | company | price preview |
| GET / POST | `advertising/company/campaigns` | company | own campaigns (paginated, newest first, `?status=`); create a DRAFT |
| GET / PATCH | `advertising/company/campaigns/{id}` | company | foreign ids 404; PATCH only a DRAFT (`campaign_not_editable`) |
| POST | `…/{id}/submit` · `…/{id}/cancel` | company | lifecycle above |
| GET | `admin/advertising/campaigns` | staff | `?status=`, `?company=`, `?payment_status=`, paginated |
| GET | `admin/advertising/campaigns/{id}` | staff | full review payload |
| POST | `…/{id}/verify-payment` · `…/{id}/reject-payment` | staff | `IsAdminAccount` (staff flag); anonymous 401, non-staff 403 |

No DELETE. The lifecycle actions `…/submit` and `…/cancel` take **no client data**: no body, or an
empty JSON object / empty form (an empty mapping), works; **anything else** is refused with
`field_not_allowed`, never silently ignored — every key of a non-empty object (amount, quote,
status, payment, company, product, reference, …) and every non-object body (a JSON array even
when empty, a string, a number, a boolean, an explicit `null`). The check uses mapping
semantics, not truthiness: `[]`, `false`, `0` and `""` are falsey but are still bodies. The campaign payload accepts only `name, product, starts_on, ends_on,
provider_types, specialties, governorates`; status, payment/paid/verified fields,
amounts, rates, days, currency, quote, reference-as-proof, company and lifecycle
keys are refused with `field_not_allowed`; the admin decision bodies refuse
amount/currency/status/company/product. Owner payloads include `quote` and a safe
`payment` summary (no admin note, no verifier); the admin payload adds both. Error
codes: `pricing_unavailable`, `campaign_not_editable`, `campaign_not_submittable`,
`company_not_eligible` (403), `product_unavailable`, `invalid_transition`,
`payment_not_pending`, `payment_quote_mismatch`, `quote_amount_too_large`, `campaign_ended`, plus per-field validation codes
(`dates_invalid`, `start_in_past`, `end_in_past`, `governorate_inactive`,
`specialty_inactive`, `product_not_found`, …). Audit events:
`advertising.campaign.created|updated|submitted|activated|cancelled`,
`advertising.payment.created|verified|rejected`, and
`advertising.rate.created|updated` (recorded by the rate admin).

## Django admin

Only `AdvertisingRate` is editable (price > 0, supported currency, no delete). Saving goes
through `services.save_rate`: activating a rate locks every active rate and the target in
primary-key order, retires the previous one and activates the new one in one transaction, so
concurrent activations serialize. The partial unique constraint `advertising_rate_one_active`
remains the final guard; the only case that can still reach it is two simultaneous
first-ever active rates (no stable row to lock), which surfaces as a message in the admin
("Another rate was activated at the same time"), never a 500 or two active rates. Campaigns, payments and target rows are inspection-only: the admin
can neither activate a campaign, mark a payment verified, rewrite a status nor change
an amount. Lifecycle goes through the services and API.

## Web

- `/company/advertising` (`RequireRole MEDICAL_COMPANY`; linked from the company workspace
  and the header): dashboard, paginated campaigns with badges, a form limited to
  owner-editable data with structured targeting checkboxes, a "Current backend quote"
  preview, submit, cancel an ACTIVE campaign. No amount, status or "paid" input, no
  fake bank details, QR code, provider or receipt upload. Only drafts show Edit; a draft
  without dates or with an unpublished product is not offered Submit (guidance only —
  the backend decides and its typed refusals are shown). Saved targets that are no
  longer active stay visible so the draft can be fixed.
- The product selector follows the backend's pagination until `next` is null — no page cap, so a company with any number of products can select every one (guards only against a backend that stops advancing). Admin campaign queries load the payment's verifier account together with the payment, so the list does not query one account per verified campaign.
- Admin console → Advertising tab: campaigns awaiting payment by default, with company,
  product, dates, targeting, quoted rate/days/amount and payment state; **Verify**
  (method, reference, note) and **Reject** (reason) via `ApiActionButton`.
- `/marketplace`: a "Sponsored / إعلان ممول" section from the backend only, each card
  labelled and linking the existing product page; the backend paginates (20 per page), so
  while it reports a `next` page a local **Load more** control appends the following page in
  the backend's order (page 1 stays rendered, the control is disabled while loading, a failed
  page shows a local retry, no duplicate ads, no page cap) — every paid campaign stays
  reachable and the browser still filters/ranks nothing; loading, error/retry and empty states
  are local, so the organic catalogue never breaks.
- Every label, state and error is available in Arabic and English.

## Security summary

Ownership from the session; lifecycle, price and payment state server-owned and
tamper-tested; company/product/provider state re-read under locks (races proven with
real second connections: verify vs reject, stale company role, product deactivation,
rate change, row locks); campaign targeting only narrows product targeting; no secrets
or payment credentials stored; no new infrastructure (no Redis/Celery/worker/webhook).

## Deferred

Payment gateway and webhooks (owner's provider choice), refunds/credits, media and
receipt uploads, non-product or real-estate campaigns, paid ranking tiers, analytics
(Phase 10), chat and notifications (Phase 9).
