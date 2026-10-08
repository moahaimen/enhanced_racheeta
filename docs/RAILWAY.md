# Railway

Target shape: **one service + one PostgreSQL**. Nothing else until a feature demonstrably needs it
(ADR-059: no Redis, no worker, no cron service).

> Status (Phase 12A): **nothing is deployed and no Railway resource exists.** This document is the
> operator's manual for creating them in Phase 12B (staging, `docs/STAGING.md`) and Phase 12C
> (production, `docs/PRODUCTION_DEPLOYMENT.md`). Every value below that depends on the owner
> (domain, e-mail provider, secrets) is marked **OWNER**. Railway's dashboard changes over time;
> where a menu name matters it is given as a hint, the variables and commands are authoritative.

## 1. What gets created

| Resource | Source | Notes |
| --- | --- | --- |
| Service `racheeta` | this repository, root directory | Built from `Dockerfile`; `railway.json` selects the Dockerfile builder, health check `/ready/`, restart on failure (max 5). |
| Database `postgres` | Railway PostgreSQL | Provides `DATABASE_URL`. Use PostgreSQL 16 (what CI tests and the backup scripts target). |
| Domain | Railway-generated, then a custom domain (**OWNER**) | TLS is terminated by Railway's edge. |

Cost guardrails: one replica, no extra services. Check the plan's price before creating anything;
the owner approves 12B/12C spend. Staging and production are **separate projects/environments with
separate databases and separate secrets** — never share a `SECRET_KEY` or database between them.

## 2. Variables for the `racheeta` service

Set these in the service's *Variables* tab. Names are exact. `${{Postgres.DATABASE_URL}}` is
Railway's reference syntax (use the reference, do not paste the URL, so a rotation follows).

| Variable | Value | Required |
| --- | --- | --- |
| `SECRET_KEY` | 64+ random characters: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`. Unique per environment. Rotating it logs everyone out. It is also the JWT signing key: a value under 50 characters or starting `change-me` / `build-time-placeholder` / `django-insecure-` stops the container at start (`racheeta.E009`). | yes |
| `DEBUG` | `false` | yes |
| `ALLOWED_HOSTS` | the public domain(s), comma separated, e.g. `app.example.com`. Railway's `RAILWAY_PUBLIC_DOMAIN` is added automatically; `healthcheck.railway.app` is added automatically when `SECURE_PROXY_SSL=true`. `*` is refused (`racheeta.E006`). | yes |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | yes |
| `SECURE_PROXY_SSL` | `true` — enables the HTTPS redirect, HSTS, secure cookies and `upgrade-insecure-requests`. | yes |
| `TRUSTED_PROXY_COUNT` | `1` (Railway's edge). **Verify in staging** (see §5). With `SECURE_PROXY_SSL=true` and `0` the container refuses to start (`racheeta.E005`). | yes |
| `CSRF_TRUSTED_ORIGINS` | `https://<domain>` — https only (`racheeta.E007`); needed for the Django admin. | yes |
| `CORS_ALLOWED_ORIGINS` | empty (the web app is same-origin) | no |
| `FRONTEND_URL` | `https://<domain>` — used in e-mail links, which carry one-time tokens. Must be an https origin only: no path, query, fragment or credentials; a trailing slash is ignored. Anything else stops the container at start (`racheeta.E010`). | yes |
| `EMAIL_URL` | **OWNER** — provider SMTP, e.g. `smtp://USER:PASSWORD@HOST:587?tls=True` (URL-encode special characters in the password). The container refuses console/locmem mail with `DEBUG=false` (`racheeta.E001`). See `docs/OPERATIONS.md` "E-mail". | yes |
| `DEFAULT_FROM_EMAIL` | **OWNER** — an address on a domain with SPF/DKIM set up at the provider, e.g. `Racheeta <no-reply@example.com>` | yes |
| `EMAIL_TIMEOUT` | `10` (default) | no |
| `DB_CONNECT_TIMEOUT` | `5` (default) | no |
| `WEB_CONCURRENCY` | gunicorn workers; `2` (default) suits the smallest plan. Raise only after measuring (`docs/PERFORMANCE.md`). | no |
| `GUNICORN_TIMEOUT` | `60` (default); keep well above `EMAIL_TIMEOUT` | no |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` (defaults) | no |
| `API_DOCS_ENABLED` | leave unset/`false` | no |
| `ADMIN_URL_PATH` | optional non-default admin path (obscurity only) | no |
| `PASSWORD_RESET_TIMEOUT_MINUTES` / `EMAIL_VERIFICATION_TIMEOUT_HOURS` | defaults 60 / 24 | no |
| `PUSH_SENDER`, `FIREBASE_*` | leave unset until Firebase is activated (`docs/PUSH.md`, `docs/AUTHENTICATION.md`) | no |

`PORT` and `SPA_DIST_DIR` are set by Railway/the Dockerfile; do not override.

## 3. Build and start

- **Build:** the multi-stage `Dockerfile` (Node 22 builds `web/`; Python 3.13-slim runs Django;
  `collectstatic` at build time with a **build-only `SECRET_KEY` generated inside that one `RUN` command** — no key is committed, none is stored in `ENV`/`ARG`, none survives into the runtime; unprivileged user `app`; code read-only to it). `.dockerignore`
  keeps `.env`, keys, tests, docs and other apps out of the image.
- **Start:** `scripts/start.sh` → `manage.py check` (a configuration error stops the container
  before it touches the database) → `migrate --noinput` → gunicorn (`backend/config/gunicorn.conf.py`)
  on `$PORT`.
- **Health check:** `GET /ready/` (`railway.json`, 120 s timeout). `/ready/` runs one `SELECT 1`; a
  release that cannot reach its database never becomes live and the previous deployment keeps
  serving. `/health/` is liveness only (no database) — use it for external uptime pings; do not use
  it as the deployment gate. Both are reachable over plain HTTP; every other path redirects to HTTPS.
- **Migrations at start** are safe with a **single replica** only. With more than one replica, move
  `migrate` to a pre-deploy command first (`docs/PRODUCTION_DEPLOYMENT.md`).
- **Restart policy:** `ON_FAILURE`, 5 retries — a crash loop stops instead of burning resources.

## 4. First-deployment checklist (12B, staging)

1. New Railway project `racheeta-staging`; add PostgreSQL; add the service from the GitHub repo.
2. Set the §2 variables (staging values, staging `SECRET_KEY`).
3. Deploy. Watch the build log, then the deploy log: expect the `check` output, migrations, then
   `Listening at: http://0.0.0.0:<port>`.
4. From your machine: `scripts/smoke_http.sh https://<staging-domain>` (all lines `ok`).
5. Follow `docs/STAGING.md` for the proxy-count check, e-mail check, backup/restore rehearsal and the
   mobile/web pass.

## 5. Verifying `TRUSTED_PROXY_COUNT`

Railway puts one proxy in front of the container, so `1` is expected, but confirm it once per
environment because a wrong value either locks everyone out (too low) or lets a client dodge the
login throttle (too high). Procedure (staging, harmless wrong-password logins):

Counters are per gunicorn worker (2 by default), so use enough requests to exhaust both.

1. From network A (e.g. your phone on mobile data) send 30 `POST /api/v1/auth/login` requests with a
   wrong password for a throw-away address. After the first few `401`s you must see `429`s.
2. Immediately from network B (a different public IP, e.g. home Wi-Fi) send three more. They must be
   `401` (wrong password), **not** `429`. A `429` means all clients are keyed to the proxy address:
   the count is too low.
3. From network A send three more with a forged header `X-Forwarded-For: 203.0.113.9`. They must
   still be `429`. A `401` means the forged value is being trusted: the count is too high.
4. Wait a minute before testing again (`auth` is 10/min per client address).

## 6. Statelessness and media

The container writes nothing that must persist (the code directory is read-only to the runtime
user). There are **no user uploads** today; `MEDIA_ROOT` is a placeholder. Uploads, when a feature
adds them, must use S3-compatible object storage, never the container disk (it is wiped on every
deploy); see `docs/PRODUCTION_DEPLOYMENT.md` "Media".

## 7. Logs and monitoring on Railway

Logs go to stdout (JSON lines from Django, plain access lines from gunicorn); Railway's log viewer
searches them (`request_id`, `level`). Configure at least one external uptime check on
`https://<domain>/health/` and one on `/ready/`, and a Railway usage/spend alert (**OWNER**). What to
watch and what to do is in `docs/OPERATIONS.md`.

## 8. Rollback

Three tiers (full procedure in `docs/PRODUCTION_DEPLOYMENT.md` §7): (1) redeploy the previous
deployment from the Railway dashboard (code only); (2) fix-forward or revert + redeploy when a
migration is involved; (3) database restore from a backup into a new database and repoint
`DATABASE_URL`. Migrations are forward-only; never "migrate backwards" in production.

## 9. Leaving Railway

Build the same `Dockerfile` elsewhere, provide the same variables and a PostgreSQL 16 database
restored from a dump (`docs/BACKUP_RESTORE.md`). No Railway API or SDK is used anywhere in the
code; the only Railway-specific pieces are `railway.json`, the `healthcheck.railway.app` allowed
host and the `RAILWAY_*_DOMAIN` host hints in `settings.py`.
