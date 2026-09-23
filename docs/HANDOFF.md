# Current State

Date: 2026-09-23
AI/Engineer: Claude (Fable 5.1) via Claude Code
Branch: `main`
Last Commit SHA: `d37dddc` (code + docs) — the commit adding this file follows it

> New session? Read `ARCHITECTURE.md`, `DECISIONS.md`, `PROGRESS.md`, then this
> file. Then run `make check`. Continue from **Exact Next Step**.

## Goal of This Work Session

Execute `MASTER_PLAN.md` §29 "First Task": Phase 0 (foundation) plus the
foundation portion of Phase 1 (Account model, authentication, `/me`).

## Completed

- Monorepo `racheeta-platform` initialised on `main` with `.gitignore`,
  `.editorconfig`, `.env.example`, proprietary `LICENSE`, `README.md`, `Makefile`.
- Backend: Django 5.2 LTS project, env-driven settings, PostgreSQL via
  `DATABASE_URL`, DRF, drf-spectacular (`/api/schema/`, `/api/docs/`),
  `GET /health/`, `/api/v1/` routing with JSON 404, uniform error envelope,
  standard pagination, base models, custom `Account`, roles/capabilities,
  register/login/refresh/logout (rotating + blacklisted refresh tokens),
  `GET/PATCH /api/v1/me`, Django admin for accounts, auth throttling.
- Web: Vite + React + TS skeleton, Arabic-first RTL with English, API layer
  (`web/src/api`), `ApiActionButton` / `AsyncPage` / `LoadingOverlay` / `Spinner`,
  demo home page calling `/health/`, Vite proxy to backend.
- CI: `.github/workflows/ci.yml` (backend: ruff, check, migrations check,
  pytest, OpenAPI freshness; web: tsc, oxlint, vitest, build).
- Deployment files: `Dockerfile` (multi-stage), `railway.json`,
  `scripts/start.sh`, `docker-compose.yml` (local Postgres).
- Documentation: all mandatory files in `docs/` + `docs/api/openapi.yaml` +
  `docs/MASTER_PLAN.md` (copy of the owner's plan).
- Live end-to-end check on a dev server: health, SPA served by Django,
  register (privilege fields rejected), login, `/me`, PATCH, logout, refresh
  reuse blocked — all behaved as documented.

## Files Added

Everything in the repository is new (100 files). Key entry points:
`backend/config/settings.py`, `backend/config/urls.py`, `backend/config/api_v1.py`,
`backend/apps/core/*`, `backend/apps/accounts/*`, `backend/conftest.py`,
`web/src/api/client.ts`, `web/src/components/*`, `web/src/i18n/index.ts`,
`.github/workflows/ci.yml`, `Dockerfile`, `scripts/*.sh`, `docs/*.md`.

## Files Modified

None (initial commit set).

## Database Migrations

- `accounts/0001_initial` — `accounts_account` with constraints
  `accounts_account_email_ci_unique`, `accounts_account_phone_unique_when_set`,
  `accounts_account_admin_role_requires_staff`, index on `role`.
- Third-party: `token_blacklist` (SimpleJWT), Django `auth`/`admin`/`contenttypes`/`sessions`.

## API Endpoints Added/Changed

`GET /health/`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`,
`POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET|PATCH /api/v1/me`,
`GET /api/schema/`, `GET /api/docs/`. Contract: `docs/api/openapi.yaml`.

## Architecture Decisions

ADR-001 … ADR-014 in `DECISIONS.md`. Highlights: modular monolith + one
container; Django 5.2 LTS with exact pins; single env-driven settings module;
one `Account` with email login and UUID PKs; coarse role + computed
capabilities; JWT with rotating blacklisted refresh; uniform error envelope;
committed OpenAPI checked by CI; Django serves the React build; mandatory
loading components; UTC timestamps in the API.

## Security Decisions

See `SECURITY.md`. Privilege fields are rejected (not ignored) on every write
serializer; `create_user` cannot create staff/ADMIN; DB check constraint for
ADMIN ⇒ staff; auth endpoints throttled 10/min; production hardening keyed on
`DEBUG=false` + `SECURE_PROXY_SSL`; web refresh token in `localStorage` is an
explicit interim decision (ADR-009).

## Tests Run

```
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd backend && .venv/bin/python manage.py check && .venv/bin/python manage.py makemigrations --check --dry-run
cd backend && .venv/bin/python -m pytest
cd web && npm run typecheck && npm run lint && npm test && npm run build
./scripts/export_openapi.sh   # then git diff docs/api/openapi.yaml is empty
```

## Test Results

- Backend: **57 passed**, ruff clean, no missing migrations (PostgreSQL 16 local).
- Web: **12 passed**, tsc clean, oxlint clean, production build OK (≈277 kB JS, 87 kB gzip).
- GitHub Actions: not yet executed (no remote configured).

## Known Problems

- `Dockerfile` has not been built locally (Docker is not installed on the
  development machine). First build will happen in CI/Railway; expect at most
  minor fixes.
- Auth throttle uses the per-process local-memory cache; fine for one container.
- `token_blacklist` tables grow until `manage.py flushexpiredtokens` runs;
  no schedule yet.
- Django admin shows times in UTC (`TIME_ZONE="UTC"` so the API emits `Z`).
- Node 25 on the dev machine prints an `EBADENGINE` warning from jsdom; CI uses Node 22.

## Incomplete Work

Phase 1 remainder: Firebase ID-token exchange, email verification, password
reset, admin account-management endpoints, web login/register/profile pages
using the auth API, `react-router`.

## Required Manual Actions

1. Create the GitHub repository and push `main` (`git remote add origin …`,
   `git push -u origin main`) so CI runs.
2. Optional: install Docker locally to use `docker compose` and to build the image.
3. No Railway deployment yet (master plan: do not deploy to production yet).

## Environment Variables Added/Changed

All defined in `.env.example`: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
`DATABASE_URL`, `DB_CONN_MAX_AGE`, `CORS_ALLOWED_ORIGINS`,
`CSRF_TRUSTED_ORIGINS`, `ACCESS_TOKEN_LIFETIME_MINUTES`,
`REFRESH_TOKEN_LIFETIME_DAYS`, `ADMIN_URL_PATH`, `SPA_DIST_DIR`, `LOG_LEVEL`,
`SECURE_PROXY_SSL`, `VITE_API_BASE_URL`. Dev-server only: `VITE_DEV_PROXY_TARGET`.
Container/Railway: `PORT`, `WEB_CONCURRENCY`, `GUNICORN_TIMEOUT`, `GUNICORN_LOG_LEVEL`.

## Railway/Infrastructure Impact

None yet. Files ready: `Dockerfile`, `railway.json`, `scripts/start.sh`;
setup described in `RAILWAY.md`.

## Exact Next Step

Finish Phase 1:

1. Web auth pages: login, register, profile (`/me`) using `ApiActionButton`
   and `AsyncPage`; add `react-router`; session state from `tokenStore.subscribe`.
2. Backend: `POST /api/v1/auth/firebase/exchange` behind a `FIREBASE_*`
   configuration (skip if credentials are not yet available — ask the owner),
   password reset flow, email verification flag flow.
3. Keep `docs/api/openapi.yaml` regenerated (`make openapi`) and docs updated.

Then start Phase 2 (providers, specialties, services, discovery).

## Recommended Next Prompt

> Read docs/HANDOFF.md, docs/PROGRESS.md, docs/DECISIONS.md and
> docs/ARCHITECTURE.md in racheeta-platform. Run `make check` and confirm it is
> green. Then complete Phase 1: build the web login, register and profile pages
> on top of the existing auth API using ApiActionButton/AsyncPage and add
> react-router; add backend password-reset and (if Firebase credentials are
> provided) the Firebase token exchange endpoint with tests. Regenerate
> docs/api/openapi.yaml, update all affected docs, commit in small steps, and
> finish by updating docs/HANDOFF.md and docs/PROGRESS.md.
