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

COPY backend/ ./
COPY scripts/start.sh ./start.sh
COPY --from=web /web/dist ./webapp_dist

# collectstatic needs settings to import; these placeholder values are never
# used at runtime (real values are injected by the platform environment).
RUN SECRET_KEY=build-time-placeholder DATABASE_URL=postgres://x:x@localhost/x \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app

USER app
EXPOSE 8000
CMD ["sh", "./start.sh"]
