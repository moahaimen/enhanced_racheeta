# Racheeta mobile (Flutter)

The Racheeta patient/provider app. **Phase 11A** is the foundation (app shell, configuration, one
API client, email/password authentication, session management, localization (Arabic RTL / English)
and reusable UI). **Phase 11B** adds the patient side (provider discovery, detail, booking, "My appointments" with
cancellation). **Phase 11C (this change) adds the provider and facility side**: dashboard,
appointment availability and the bookings a provider received, with status transitions. The
marketplace/jobs/real estate and chat/notifications arrive in 11D–11E (see `docs/MASTER_PLAN.md`);
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
| `API_BASE_URL` | absolute URL | required for `staging`/`production`; `http://` only for debug + `development` |

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

## Not in 11C

Profile and service editing, facility membership management (the endpoints exist), marketplace, jobs
and real estate (11D), chat, notifications and FCM
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
