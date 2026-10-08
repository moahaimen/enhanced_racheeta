# Backup and restore

The only stateful component is **PostgreSQL**. There is no object storage yet (no uploads exist;
when they do, their bucket joins this document). Everything below is provider-neutral: it needs
`pg_dump`/`pg_restore`/`psql` **version 16** and network access to the database.

> Phase 12A status: the scripts are written and tested (`backup_restore_smoke.sh` runs in CI against a
> throw-away PostgreSQL), but **no production or staging backup exists, and no off-site bucket has
> been chosen**. The owner must complete §5 before 12C.

## 1. Targets (propose, owner decides)

| | Proposal | Why |
| --- | --- | --- |
| RPO (acceptable data loss) | 24 h at launch; 1 h once there are paying users | A daily logical dump is the minimum that is cheap and verifiable. Railway's own point-in-time/volume backups, if the plan includes them, can lower this but are a convenience, not the strategy (they do not survive leaving the platform). |
| RTO (time to restore) | 2–4 h | Create a database, restore, repoint `DATABASE_URL`, smoke test. The first rehearsal (`docs/STAGING.md`) must measure the real number; put it here. |
| Retention | 7 daily + 4 weekly + 3 monthly | Daily covers an operator error noticed next morning; weekly/monthly cover slow corruption. Set as a bucket lifecycle rule, not in the upload script. |

## 2. Scripts (`scripts/backup/`)

| Script | Purpose |
| --- | --- |
| `backup_db.sh [dir]` | `pg_dump --format=custom --no-owner --no-privileges` to `racheeta-<UTC>.dump` + `.sha256`. Private files (umask 077). Verifies the archive can be listed. `BACKUP_RETENTION_DAYS=N` prunes old **local** copies after a successful backup. Read-only against the database; never prints the connection string. |
| `restore_db.sh <dump>` | Restores into `TARGET_DATABASE_URL`. Refuses a **non-empty** target, refuses when the target equals `DATABASE_URL` (the live database), verifies the checksum, prints table and migration counts. There is deliberately no `--force`. |
| `backup_restore_smoke.sh` | Round-trip proof: dump → restore into a throw-away database → exact row-count comparison of every table; also asserts the refusals and that a corrupted dump is rejected. Run by CI after migrating an empty database and seeding one user. |
| `offsite_upload.sh <dump>` | Copies to an S3-compatible bucket with the `aws` CLI; optional `age` encryption; `--dry-run`. **Not scheduled** (see §5). |

```bash
# one backup (from any machine with network access and pg_dump 16)
DATABASE_URL='postgres://…' scripts/backup/backup_db.sh ./backups

# restore into a fresh database
createdb racheeta_restore            # or the provider's "new database" button
TARGET_DATABASE_URL='postgres://…/racheeta_restore' scripts/backup/restore_db.sh ./backups/racheeta-<stamp>.dump

# prove the whole mechanism on any migrated disposable database
SOURCE_DATABASE_URL='postgres://…/some_db' scripts/backup/backup_restore_smoke.sh
```

On Railway use the Postgres service's **public** connection URL for the dump from your machine
(Connect tab), or run the script where the private network is reachable. Treat the URL as a
secret: do not paste it into chat, tickets or shell history you share (`HISTCONTROL=ignorespace`
and a leading space help).

## 3. What a backup contains — and does not

Contains: all application data (accounts with password hashes, profiles, jobs, reservations,
messages, notifications, billing records, audit log, refresh-token tables). **It is personal data:**
encrypt it at rest, restrict who can read it, delete expired copies.

Does not contain: `SECRET_KEY` and the other environment variables (keep a current copy of every
production variable in the owner's password manager: without the same `SECRET_KEY` password-reset
tokens and JWTs issued before the restore are invalid, and rotating it logs everyone out),
Firebase credentials, or the web/mobile build.

## 4. Restore procedures

**A. Rehearsal / verification (monthly, and before 12C):**
1. Restore the latest dump into a new, empty database (`restore_db.sh`).
2. Point a staging or local backend at it and run `python manage.py check`, `showmigrations` (all
   applied), and `python manage.py migrate --check`.
3. Open the admin and a few accounts; hit `/ready/`.
4. Record the elapsed time in this file (measured RTO) and drop the scratch database.

**B. Disaster recovery (production database lost or corrupted):**
1. Decide the restore point (latest dump; if the corruption is recent, an earlier one).
2. Put the app in maintenance by scaling the service to zero or removing its domain (prevents new
   writes into a database you are about to replace).
3. Create a **new** database; restore into it. Never restore over the damaged one: keep it for
   forensics until the incident is closed.
4. Set `DATABASE_URL` on the service to the new database, redeploy (the start script migrates, which
   applies any migrations newer than the dump), run `scripts/smoke_http.sh`.
5. Tell users what window of data was lost; record the incident in `docs/OPERATIONS.md`.

Restoring a dump taken with an **older** code version into the current code is supported (`migrate`
brings it forward). Restoring a **newer** dump into older code is not; deploy the matching code
first.

## 5. Off-site copies (owner decision required before 12C)

A backup that lives only on the database host or the same Railway project is not a backup.
Design (no cost until the owner creates a bucket):

1. **Destination:** an S3-compatible bucket outside Railway (AWS S3, Cloudflare R2, Backblaze B2,
   or a MinIO server the owner runs), private, with versioning or object lock, and a lifecycle rule
   implementing §1 retention.
2. **Credentials:** a key restricted to that bucket with **write but no delete** permission. Store
   it in the scheduler's secret store, never in the repository.
3. **Encryption:** server-side encryption is the minimum; for client-side encryption set
   `AGE_RECIPIENT` (public key) so the plain dump never leaves the machine, and keep the private
   key in the owner's password manager *and* one offline place.
4. **Schedule:** a daily job on a machine the owner controls (a small VPS cron, or a scheduler
   service) running `backup_db.sh` then `offsite_upload.sh`, and alerting on a non-zero exit or a
   missing daily object. A GitHub Actions cron is possible but needs the production database URL as
   a repository secret; the repository intentionally ships **no** scheduled workflow, because one
   without those secrets would fail every day and train people to ignore red builds. If the owner
   chooses Actions, add the workflow in the same PR as the secrets, with `workflow_dispatch` first.
5. **Monitoring:** the job must notify on failure and on "no new object in 26 hours".

## 6. Token tables

Refresh-token bookkeeping (`token_blacklist_*`) is included in backups and grows continuously;
`manage.py prune_expired_tokens` keeps it bounded (`docs/OPERATIONS.md` for cadence).
