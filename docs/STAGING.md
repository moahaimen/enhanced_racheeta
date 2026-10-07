# Staging

A staging environment is a full, separate copy of the production shape (one service + one
PostgreSQL) with **its own secrets, its own database and no real user data**. Its job is to prove
every unverifiable claim from Phase 12A before production: proxy behaviour, e-mail delivery,
migrations on a real platform, backup/restore timing, mobile and web against a real HTTPS API.

> Phase 12A status: **not created.** Creating it is Phase 12B and needs owner approval of the
> spend and the inputs in §1. Do not skip staging and go straight to production.

## 1. Owner inputs needed before 12B

| Input | Notes |
| --- | --- |
| Railway account/project access and approval of the plan cost | Staging runs one small service + one Postgres; check the current price. A hobby/low plan is enough; staging may be stopped when idle. |
| Staging hostname | The Railway-generated domain is fine; a custom `staging.<domain>` needs DNS control. |
| E-mail provider SMTP credentials + a verified sending domain | Use a real mailbox you own as the test recipient. Use a separate credential from production. |
| A mailbox/phone for the throttle check from two networks (§3.2) | |
| Optional: Firebase project for push (staging project, not production) | Skip push on first pass; it is disabled without configuration. |
| An Android device or emulator that can reach the staging URL | For the mobile pass. |

## 2. Create it

Follow `docs/RAILWAY.md` §1–§4 with these differences from production:

- Project/environment name `racheeta-staging`; **new** `SECRET_KEY`; new database; no shared secrets.
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` use the staging host.
- `EMAIL_URL` points at the real provider but `DEFAULT_FROM_EMAIL` clearly marks staging
  (`Racheeta Staging <no-reply@…>`); only send to mailboxes you control.
- Keep `API_DOCS_ENABLED` unset (staging should behave like production). If you need Swagger for
  a test, enable it temporarily and remove it.
- Deploy from a tagged commit of `main` after the 12A PR is merged (not from the feature branch).

## 3. Acceptance checklist (record the date, commit and result of each)

### 3.1 Platform and configuration
- [ ] Deploy log shows `check` passing, migrations applied, gunicorn listening; no `racheeta.E…`.
- [ ] `scripts/smoke_http.sh https://<staging-host>` prints `SMOKE PASSED`.
- [ ] `GET /ready/` is 200; stop the Postgres service briefly → `/ready/` 503 and `/health/` 200;
      start it again → recovers without redeploying. (Do not do this in production.)
- [ ] A deliberately broken variable (e.g. `TRUSTED_PROXY_COUNT=0`) makes the *new* deployment fail
      its health check and the previous deployment keeps serving. Restore the variable.
- [ ] `curl -I https://<host>/` shows the CSP, `Referrer-Policy: no-referrer`, HSTS, `X-Frame-Options`;
      `curl -I http://<host>/` redirects to HTTPS; `/api/docs/` is 404.
- [ ] Open the site in a browser with dev tools: no CSP violations in the console on the home page,
      login, provider search, jobs and real-estate pages (Arabic and English).

### 3.2 Proxy count / rate limiting
- [ ] The two-network procedure in `docs/RAILWAY.md` §5 passes (record the value you ended with).

### 3.3 E-mail (ADR-059, `docs/OPERATIONS.md` §4)
- [ ] Password reset mail arrives, link works, token is single use.
- [ ] Verification mail arrives, link works.
- [ ] Mail from the staging domain passes SPF/DKIM/DMARC (check the headers in the received message).
- [ ] With a broken credential: reset request 202, verification 503 `email_unavailable`, ERROR in
      logs without tokens. Credential restored.
- [ ] The token does not appear in any Railway log line (search for the first 6 characters of a real
      token you received).

### 3.4 Data and backups
- [ ] Create staging accounts through the UI (provider, patient, employer) and a few records.
- [ ] `scripts/backup/backup_db.sh` against staging produces a dump; `restore_db.sh` restores it into a
      new database; `check`/`showmigrations` against that copy are clean. **Write down the elapsed
      time** in `docs/BACKUP_RESTORE.md` §1 (the measured RTO).
- [ ] `manage.py prune_expired_tokens --dry-run` runs inside the service shell.
- [ ] The off-site upload (`offsite_upload.sh`) works against a real test bucket, if one was chosen.

### 3.5 Load (indicative only)
- [ ] `scripts/loadtest/loadtest.py --allow-host <staging-host>` at concurrency 4/8/16, 30 s each,
      with `seed_synthetic --allow-nonlocal-host` data on **staging only**. Record the results in
      `docs/PERFORMANCE.md` §5 with the instance size. Delete the synthetic rows afterwards (they are
      all `@synthetic.invalid`).

### 3.6 Clients
- [ ] Web: full walkthrough in Arabic and English on a phone and a desktop.
- [ ] Mobile: build with the release defines for staging
      (`--dart-define=APP_ENV=staging --dart-define=API_BASE_URL=https://<staging-host>` — origin only, no
      path), register, log in, book a reservation, receive a persistent notification, chat.
      `API_BASE_URL` with a path is rejected at startup.
- [ ] Push (only if a staging Firebase project was configured): token registers and a notification
      push arrives on a real device. Otherwise record "push untested".

### 3.7 Rollback rehearsal
- [ ] Redeploy the previous deployment from the Railway UI (tier 1) and confirm it serves.
- [ ] Walk through tier 3 once (restore into a new database and repoint) using the staging backup.

## 4. Exit criteria

Staging is "green" when every box above is ticked or has a written, owner-accepted reason, and the
results (dates, commit, instance size, timings) are recorded in this file. Only then plan 12C.

## 5. Results log

| Date | Commit | Result | Notes |
| --- | --- | --- | --- |
| — | — | not yet run | Phase 12B |
