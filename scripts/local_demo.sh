#!/usr/bin/env bash
# Local-only demo workflow on a DISPOSABLE database. Never points at Railway/staging/production.
# Settings come from local-demo/.env.demo (git-ignored; created on first use, holds the generated
# demo password). Every database step runs `check_local_demo_db` first and stops if it refuses.
#
#   scripts/local_demo.sh create-db     # create racheeta_workspace_demo + disposable marker
#   scripts/local_demo.sh migrate       # guard, then migrate
#   scripts/local_demo.sh seed          # guard, then seed (adds --with-admin)
#   scripts/local_demo.sh dry-run       # what the seed would create
#   scripts/local_demo.sh clear-dry     # what clear would delete
#   scripts/local_demo.sh clear         # delete the demo rows
#   scripts/local_demo.sh serve         # API on 127.0.0.1:8010 against the demo database
#   scripts/local_demo.sh web           # web on 127.0.0.1:5180, proxied to that API
#   scripts/local_demo.sh drop-db       # drop the disposable database (asks first)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
envfile="$here/local-demo/.env.demo"
dbname="racheeta_workspace_demo"
marker="racheeta-disposable-local-demo"

if [ ! -f "$envfile" ]; then
  mkdir -p "$here/local-demo"
  pw="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  umask 077
  printf 'DATABASE_URL=postgres://%s@localhost:5432/%s\nRACHEETA_LOCAL_DEMO=1\nLOCAL_DEMO_PASSWORD=%s\n' "$USER" "$dbname" "$pw" > "$envfile"
  echo "created $envfile (local only, git-ignored)"
fi
if ! grep -q '^LOCAL_DEMO_ADMIN_PASSWORD=' "$envfile"; then
  apw="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  umask 077
  printf 'LOCAL_DEMO_ADMIN_PASSWORD=%s\n' "$apw" >> "$envfile"
  echo "added a separate local admin password to $envfile"
fi
set -a; . "$envfile"; set +a
for v in $(env | grep -o '^RAILWAY_[A-Z_]*' || true); do unset "$v"; done
# Absolute links the seed writes (demo portraits, e-mail links) must point at the demo web origin.
export FRONTEND_URL="${LOCAL_DEMO_FRONTEND_URL:-http://127.0.0.1:${LOCAL_DEMO_WEB_PORT:-5180}}"

cd "$here/backend"
py=".venv/bin/python"
guard() { "$py" manage.py check_local_demo_db; }

case "${1:-}" in
  create-db)
    createdb -h localhost "$dbname"
    psql -h localhost -d postgres -c "COMMENT ON DATABASE $dbname IS '$marker'" ;;
  migrate) guard && "$py" manage.py migrate --noinput ;;
  seed) guard && "$py" manage.py migrate --noinput && "$py" manage.py seed_local_demo --with-admin ;;
  dry-run) guard && "$py" manage.py seed_local_demo --dry-run ;;
  clear-dry) guard && "$py" manage.py clear_local_demo --dry-run ;;
  clear) guard && "$py" manage.py clear_local_demo --yes ;;
  serve) guard && exec "$py" manage.py runserver "127.0.0.1:${LOCAL_DEMO_API_PORT:-8010}" ;;
  web)
    cd "$here/web" && VITE_DEV_PROXY_TARGET="http://127.0.0.1:${LOCAL_DEMO_API_PORT:-8010}" \
      exec npx vite --host 127.0.0.1 --port "${LOCAL_DEMO_WEB_PORT:-5180}" --strictPort ;;
  drop-db)
    read -r -p "Drop the disposable database $dbname? [y/N] " ok
    [ "$ok" = "y" ] && dropdb -h localhost "$dbname" ;;
  *) sed -n '2,16p' "$0"; exit 2 ;;
esac
