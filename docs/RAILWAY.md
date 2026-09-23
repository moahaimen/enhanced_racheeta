# Railway

Target shape: **one service + one PostgreSQL**. Nothing else until a feature
demonstrably needs it.

> Status: **not deployed yet.** This document describes the intended setup;
> the configuration files already exist and are tested locally.

## Services

| Service | Source | Notes |
| --- | --- | --- |
| `racheeta` | this repository, root directory | Built from `Dockerfile` (`railway.json` selects the Dockerfile builder). |
| `postgres` | Railway PostgreSQL plugin | Provides `DATABASE_URL` via variable reference. |

## Environment variables for the `racheeta` service

| Variable | Value |
| --- | --- |
| `SECRET_KEY` | 64+ random characters. Generate locally; never reuse the dev one. |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | Custom domain(s), comma separated. Railway's `RAILWAY_PUBLIC_DOMAIN` is added automatically by settings. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference to the plugin) |
| `CORS_ALLOWED_ORIGINS` | Empty (web app is same-origin) unless another origin must call the API. |
| `CSRF_TRUSTED_ORIGINS` | `https://<domain>` — needed for the Django admin. |
| `SECURE_PROXY_SSL` | `true` |
| `ADMIN_URL_PATH` | Optional non-default path for the admin. |
| `WEB_CONCURRENCY` | gunicorn workers; `2` is fine for the smallest plan. |
| `LOG_LEVEL` | `INFO` |

`SPA_DIST_DIR` and `PORT` are set by the Dockerfile / Railway; do not override.

## Build & start

- Build: Docker multi-stage (`node:22-alpine` builds `web/`, `python:3.13-slim`
  runs Django). `collectstatic` runs at build time.
- Start: `scripts/start.sh` → `migrate --noinput` → gunicorn on `$PORT`.
- Health check: `GET /health/` (configured in `railway.json`, 120 s timeout).

Migrations run in the container start because Railway has no separate release
phase. With a single replica this is safe. If replicas are ever > 1, move
`migrate` to a pre-deploy command.

## Statelessness

The container writes nothing that must persist. `MEDIA_ROOT` is a local
placeholder only; user uploads must go to S3-compatible storage before any
upload feature ships (**planned**).

## Cost guardrails

No Redis, no worker, no cron service, no additional replicas until a
documented feature needs them. Add such a decision to `DECISIONS.md` first.

## Leaving Railway

Build the same `Dockerfile` elsewhere, provide the same variables and a
PostgreSQL 16 database restored from a dump (`BACKUP_RESTORE.md`). No Railway
API or SDK is used anywhere in the code.
