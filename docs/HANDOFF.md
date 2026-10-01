# Current State

Date: 2026-10-01
AI/Engineer: Claude (Sonnet 5.5)
Branch: `main`
HEAD: `46f4d8ffb2465f3bee35bff7ca1c432540034816` (merge of PR #9)

- **Phase 8 — Advertising and Payments is DONE and merged** through PR #9. Accepted head `25b4e6ef9f723c7ac41850f4167367a281f3259f`; the final exact-head Codex review found no major issues; post-merge CI #216 (id `36854496027`) is green (Web, Backend, OpenAPI freshness).
- Tests on `main`: **1473 backend, 389 web**.
- **Phase 9 — Chat and Notifications is the next / current phase.** No Phase 9 code exists yet (no `apps/chat`, no `apps/notifications`, no migrations, endpoints, pages, Firebase dependency or environment variables).

## Exact next step

Branch `feat/phase9-chat-notifications` from this `main` and start with **Phase 9A** (below). Re-read the Phase 9 section of `MASTER_PLAN.md` first; its scope is unchanged: conversations, messages, notification records, Firebase push, realtime only if justified. Architectural rule: **REST** for initial message/history loading, **FCM** for push, **WebSockets only later if justified**, and no Redis merely because WebSockets might be useful later.

## Phase 9 handoff notes

### Existing facts that shape the design

- **Jobs messaging already exists.** `backend/apps/jobs/models.py` defines `RecruitmentMessage`: scoped to one `JobApplication`, immutable, text-only, sender/account backed, protected by the jobs/recruitment authorization flow and contact-leak moderated (`MODERATION.md`). Inspect it **before** creating generic conversations so Phase 9 does not duplicate behaviour. Do not delete, migrate or redesign it as part of the first Phase 9 steps.
- **A reservation notification boundary already exists.** `backend/apps/reservations/hooks.py` defines the signals `reservation_created` and `reservation_status_changed`, emitted through `transaction.on_commit(...)` (so a rolled-back reservation never notifies). The file states that Phase 9 receivers may subscribe and create persistent notifications **without changing reservation transaction code**. This is the preferred first integration point.

### Recommended order (conservative)

- **Phase 9A — persistent notifications first.** PostgreSQL notification records: recipient `Account`, typed event/category, title/body or a safe presentation payload, optional resource reference, `created_at`, `read_at`. Authenticated, paginated list; unread count; mark one read; mark all read. Notifications are backend-created only, with the reservation hook receivers first. **No** Redis, Celery, WebSockets, Firebase credential work or background service yet. Add FCM only after persistent notification semantics are correct.
- **Phase 9B — generic conversations/messages via REST.** Do not migrate `RecruitmentMessage` yet. Do not let arbitrary users message arbitrary accounts until the business authorization rules are deliberately defined.
- **Phase 9C — FCM device registration and push delivery.** Persistent database notifications stay authoritative; push is best-effort delivery, never the source of truth.
- **Realtime.** WebSockets remain deferred unless UX requirements justify them. No Redis in anticipation of them.

## Phase 8 summary — Advertising and Payments (merged via PR #9)

- New `apps/advertising` (migration `0001_initial`): `AdvertisingRate` (admin-set daily price, **no seeded price**, one active by constraint), `AdvertisingCampaign` (DRAFT → PENDING_PAYMENT → ACTIVE | REJECTED; ACTIVE → CANCELLED; frozen after submission; price snapshot), normalized targets, `CampaignPayment` (one per campaign; `billing.PaymentRecord` untouched).
- Pricing: `(ends - starts).days + 1` × active rate (Decimal). `POST advertising/company/quote` is a preview; `services.submit_campaign` recomputes under the rate lock and snapshots. No rate → `pricing_unavailable`.
- Payments: no gateway/webhook. `services.verify_campaign_payment` (the future-gateway boundary) activates payment+campaign atomically after re-checking company (`MedicalCompany.can_publish`), product exposure (`Product.objects.exposable()`), targets and end date on locked rows; `reject_campaign_payment` rejects both. Lock order company+account → campaign → payment → product/rate.
- Visibility: `AdvertisingCampaignQuerySet.visible_to(provider)` — `ProductQuerySet.targeted_for` ∩ campaign narrowing ∩ ACTIVE + VERIFIED payment + date window, current-state, bounded queries. A campaign can only narrow Phase 6 targeting.
- APIs: company (dashboard, quote, campaigns, submit, cancel), admin (list/detail/verify-payment/reject-payment), provider (`advertising/marketplace`). Django admin: only the rate is editable. OpenAPI regenerated (no existing schema changed; `ProviderTypeEnum` and campaign enums pinned in settings).
- Web: `/company/advertising`, admin console Advertising tab, sponsored section on `/marketplace`, nav/company links, Arabic/English.
- Deferred: gateway/webhook, refunds, media/receipts, non-product/real-estate campaigns, analytics (Phase 10), chat/notifications (Phase 9). See `ADVERTISING.md`, ADR-047.
- PR #9 review fixes: `visible_to()` requires `specialty__is_active=True` on the matching specialty target; `views._require_no_body` rejects any body key on submit/cancel (`field_not_allowed`); `services._require_quote_coherent` runs in `verify_campaign_payment` (payment ↔ snapshot, never the current rate; `payment_quote_mismatch` 409); `services.save_rate` locks the rates it swaps (Django admin uses it; `RateActivationConflict` becomes an admin message). OpenAPI unchanged.
- PR #9 follow-up: `views._require_no_body` uses `isinstance(data, Mapping)` (empty mapping = no data; any non-mapping body, including `[]`, `false`, `0`, `""`, JSON null, is `field_not_allowed`).
- PR #9 Codex fixes: `services._require_quote_coherent` also checks `(ends_on - starts_on).days + 1 == quoted_days`; `views._admin_campaigns()` selects `payment__verified_by`; `loadAllMyProducts` (advertising workspace) follows `next` until null with only no-progress guards.
- PR #9 second Codex fixes: `SponsoredSection` appends later pages via a local Load more (`ApiActionButton`, abort on unmount, id dedupe); `_build_quote()` raises `QuoteAmountTooLarge` above `models.MAX_CAMPAIGN_AMOUNT` (from field metadata; `QuoteResponseSerializer.total` mirrors it).
- PR #9 third Codex fix: `advertisingFormat.formatMoney` formats decimal strings exactly (BigInt integer part, exact fraction, `Intl` separator; malformed input shown as received); `SponsoredSection` price uses it too. Advertising money is never converted to a JS number.
- Tests: backend 1473 passed, web 389 passed.

## Previous phase (Phase 7 — merged via PR #8)

Medical real estate (`REAL_ESTATE.md`, ADR-046): seller profiles, listings, one visibility rule, publication gate, owner dashboard, and the review hardening (current-seller eligibility on every mutation, live city→governorate visibility, historical geography recovery in the owner UI). Details are in `PROGRESS.md`.

## Previous session (Phase 5)

Continue Phase 5 — Reviews & Offers — without rebuilding existing work. Keep reviews tied to verified interactions, offers tied to provider-owned services, and avoid new payment/background infrastructure.

## Completed

- Phase 4 documentation on `main` corrected to reflect merged/accepted status and post-merge CI #148.
- Existing Phase 5 branch inspected and preserved; it already contained substantial Reviews & Offers implementation.
- Reviews:
  - one review per reservation;
  - patient must own the reservation;
  - reservation must be COMPLETED;
  - rating is 1–5;
  - provider/service snapshots retained;
  - public provider review list and patient review creation/list APIs;
  - provider discovery/detail exposes real aggregate rating/count.
- Offers:
  - provider creates offers only against an owned active service;
  - original service title/price/currency are snapshotted;
  - offer price must be below original price;
  - start/end validity is server checked;
  - public API exposes only active offers inside the current server-time window and on active services;
  - provider workspace supports paginated management.
- Web:
  - completed reservations can submit reviews;
  - provider detail shows real rating/reviews and current offers;
  - provider offers management page exists;
  - Arabic/English strings and loading/error/action patterns are wired.
- Fixed the latest Phase 5 CI failures:
  - mapped API field `service` to service-layer `service_id`;
  - updated provider discovery contract test for `average_rating` and `review_count`.

## Files Added

- `backend/apps/reviews/`
- `backend/apps/offers/`
- `web/src/api/endpoints/reviews.ts`
- `web/src/api/endpoints/offers.ts`
- `web/src/api/engagement.types.ts`
- `web/src/pages/offers/ProviderOffersPage.tsx`
- `web/src/pages/offers/ProviderOffersPage.test.tsx`
- `docs/REVIEWS_OFFERS.md`

## Files Modified

Provider serializers/views, reservation serializers/views, API registration/settings, provider cards/detail pages, patient reservations page, app routes/header, translations, tests, OpenAPI contract and project documentation.

## Database Migrations

- `reviews/0001_initial.py`
- `offers/0001_initial.py`

## API Endpoints Added/Changed

See `docs/REVIEWS_OFFERS.md` and `docs/api/openapi.yaml`.

## Architecture Decisions

- Reviews are evidence-backed: only the patient on a COMPLETED reservation can create the single review for that reservation.
- Offers are provider/service scoped and time-windowed by server state; clients cannot make an expired/future offer publicly active.
- Ratings shown in discovery/detail are aggregates of persisted reviews; no fabricated rating data.

## Security Decisions

- Public review/offer lookups require the provider to be discoverable.
- Review creation is ownership-scoped to the patient reservation.
- Offer creation/update is scoped to the authenticated provider profile.
- Offer service ownership and active state are re-checked under transaction locks.
- No billing, payment gateway, Redis, Celery, or file-upload surface was added.

## Tests Run

GitHub Actions on the Phase 5 branch:
- Backend: Ruff, Django checks, migration check, pytest, OpenAPI freshness.
- Web: TypeScript, lint, Vitest, production build.

## Test Results

Latest failing checkpoint `7a14fe17...`: 872 backend tests passed, 3 failed; web suite passed.
The three failures were corrected in commit `d3ca7b9f3965601f8bb41eabc82cb2359794684d`.
Current-head CI must finish before the Phase 5 PR is opened.

## PR #6 Phase 5 acceptance review (2026-09-28, on `a387bc7`)

| Finding | Fix |
| --- | --- |
| P2 #1 stale-service offers could be (re)activated | `update_offer` re-validates the linked service on the locked row whenever the result is active (`_locked_valid_service`, shared with creation: exists, same provider, active); `service_unavailable` (409) otherwise, nothing partially applied, no audit event. Deactivation of a stale offer and owner history are preserved. |
| P2 #2 unbounded anonymous public offers | `PublicProviderOfferListView` uses the repository's standard pagination (20/page, `ends_at, id` ordering); the web client, types and the provider-detail section paginate with the shared control. |
| P2 #3 review form for a deleted provider | `ReviewForm` renders only for COMPLETED, unreviewed reservations with a `provider_id`; the reservation stays visible through its snapshots. |
| P2 #4 / #5 nullable UUID contracts | `review_id` is annotated `UUIDField(allow_null=True)`; `OfferOwner.service_id` is `allow_null=True`; OpenAPI regenerated. |

Backend tests 886, web tests 249, no migration, OpenAPI regenerated (paginated public offers, nullable `review_id` and `service_id`).

## Known Problems

- Persistent notification delivery remains Phase 9.
- Offers do not add images because production media/object storage is intentionally deferred.
- Phase 5 acceptance review has not yet been run.

## Incomplete Work

- Confirm current-head CI is green.
- Ensure OpenAPI is current.
- Open the Phase 5 PR.
- Run final P1/P2 production-blocker review and fix only confirmed blockers.

## Required Manual Actions

None.

## Environment Variables Added/Changed

None.

## Railway/Infrastructure Impact

PostgreSQL migrations only. No new service, worker, cache, object storage, payment gateway, or environment variable.

## Exact Next Step

1. Confirm CI green on the current Phase 5 head.
2. If OpenAPI is stale, regenerate/commit it.
3. Open Phase 5 PR.
4. Run Codex review limited to P1/P2 production blockers.
5. Fix blockers, re-run CI, and merge only after explicit owner approval.

## Recommended Next Prompt

`Check Phase 5 CI and open the Reviews & Offers PR when green; then run a P1/P2 acceptance review.`
