#!/usr/bin/env bash
# Logical backup of the Racheeta PostgreSQL database (provider-neutral: any host that has
# pg_dump 16 and network access to the database).
#
#   DATABASE_URL=postgres://... scripts/backup/backup_db.sh [output-dir]
#
# Writes   racheeta-<UTC timestamp>.dump        (pg_dump custom format, compressed)
#          racheeta-<UTC timestamp>.dump.sha256 (checksum, verified by restore_db.sh)
# Read-only against the database. The connection string (it contains the password) is never
# printed. Output files are private (umask 077); store them OFF the database host
# (docs/BACKUP_RESTORE.md).
#
# Optional: BACKUP_RETENTION_DAYS=N deletes racheeta-*.dump(.sha256) files in the output
# directory older than N days after a SUCCESSFUL backup (never runs on failure).
set -euo pipefail
umask 077

: "${DATABASE_URL:?set DATABASE_URL (the database to back up)}"
OUT_DIR="${1:-${BACKUP_DIR:-./backups}}"
mkdir -p "$OUT_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
final="$OUT_DIR/racheeta-$stamp.dump"
partial="$final.partial"
trap 'rm -f "$partial"' EXIT

pg_dump "$DATABASE_URL" --format=custom --no-owner --no-privileges --file "$partial"

# A dump that cannot be listed is not a backup.
pg_restore --list "$partial" > /dev/null
[ -s "$partial" ] || { echo "backup is empty" >&2; exit 1; }

mv "$partial" "$final"
( cd "$OUT_DIR" && { sha256sum "racheeta-$stamp.dump" 2>/dev/null || shasum -a 256 "racheeta-$stamp.dump"; } > "racheeta-$stamp.dump.sha256" )

echo "backup written: $final ($(wc -c < "$final" | tr -d ' ') bytes)"

if [ -n "${BACKUP_RETENTION_DAYS:-}" ]; then
  case "$BACKUP_RETENTION_DAYS" in (*[!0-9]*|'') echo "BACKUP_RETENTION_DAYS must be a number" >&2; exit 1;; esac
  find "$OUT_DIR" -maxdepth 1 -type f \( -name 'racheeta-*.dump' -o -name 'racheeta-*.dump.sha256' \) \
    -mtime "+$BACKUP_RETENTION_DAYS" -print -delete | sed 's/^/pruned: /'
fi
