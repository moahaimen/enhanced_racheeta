#!/bin/sh
# Production entrypoint (container CMD).
#
#   1. `check`   — Django system checks; an ERROR (unsafe production settings such as an
#                  unconfigured proxy count, console e-mail, wildcard hosts) stops the container
#                  here, before it touches the database or accepts traffic.
#   2. `migrate` — applies pending migrations. Railway has no separate release phase, so this runs
#                  at container start. This is safe ONLY with a single replica; with more than one,
#                  move migrate to a dedicated pre-deploy step (docs/PRODUCTION_DEPLOYMENT.md).
#                  A failed migration exits non-zero: the new container never becomes ready (the
#                  platform health check fails), so the previous deployment keeps serving.
#   3. gunicorn  — config/gunicorn.conf.py (workers, timeouts, privacy-safe access log).
#
# Volume (optional, e.g. Railway): a platform volume is mounted root-owned, so to use one the
# service sets RAILWAY_RUN_UID=0 and the container starts as root. Then, and only then, this
# script gives the private-media folder (PRIVATE_MEDIA_ROOT: seller documents, product photos) to
# the unprivileged `app` user and immediately re-runs itself as `app` (setpriv): the checks,
# migrations and gunicorn never run as root (the environment, i.e. the platform secrets, is kept).
# Without a volume nothing changes (USER app).
set -eu

if [ "$(id -u)" = "0" ]; then
  if [ -n "${PRIVATE_MEDIA_ROOT:-}" ]; then
    mkdir -p "$PRIVATE_MEDIA_ROOT"
    chown -R app:app "$PRIVATE_MEDIA_ROOT"
  fi
  echo "start.sh: dropping root privileges to user app"
  HOME=/home/app exec setpriv --reuid=app --regid=app --init-groups sh "$0" "$@"
fi

python manage.py check
python manage.py migrate --noinput

exec gunicorn config.wsgi:application -c config/gunicorn.conf.py
