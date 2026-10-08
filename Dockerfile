# syntax=docker/dockerfile:1
# Racheeta 2.0 — single-image deployment (React build served by Django/WhiteNoise).
# Used by Railway (see railway.json) and portable to any container host.

# ---------- Stage 1: build the web app -----------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- Stage 2: backend runtime -------------------------------------------
FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    SPA_DIST_DIR=/app/webapp_dist \
    PORT=8000

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY backend/requirements/ requirements/
RUN pip install -r requirements/production.txt

# Code stays root-owned and read-only to the runtime user; only collectstatic's output is
# writable at build time. The container runs as the unprivileged `app` user (no shell login,
# no secrets baked in: see .dockerignore and the build-only key below).
COPY backend/ ./
COPY scripts/start.sh ./start.sh
COPY --from=web /web/dist ./webapp_dist

# collectstatic only needs settings to import. The SECRET_KEY is generated inside this single RUN
# command, is never written to an ENV/ARG or a file, and is discarded with the build layer's shell:
# nothing committed here can ever be mistaken for (or used as) a runtime credential. The runtime
# `manage.py check` rejects weak/placeholder keys (racheeta.E009), so the container's real key must
# be injected by the platform. DATABASE_URL is a dummy that is never connected to.
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
    DATABASE_URL=postgres://x:x@localhost/x \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000
CMD ["sh", "./start.sh"]
