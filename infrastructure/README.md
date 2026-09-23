# Infrastructure

Racheeta 2.0 deploys as **one container + one PostgreSQL database**. Nothing else.

| File | Purpose |
| --- | --- |
| `../Dockerfile` | Multi-stage build: Vite web build → Python image with Django + gunicorn + WhiteNoise. |
| `../railway.json` | Railway service config: Dockerfile builder, `/health/` health check, restart policy. |
| `../docker-compose.yml` | Local PostgreSQL only (never used in production). |
| `../scripts/start.sh` | Container entrypoint: `migrate` then `gunicorn`. |

Everything is configured through environment variables listed in `../.env.example`
and explained in `../docs/RAILWAY.md`. No provider-specific code exists in the
application, so moving off Railway means: build the Dockerfile anywhere, point
`DATABASE_URL` at any PostgreSQL 16, set the same variables.
