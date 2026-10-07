#!/usr/bin/env bash
# Restores a dump made by backup_db.sh into a TARGET database.
#
#   TARGET_DATABASE_URL=postgres://.../racheeta_restore scripts/backup/restore_db.sh racheeta-<stamp>.dump
#
# Safety rails (a restore is destructive if aimed at the wrong place):
#   * the target must be an EMPTY database (no tables) — create a fresh one first;
#   * it refuses to run if TARGET_DATABASE_URL equals DATABASE_URL (the live database);
#   * it verifies the .sha256 file next to the dump when present.
# To restore over a non-empty database on purpose, drop and recreate it yourself first; this
# script deliberately has no "--force" mode.
set -euo pipefail

dump="${1:?usage: restore_db.sh <dump-file>}"
: "${TARGET_DATABASE_URL:?set TARGET_DATABASE_URL (an empty database to restore into)}"
[ -f "$dump" ] || { echo "no such dump: $dump" >&2; exit 1; }

if [ -n "${DATABASE_URL:-}" ] && [ "$TARGET_DATABASE_URL" = "$DATABASE_URL" ]; then
  echo "refusing: TARGET_DATABASE_URL is the same as DATABASE_URL (the live database)" >&2
  exit 1
fi

if [ -f "$dump.sha256" ]; then
  ( cd "$(dirname "$dump")" && { sha256sum -c "$(basename "$dump").sha256" 2>/dev/null \
      || shasum -a 256 -c "$(basename "$dump").sha256"; } > /dev/null ) \
    || { echo "checksum mismatch: the dump is corrupt or modified" >&2; exit 1; }
  echo "checksum ok"
else
  echo "warning: no $dump.sha256 next to the dump; integrity not verified" >&2
fi

pg_restore --list "$dump" > /dev/null || { echo "not a readable pg_dump archive" >&2; exit 1; }

tables="$(psql "$TARGET_DATABASE_URL" -Atqc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
if [ "$tables" != "0" ]; then
  echo "refusing: target database already has $tables table(s); restore needs an empty database" >&2
  exit 1
fi

pg_restore --no-owner --no-privileges --exit-on-error --dbname "$TARGET_DATABASE_URL" "$dump"

restored="$(psql "$TARGET_DATABASE_URL" -Atqc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
applied="$(psql "$TARGET_DATABASE_URL" -Atqc "SELECT count(*) FROM django_migrations" 2>/dev/null || echo "?")"
echo "restore complete: $restored tables, $applied applied Django migrations"
echo "next: point a staging app at it and run 'python manage.py migrate' (no-op if the dump is current)"
