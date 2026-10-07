# Mobile release

Phase 11F makes release builds reproducible and fail-closed. It does **not** commit production
signing material or upload to either store.

## Stable application identity

| Platform | Identifier |
| --- | --- |
| Android | `app.racheeta.racheeta_mobile` |
| iOS | `app.racheeta.racheetaMobile` |
| App version | `1.0.0+1` |

Changing an identifier after first publication creates a different store application. Treat these
values as stable once a store record is created.

## Production configuration

Every release must set:

```text
--dart-define=APP_ENV=production
--dart-define=API_BASE_URL=https://<production-api-origin>
```

`AppConfig` rejects a development environment or cleartext HTTP in a release build. Android also
sets `usesCleartextTraffic=false` in the main manifest; only the debug manifest overrides it for
the local `http://10.0.2.2:8000` workflow.

Firebase client identifiers are public build configuration, not secrets. They remain optional:
without all four `FIREBASE_*` defines the app works with push disabled. A Firebase Admin service
account/private key must never be placed in the mobile build.

## Android signing

Release builds never fall back to the debug key. Provide all four environment variables:

```text
RACHEETA_ANDROID_KEYSTORE_PATH
RACHEETA_ANDROID_STORE_PASSWORD
RACHEETA_ANDROID_KEY_ALIAS
RACHEETA_ANDROID_KEY_PASSWORD
```

Then build:

```bash
cd mobile
flutter pub get --enforce-lockfile
flutter build appbundle --release \
  --dart-define=APP_ENV=production \
  --dart-define=API_BASE_URL=https://api.example.com
```

The keystore and passwords belong in the owner's password/secret manager. `.jks` and `.keystore`
files are ignored by Git. CI generates a throwaway one-day key only to prove that the release path
builds; that CI-signed AAB must never be uploaded to Google Play.

For the real first publication, enable/record Google Play App Signing and keep an offline backup of
the upload key plus its alias/passwords.

## iOS signing

CI runs:

```bash
flutter build ios --release --no-codesign \
  --dart-define=APP_ENV=production \
  --dart-define=API_BASE_URL=https://api.example.com
```

This proves the release target compiles without requiring Apple credentials in GitHub. A real App
Store archive/IPA still requires the owner's Apple Developer team, distribution certificate and
provisioning/profile configuration on a trusted macOS machine or signing CI.

APNs/iOS push remains unconfigured until a real Firebase/Apple project is supplied.

## Release CI

Normal Flutter format/analyze/tests remain mandatory. Phase 11F additionally builds:

- Android release AAB on Linux with an ephemeral CI signing key.
- iOS release app on macOS with `--no-codesign`.
- Production-mode `APP_ENV` and HTTPS API configuration in both builds.
- accessibility/tap-target/text-scaling smoke tests and a lazy-list regression test.

No CI-generated release artifact is a production-signed store artifact.

## Manual store prerequisites

These cannot be manufactured by source code and must be supplied by the owner before publication:

- Google Play Console application / Play App Signing ownership.
- Apple Developer/App Store Connect application ownership and signing credentials.
- final production API HTTPS origin.
- final production Firebase client identifiers if push will be enabled.
- APNs/Firebase iOS setup if iOS push is required at launch.
- final store listing metadata, privacy-policy/support URLs, screenshots, and approved production
  app icon/branding assets.

The repository currently contains the Flutter-generated icon set. Replace it with the approved
Racheeta production artwork before public store submission if that artwork has not already been
approved.

## Release checklist

1. Confirm `main` CI green.
2. Increment `version: x.y.z+build` for every store upload.
3. Confirm the production HTTPS API health endpoint.
4. Run the full Flutter test/analyze/format suite.
5. Produce the signed Android AAB and archive its checksum.
6. Produce the signed iOS archive/IPA and archive its symbols.
7. Smoke-test login, account switch/logout, reservations, jobs/marketplace/real-estate, chat and
   notifications against staging before production rollout.
8. Verify Arabic RTL and large-text accessibility.
9. Verify push on real devices only after Firebase/APNs configuration exists.
10. Keep signing material and store recovery codes outside the repository.
