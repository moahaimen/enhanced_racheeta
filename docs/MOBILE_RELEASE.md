# Mobile release (Phase 11F)

Status: **release hardening implemented, awaiting independent review.** This document is the single
place for how the Flutter app is configured, signed, built and verified for release, and for what
the owner must still supply. No store upload, no signing key and no production deployment is part of
Phase 11F.

## 1. Build configuration

The app reads two compile-time values (`--dart-define`, never secrets):

| Define | Values | Rule |
|---|---|---|
| `APP_ENV` | `development` (default), `staging`, `production` | a **release** build rejects `development` |
| `API_BASE_URL` | absolute origin, e.g. `https://api.example.com` | required for staging/production; **no default**; `https` only (cleartext `http` only in a *debug* `development` build) |

`AppConfig.validate` (tested in `test/app_config_test.dart`) additionally refuses, for release builds
and for staging/production in any mode: `localhost`, `*.localhost`, `127.*`, `::1`, `0.0.0.0`,
`10.0.2.2`/`10.0.3.2` (the emulator host aliases); and refuses any URL carrying credentials, a query
or a fragment. The development fallback (`http://10.0.2.2:8000`) is guarded by the compile-time
constant `kReleaseMode`, so release binaries do not contain it (checked by `tool/verify_release_apk.py`).
A misconfigured build shows the "The app is not configured" screen — it never falls back silently
(observed on an emulator: a build made with a malformed `APP_ENV` showed exactly that screen).

Build commands (use **separate** `--dart-define` arguments; in zsh do not put them in an unquoted
variable, it will not split):

```sh
cd mobile
flutter build appbundle --release \
  --dart-define=APP_ENV=production --dart-define=API_BASE_URL=https://<production API origin>
flutter build apk --release --target-platform android-arm64 \
  --dart-define=APP_ENV=production --dart-define=API_BASE_URL=https://<production API origin>
```

## 2. Android identity and versions

| Item | Value |
|---|---|
| `applicationId` / namespace | `app.racheeta.racheeta_mobile` (**owner decision**, see blockers: permanent once on Google Play) |
| label | `Racheeta` |
| `version` (pubspec) | `0.1.0+1` → `versionName 0.1.0`, `versionCode 1` (conservative; no launch version invented) |
| minSdk / targetSdk / compileSdk | 24 / 36 / 36 (Flutter 3.47.6 defaults) |
| ABIs in the release APK/AAB | `arm64-v8a`, `armeabi-v7a`, `x86_64` |
| Tooling | AGP 9.1.0, Gradle 9.3.1, Kotlin 2.4.0, Java 17 (unchanged; not upgraded) |

Version policy for future releases: bump the semantic part of `version:` for user-visible changes and
**always** increase the build number after `+` for every upload (it becomes the Android `versionCode`
and the iOS `CFBundleVersion`; Google Play and App Store Connect reject a repeated value). No
automatic version service.

## 3. Release signing (no secret in the repository)

`android/app/build.gradle.kts` reads the release keystore from `android/key.properties` (git-ignored;
template `android/key.properties.example`) **or** the environment (`RACHEETA_KEYSTORE_PATH`,
`RACHEETA_KEYSTORE_PASSWORD`, `RACHEETA_KEY_ALIAS`, `RACHEETA_KEY_PASSWORD`).

* A release build **without** credentials **fails** with "Release signing is not configured…"
  (verified locally and by a CI step that asserts the failure).
* The only escape hatch is the explicit smoke switch
  `ORG_GRADLE_PROJECT_racheetaAllowDebugSignedRelease=true` (or `-PracheetaAllowDebugSignedRelease=true`),
  which signs with the debug key so the release **configuration** can be compiled in CI. Such an
  artifact is not a production build and must never be uploaded.
* `*.jks`, `*.keystore`, `*.p12`, `key.properties` are git-ignored; `test/release_hygiene_test.dart`
  fails if signing material appears under `mobile/android`.
* For Play App Signing, upload the AAB signed with an *upload key* the owner generates and keeps
  offline; Google holds the app-signing key.

## 4. Permissions and exported components (audited on the merged release manifest)

`tool/verify_release_apk.py <apk>` reads the compiled manifest and fails on anything outside this list.

| Permission | Why |
|---|---|
| `INTERNET` | API access. **Was missing from the main manifest** (Flutter declares it only for debug/profile): a release build could not reach the API. Fixed. |
| `POST_NOTIFICATIONS` | Android 13+ runtime permission for push; asked only from a button on the notification centre; the app works without it |
| `WAKE_LOCK`, `ACCESS_NETWORK_STATE`, `com.google.android.c2dm.permission.RECEIVE` | merged from `firebase_messaging` (FCM); inert while push is disabled |
| `<package>.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` | androidx signature permission for non-exported receivers |

No location, contacts, camera, microphone or storage permission. Exported components in the release
merge: the launcher `MainActivity` and three library receivers that are protected by a system
permission (`com.google.android.c2dm.permission.SEND`, `android.permission.DUMP`); every service and
provider is `exported=false`. The app is not debuggable and declares no cleartext traffic.

## 5. Backup and data extraction

`android:allowBackup="false"` plus `data_extraction_rules.xml` / `backup_rules.xml` exclude everything
from cloud backup and device-to-device transfer. Reason: the refresh token lives in Keystore-backed
secure storage, which cannot be decrypted on another device, so a restored copy could only create a
broken session; the only other state is the UI language and the push-ownership counter (non-sensitive,
cheap to recreate). Nothing of value is lost. (Note for review: a restored `racheeta.push_ownership_seq`
would be harmless — the counter is `max(last+1, clock)` — but keeping it out of backups avoids any
cross-device surprise.)

## 6. Logging and privacy

* `SafeLogger` is enabled only in debug (`kDebugMode`), redacts bearer tokens, JWTs, `token/password/...`
  pairs and e-mail addresses, and is the only code that prints (`test/release_hygiene_test.dart` scans
  `lib/` for `print`, `debugPrint`, `developer.log`, `stdout/stderr`, and for log calls that interpolate
  tokens, passwords, e-mail, message bodies or payloads).
* On an emulator, the release build produced **0** `[racheeta]` log lines and a single engine line
  (`Using the Impeller rendering backend`).
* FCM tokens are never logged or persisted; message bodies never appear in `toString`; server error
  text is never shown (fixed localized messages only).

## 7. Firebase / FCM — what the owner must supply

Phase 11E ships the client without any Firebase project configuration; the app runs with push
**disabled** (`DisabledPushSource`) when the defines are absent, and the release build is valid
without push. To enable real push the owner must provide **client** identifiers (not secrets) from
their Firebase project and pass them at build time:

`--dart-define=FIREBASE_API_KEY=… --dart-define=FIREBASE_APP_ID=… --dart-define=FIREBASE_MESSAGING_SENDER_ID=… --dart-define=FIREBASE_PROJECT_ID=…`

and configure the server's own Firebase Admin credential (`FIREBASE_CREDENTIALS_FILE`, `PUSH_SENDER`)
on the backend — that file is a **server** secret and never belongs in the app or the repository.
Real FCM transport has **not** been exercised end to end (no Firebase project is available); the token
lifecycle, ordering (`ownership_seq`), routing and permission logic are covered by automated tests with a
fake push source. iOS push additionally needs an APNs key uploaded to Firebase and the Push
Notifications capability; it is **not configured** and must not be claimed to work.

## 8. iOS audit (no release attempted)

Bundle identifier `app.racheeta.racheetaMobile` (differs in style from the Android id — align before the
first store submission), display name `Racheeta Mobile`, deployment target 15.0, automatic signing with
no team set (placeholder), no entitlements file, no background modes, no ATS exceptions (HTTPS enforced by
default), no push capability or `aps-environment`. A compile check was **not** run: Xcode 27 is present but the
iOS 27 simulator runtime is not installed and a signing-less device build was judged not worth the disk
and time risk; iOS release is therefore unverified.

## 9. Accessibility, text scaling and RTL (audited by automated tests)

`test/accessibility_audit_test.dart` runs Flutter's tap-target (Android 48 dp, iOS 44 dp), labelled-tap-target
and text-contrast guidelines on 13 surfaces (login, home, account, provider discovery, reservations list/detail,
provider bookings, marketplace, jobs list/detail, real estate, notifications, conversation list/thread) in English
and Arabic at 360 dp width; `test/text_scale_audit_test.dart` renders the same surfaces at 1.0×, 1.5× and 2.0×
text scale in both languages (no overflow, no exception). Defects found and fixed:

| Finding | Fix |
|---|---|
| Warning/success/neutral tokens below WCAG AA (3.64 / 4.14 / 4.45 : 1) — "Pending" status chip and success messages | text-safe mobile tokens `warning #956000`, `success #187A4E`, `neutral500 #627076` (≥ 4.5 : 1) |
| `SelectableText` exposed read-only values as text fields below 48 dp | `SelectableValue` (`Text` inside `SelectionArea`) |
| Reservation status row overflowed in Arabic at phone width (client and provider detail) | `Wrap` instead of `Row` |
| Notification header ("N unread" + *Mark all*) overflowed at ≥ 1.5× text | `Wrap` |
| Discovery search/filters kept account A's pending debounce / open draft after an account switch | scoped to the account (like `SearchFilterBar`), with regression tests |

Also asserted: unread notifications are announced as unread; chat bubbles are announced with author and time (not
only by alignment); "mine" stays on the end side in LTR and RTL; back control and chevrons mirror in Arabic.
Not covered by automation: real TalkBack/VoiceOver behaviour, keyboard/focus traversal on hardware keyboards.

## 10. Performance and lifecycle

Reviewed, no change needed: every list is paginated (`PagedNotifier`/`PagedListView`, `ListView.builder`); no polling
or periodic timers exist; no images are loaded; providers are account-keyed (no cross-account cache) and
auto-disposed where per-screen; every `Timer`, `StreamSubscription`, `TextEditingController` is disposed
(`test/release_hygiene_test.dart` guards this); the push subscription, the intent coordinator and the ownership lane
are released with their providers; network timeouts are finite (connect 10 s, send/receive 20 s); there is no
automatic retry of mutations; logout stays usable offline (local state is cleared first, revocation and the
push-unregister hook are best effort and bounded to 3 s). Changed: Firebase initialisation can no longer delay
start-up beyond 5 s (`createPushSource` timeout). Known and accepted: opening a conversation by deep link also loads the
first page of the conversation list (used for the header). **Profile build:** compiled successfully
(`app-profile.apk`); **no frame-timing numbers were taken** — the available emulator renders in software, so FPS
figures would be meaningless and none are claimed.

## 11. Release smoke suite and matrix

`test/release_smoke_test.dart` (account switch with requests in flight on 8 screens; FCM registration during a switch;
session expiry during a list fetch, a detail fetch, a mutation, a message send, a notification read and FCM
synchronisation; no-Firebase start) complements the per-feature suites.

| Area | Scenario | Automated coverage |
|---|---|---|
| Authentication | signed-out launch, login, restore, logout, token expiry | `session_test`, `app_widget_test`, `release_smoke_test`, login audit |
| Patient | discovery, booking, appointments, cancellation | `discovery_test`, `booking_test`, `reservations_test` |
| Provider | dashboard, availability, bookings, transition | `provider_*_test` |
| Jobs | browse, detail, apply, withdraw, recruiter close | `jobs_test`, `recruiter_test` |
| Marketplace | browse/detail, company activate/deactivate | `marketplace_test`, `company_workspace_test` |
| Real estate | browse/detail, seller publish/unpublish | `real_estate_test`, `seller_workspace_test` |
| Chat | list, thread, send, read cursor | `chat_test` |
| Notifications | list, mark read, mark all | `notifications_test` |
| Push | disabled configuration; token lifecycle, ordering, routing | `push_*_test`, `release_smoke_test` (real FCM: **needs external configuration**) |
| Cross-cutting | Arabic/English, account switch, offline/server errors, accessibility, text scaling | per-feature suites, `accessibility_audit_test`, `text_scale_audit_test`, `release_smoke_test` |

## 12. Verification evidence (Phase 11F)

* `flutter build apk --release` (arm64, staging defines) → 21.3 MB; `flutter build appbundle --release` → 58.3 MB;
  `flutter build apk --profile` compiled. All with the explicit **non-production** smoke signing; without it the build
  fails closed. Artifacts are not committed or uploaded.
* `tool/verify_release_apk.py` on the release APK: application id `app.racheeta.racheeta_mobile`, permissions within the
  audited list, backup/cleartext off, not debuggable, no development URL in the Dart snapshot. It fails on the profile
  APK (debuggable, embeds the dev fallback), proving it can fail.
* Emulator (software-rendered, 4 GB): the release APK installed, `INTERNET` granted, launched to the login screen with
  no debug banner, the language switch produced RTL Arabic, **0** app log lines. Not exercised on the emulator: login
  against a server (a release build refuses the plain-HTTP local backend by design), any signed-in flow, push.
* Flutter: 758 tests passing (`flutter analyze --fatal-infos` and `dart format` clean).
* CI: the new job "Mobile release smoke (Android)" repeats the fail-closed check, the signed-less smoke build, the APK
  verification and an AAB build, without any production secret and without publishing.

## 13. External prerequisites and known release blockers

1. **Production signing:** an upload keystore (and Play App Signing enrolment) — owner-held.
2. **Application id:** confirm `app.racheeta.racheeta_mobile` (permanent on Play); the iOS bundle id is spelled differently.
3. **Production `API_BASE_URL`** (https) and, if push is wanted, the four `FIREBASE_*` client values + backend Admin credential.
4. **Launcher icon and splash are the Flutter defaults** — the repository has no square raster Racheeta asset (only
   `web/public/favicon.svg`); brand assets must be supplied. Adaptive icon, notification icon and splash are unset.
5. **Store listing material** (not invented here): app name and localized descriptions, privacy-policy URL, support
   e-mail, screenshots, feature graphic, content rating questionnaire, Data-safety (Play) / privacy nutrition labels
   (App Store) answers, target-audience declaration, **account-deletion URL / in-app path** (required by Play for apps with
   account creation — the app has no deletion flow and creates no accounts itself), and the legal text.
6. iOS: Apple developer team and signing, APNs key, entitlements, an iOS build/verification pass.
7. Real-device verification (TalkBack, performance, push) was not possible in this environment.
8. Decisions deferred: dependency upgrades (all direct dependencies are exact-pinned and current except
   `shared_preferences` 2.5.5 → 2.5.6, a patch release); Kotlin built-in migration warnings from plugins; a localized
   app label.

## 14. Dependency audit

Direct dependencies: `dio`, `flutter_riverpod`, `flutter_secure_storage`, `go_router`, `intl`, `shared_preferences`,
`firebase_core`, `firebase_messaging` (+ Flutter SDK/localizations). None is obsolete or unnecessary; there is no
`url_launcher`, WebView, analytics or crash-reporting package (guarded by `release_hygiene_test`). Firebase packages
are required by 11E and inert without configuration. No upgrade was made in 11F.
