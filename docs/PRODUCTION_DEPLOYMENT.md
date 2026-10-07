# Production deployment runbook (Phase 12C)

> **Status (Phase 12A): this is a plan, not a record.** Nothing has been deployed. Phase 12C is
> a separate, owner-authorized step and must not start until `docs/STAGING.md` is fully green.
> Where this runbook depends on something the owner has not provided, it says **OWNER** and the
> step cannot be completed by an engineer alone.

## 1. Go / no-go checklist

All must be true. Any **OWNER** item that is missing is a *no-go*, not something to work around.

| # | Condition | Status at end of 12A |
| --- | --- | --- |
| 1 | 12A PR merged to `main`; CI green on the merge commit | pending review |
| 2 | Staging exists and `docs/STAGING.md` checklist is complete with results recorded | not started (12B) |
| 3 | **OWNER:** production domain and DNS control | not provided |
| 4 | **OWNER:** e-mail provider, verified sending domain (SPF/DKIM/DMARC), production credential | not chosen |
| 5 | **OWNER:** off-site backup destination and credentials; one successful restore rehearsal; measured RTO written in `docs/BACKUP_RESTORE.md` | not chosen |
| 6 | **OWNER:** approval of Railway production plan/cost and a usage alert | not given |
| 7 | **OWNER:** monitoring recipient(s) for uptime/alerts (`docs/OPERATIONS.md` §2) | not set |
| 8 | **OWNER:** decision on admin 2FA / admin access policy (`docs/OPERATIONS.md` §8) | not decided |
| 9 | **OWNER:** privacy policy / terms / data-retention statement for real users (legal) | not provided |
| 10 | Dependency and secret scans re-run on the release commit, findings dispositioned | 12A results recorded; re-run at release |
| 11 | Mobile release prerequisites (`docs/MOBILE_RELEASE.md` §13) if the app ships with this release: signing key, application id, Play listing, Firebase production values | not provided |
| 12 | A named person is on call for the first 48 hours | **OWNER** |

## 2. Production is a new, separate environment

Never promote the staging project. Create a **new** Railway project/environment `racheeta-production`
with its own PostgreSQL and its own freshly generated `SECRET_KEY` (and never reuse one that has
appeared in chat, a ticket or a screenshot). Variables: `docs/RAILWAY.md` §2.

Pre-flight on your machine, with the production variable values in a scratch shell (not committed):

```bash
cd backend
SECRET_KEY=… DEBUG=false ALLOWED_HOSTS=… DATABASE_URL=… EMAIL_URL=… FRONTEND_URL=… \
CSRF_TRUSTED_ORIGINS=… SECURE_PROXY_SSL=true TRUSTED_PROXY_COUNT=1 \
python manage.py check --deploy          # expect only the push-disabled warning if Firebase is off
```

## 3. Cutover sequence

1. **Freeze:** merge nothing else; tag the release commit (`git tag -a release-<date> <sha>`).
2. **Create** the project, database and service; set variables; attach the custom domain and wait for
   the certificate (do the DNS change at the registrar; keep the TTL short for the first day).
3. **Deploy** the tagged commit. Expect: build OK → `check` passes → migrations apply on the empty
   database → `/ready/` 200.
4. **Smoke:** `scripts/smoke_http.sh https://<domain>` → `SMOKE PASSED`.
5. **Create the first administrator** with `python manage.py createsuperuser` in the service shell
   (strong unique password; do not reuse staging's). Log in to the admin once.
6. **Verify the proxy count** (RAILWAY §5) — yes, again, in production, with a throw-away address.
7. **Verify e-mail** with a mailbox you own (reset + verification).
8. **Backups:** take the first backup immediately (`backup_db.sh`), copy it off-site, restore it into a
   scratch database to prove it, delete the scratch database. Schedule the daily job
   (`docs/BACKUP_RESTORE.md` §5) and set the alerts (`docs/OPERATIONS.md` §2).
9. **Publish** the domain to users / submit the mobile build only after steps 4–8 pass.
10. **Watch** the logs and uptime checks closely for 48 hours. Record the cutover in
    `docs/OPERATIONS.md` (date, commit, who).

Seed data: migrations seed reference data (Iraqi geography, specialties, billing plan configuration). There is no
other seed. **No legacy data is imported** (`docs/DATA_MIGRATION.md`). The seeded billing plans are
reference data **without prices**; prices, subscriptions and payments are entered by the owner's
administrators (manual activation), the backend never invents them.

## 4. Database migrations and releases

- Migrations run automatically at container start (`scripts/start.sh`) — acceptable with one
  replica. They are applied in a transaction per migration by PostgreSQL where possible.
- **Before every release that contains a migration:** take a backup (`backup_db.sh`) and read the
  migration. Prefer *expand → migrate → contract* releases: add nullable columns/tables first,
  deploy code that works with both shapes, backfill, and only drop/rename in a later release. Never
  ship a migration that rewrites a large table or takes a long exclusive lock in the same deploy as
  a code change that needs it.
- Migrations are forward-only. "Rolling back a migration" in production is a restore (tier 3) or a new
  corrective migration (tier 2). CI proves `migrate` on an empty database and `makemigrations
  --check`; Phase 12A added **no migrations**, and migrating a database created by the pre-12A code
  with the 12A code is a no-op (verified: "No migrations to apply", `migrate --check` clean).
- With more than one replica: run `python manage.py migrate --noinput` as a Railway pre-deploy
  command (or a one-off job) and remove it from `start.sh`; two containers must never migrate
  concurrently.

## 5. Media and uploads (deferral)

No feature stores uploaded files today (no avatars, résumés, listing photos, product images,
chat attachments), so there is nothing to back up or serve and no upload attack surface. The first
feature that needs files must, in the same pull request: choose S3-compatible storage, add
`django-storages` with a private bucket and signed URLs, enforce size and content-type limits and
virus scanning policy, strip image metadata, add the bucket to `docs/BACKUP_RESTORE.md`, and extend
the CSP `img-src`/`connect-src` for the bucket origin (`CSP_CONNECT_SRC` exists for the latter).
The container filesystem is ephemeral and must never be used for user files.

## 6. Post-deploy verification (every release)

```bash
scripts/smoke_http.sh https://<domain>
```

Then by hand: log in on web and mobile, open a provider page, book a test reservation as a test
patient, check `/ready/`, and scan the logs for ERROR lines from the last 15 minutes.

## 7. Rollback — three tiers

Choose the lowest tier that solves the problem. Decide within minutes; do not debug on a broken
production for an hour before rolling back.

**Tier 1 — redeploy the previous build (code only, no migration in the bad release).**
Railway dashboard → service → Deployments → select the last good deployment → *Redeploy*. Verify
with `smoke_http.sh`. Variables are unchanged. Use when: a code regression, a bad config value (fix
the variable instead if that is the cause).

**Tier 2 — fix forward / revert commit + redeploy (the bad release ran a migration).**
The old code may not work with the new schema, and the schema cannot be un-migrated safely.
Options in order: (a) ship a hotfix that works with the new schema; (b) if the migration was purely
additive (new nullable column/table, the expand step), the previous code usually still works —
redeploy it (tier 1) and leave the schema; (c) otherwise go to tier 3. Never edit applied
migrations and never hand-run `migrate <app> <older>` against production.

**Tier 3 — restore the database.**
Use when data was corrupted or a destructive migration cannot be fixed forward. Follow
`docs/BACKUP_RESTORE.md` §4B: stop writes, restore the last good dump into a **new** database,
repoint `DATABASE_URL`, deploy the code version that matches the dump, smoke test, communicate the
data-loss window. Data since the backup is lost — hence the backup immediately before every
migration release.

**Also:** a bad `SECRET_KEY` change is rolled back by restoring the old value (sessions and links
issued with the old key work again). A DNS/certificate problem is fixed at the domain, not in the app.

## 8. Known gaps (be honest with stakeholders)

These are *not* blockers the engineer can fix; they are the boundary of what 12A delivers.

- **No production or staging environment exists; none of the platform-dependent claims has been
  verified on Railway** (proxy count, edge logs, health-check behaviour, certificate, e-mail
  delivery, backup timing).
- **E-mail provider, sending domain, off-site backup store, domain name, monitoring recipients, admin
  2FA policy, privacy policy** — owner-provided inputs, not yet provided.
- Python transitive dependencies are not hash-locked (only direct pins plus PyJWT); a full lock file
  with hashes is a worthwhile follow-up.
- Throttle counters are per process; no shared cache or Redis (not needed for one container).
- The refresh token is in `localStorage` (ADR-061, deferred).
- No automated retention for audit logs, notifications or chat beyond refresh tokens
  (`prune_expired_tokens`); decide retention with the owner/legal before the tables become large.
- No performance measurement on target hardware (`docs/PERFORMANCE.md`).
- Mobile: production signing key, store listing, Firebase production values, real-device and
  real-FCM verification (`docs/MOBILE_RELEASE.md` §13).
- Images/uploads: not implemented (§5).
