# Staging

A staging environment is a full, separate copy of the production shape (one service + one
PostgreSQL) with **its own secrets, its own database and no real user data**. Its job is to prove
every unverifiable claim from Phase 12A before production: proxy behaviour, e-mail delivery,
migrations on a real platform, backup/restore timing, web (and later mobile) against a real HTTPS API.

> **Status (2026-10-27): staging EXISTS and is healthy.** Railway project `racheeta-staging`
> (environment `staging`, services `racheeta-app` + `Postgres`), created by the owner; public origin
> **`https://racheeta-app-staging.up.railway.app`**. It serves `main`
> `83ac6dd2363c6ce256402885d3fea10c0249248b` (the web bundle hash served by staging,
> `assets/index-DrgHL6ik.js`, is the hash a local production build of that commit produces).
> The database holds **no demo data yet** (`GET /api/v1/providers` → `count: 0`): seeding happens
> after the demo-data PR is reviewed and merged (§6). Production does not exist.

## 1. Owner inputs (what was needed, what is still open)

| Input | State |
| --- | --- |
| Railway account/project, plan cost approved | **done** (project exists) |
| Staging hostname | Railway-generated domain in use; a custom `staging.<domain>` is optional |
| E-mail provider | Resend transport is deployed in code (`EMAIL_PROVIDER=resend`, ADR-062). Whether the staging service's `RESEND_API_KEY` / `DEFAULT_FROM_EMAIL` are set, and whether a sending domain is verified, is **only visible in the Railway dashboard** — see §3.3 |
| A mailbox/phone for the throttle check from two networks (§3.2) | **OWNER** |
| Optional: Firebase project for push | out of scope for the web release |
| An Android device or emulator | out of scope for the web release (mobile is a later phase) |

## 2. Create it

Follow `docs/RAILWAY.md` §1–§4 with these differences from production:

- Project/environment name `racheeta-staging`; **new** `SECRET_KEY`; new database; no shared secrets.
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` use the staging host.
- E-mail: **Resend over HTTPS** (`EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, no `EMAIL_URL`; see
  `docs/OPERATIONS.md` §4). `DEFAULT_FROM_EMAIL` clearly marks staging; only send to mailboxes you
  control.
- Keep `API_DOCS_ENABLED` unset (staging behaves like production). Verified: `/api/docs/` is 404.
- Deploy from `main` (not from a feature branch).

## 3. Acceptance checklist

Legend: **VERIFIED** (done, evidence in §5) · **NOT VERIFIED** (an engineer can do it with
dashboard/variable access; exact procedure given) · **OWNER** (needs an owner-only input or decision)
· **OPTIONAL** (not required for the first web release).

### 3.1 Platform and configuration
- [x] **VERIFIED** `GET /health/` 200 `{"status":"ok"}`, `GET /ready/` 200 `{"status":"ready"}` over HTTPS.
- [x] **VERIFIED** `http://` → 301 to `https://`; HSTS (30 days, includeSubDomains), CSP,
      `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
      `Cross-Origin-Opener-Policy`, `Permissions-Policy` present; `/api/docs/` 404.
- [x] **VERIFIED** The web app loads in Arabic (RTL) and English (LTR) with the self-hosted Cairo
      font on `/`, `/providers`, `/jobs`, `/real-estate`, `/login` at 1440×900 and 390×844: no
      horizontal overflow, no console error, no CSP violation (headless Chromium, §5).
- [ ] **NOT VERIFIED** Deploy log shows `check` passing, migrations applied, gunicorn listening; no
      `racheeta.E…` — *read the deploy log in the Railway dashboard.*
- [ ] **NOT VERIFIED** `scripts/smoke_http.sh https://racheeta-app-staging.up.railway.app` —
      *run from any machine with curl; expected `SMOKE PASSED`* (the individual expectations it
      encodes — health, ready, redirect, headers, docs 404 — were checked by hand).
- [ ] **NOT VERIFIED** Stop Postgres briefly → `/ready/` 503, `/health/` 200; restart → recovers —
      *Railway dashboard; do it only outside a demo.*
- [ ] **NOT VERIFIED** A deliberately broken variable makes the new deployment fail its health check
      and the previous one keeps serving — *Railway dashboard.*
- [ ] **NOT VERIFIED** A `GET` of a fresh dashboard page after login shows no CSP violation —
      *covered locally for every role (§5); on staging it needs demo accounts, i.e. after seeding.*

### 3.2 Proxy count / rate limiting
- [ ] **OWNER** The two-network procedure in `docs/RAILWAY.md` §5 (needs two networks and the
      variable `TRUSTED_PROXY_COUNT` visible in the dashboard). *Record the value you ended with.*

### 3.3 E-mail (ADR-059/062, `docs/OPERATIONS.md` §4)
- [ ] **NOT VERIFIED / OWNER** Password-reset mail arrives, link works, token single-use;
      verification mail arrives. *Needs a mailbox the owner controls.* Note: a Resend account
      without a verified sending domain can only deliver to the account owner's own address
      (Resend "onboarding" sender) — in that state staging e-mail is **functional but restricted**;
      classify it that way rather than as broken. A verified production sending domain is a
      production (12C) OWNER prerequisite, not a staging blocker.
- [ ] **NOT VERIFIED** SPF/DKIM/DMARC pass on a received message — *after a domain is verified.*
- [ ] **NOT VERIFIED** Broken credential → reset 202, verification 503 `email_unavailable`, ERROR
      logged without tokens — *Railway variables.*
- [ ] **NOT VERIFIED** No token appears in any Railway log line — *Railway logs.*

### 3.4 Data and backups
- [ ] **NOT VERIFIED** Create staging accounts through the UI — *superseded by the demo dataset (§6);
      a real registration through the UI still proves the e-mail path (3.3).*
- [x] **VERIFIED (locally)** `backup_restore_smoke.sh` round trip on the seeded demo database: 7 s,
      checksums, identical row counts (`docs/BACKUP_RESTORE.md` §1a).
- [ ] **NOT VERIFIED** The same round trip against the **staging** database — *needs the staging
      `DATABASE_URL` from the Railway dashboard:*
      `SOURCE_DATABASE_URL='<staging DATABASE_URL>' scripts/backup/backup_restore_smoke.sh`
      (it restores into a **new** scratch database and never writes to the source; record the
      elapsed time in `docs/BACKUP_RESTORE.md` §1).
- [ ] **NOT VERIFIED** `manage.py prune_expired_tokens --dry-run` inside the service shell —
      *Railway shell.*
- [ ] **OWNER** Off-site upload (`offsite_upload.sh`) — *needs a bucket and credentials.*

### 3.5 Load (indicative only)
- [ ] **OPTIONAL** `scripts/loadtest/loadtest.py --allow-host racheeta-app-staging.up.railway.app`
      at concurrency 4/8/16 with synthetic data; record in `docs/PERFORMANCE.md` §5. *Not required
      for the first web release; needs an owner-approved window on the shared plan.*

### 3.6 Clients
- [x] **VERIFIED (web, anonymous pages)** Arabic/English, desktop/mobile widths (§5).
- [ ] **NOT VERIFIED (web, signed-in pages on staging)** — *after seeding (§6): log in as each demo
      role and walk the dashboards; the same walk was done locally against the seeded database
      (`docs/FINAL_WEB_READINESS.md` §3).*
- [ ] **OUT OF SCOPE** Mobile app against staging; push — later phase.

### 3.7 Rollback rehearsal
- [ ] **NOT VERIFIED** Redeploy the previous deployment (tier 1) — *Railway dashboard.*
- [ ] **NOT VERIFIED** Tier 3 (restore into a new database and repoint) — *after 3.4.*

## 4. Exit criteria

Staging is "green" for the **web release** when every item above is VERIFIED or has a written,
owner-accepted reason. The items an engineer cannot do from the repository alone are exactly the
NOT VERIFIED ones that need Railway dashboard/variable/shell access, plus the OWNER ones.

## 5. Results log

| Date | Commit on staging | Check | Result |
| --- | --- | --- | --- |
| 2026-10-27 | `83ac6dd` (bundle `index-DrgHL6ik.js`) | `/health/`, `/ready/` | 200 / 200, ≈0.5 s each from outside |
| 2026-10-27 | `83ac6dd` | HTTP→HTTPS, HSTS, CSP, XFO, nosniff, COOP, Permissions-Policy, Referrer-Policy | present (`curl -I`) |
| 2026-10-27 | `83ac6dd` | `/api/docs/` | 404 (docs disabled) |
| 2026-10-27 | `83ac6dd` | `/api/v1/specialties`, `/api/v1/providers`, `/api/v1/jobs`, `/api/v1/real-estate/listings`, `/api/v1/marketplace/categories` | 200; counts 0 (unseeded) except reference data |
| 2026-10-27 | `83ac6dd` | Web walk (`/`, `/providers`, `/jobs`, `/real-estate`, `/login`) ar 1440 / ar 390 / en 1440 | `scrollWidth == clientWidth` everywhere, 5 nav links, `lang`/`dir` correct, Cairo Variable, 0 console errors, 0 CSP violations |
| 2026-10-27 | local (`racheeta_dev`, seeded) | `backup_restore_smoke.sh` | PASSED, 7 s |
| — | — | proxy count, e-mail delivery, failed-deploy behaviour, Railway backup timing, rollback | not run (dashboard/variable access needed) |

## 6. Seeding the demo dataset on staging (do this only after merge)

Preconditions, in order: the demo-data PR is independently reviewed → the owner authorises the
merge → merge → CI green on the merge commit → Railway deploys that commit to staging (check the
deployed commit in the dashboard; the migration `demo/0001` is applied by the release command).
Then, in the Railway dashboard for the **staging** service only:

1. Variables: add `DEMO_DATA_ENABLED=true` and `DEMO_PASSWORD=<a staging-only password ≥ 12 chars>`
   (or, for the **first** seed only, omit `DEMO_PASSWORD` and use `--generate-password`, which prints
   it once; a re-run must use the same password — a different one or `--generate-password` is refused).
2. Shell (`railway ssh` or the dashboard shell): `python manage.py seed_demo_data --dry-run`, read
   the plan, then `python manage.py seed_demo_data`. Expected end: `seed_demo_data: done.` with the
   counts in `docs/DEMO_DATA.md` §3.
3. Open the site: the homepage statistics, doctors, facilities, jobs, listings and categories are
   populated. Log in with the matrix in `docs/DEMO_DATA.md` §2.
4. Remove `DEMO_DATA_ENABLED` afterwards if the commands should not stay usable. To empty the
   environment: `python manage.py clear_demo_data --dry-run --yes`, then `--yes`.

**Adding portraits to an existing seed:** run `python manage.py seed_demo_data` again with the same
`DEMO_DATA_ENABLED=true` and `DEMO_PASSWORD` (the password the demo accounts already use; a different
one is refused). It only fills empty `image_url` fields of registered demo practitioners.

Never set `DEMO_DATA_ENABLED` on a production service.
