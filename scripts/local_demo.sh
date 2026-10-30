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
#   scripts/local_demo.sh serve         # API on 127.0.0.1:8000 against the demo database
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
set -a; . "$envfile"; set +a
for v in $(env | grep -o '^RAILWAY_[A-Z_]*' || true); do unset "$v"; done

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
  serve) guard && exec "$py" manage.py runserver 127.0.0.1:8000 ;;
  drop-db)
    read -r -p "Drop the disposable database $dbname? [y/N] " ok
    [ "$ok" = "y" ] && dropdb -h localhost "$dbname" ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
