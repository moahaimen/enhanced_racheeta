# Architecture

> Describes what exists today. Planned pieces are marked **(planned)**.

## Shape

Racheeta 2.0 is a **modular monolith**: one Django application, one PostgreSQL
database, one container. Business modules are Django apps under `backend/apps/`.
They share a database and a process; they are *not* separate services.

```
                 Browser (React SPA)        Flutter app (planned)
                         \                      /
                          \   /api/v1/  JSON   /
                           v                  v
                    +--------------------------------+
                    |  Django (gunicorn, WhiteNoise)  |
                    |  config/   apps/core  apps/...  |
                    +--------------------------------+
                                   |
                              PostgreSQL 16
```

In production Django also serves the built React app (WhiteNoise serves
`web/dist` from the URL root; `apps.core.views.spa_index` returns `index.html`
for client-side routes). The API is therefore same-origin for the web app.

## Repository layout

```
racheeta-platform/
├── backend/            Django project
│   ├── config/         settings.py, urls.py, api_v1.py, asgi.py, wsgi.py
│   ├── apps/
│   │   ├── core/       shared base models, pagination, error envelope, /health/
│   │   └── accounts/   Account model, roles, JWT auth, /me, reset, verification, Firebase adapter
│   ├── requirements/   base.txt (pinned runtime), dev.txt, production.txt
│   ├── tests/          cross-cutting tests (health, smoke)
│   └── conftest.py     shared pytest fixtures
├── web/                React + TypeScript + Vite SPA
│   └── src/
│       ├── api/        the only HTTP layer (client, tokens, endpoints, types)
│       ├── app/        routes.tsx, guards.tsx (all auth checks), AppLayout
│       ├── auth/       AuthProvider (single session layer), useAuth
│       ├── components/ ApiActionButton, AsyncPage, LoadingOverlay, Spinner, forms/
│       ├── hooks/      useAsyncAction, useAsyncData
│       ├── i18n/       Arabic (default, RTL) + English
│       └── pages/      home, login, register, profile, forgot/reset password, verify-email, 404
├── mobile/             Flutter (planned, Phase 11)
├── docs/               this documentation + docs/api/openapi.yaml (contract)
├── infrastructure/     deployment notes
├── scripts/            bootstrap.sh, start.sh, export_openapi.sh
├── .github/workflows/  CI
├── Dockerfile          single production image (web build + backend)
├── railway.json        Railway service configuration
└── docker-compose.yml  local PostgreSQL
```

## Backend

| Concern | Implementation |
| --- | --- |
| Framework | Django 5.2 LTS, Django REST Framework |
| Settings | One module, `backend/config/settings.py`, driven by environment variables (django-environ). Repo-root `.env` is read on developer machines only. |
| Database | PostgreSQL via `DATABASE_URL`. Persistent connections, health checks. No other database is supported. |
| Auth | JWT (SimpleJWT): short-lived access token, rotating refresh token with blacklist. Password reset, email verification and a Firebase adapter. See `AUTHENTICATION.md`. |
| Email | Django email backend from `EMAIL_URL` (console in dev; production provider is an owner decision). `apps/accounts/emails.py`. |
| i18n | `LocaleMiddleware`; messages follow `Accept-Language` (`ar` default, `en`). |
| API | Everything public is under `/api/v1/` (`config/api_v1.py`). Unknown `/api/v1/*` paths return a JSON 404. |
| Errors | One envelope for every error, produced by `apps.core.exceptions.api_exception_handler`. See `API.md`. |
| Pagination / filtering | `apps.core.pagination.StandardPagination`, django-filter, DRF ordering + search backends. |
| OpenAPI | drf-spectacular. Live at `/api/schema/` and `/api/docs/`; committed at `docs/api/openapi.yaml`; CI fails if stale. |
| Static / SPA | WhiteNoise with manifest storage for Django assets; `SPA_DIST_DIR` for the React build. |
| Media | `FileSystemStorage` placeholder for development only. Production must use S3-compatible storage **(planned)**. |
| ASGI | `config/asgi.py` exists; production runs WSGI gunicorn today. Switch to an ASGI server when async views/WebSockets arrive. |
| Health | `GET /health/` → `{"status": "ok"}`. Deliberately does not check the database. |

### Base models (`apps/core/models.py`)

- `UUIDModel` – UUID v4 primary key.
- `TimeStampedModel` – `created_at`, `updated_at`.
- `BaseModel` – both. Use it for every new domain entity.

### Module conventions

Each business module (`apps/<name>/`) owns: `models.py`, `serializers.py`
(separate read/write), `views.py`, `urls.py`, `permissions.py` if needed,
`admin.py`, `migrations/`, `tests/`. It registers its URLs in
`config/api_v1.py`. Modules may import from `apps.core` and `apps.accounts`;
avoid circular imports between business modules — put shared logic in `core`.

### Modules today

| Module | Status |
| --- | --- |
| `core` | done (foundation) |
| `accounts` | Account model, roles, register/login/refresh/logout, `/me`, password reset, email verification, Firebase exchange adapter (disabled until configured) — done. |
| everything in master plan §8 | **(planned)** |

## Accounts and roles

One `Account` model (`apps/accounts/models.py`) is the only authentication
identity. `email` is the login identifier (unique, case-insensitive). There is
no username.

`Account.role` is the coarse primary role:
`PATIENT | PROVIDER | MEDICAL_COMPANY | REAL_ESTATE_SELLER | ADMIN`.
Finer identity (doctor vs nurse, hospital vs pharmacy) will live in profile
models under the account **(planned, Phase 2)**:

```
Account
 ├── PatientProfile              (planned)
 ├── ProviderProfile             (planned)
 │     ├── Practitioner (Doctor, Nurse, Therapist)
 │     └── Facility (Hospital, Pharmacy, Laboratory, MedicalCenter, BeautyCenter)
 ├── MedicalCompany              (planned)
 ├── RealEstateSeller            (planned)
 └── JobSeekerProfile            (planned)
```

`GET /api/v1/me` is the canonical source of identity, role and capability
codes for every client. Clients never store `doctor_id`-style identifiers.

## Web

- Vite + React 19 + TypeScript (strict). Lint: oxlint. Tests: Vitest + Testing Library.
- `src/api/client.ts` is the only place `fetch` is called. It attaches the
  bearer token, refreshes once on 401, and converts the error envelope to `ApiError`.
- Mandatory loading rule (master plan §19) is implemented by
  `ApiActionButton`, `AsyncPage`, `LoadingOverlay` and the `useAsync*` hooks.
- RTL: `<html dir>` is set from the active language; CSS uses logical
  properties only, so one stylesheet serves both directions.
- `react-router` data router. Route table in `src/app/routes.tsx`; auth guards
  only in `src/app/guards.tsx`; session state only in `src/auth/AuthContext.tsx`.
- Forms use `components/forms/*` and map the backend error envelope onto fields.

## Deployment

One container built from the root `Dockerfile` (Node build stage → Python
runtime). `scripts/start.sh` runs `migrate` then gunicorn. Railway config is in
`railway.json`. See `RAILWAY.md`.

## What is intentionally absent

Redis, Celery, WebSockets, Elasticsearch, PostGIS, object storage, payment
gateways, an activated Firebase project, a production email provider. Each has a defined insertion point (see `DECISIONS.md`)
and will be added only when a feature requires it.
