# Current State

Date: 2026-10-02
AI/Engineer: ChatGPT
Branch: `feat/phase9b-conversations` (from `main` `882c97cb66c7dc999009583659733b4847a7d427`)
Current Git Tip: run `git rev-parse HEAD` (no moving SHA pinned here)
Phase 9A Merge Baseline: `882c97cb66c7dc999009583659733b4847a7d427` (PR #10; post-merge CI #224 green)

- **Phase 9A — Persistent Notifications is DONE and merged** through PR #10.
- **Phase 9B — Generic Conversations & Messages is CURRENT on `feat/phase9b-conversations`.**
- **Phase 9C — FCM push has not started.**
- Do not merge Phase 9B until exact-head CI and acceptance review are green and the owner explicitly says **`merge it`**.

## Exact next step

1. Finish exact-head Phase 9B CI.
2. Regenerate/commit `docs/api/openapi.yaml` if freshness fails.
3. Open a draft PR into `main`.
4. Run exact-head P1/P2 acceptance review (and Codex if available).
5. Fix confirmed blockers only, re-run exact-head CI.
6. Wait for explicit owner **`merge it`** before merging.
7. Do not start Phase 9C before Phase 9B merge + post-merge main CI.

## Phase 9B summary — Generic Conversations & Messages

- New backend app: `backend/apps/chat/`.
- Generic domain: `Conversation`, `ConversationParticipant`, immutable text-only `Message`.
- Enabled creation context: Reservation only. Participants are derived from the locked reservation; client account IDs are never accepted.
- One conversation per context by DB uniqueness; one participant row per account/conversation; one sequence number per conversation/message.
- Participant-scoped REST APIs: conversation list, bounded message history, send, observed-sequence read receipt, aggregate unread count.
- Read cursor is `last_read_sequence`. The client submits only the highest sequence it actually rendered; a later concurrent message remains unread.
- Sender is server-owned; undeclared write fields are rejected. Message body is trimmed, nonblank and bounded to 2000 in serializer + service boundary.
- Foreign/missing conversation references are non-disclosing 404s.
- Django admin is inspection-only.
- Web: `/messages`, `/messages/:id`, header unread badge, patient/provider reservation entry actions, Arabic/English.
- Existing jobs `RecruitmentMessage` is untouched.
- No FCM, WebSockets, Redis, Celery/workers, attachments, group chat or arbitrary account-to-account messaging.
- See `docs/CHAT.md` and ADR-049.

## Phase 9A merged baseline

- Persistent PostgreSQL notifications remain authoritative (ADR-048).
- Reservation post-commit receivers, safe payload, read-time localized presentation, recipient-scoped REST API, web notification center/header badge.
- Accepted branch head before merge: `a6ed6500da2349c5f59d27102e56559cc7bc55c9`.
- Merge commit: `882c97cb66c7dc999009583659733b4847a7d427`.
- Post-merge CI #224 green: Backend, Web and OpenAPI.
- No FCM/Redis/Celery/WebSockets.

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
