# Racheeta mobile (Flutter)

The Racheeta patient/provider app. **Phase 11A** is the foundation (app shell, configuration, one
API client, email/password authentication, session management, localization (Arabic RTL / English)
and reusable UI). **Phase 11B** adds the patient side (provider discovery, detail, booking, "My appointments" with
cancellation). **Phase 11C** adds the provider and facility side (dashboard, availability, received bookings).
**Phase 11D** adds the marketplace, medical jobs and real estate behind an *Explore* section on Home.
**Phase 11E** adds chat, the persistent notification centre and the FCM client.
**Phase 11F (this change) is release hardening** (signing, store builds, audits) — see `docs/MOBILE_RELEASE.md`;
nothing unfinished is exposed in the app.

- Flutter **3.47.6** / Dart **3.13.5** (pinned in `pubspec.yaml`, CI and `docs/DECISIONS.md`)
- State: **Riverpod** · Routing: **go_router** · HTTP: **dio** · Secrets: **flutter_secure_storage**
- Backend: the existing `/api/v1/` REST API (`backend/`, OpenAPI is the source of truth).

## Layout

```
lib/
  main.dart                  entry point (config + ProviderScope)
  app/                       RacheetaApp, router (session-driven redirects)
  core/
    config/                  AppConfig (environment, base URL, timeouts, https rules)
    api/                     ApiClient, ApiException, Page<T>, session scope
    storage/                 TokenStore (secure), PreferencesStore (language only)
    logging/                 SafeLogger (redacts tokens/e-mail/passwords)
    time/                    timezone policy: offset-required parsing, UTC internally, local display
    paging/                  PagedNotifier (epoch-protected pagination)
  features/
    auth/                    data (AuthApi, models) · application (SessionCore/Controller) · presentation
    home/  account/  shell/  signed-in screens and role-aware navigation
    discovery/               provider search, filters, detail, booking (data · application · presentation)
    reservations/            patient appointments list/detail, booking and cancel actions
    provider/                provider & facility workspace: dashboard, availability, received bookings
    explore/                 Home "Explore" entries gated by capabilities / dashboard index
    real_estate/  marketplace/  jobs/   11D domains (data · application · presentation)
    notifications/  chat/  push/   11E: notification centre, conversations, FCM client
  shared/                    theme, buttons, text field, loading/error/empty views, dialogs
  l10n/                      app_en.arb, app_ar.arb (+ generated code, committed)
test/                        unit + widget tests (no network, no real credentials)
```

## Running

```sh
cd mobile
flutter pub get
# Android emulator against a backend on the host (http://10.0.2.2:8000 is the default in debug):
flutter run
# Any other backend (must be https unless it is a debug/development build):
flutter run --dart-define=APP_ENV=staging --dart-define=API_BASE_URL=https://api.example.com
```

| Define | Values | Notes |
|---|---|---|
| `APP_ENV` | `development` (default), `staging`, `production` | `development` is rejected in release builds |
| `API_BASE_URL` | absolute origin (no path) | required for `staging`/`production`; `http://` only for debug + `development` |

A misconfigured build shows an explicit configuration error screen instead of falling back to an
insecure default. No secret belongs in a `--dart-define` (they are readable in the app binary).

## Checks (the same as CI)

```sh
flutter pub get --enforce-lockfile
dart format --output=none --set-exit-if-changed .
flutter analyze --fatal-infos
flutter test
```

Regenerate localization code after editing an `.arb` file: `flutter gen-l10n` (output committed).

## Not in 11E

Attachments, group chat, starting a conversation other than from a reservation, local-notification display, iOS push (APNs), release signing/store (11F), plus: create/edit forms for products, jobs and listings, applicant management, résumé/profile editing, images and uploads, external links, profile and service editing, facility membership management (the endpoints exist), chat, notifications and FCM
device registration (11E), payments and store release. Android/iOS signing and Firebase configuration are deliberately
absent from the repository. The IBM Plex Sans Arabic font from the design system is not bundled
yet (system font is used); bundling it is a follow-up.

## Patient flows (11B)

- Destinations *Find care* and *Appointments* appear only for accounts whose `/me` lists the needed
  permission (PATIENT); the backend re-checks every call. Details: `docs/RESERVATIONS.md`
  "Mobile (Phase 11B)", ADR-054.
- **Timezone:** the API is UTC with no provider timezone. Timestamps must carry an offset; the app
  keeps UTC internally and shows the device's local time (and groups slots by local day).
- **No retry of bookings:** `POST /reservations` has no idempotency key, so it is never retried
  automatically and duplicate taps are ignored.
- **Testing:** widget tests use a scripted HTTP adapter and an injected clock/wall clock. Calls that
  need real async (`dio`) from a test body (e.g. `logout()` / `login()`) must be wrapped in
  `tester.runAsync`, and `pumpAndSettle` must not be used while a request is deliberately hanging.
  `test/openapi_contract_test.dart` reads `../docs/api/openapi.yaml` (run tests from `mobile/`).

## Provider & facility workspace (11C)

- Destinations *Dashboard*, *Availability* and *Bookings* appear only for accounts whose `/me` lists
  `reservations.manage_received` (provider role); the backend additionally needs a provider profile
  (403 → guidance). The dashboard (doctor or facility) is chosen by `GET /dashboards/`. Details:
  `docs/RESERVATIONS.md` "Mobile provider and facility (Phase 11C)", ADR-055.
- **Availability** is created from an active service with a duration, a date and a start time picked
  in the device's time zone (sent as UTC). Overlap, future-time and in-use removal are the backend's.
- **Bookings**: the provider's received reservations; transitions are offered from status and start
  time as a hint, the backend decides, destructive ones need confirmation.
- **Isolation**: provider data is keyed by account id, local state resets on an account change, and
  a mutation finishing under another account is dropped (never shown, never invalidating).
- **Testing**: besides the 11B notes — account switching is simulated with `switchAccountTo`
  (a `/me` refresh that returns another account while the screen stays mounted), local pickers must
  not use the shared progress button, and buttons from `AsyncActionButton` are full-width by theme
  (don't put them in an unbounded `Row`).

## Marketplace, jobs and real estate (11D)

- **Explore** (Home): Jobs and Real estate for everyone; Marketplace (`marketplace.view_targeted_products`), Company workspace (`marketplace.manage_own_products`), Seller workspace (`real_estate.manage_own_listings`) from `/me`; Recruiter workspace when the server's `GET /dashboards/` lists `recruiter` (membership is not a capability). Hints only; the backend authorizes. Details: `docs/MARKETPLACE.md`, `docs/JOBS.md`, `docs/REAL_ESTATE.md` "Mobile (Phase 11D)", ADR-056.
- **Search/filters/pagination:** `SearchQuery` + `SearchFilterBar` (debounced 400 ms) + `PagedListView` on `PagedNotifier`; only documented query parameters are sent (the marketplace has a category filter and no search); a new query or account restarts at page 1 and a late answer for an old query is dropped.
- **Mutations:** `runAsAccount` (capture the account, run once, drop the result if the account changed or the screen was unmounted); never retried; buttons keyed per account; withdraw/close/unpublish/deactivate confirmed.
- **Dates and money:** job deadlines are calendar DATES (never zone-converted); prices/salaries are the backend decimal strings with the backend currency.
- **Testing:** `FakeBackend` scripts, `switchAccountTo` (keeps the route mounted while `/me` changes account). `test/openapi_contract_test.dart` also reads `../backend/apps/*/types.py` to pin the vocabularies.
- **Android check (local scratch backend):** `flutter build apk --debug --target-platform android-arm64`, install on the emulator, `--dart-define` not needed (default `http://10.0.2.2:8000`); run the backend with `ALLOWED_HOSTS` including `10.0.2.2`.

## Chat, notifications and push (11E)

- **Where:** Home → Explore → *Notifications* / *Messages* (badges are the backend's counts); *Message the provider/patient* on reservation details. Details: `docs/NOTIFICATIONS.md`, `docs/CHAT.md`, `docs/PUSH.md` "Mobile (Phase 11E)", ADR-057.
- **Persistence is the truth:** push is a hint; a foreground push only refreshes. Mutations (`mark read`, `mark all`, `send`, `open conversation`) use `runAsAccount`; the composer, draft and busy state are per account.
- **Token ownership:** every register/unregister carries `ownership_seq` from `PushOwnershipSequence` (persisted in preferences, `max(last+1, clock µs)`, never reset by logout/account switch); the server applies an operation only if it is newer, so a late request can never take the token back (ADR-057).
- **FCM configuration (optional):** build with `--dart-define=FIREBASE_API_KEY=… --dart-define=FIREBASE_APP_ID=… --dart-define=FIREBASE_MESSAGING_SENDER_ID=… --dart-define=FIREBASE_PROJECT_ID=…` (public client identifiers of YOUR Firebase project; never a service-account key). Without them push is disabled and everything else works. No `google-services.json` or Gradle plugin is used.
- **Testing:** `FakePushSource` (test/support/comms_support.dart) scripts permission, token, refresh, foreground, opened and initial messages; the coordinator and registration are tested without Firebase.

## Release (11F)

- Full guide: `docs/MOBILE_RELEASE.md`. Release builds need an explicit `APP_ENV` (not `development`) and an https `API_BASE_URL`, each as its **own** `--dart-define`.
- Signing: copy `android/key.properties.example` to `android/key.properties` (git-ignored) or set `RACHEETA_KEYSTORE_PATH`, `RACHEETA_KEYSTORE_PASSWORD`, `RACHEETA_KEY_ALIAS`, `RACHEETA_KEY_PASSWORD`. Without them `flutter build apk|appbundle --release` fails. For a NON-production compile check only: `ORG_GRADLE_PROJECT_racheetaAllowDebugSignedRelease=true`.
- Verify a built APK: `ANDROID_HOME=… python3 tool/verify_release_apk.py build/app/outputs/flutter-apk/app-release.apk`.
- Audits that run in `flutter test`: `accessibility_audit_test` (tap targets, labels, contrast), `text_scale_audit_test` (1.0/1.5/2.0×), `release_smoke_test` (account switch in flight, session expiry), `release_hygiene_test` (logging, manifest, signing, pins, disposal).
- Text-safe colour tokens (`warning`, `success`, `neutral500`) differ slightly from the web tokens to meet WCAG AA text contrast.
