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
set -eu

python manage.py check
python manage.py migrate --noinput

exec gunicorn config.wsgi:application -c config/gunicorn.conf.py
