# Current State

Date: 2026-09-28
AI/Engineer: ChatGPT (GPT-5.6 Sol)
Branch: `feat/phase5-reviews-offers`
Base: Phase 4 merged to `main` at `919bfe924736f4adfb38340ae742f181f0e825b5`; documentation cleanup followed on `main`.
Pull Request: not opened yet
Last Commit SHA: updated by the Phase 5 documentation checkpoint commit

## Goal of This Work Session

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
