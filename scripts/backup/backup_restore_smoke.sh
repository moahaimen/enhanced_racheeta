#!/usr/bin/env bash
# Proves backup -> restore round-trips: dumps SOURCE, restores into a throwaway database, and
# compares the exact row count of every public table. Needs a role that may CREATE/DROP
# DATABASE (CI's postgres superuser; locally your own user). Secret-free; touches nothing but
# the throwaway database it creates and removes.
#
#   SOURCE_DATABASE_URL=postgres://user:pw@host:5432/dbname scripts/backup/backup_restore_smoke.sh
#
# The SOURCE must already hold the application schema (run `manage.py migrate` first; CI also
# seeds a user so the comparison covers real rows).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
: "${SOURCE_DATABASE_URL:?set SOURCE_DATABASE_URL to a migrated database}"

# Same server, different database name: swap the last path segment of the URL.
scratch_name="racheeta_restore_smoke_$$"
base="${SOURCE_DATABASE_URL%%\?*}"
query=""; [ "$base" != "$SOURCE_DATABASE_URL" ] && query="?${SOURCE_DATABASE_URL#*\?}"
admin_url="${base%/*}/postgres$query"
target_url="${base%/*}/$scratch_name$query"

work="$(mktemp -d)"
cleanup() {
  psql "$admin_url" -qc "DROP DATABASE IF EXISTS \"$scratch_name\"" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

DATABASE_URL="$SOURCE_DATABASE_URL" "$here/backup_db.sh" "$work"
dump="$(ls "$work"/racheeta-*.dump)"

psql "$admin_url" -qc "CREATE DATABASE \"$scratch_name\"" >/dev/null
DATABASE_URL="$SOURCE_DATABASE_URL" TARGET_DATABASE_URL="$target_url" "$here/restore_db.sh" "$dump"

# restore_db.sh must refuse a non-empty target and the live database.
if TARGET_DATABASE_URL="$target_url" "$here/restore_db.sh" "$dump" >/dev/null 2>&1; then
  echo "FAIL: restore into a non-empty database was not refused" >&2; exit 1
fi
if DATABASE_URL="$SOURCE_DATABASE_URL" TARGET_DATABASE_URL="$SOURCE_DATABASE_URL" \
   "$here/restore_db.sh" "$dump" >/dev/null 2>&1; then
  echo "FAIL: restore over the live database was not refused" >&2; exit 1
fi
echo "ok: restore refuses a non-empty target and the live database"

# Corruption must be detected.
cp "$dump" "$work/corrupt.dump"; cp "$dump.sha256" "$work/corrupt.dump.sha256"
sed -i.bak 's/^[0-9a-f]\{8\}/00000000/' "$work/corrupt.dump.sha256"
psql "$admin_url" -qc "CREATE DATABASE \"${scratch_name}_c\"" >/dev/null
if TARGET_DATABASE_URL="${base%/*}/${scratch_name}_c$query" "$here/restore_db.sh" "$work/corrupt.dump" >/dev/null 2>&1; then
  psql "$admin_url" -qc "DROP DATABASE \"${scratch_name}_c\"" >/dev/null
  echo "FAIL: a checksum mismatch was not detected" >&2; exit 1
fi
psql "$admin_url" -qc "DROP DATABASE \"${scratch_name}_c\"" >/dev/null
echo "ok: a corrupted dump is rejected"

tables="$(psql "$SOURCE_DATABASE_URL" -Atqc \
  "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1")"
[ -n "$tables" ] || { echo "FAIL: source database has no tables (run migrate first)" >&2; exit 1; }
count=0; total=0
for t in $tables; do
  a="$(psql "$SOURCE_DATABASE_URL" -Atqc "SELECT count(*) FROM \"$t\"")"
  b="$(psql "$target_url" -Atqc "SELECT count(*) FROM \"$t\"")"
  if [ "$a" != "$b" ]; then echo "FAIL: $t has $a rows in source but $b after restore" >&2; exit 1; fi
  count=$((count + 1)); total=$((total + a))
done
echo "ok: $count tables restored with identical row counts ($total rows)"
echo "BACKUP/RESTORE SMOKE PASSED"
