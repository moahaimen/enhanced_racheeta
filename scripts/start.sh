#!/bin/sh
# Production entrypoint (container CMD). Applies migrations, then serves.
# Migrations run here because Railway has no separate release phase; with one
# replica this is safe. Move to a dedicated pre-deploy step if replicas > 1.
set -eu

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile - \
  --log-level "${GUNICORN_LOG_LEVEL:-info}"
