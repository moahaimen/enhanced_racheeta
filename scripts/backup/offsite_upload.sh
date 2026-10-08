#!/usr/bin/env bash
# Copies a backup made by backup_db.sh to an S3-compatible bucket (AWS S3, Cloudflare R2,
# Backblaze B2, MinIO, ...). Provider-neutral: only the `aws` CLI and environment variables.
#
#   OFFSITE_BUCKET=my-bucket OFFSITE_PREFIX=racheeta/prod \
#   [OFFSITE_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com] \
#   [AGE_RECIPIENT=age1...] \
#   AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
#     scripts/backup/offsite_upload.sh racheeta-<stamp>.dump [--dry-run]
#
# * Credentials come from the environment only (use a key that can write to ONE bucket and cannot
#   delete: ransomware/mistake protection; expiry is a bucket lifecycle rule, not this script).
# * If AGE_RECIPIENT is set the dump is encrypted with `age` before it leaves the machine; keep the
#   private key somewhere other than the database host and the bucket.
# * Not scheduled anywhere in this repository on purpose: a scheduled job without owner-provided
#   credentials would fail every day. Wire it into the owner's scheduler once the bucket exists
#   (docs/BACKUP_RESTORE.md "Off-site copies").
set -euo pipefail

dump="${1:?usage: offsite_upload.sh <dump-file> [--dry-run]}"
dry="${2:-}"
: "${OFFSITE_BUCKET:?set OFFSITE_BUCKET}"
prefix="${OFFSITE_PREFIX:-racheeta}"
[ -f "$dump" ] || { echo "no such dump: $dump" >&2; exit 1; }

source_file="$dump"
if [ -n "${AGE_RECIPIENT:-}" ]; then
  command -v age >/dev/null || { echo "AGE_RECIPIENT is set but 'age' is not installed" >&2; exit 1; }
  source_file="$(mktemp)"
  trap 'rm -f "$source_file"' EXIT
  age -r "$AGE_RECIPIENT" -o "$source_file" "$dump"
  key="$prefix/$(basename "$dump").age"
else
  key="$prefix/$(basename "$dump")"
fi

endpoint=()
[ -n "${OFFSITE_ENDPOINT_URL:-}" ] && endpoint=(--endpoint-url "$OFFSITE_ENDPOINT_URL")

echo "upload: $(basename "$dump") -> s3://$OFFSITE_BUCKET/$key$([ -n "${AGE_RECIPIENT:-}" ] && echo ' (age-encrypted)')"
if [ "$dry" = "--dry-run" ]; then echo "dry run: nothing uploaded"; exit 0; fi

command -v aws >/dev/null || { echo "the aws CLI is required" >&2; exit 1; }
aws s3 cp "$source_file" "s3://$OFFSITE_BUCKET/$key" ${endpoint[@]+"${endpoint[@]}"} --only-show-errors
if [ -f "$dump.sha256" ]; then
  aws s3 cp "$dump.sha256" "s3://$OFFSITE_BUCKET/$prefix/$(basename "$dump").sha256" \
    ${endpoint[@]+"${endpoint[@]}"} --only-show-errors
fi
echo "uploaded"
