# Phase 11B handoff (work in progress)

Repo `moahaimen/enhanced_racheeta`, branch `feat/phase11b-patient-reservations` (from `main` `9282db3`, Phase 11A merged, CI #301 green). One WIP commit is pushed. No PR yet. Do not merge; do not start 11C; only the owner authorizes merges. Do not commit model identifiers.

## Task (user's spec, short)
Flutter patient discovery + reservations in `mobile/`, reusing 11A (Riverpod, go_router, one dio ApiClient, session, l10n ar/en, shared widgets). No invented endpoints/fields/statuses, no backend changes, no FCM/payments/provider side. Backend is authoritative (availability, cancellation). Timezone policy explicit. No auto-retry of reservation creation. Every action: spinner + duplicate-submit guard. Account switching/logout must isolate state and drop stale responses. Finish: tests, docs, format/analyze/test, push, DRAFT PR to `main`, report (verified start SHA, final HEAD, screens, endpoints, behaviour, timezone, security, test results, CI, docs, limitations, PR URL), then stop for P1/P2 review.

## API inventory (from docs/api/openapi.yaml)
- `GET /providers` (public, paginated): `search, kind(PRACTITIONER|FACILITY), type(ProviderTypeEnum), specialty(slug), governorate(id), city(id), ordering(display_name|-display_name|created_at|-created_at), page, page_size`.
- `GET /providers/{id}`; `GET /providers/{id}/availability?service&from&to` (unpaginated array, UTC); `GET /specialties`; `GET /geo/governorates`; `GET /geo/cities?governorate=`.
- Patient only (role PATIENT, else 403): `POST /reservations {availability_slot, patient_note<=1000}` -> 201; `GET /reservations/me` (paginated, newest start first, no status filter); `GET /reservations/me/{id}`; `POST /reservations/me/{id}/cancel {reason<=500}` -> 200.
- Errors: envelope codes `slot_unavailable|slot_conflict|service_unavailable|provider_unavailable` (409), `invalid_transition|invalid_availability` (400), `not_found` (404).
- Rules (docs/RESERVATIONS.md): statuses PENDING, CONFIRMED, COMPLETED, REJECTED, CANCELLED, NO_SHOW; patient may cancel own PENDING/CONFIRMED before start. API has NO `can_cancel` field (UI offers Cancel from status+start time as a hint only; backend decides). Backend is UTC, no provider timezone field (gap to document). No idempotency key on create (gap to document). No rescheduling.

## Done in the WIP commit (all under mobile/)
- `lib/core/api/json_reader.dart`, `core/time/{instants,time_providers}.dart` (strict offset-required parse, UTC internally, device-local display, injectable now/wallClock), `core/paging/paged_notifier.dart` (epoch-based stale protection, noRetry), `ApiClient` wraps FormatException as `invalid_response`; `error_messages.dart` maps conflict codes, notFound -> generic.
- `features/discovery/{data,application,presentation}`: models, `DiscoveryApi`, `DiscoveryFilters`, providers (filters, search controller, detail, availability), discovery page, filters sheet, provider card, provider detail, booking page.
- `features/reservations/{data,application,presentation}`: models, `ReservationsApi`, list controller, detail provider, `bookSlot`/`cancelReservation`/`invalidateReservationData`, list + detail pages.
- `features/auth/application/account_scope.dart` (`accountIdProvider`; all patient state watches it).
- Router routes `/providers`, `/providers/:id`, `/providers/:id/book/:serviceId`, `/reservations`, `/reservations/:id`; destinations `appDestinations` (Discover, Reservations for patients only); `AsyncActionButton.confirm` gate.
- ARB strings ar+en added, generated code regenerated (`flutter gen-l10n`).
- Tests: `test/support/patient_support.dart` (fixtures, fixed now 2026-10-03 09:00Z, UTC+3 wall clock, `pumpPatientApp`), `test/discovery_test.dart`. `flutter analyze --fatal-infos` was clean before the tests were added.

## Known state / next steps
1. `test/discovery_test.dart`: last test ("logout and a different login...") fails only because the test calls `pumpPatientApp(path:'/providers')` with a hanging request (pumpAndSettle times out). Fix: start at '/', then `h.container.read(routerProvider).go('/providers')` and `pump(50ms)` (never pumpAndSettle while a request hangs).
2. Write remaining tests: provider detail (booking button only with `reservations.create_own` and duration != null; 404 generic text); booking (slots grouped by local day, midnight crossing 21:30Z -> next day at UTC+3, empty, 409 conflict -> banner + refetch + selection cleared, success view + POST body, double-tap = 1 POST, patient_note validation, 403, no retry after failure, note >1000 blocked, invalidation refetch); reservations list (upcoming/past headings, pagination, empty, error/retry), detail (transitions), cancel (decline = no POST; confirm = POST + message; 400 invalid_transition -> localized message + refetch; not offered for past/cancelled); instants/JsonReader unit tests; Arabic RTL + English for new screens; account switching on reservations; contract test reading `docs/api/openapi.yaml` fields used by models if feasible.
3. Check existing 85 tests still pass (`router_and_nav_test` already updated; notFound message change may affect others).
4. Docs: MASTER_PLAN (11A merged: PR #14, merge `9282db3`, CI #301; 11B in progress, not completed), PROGRESS, HANDOFF, RESERVATIONS.md (mobile section + timezone policy), API.md, DECISIONS (ADR-054: patient state/stale protection, timezone), SECURITY (mobile patient), mobile/README. Mention gaps: no can_cancel field, no idempotency key, no provider timezone, images not rendered, coordinates not rendered, availability window 30 days.
5. Run in `mobile/`: `export PATH=/home/user/flutter/bin:$PATH CI=true`; `dart format --set-exit-if-changed .`; `flutter analyze --fatal-infos`; `flutter test`. No backend change, so backend/web verification not required; confirm `git diff --stat main` touches only mobile/, docs/.
6. Secrets scan, push, open DRAFT PR (title "feat(mobile): Phase 11B ..."), watch CI (`gh run list --branch ...`), final report, stop.

## Environment notes
Flutter 3.47.6 at `/home/user/flutter` (a new environment must reinstall it; CI uses subosito/flutter-action 3.47.6). Riverpod 3: `Override` from `package:flutter_riverpod/misc.dart`; providers take `retry:`. Commit trailers: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: <session url>`; PR body ends with the Claude Code generated line and session link. GitHub only via MCP tools in cloud sessions.
