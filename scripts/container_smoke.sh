#!/usr/bin/env bash
# Builds the production image and proves it boots the way Railway will run it: unprivileged user,
# `manage.py check` + `migrate` in start.sh, gunicorn serving, health/ready/security headers.
# Needs docker and a reachable, EMPTY PostgreSQL database (CI provides one; never point this at
# a database that holds real data — start.sh runs migrations).
#
#   DATABASE_URL=postgres://user:pass@localhost:5432/db scripts/container_smoke.sh [image-tag]
#
# All values below are throwaway: the SECRET_KEY is generated per run and discarded.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${1:-racheeta-smoke:local}"
NAME="racheeta-smoke-$$"
PORT="${SMOKE_PORT:-8000}"
: "${DATABASE_URL:?set DATABASE_URL to a disposable PostgreSQL database}"
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then echo "--- container logs ---"; docker logs "$NAME" 2>&1 | tail -60 || true; fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

docker build -t "$IMAGE" .

docker run -d --name "$NAME" --network host \
  -e SECRET_KEY="$SECRET_KEY" -e DEBUG=false -e PORT="$PORT" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e FRONTEND_URL=https://smoke.example.invalid \
  -e CSRF_TRUSTED_ORIGINS=https://smoke.example.invalid \
  -e CORS_ALLOWED_ORIGINS=https://smoke.example.invalid \
  -e EMAIL_URL=smtp://localhost:25 \
  -e SECURE_PROXY_SSL=true -e TRUSTED_PROXY_COUNT=1 \
  "$IMAGE" >/dev/null

echo "waiting for the container to become healthy..."
for i in $(seq 1 60); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/ready/")" = "200" ]; then break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]; then
    echo "container exited early"; exit 1
  fi
  sleep 2
  [ "$i" -lt 60 ] || { echo "container never became ready"; exit 1; }
done

uid="$(docker exec "$NAME" id -u)"
[ "$uid" != "0" ] && echo "  ok    runs as unprivileged uid $uid" || { echo "  FAIL  runs as root"; exit 1; }

if docker exec "$NAME" sh -c 'touch /app/.write-test 2>/dev/null'; then
  echo "  FAIL  application directory is writable by the runtime user"; exit 1
else
  echo "  ok    application code is read-only for the runtime user"
fi

scripts/smoke_http.sh "http://127.0.0.1:$PORT"

# Logs into a variable first: under pipefail an early-exiting grep could turn a leak into "ok".
container_logs="$(docker logs "$NAME" 2>&1)"
if grep -qF "$SECRET_KEY" <<<"$container_logs"; then
  echo "  FAIL  SECRET_KEY appears in container logs"; exit 1
else
  echo "  ok    SECRET_KEY not present in container logs"
fi

# Volume mode (Railway with a volume: RAILWAY_RUN_UID=0, root-owned mount). start.sh must hand the
# private-media folder to `app` and drop root BEFORE check/migrate/gunicorn.
docker rm -f "$NAME" >/dev/null
docker run -d --name "$NAME" --network host --user 0 \
  --tmpfs /data:uid=0,gid=0,mode=0755 \
  -e PRIVATE_MEDIA_ROOT=/data/private_media \
  -e SECRET_KEY="$SECRET_KEY" -e DEBUG=false -e PORT="$PORT" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e FRONTEND_URL=https://smoke.example.invalid \
  -e CSRF_TRUSTED_ORIGINS=https://smoke.example.invalid \
  -e CORS_ALLOWED_ORIGINS=https://smoke.example.invalid \
  -e EMAIL_URL=smtp://localhost:25 \
  -e SECURE_PROXY_SSL=true -e TRUSTED_PROXY_COUNT=1 \
  "$IMAGE" >/dev/null
echo "volume mode: waiting for the container to become healthy..."
for i in $(seq 1 60); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/ready/")" = "200" ]; then break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]; then
    echo "container exited early (volume mode)"; exit 1
  fi
  sleep 2
  [ "$i" -lt 60 ] || { echo "container never became ready (volume mode)"; exit 1; }
done
server_uid="$(docker exec "$NAME" stat -c %u /proc/1)"
[ "$server_uid" = "1000" ] && echo "  ok    volume mode: the server runs as uid 1000, not root" \
  || { echo "  FAIL  volume mode: the server runs as uid $server_uid"; exit 1; }
owner="$(docker exec "$NAME" stat -c %u /data/private_media)"
[ "$owner" = "1000" ] && echo "  ok    volume mode: private media folder belongs to app" \
  || { echo "  FAIL  volume mode: private media folder owned by uid $owner"; exit 1; }
# Read the logs first: `docker logs | grep -q` can fail under pipefail (grep exits early, SIGPIPE).
volume_logs="$(docker logs "$NAME" 2>&1)"
grep -q "dropping root privileges to user app" <<<"$volume_logs" \
  && echo "  ok    volume mode: start.sh dropped root before check/migrate" \
  || { echo "  FAIL  volume mode: no privilege drop logged"; exit 1; }
echo "CONTAINER SMOKE PASSED"
