# Current State

Date: 2026-09-23
AI/Engineer: Claude (Fable 5.1) via Claude Code
Branch: `feat/phase1-auth-completion` (pushed; PR into `main` to be opened/merged by the owner)
Last Commit SHA: `4c04c6a` (the commit adding this handoff follows it; see `git log -1`)
Remote: `git@github.com:moahaimen/enhanced_racheeta.git` (https://github.com/moahaimen/enhanced_racheeta)

> New session? Read `ARCHITECTURE.md`, `DECISIONS.md`, `PROGRESS.md`, then this
> file. Then run `make check`. Continue from **Exact Next Step**.

## Goal of This Work Session

Finish Phase 1 — Accounts & Authentication — completely enough to begin
Phase 2 safely. Do not start Phase 2.

## Completed

- Backend: `email_verified_at` timestamp + `firebase_uid` (migration
  `accounts.0002`), stateless HMAC tokens for reset/verification, endpoints
  `POST /auth/password-reset/{request,confirm}`,
  `POST /auth/email-verification/{request,confirm}`,
  `POST /auth/firebase/exchange` (adapter; disabled → 503), `/me` now exposes
  `email_verified_at` and `has_password`; email via `EMAIL_URL` with a
  production check refusing console backends; `LocaleMiddleware`; throttle
  scopes `password_reset`, `email_verification`; OpenAPI regenerated.
- Web: `react-router`; `AuthProvider` single session layer; guards
  (`RequireAuth`, `PublicOnly`, restoration loading); pages `/`, `/login`,
  `/register`, `/profile`, `/forgot-password`, `/reset-password`,
  `/verify-email`, 404; shared form components; `ApiActionButton` as submit
  button; `Accept-Language` header.
- Security review of Phase 1 documented in `SECURITY.md` with regression tests.
- Browser walkthrough against the local backend (Django + Vite, console
  email): register (client validation caught mismatch) → profile from `/me`
  → send verification → open link → verified → edit + save (language switch
  to English applied) → logout → wrong password rejected → login via Enter →
  forgot password → weak password rejected by backend → reset → login with
  new password. All API calls logged as expected; no server errors.
- CI now runs on every branch push.

## Files Added

Backend: `apps/accounts/{tokens,emails,firebase,services}.py`,
`apps/accounts/migrations/0002_email_verification_and_firebase.py`,
`apps/core/checks.py`, tests `test_password_reset.py`,
`test_email_verification.py`, `test_firebase_exchange.py`, `tests/test_checks.py`.
Web: `src/app/{routes,guards,AppLayout}.tsx`, `src/auth/{AuthContext.tsx,context.ts,useAuth.ts,roles.ts}`,
`src/components/forms/*`, `src/pages/{LoginPage,RegisterPage,ProfilePage,ForgotPasswordPage,ResetPasswordPage,VerifyEmailPage,NotFoundPage}.tsx`,
`src/pages/validation.ts`, `src/test/renderApp.tsx`, tests for guards, auth
context, login, register, profile, password reset/verify pages.

## Files Modified

`backend/config/{settings,test_settings}.py`, `apps/accounts/{models,roles,serializers,views,urls,admin}.py`,
`apps/core/apps.py`, existing account tests, `web/src/api/{client,types}.ts`,
`web/src/api/endpoints/auth.ts`, `web/src/components/ApiActionButton.tsx`,
`web/src/{App,main}.tsx`, `web/src/pages/HomePage.tsx`, `web/src/i18n/locales/*`,
`web/src/styles/index.css`, `web/package.json`, `.env.example`,
`.github/workflows/ci.yml`, `docs/*`.

## Database Migrations

`accounts.0002_email_verification_and_firebase`: adds `email_verified_at`
(carries over the old boolean), removes `email_verified`, adds `firebase_uid`
+ unique-when-set constraint. Applied locally; runs automatically on deploy.

## API Endpoints Added/Changed

Added: `POST /api/v1/auth/password-reset/request`, `POST /api/v1/auth/password-reset/confirm`,
`POST /api/v1/auth/email-verification/request`, `POST /api/v1/auth/email-verification/confirm`,
`POST /api/v1/auth/firebase/exchange`.
Changed: `GET /api/v1/me` adds `email_verified_at`, `has_password`.
Contract: `docs/api/openapi.yaml` (11 operations).

## Architecture Decisions

ADR-015 … ADR-022 in `DECISIONS.md` (stateless tokens; verification
timestamp without gating; Firebase adapter disabled by default; email
required / phone-only deferred; `EMAIL_URL` + production check; per-request
localisation; web session layer and guards; submit buttons are
`ApiActionButton`).

## Security Decisions

See the Phase 1 review table in `SECURITY.md`. Notable: enumeration-safe
reset (same 202 always), single-use tokens by hash design, reset revokes all
refresh tokens, unverified Firebase emails can never link to an existing
account, console email refused in production, access-token-as-refresh
rejected, client cannot set `email_verified_at`/`firebase_uid`.

## Tests Run

```
make check
  ruff check / ruff format --check / manage.py check / makemigrations --check
  pytest                       (backend)
  tsc -b / oxlint / vitest run / vite build   (web)
./scripts/export_openapi.sh   (docs/api/openapi.yaml up to date)
```

## Test Results

- Backend: **104 passed**, ruff clean, checks clean, no migration drift.
- Web: **49 passed**, tsc clean, oxlint clean, production build OK
  (≈397 kB JS, 124 kB gzip — react-router and i18next included).
- CI: see the Actions tab for the branch push and the PR.

## Known Problems

- Firebase is **not activated**: `FirebaseAdminVerifier` is untested against
  real Firebase (no credentials). Activation steps in `AUTHENTICATION.md`.
- Phone-only Firebase sign-in is rejected (`email_required`) until ADR-018 is
  revisited.
- Password-reset request timing could differ for existing vs unknown emails
  once a slow SMTP provider is used (synchronous send). Move sending to a
  background task when a worker exists.
- Throttle counters are per process (local-memory cache).
- Dev only: React StrictMode double-invokes effects, so `/me` is fetched
  twice on start-up in development. Not in production builds.
- `Dockerfile` still not built locally (no Docker on the dev machine).
- Production email provider not chosen; `manage.py check` will fail on
  Railway until `EMAIL_URL` points at a real backend (intentional).

## Incomplete Work

Nothing required by Phase 1 is left. Deliberately deferred: admin
account-management endpoints (Phase 10), password change for logged-in
users (small, can ride with Phase 2), phone-only Firebase sign-in (ADR-018),
Firebase activation (owner configuration).

## Required Manual Actions

1. Open a pull request `feat/phase1-auth-completion` → `main` and merge when
   CI is green:
   https://github.com/moahaimen/enhanced_racheeta/compare/main...feat/phase1-auth-completion?expand=1
   (GitHub CLI is not authenticated on the dev machine, so the PR could not be
   opened automatically.)
2. Decide the production email provider and set `EMAIL_URL`,
   `DEFAULT_FROM_EMAIL`, `FRONTEND_URL` on Railway before the first deploy.
3. Optional: provide Firebase credentials to activate the exchange endpoint.

## Environment Variables Added/Changed

Added (all documented in `.env.example`): `EMAIL_URL`, `DEFAULT_FROM_EMAIL`,
`FRONTEND_URL`, `PASSWORD_RESET_TIMEOUT_MINUTES`,
`EMAIL_VERIFICATION_TIMEOUT_HOURS`, `FIREBASE_VERIFIER`,
`FIREBASE_CREDENTIALS_FILE`. CI sets placeholder `EMAIL_URL` and `FRONTEND_URL`.

## Railway/Infrastructure Impact

No new services. New required variables at deploy time: `EMAIL_URL`,
`FRONTEND_URL` (see `RAILWAY.md`). Migration `accounts.0002` runs at container
start.

## Exact Next Step

After the PR is merged: start **Phase 2 — Providers and Medical Services** on
a new branch from `main`:

1. `apps/providers`: `ProviderProfile` (practitioner vs facility), provider
   types, verification status (admin-controlled), relation to `Account`;
   `ProviderMembership` for practitioners at facilities.
2. `apps/specialties`, `apps/services`, governorate/city reference data.
3. Public discovery endpoints with filters (type, specialty, governorate,
   city, rating placeholder) and pagination.
4. Provider self-management endpoints (own profile only).
5. Web: provider search page + provider profile management page under
   `RequireAuth`, using `AsyncPage`/`ApiActionButton`.
6. Tests, OpenAPI, docs, HANDOFF.

## Recommended Next Prompt

> Read docs/HANDOFF.md, docs/PROGRESS.md, docs/DECISIONS.md and
> docs/ARCHITECTURE.md in racheeta-platform. Confirm `main` contains the
> merged Phase 1 branch and `make check` is green. Then start Phase 2 on
> `feat/phase2-providers`: design and implement the providers, specialties and
> services modules (ProviderProfile with practitioner/facility subtypes,
> ProviderMembership, admin-controlled verification, public discovery with
> filters and pagination, provider self-management), with tests, regenerated
> docs/api/openapi.yaml, updated docs, small commits, and a final
> docs/HANDOFF.md + docs/PROGRESS.md update. Do not add PostGIS yet.
