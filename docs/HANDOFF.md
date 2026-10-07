# Current State

Date: 2026-10-07
Branch: `feat/phase11f-release-hardening` (from `main` `5805713cbb119579681448dbc16773ed1cc85cb2`, Phase 11E merge; post-merge CI #331 green)
Current Git Tip: run `git rev-parse HEAD` (no moving SHA pinned here)

- **Phases 9A–9C, Phase 10 and Phase 11A–11E are DONE and merged.** Phase 11E: PR #18, accepted head `c2d658a4a25b4fc927258c5ac146967c79f0c5b0`, merge `5805713cbb119579681448dbc16773ed1cc85cb2`, post-merge CI #331 green.
- **Phase 11 — Flutter mobile is CURRENT, subphase 11F** (release hardening). Work only on `feat/phase11f-release-hardening`; Phase 12 must not start until 11F is accepted, merged and post-merge CI is green.

## Phase 11F summary — release hardening (see ADR-058 / MOBILE_RELEASE.md)

- Android release builds no longer use the debug signing key. Four `RACHEETA_ANDROID_*` environment variables provide the production signing material; release tasks fail closed when they are absent. CI uses a throwaway one-day key only to prove the build path.
- Android main/release explicitly has INTERNET permission and `usesCleartextTraffic=false`; debug overrides cleartext only for the local emulator HTTP backend. App display name is Racheeta; version is 1.0.0+1. iOS display name is Racheeta and its bundle id is unchanged.
- CI adds Android release AAB and macOS iOS release/no-codesign builds with `APP_ENV=production` and an HTTPS API origin. Flutter unit/widget tests add signing/network policy, accessibility/tap-target, 200% text scale and lazy-list checks.
- Required manual actions before public store submission: owner-controlled Play/App Store records and signing credentials, production HTTPS API URL, final store metadata/privacy/support URLs and approved production icon/branding; Firebase/APNs client configuration only if push is enabled on those store builds.

## Phase 11E summary — chat, notifications and FCM client (see ADR-057)

- Code: `mobile/lib/features/{notifications,chat,push}/`, `app/push_bootstrap.dart`; routes `/notifications`, `/chat`, `/chat/:id`; Home *Explore* entries *Notifications* and *Messages* (every account; unread badges from the backend counts); *Message the provider/patient* button on both reservation details (`OpenConversationButton`).
- Endpoints used (existing 9A–9C; the push-device endpoints gained the authorized `ownership_seq` ordering field in the P1 fix): `GET /notifications/`, `/notifications/unread-count/`, `POST /notifications/{id}/read/`, `/notifications/read-all/` (empty JSON object), `POST /notifications/push-devices/` (idempotent upsert `{token, platform: ANDROID}`) and `/push-devices/unregister/` (204); `GET /chat/conversations/`, `GET|POST /chat/conversations/{id}/messages/` (page 1 = latest page, chronological inside each page; body 1..2000), `POST /chat/conversations/{id}/read/` `{through_sequence}`, `GET /chat/unread-count/`, `POST /chat/reservations/{id}/conversation` (the only way a conversation starts).
- Read semantics (as the server defines them): fetching a thread does NOT mark it read. The thread screen sends one `POST .../read/` with the highest sequence it loaded, only when it loaded a message from the other side newer than what it already marked; a failure is not retried in a loop and a later refresh may try again. Notification rows are marked by an explicit tap (one POST, duplicate taps ignored); the list and the counts are then reloaded from the backend, never patched locally.
- Push payload (backend `push_service.py`): only `{type: notification, notification_id, event_type}` or `{type: chat_message, conversation_id}` plus a generic title/body; no resource ids and no account id. A notification push opens the notification centre; a chat push opens `/chat/<validated uuid>`; unknown or malformed data opens nothing. Notification rows open the reservation (provider or patient side from the account's capability) only for the known events/resource and a UUID id.
- Account isolation: lists/threads/counts are keyed by account (a new account starts from loading); the thread key is `(account, conversationId)`; the composer, its draft, busy flag and errors are keyed by account; mutations use `runAsAccount` (late success or error of A is dropped under B, nothing invalidated); the token lifecycle and the tap coordinator are account-bound (see below).
- FCM: `firebase_core 4.15.0`, `firebase_messaging 16.7.0` (exact pins). Firebase is initialised from `--dart-define FIREBASE_API_KEY|FIREBASE_APP_ID|FIREBASE_MESSAGING_SENDER_ID|FIREBASE_PROJECT_ID` (public client identifiers; no `google-services.json`, no Gradle plugin, no secret in the repo); if any is missing push is disabled (`DisabledPushSource`) and the app is otherwise unchanged. Permission (Android 13+ `POST_NOTIFICATIONS`) is asked once from an explicit button on the notification centre, never at start-up; denial leaves persistent notifications and chat fully working. The token is registered only for the signed-in account with permission (re-read on every synchronisation, including token refreshes), re-synchronised on a refresh, and unregistered (best effort, 3 s bound) BEFORE credentials are cleared on logout. **Ownership protocol.** `POST /notifications/push-devices/` transfers the globally unique token to whichever account calls it, and HTTP gives no ordering, so a request that lands late (even one the client gave up on after a timeout) could re-assign the token to an account that is no longer signed in. The authorized fix is a server-enforced client sequence: both ownership endpoints (register AND unregister) carry `ownership_seq`; `PushDevice.ownership_seq` (nullable bigint, migration `0003_pushdevice_ownership_seq`) stores the highest applied value; under the token row lock an operation changes owner or active state only if its sequence is strictly greater, and an older, equal or missing sequence on a sequenced row changes nothing (register answers a typed `409 stale_ownership`, an exact replay by the active owner is `200`, unregister stays `204`). A sequenced unregister for an unseen token leaves an inactive ordering marker (retained durably with no count- or time-based expiry because the stored sequence is ordering state) so a register overtaken by its own unregister cannot resurrect the account. Unsequenced (legacy) requests keep working only on rows that were never sequenced and can never supersede a sequenced row. The client allocates `max(lastPersisted + 1, wall-clock microseconds)`, persisted before sending, in the one ownership lane (never reset by an account switch, logout, restart or clock rollback). The final owner is therefore independent of arrival/commit order; the client lane (serialised, session-independent, ordered logout cleanup) and the bounded repair registration remain as resilience (e.g. when the lost request was the current account's own registration) but correctness no longer depends on them. Tokens are never logged.
- Foreground push: refresh only (counts, lists, an open thread). Background tap and the launching push go through `PushIntentCoordinator`: held while the session restores, delivered once when signed in, dropped if the session ends signed out, validated, deduplicated (Firebase message id, or a 5 s window), through the existing `GoRouter` push. No local notification package, no background data handler (the system tray shows the backend's notification message).
- Gaps (recorded, not invented): conversations start only from a reservation; no attachments, group chat, typing/online state; push payload carries no resource id so a notification push opens the centre rather than the reservation; no Firebase project/client configuration exists in the repository, so real FCM transport is unverified; iOS push (APNs) is not configured; a logout-less session expiry cannot unregister (the backend transfers the token on the next registration).
- Android emulator check: (2026-10-06) The Firebase-enabled debug arm64 APK built successfully (`flutter build apk --debug --target-platform android-arm64`), but the emulator run was NOT completed: the 3 GB disk watchdog stopped Android work twice (free space fell to 2.6 GB during the Gradle build with the emulator booting and to 2.87 GB during the emulator boot), so no 11E screen was exercised on an emulator or device and none is claimed. The scratch backend, database and credentials were removed. Real FCM transport was not tested either: the repository has no Firebase client configuration, so push runs disabled; the token, routing and lifecycle logic is covered only by automated tests with a fake push source.
- Tests: 609 Flutter tests (backend 1790) (fake push source, scripted backend); contract tests also pin the push payload keys and vocabularies to the backend source.

## Phase 11D summary — marketplace, jobs and real estate (see ADR-056)

- Code: `mobile/lib/features/{real_estate,marketplace,jobs,explore}/`, shared `shared/search/search_query.dart`, `shared/widgets/{paged_list,search_filter_bar}.dart`, `features/auth/application/account_scope.dart` (`AccountScoped`, `runAsAccount`). Navigation: an *Explore* section on Home (bottom bar unchanged); entries: Jobs and Real estate (everyone), Marketplace (`marketplace.view_targeted_products`), Company workspace (`marketplace.manage_own_products`), Seller workspace (`real_estate.manage_own_listings`), Recruiter workspace (server dashboard index lists `recruiter`; recruiter membership is not a `/me` capability). All routes are flat: `/real-estate`, `/real-estate/listing/:id`, `/seller`, `/seller/listings`, `/seller/listings/:id`, `/marketplace`, `/marketplace/product/:id`, `/company`, `/company/products`, `/company/products/:id`, `/jobs`, `/jobs/applications` (before `/jobs/:id`), `/jobs/:id`, `/recruiter`, `/recruiter/jobs`, `/recruiter/jobs/:id`.
- Endpoints used (existing only): real estate `GET /real-estate/listings[/{id}]` (public), `GET /real-estate/owner/dashboard|listings[/{id}]`, `POST /real-estate/owner/listings/{id}/publish|unpublish`; marketplace `GET /marketplace/categories|products[/{id}]`, `GET /marketplace/company/dashboard|products[/{id}]`, `POST /marketplace/company/products/{id}/activate|deactivate`; jobs `GET /jobs[/{id}]` (public), `POST /jobs/{id}/apply`, `GET /jobs/me/applications`, `POST /jobs/me/applications/{id}/withdraw`, `GET /dashboards/` and `/dashboards/recruiter`, `GET /jobs/employer/jobs[/{id}]`, `POST /jobs/employer/jobs/{id}/close`.
- Filters sent are only the documented backend parameters (jobs: `q`, `profession`, `employment_type`, `work_mode`, `governorate`, employer `status`; real estate: `search`, `transaction_type`, `property_type`, `governorate`, `ordering`; marketplace: `category` only — the API has no search); search is debounced (400 ms), stale responses are rejected, pagination restarts on any query or account change.
- Mutations (all via `runAsAccount`: capture the initiating account, one request, result and invalidation dropped if another account is signed in or the screen was unmounted; never retried; buttons keyed per account): publish/unpublish listing (unpublish confirmed), activate/deactivate product (deactivate confirmed), apply, withdraw (confirmed), close job (confirmed).
- Time/money: job application deadlines are calendar DATES (`parseCalendarDate`, never converted between zones); instants keep the 11B policy; prices and salaries are the backend's decimal strings with the backend currency (no conversion); salary only when `salary_visible`.
- External links: none are opened. Contact values are shown as plain text exactly as the API returns them.
- Gaps (recorded, not invented): no create/edit forms for products, jobs or listings; no applicant management, interviews, invitations, résumé/profile editing; no images/uploads; the marketplace API has no search; `/dashboards/company` (advertising included) is not used — the company workspace uses `/marketplace/company/dashboard`; billing/verification requests and facility membership UI stay on the web.
- Android emulator check: (2026-10-05, debug arm64 build, Pixel_10_Pro_XL image, local scratch backend/database with throwaway accounts, all since deleted; the emulator was very slow under host load, with ANR dialogs dismissed by tapping Wait, so only the flows below were exercised) **Seeker:** sign-in showed only Jobs and Real estate under Explore; the jobs list showed the 3 published jobs (draft and closed hidden), a salary and the deadline as a calendar date; one *Send application* tap produced exactly one `POST /jobs/{id}/apply` (201) and the sent state; *My applications* listed it, withdrawal asked for confirmation first and then sent exactly one POST (200); the real-estate list showed the 2 published listings (draft hidden) and a listing detail; the language switch gave RTL Arabic (mirrored layout, Arabic vocabulary labels and dates) on Home, Jobs and Account. **Recruiter:** sign-in showed the Recruiter workspace entry; the organisation dashboard and the organisation's 5 jobs loaded; closing a job asked for confirmation and sent exactly one `POST .../close` (200), after which the page showed *Closed*. **Company:** the Company workspace and own products (including an inactive one) loaded; *Activate* sent one POST (200); *Deactivate* asked for confirmation and *Keep active* sent nothing. **Seller:** the Seller workspace dashboard and own listings loaded; *Publish* of a draft sent one POST (200) and the page showed it published. Sign-out followed by another role's sign-in showed only that account's entries and data. Not exercised on the device: the cover-note field (typing triggered an emulator ANR; covered by widget tests), the marketplace provider catalogue (needs a verified provider account — covered by widget tests), search/filter sheets, pagination beyond one page, error paths (403/409), unpublish, release builds.
- Tests: 465 Flutter tests; contract tests also pin the job/real-estate vocabularies to `backend/apps/*/types.py`.

## Phase 11C summary — provider & facility workspace (see ADR-055)

- `mobile/lib/features/provider/` (data · application · presentation), destinations *Dashboard*, *Availability*, *Bookings* shown only when `/me` lists `reservations.manage_received`; routes `/workspace`, `/workspace/availability`, `/workspace/availability/new`, `/workspace/reservations`, `/workspace/reservations/:id` (flat, not nested).
- Endpoints used (all existing, no backend change): `GET /dashboards/`, `/dashboards/doctor|facility`, `GET /providers/me/services`, `GET|POST /reservations/provider/availability`, `DELETE /reservations/provider/availability/{id}`, `GET /reservations/provider`, `/reservations/provider/{id}`, `POST /reservations/provider/{id}/transition`.
- Permission: UI gate is the `/me` capability; the backend requires role PROVIDER **and** a provider profile (403 → "create your provider profile on the website"). The dashboard kind comes from the server's index (facility wins over doctor), never from a role label. Individual providers and facilities share the same availability/reservation endpoints; the only difference is the dashboard (facility adds membership counts) — no facility-wide practitioner aggregation exists in the API and none is invented.
- Transitions: PENDING → CONFIRMED (before start) / REJECTED / CANCELLED; CONFIRMED → COMPLETED and NO_SHOW (after start) / CANCELLED; offered as a hint from status + start time, the backend decides (`invalid_transition` is shown and the record refetched). Destructive ones need a confirmation dialog.
- Availability: only an active service with a duration can be used; the start is picked in device-local time and sent as UTC (`localToUtcProvider`); overlap, "must be in the future" and in-use removal are the backend's (`slot_conflict`, `invalid_availability`, `slot_unavailable` → own messages). The provider list endpoint has no filter and includes inactive/past slots, so the screen shows active, not-yet-ended slots from the loaded pages (page size 100) with an explicit "load more" note.
- Account isolation: provider data families are keyed by account id (a new account starts from loading, never from the previous value); list notifiers rebuild on account change; screen-local state resets via `ref.listen(accountIdProvider)`; mutations run through `_asAccount` (capture the account, drop a result and skip invalidation if the account changed); tested with the account switched through a `/me` refresh while the screen stays mounted.
- Latent 11B leak fixed here: `reservationDetailProvider` is now keyed by (account, id).
- Gaps (recorded, not invented): no profile or service editing on mobile; facility membership endpoints exist (`/providers/me/memberships*`) but staff management is out of 11C; no `reason` on transitions in the UI (the API accepts one); the availability list has no filter/booking state; no per-slot "reserved" flag.
- **Android emulator check (2026-10-05, debug build, Pixel_10_Pro_XL image, local scratch backend with throwaway data, since deleted):** the app launched; sign-in as a doctor showed the provider navigation (Dashboard, Availability, Bookings) and none of the patient destinations; the dashboard, the availability list (grouped by local day) and the bookings list loaded real data; one real PENDING → CONFIRMED transition sent exactly one POST (200), showed the success message, updated the status/history and then offered only *Cancel*; the dashboard reflected it on the next visit; the language switch gave RTL Arabic on every screen; sign-out followed by a facility sign-in showed only the facility's own dashboard (no doctor data). Not exercised on the device: slot creation/removal and the date/time pickers (covered by widget tests), the 403 no-profile path, release builds.
- Tests: 283 Flutter tests (scripted HTTP adapter, injected clock/wall clock/local→UTC; dio calls from test bodies under `tester.runAsync`; never `pumpAndSettle` while a button shows a progress indicator for a dialog), OpenAPI contract tests over `docs/api/openapi.yaml`.

## Phase 11B summary — patient discovery and reservations (see ADR-054)

- `mobile/lib/features/discovery/` (provider search + filters sheet + detail + booking page), `mobile/lib/features/reservations/` (list, detail, cancel), `core/time/` (timezone policy), `core/paging/` (epoch-protected paged notifier), `features/auth/application/account_scope.dart` (every patient provider watches the account id, so logout/switching discards state).
- Endpoints used (all existing, no backend change): `GET /providers`, `/providers/{id}`, `/providers/{id}/availability`, `/specialties`, `/geo/governorates`, `/geo/cities`; patient-only `POST /reservations`, `GET /reservations/me`, `GET /reservations/me/{id}`, `POST /reservations/me/{id}/cancel`.
- Backend authoritative: availability is a snapshot, booking and cancellation answers are final; `Cancel` is offered from status + start time as a hint only (no `can_cancel` field exists).
- Timezone: timestamps must carry an explicit offset (else the response is rejected), kept as UTC, displayed and grouped in the device's local time; documented in `RESERVATIONS.md`.
- Reservation creation is never retried and duplicate taps are blocked (no idempotency key exists); a taken slot refetches availability and clears the selection.
- Gaps recorded for later phases: no `can_cancel` field, no idempotency key on `POST /reservations`, no provider timezone, provider/service images and coordinates are not rendered, availability is requested for a 30-day window, `provider_id` is documented as always present although the backend nulls it when a provider is deleted (the app tolerates null).
- Tests: 168 Flutter tests (scripted HTTP adapter, injected clock/wall clock; widget tests must run `dio` calls through `tester.runAsync`), an OpenAPI contract test reading `docs/api/openapi.yaml`.

## Phase 11A summary — Flutter foundation (see ADR-052, ADR-053)

- `mobile/`: Flutter 3.47.6 / Dart 3.13.5, feature-oriented (`app/`, `core/{config,api,storage,logging}`, `features/{auth,home,account,shell}`, `shared/`, `l10n/`). Riverpod (state/DI), go_router (session-driven redirects), dio (HTTP), flutter_secure_storage (refresh token), shared_preferences (language only).
- One `ApiClient` against `/api/v1/`: base URL from `--dart-define`, bearer header, `Accept-Language` ar/en, connect/send/receive timeouts, cancellation, typed `ApiException` from the error envelope, `Page<T>`, safe logging (method/path/status only).
- Session: access token in memory, refresh token persisted and rotated; 401 → one single-flight refresh → one retry; definitive refresh rejection clears the session and returns to login with an expiry notice; transient failure keeps the session. Logout clears local state first and revokes best-effort. `SessionScope` aborts in-flight requests of an ended session; generation/ticket checks drop stale results (logout, account switching).
- Screens: restoration/offline-retry, login (presence-only validation, server field errors), authenticated shell (bottom bar <720dp, rail wider), home, account (details from `/me`, language, confirmed logout). Navigation destinations come from a registry filtered by `/me` role and permission codes; 11B+ append to it.
- Tests: unit + widget tests with a scripted HTTP adapter (no network, no credentials). CI: new `mobile` job (pinned Flutter, `pub get --enforce-lockfile`, format check, `analyze --fatal-infos`, `test`). Backend/web jobs untouched.
- Not done by design: reservations, provider management, marketplace, jobs, real estate, chat, FCM device registration (11E), payments, signing/Firebase config, store release. The IBM Plex Sans Arabic font is not bundled yet (system font). Android/iOS builds were not run in the authoring environment (no platform SDKs); only `flutter analyze`/`flutter test` were.

## Phase 10 summary — Dashboards & Analytics (see `docs/DASHBOARDS.md`, ADR-051)

- New backend app `apps/dashboards/` — **no models, no migrations**. `services/` (per-domain aggregates), `access.py` (single source of who may open what; used by permissions and the index), `permissions.py`, `serializers.py` (explicit output contracts), `views.py`, `urls.py`.
- Endpoints (all `GET`, read-only, parameterless, `private, no-store`): `/api/v1/dashboards/` (index), `/patient`, `/doctor`, `/facility`, `/company`, `/recruiter`, `/admin`. The real-estate owner dashboard is the existing `/real-estate/owner/dashboard`.
- Reused, not rebuilt: marketplace + advertising `dashboard_summary` (company), real-estate owner summary, notification/chat unread counts, `has_role`/`IsAdminAccount`/`membership_for`/entitlements.
- Authorization is current-state and server-side; isolation is tested across accounts and organisations; recruiter applicant aggregates follow the applicant-read gate and are `null` with a reason when withheld; admin dashboard is counts only.
- Web: `/dashboard` hub (`web/src/pages/dashboard/`), Dashboard header link, Arabic/English; keyed by account, no polling, only the selected dashboard loads.
- Deferred (no authoritative data): revenue, views, impressions, conversions, trends, facility-wide practitioner reservations, recruiter time-to-hire, unread recruitment messages.

## Phase 9C summary (merged via PR #12, merge `3ff9cdd`) — FCM push (see `docs/PUSH.md`, ADR-050)

- PostgreSQL stays authoritative; push is a best-effort hint sent after commit.
- `notifications_pushdevice`: globally unique token, one owner (`request.user`), platforms `ANDROID|IOS|WEB`, transfer on account switch, ≤10 active devices/account.
- API: `POST /api/v1/notifications/push-devices/` (register/upsert) and `.../unregister/` (idempotent `204`, no ownership disclosure). Tokens are never returned.
- `apps.notifications.push` (`PushSender` with ONE method `send_batch`, Disabled default, `FirebaseAdminPushSender` = one `send_each_for_multicast` under a hard 3 s deadline, ≤4 in-flight batches, 10 s fail-fast window) and `push_service` (never raises; per-token permanent errors deactivate, everything else keeps the device). `on_commit` is synchronous, so this bound is what keeps requests from hanging on Firebase; see `PUSH.md`.
- Triggers: newly created persistent notifications; new chat messages (other participant only) via `apps.chat.hooks.message_sent`.
- New env `PUSH_SENDER` (reuses `FIREBASE_CREDENTIALS_FILE`); `firebase-admin==7.7.0` in production requirements.
- Deferred: web/mobile token acquisition (no Firebase client/service worker in repo; mobile is Phase 11), workers/queues, realtime.

## Phase 9B summary (merged) — Generic Conversations & Messages

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
