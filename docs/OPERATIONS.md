# Operations

How to run Racheeta once it is deployed. Written for an engineer who has this repository and the
platform dashboards, nothing else. Deployment itself is in `docs/RAILWAY.md`,
`docs/STAGING.md` and `docs/PRODUCTION_DEPLOYMENT.md`; backups in `docs/BACKUP_RESTORE.md`;
performance numbers in `docs/PERFORMANCE.md`.

> Phase 12A status: the code, logs and scripts described here exist and are tested locally and in
> CI. **Nothing is deployed, so no alert, dashboard or uptime check has been created** — §2 lists
> exactly what the owner must create in 12B/12C.

## 1. What the system emits

| Signal | Where | Meaning |
| --- | --- | --- |
| `GET /health/` → `{"status":"ok"}` | HTTP | The process is up. No database call. Use for uptime pings and container liveness. |
| `GET /ready/` → `{"status":"ready"}` / 503 `{"status":"unavailable"}` | HTTP | The process can reach PostgreSQL (`SELECT 1`, 2 s statement timeout). The deployment gate. A 503 never carries an error text. |
| JSON log line `{"ts","level","logger","msg","request_id", "exc"?}` | stdout (Railway logs) | Application logs. `level` ∈ DEBUG/INFO/WARNING/ERROR; `exc` is a redacted traceback. Bearer tokens, `token=`/`password:` pairs and e-mail addresses are redacted; no request bodies or headers are ever logged. |
| `X-Request-ID` response header = `request_id` in logs | HTTP / logs | Ask whoever reports an error for the id (browser dev tools → Network → the failing request → response headers) and search the logs for it. |
| gunicorn access line `ip "METHOD /path" status bytes seconds` | stdout | One per request. No query string, no referer (one-time tokens travel in query strings). The IP is the proxy's, not the client's. |
| `django.request` WARNING `Unauthorized: /api/...` | logs | A 401/4xx response. Bursts on `/api/v1/auth/login` = credential stuffing or a client bug. |
| `django.request` ERROR `Internal Server Error: /...` | logs | An unhandled exception (HTTP 500). Always actionable. |
| `password reset email delivery failed account=<uuid>` / `email verification delivery failed …` (ERROR + traceback) | logs | The mail provider refused or timed out. Users see success (reset) or a 503 `email_unavailable` (verification). |
| `[CRITICAL] WORKER TIMEOUT` (gunicorn) | logs | A request ran past `GUNICORN_TIMEOUT` (60 s) and its worker was killed. Look for a slow query or a stalled dependency. |

## 2. Monitoring and alerting the owner must create

None of these exist yet. All can be done with free tiers except where noted.

| Check | How | Alert when |
| --- | --- | --- |
| External uptime, liveness | Any uptime service, `GET https://<domain>/health/` every 1–5 min | 2 consecutive failures |
| External uptime, readiness | same, `/ready/` | 2 consecutive failures (the app is up but the database is not) |
| Error rate | Railway log search for `"level":"ERROR"` (or an external log drain if the owner adds one) | any ERROR burst; at minimum review daily for the first two weeks |
| Login failures | log search `Unauthorized: /api/v1/auth/login` | sudden multiplication versus the daily baseline |
| Platform | Railway: deployment failed, service crashed/restarting, usage/spend alert | any |
| Database size / connections | Railway PostgreSQL metrics | disk > 70%; connections near the plan limit |
| Backups | job exit status + "newest object < 26 h old" on the off-site bucket (`docs/BACKUP_RESTORE.md` §5) | missing or failed backup |
| TLS certificate | the uptime service's certificate check | < 14 days to expiry (Railway renews automatically; this catches DNS mistakes) |

Do not add a metrics stack (Prometheus, APM, Sentry) before there is traffic to justify it; if the
owner wants error tracking, a hosted service can be added as a deliberate change (new dependency,
privacy review: stack traces can contain personal data).

## 3. Routine tasks

| Task | Cadence | Command / place |
| --- | --- | --- |
| Backup + off-site copy | daily | `scripts/backup/backup_db.sh`, `offsite_upload.sh` (§ BACKUP_RESTORE) |
| Restore rehearsal | monthly and before each major release | `docs/BACKUP_RESTORE.md` §4A |
| Prune expired refresh tokens | weekly | `python manage.py prune_expired_tokens` (see below) |
| Dependency scans | before every production deploy and monthly | §6 |
| Review admin accounts | monthly | Django admin → Accounts → filter staff/superuser; remove anyone who left |
| Rotate secrets | on suspicion, staff departure, or yearly | §7 |
| Review logs for repeated ERROR lines | daily for 2 weeks after launch, then weekly | Railway logs |

**Pruning refresh tokens.** `OutstandingToken` rows (one per issued refresh token) and their
`BlacklistedToken` rows only grow. The command deletes expired tokens in batches (default 5000),
is idempotent, prints one summary line, and has `--dry-run`:

```bash
python manage.py prune_expired_tokens --dry-run   # count only
python manage.py prune_expired_tokens             # delete expired
```

Run it weekly, inside the running service (Railway: the service's shell, or `railway ssh` in a recent CLI — check the current Railway docs, the menu names change; note that `railway run` executes on *your* machine with the service's variables, where the private database address is not reachable, so use the public `DATABASE_URL` only for a deliberate one-off). (**no scheduler is configured by this
repository** — a cron service would be a new always-on resource and needs an ADR; a manual weekly run
is enough at launch volumes, and a reminder in the owner's calendar is acceptable). If the table is
very large (millions), run with a smaller `--batch-size` during off-peak hours.

## 4. E-mail

Mail is sent synchronously and is bounded (ADR-059): connection and send time out after
`EMAIL_TIMEOUT` seconds (default 10). Failures are logged (ERROR with the account id) and never
shown to anonymous callers.

**Choosing a provider (owner).** Any provider offering authenticated SMTP works (the code only uses
Django's SMTP backend via `EMAIL_URL`). Requirements: a sending domain you control with **SPF,
DKIM and DMARC** published; STARTTLS on port 587; an API/SMTP credential limited to sending. Set
`EMAIL_URL=smtp://USER:PASSWORD@HOST:587?tls=True` (percent-encode `@`, `:` and `/` in credentials)
and `DEFAULT_FROM_EMAIL=Racheeta <no-reply@yourdomain>`. A provider with an HTTP API but no SMTP
needs a small backend added in a later phase; none is assumed here.

**Verification in staging (mandatory before 12C):**
1. Request a password reset for a mailbox you own → the mail arrives (check spam), the link opens
   `https://<domain>/reset-password?uid=…&token=…`, and resetting works.
2. Register a new account → request verification → mail arrives → link verifies.
3. Break the credential deliberately (wrong password in `EMAIL_URL` on staging): the reset request
   still answers 202, the verification request answers 503 `email_unavailable`, and the logs show the
   ERROR line without any token. Restore the credential.
4. Confirm the token does **not** appear in Railway's HTTP/edge logs for the page URL
   (`/reset-password?token=…`). If the platform's edge log records query strings, treat reset links
   as sensitive in that log (restrict who can read logs) — the application cannot change that.

**Bounces and complaints** are handled in the provider's dashboard; there is no bounce webhook.

## 5. Incident runbook

First actions for any incident: note the time, check `/ready/` and `/health/`, check the last
deployment in Railway, read the last 200 log lines filtered to WARNING/ERROR.

| Symptom | Likely cause | Do |
| --- | --- | --- |
| `/health/` fails | container crashed / not started | Railway deploy log: a failed `manage.py check` prints the offending `racheeta.E…` id (e.g. E005 proxy count, E007 CSRF origin). Fix the variable and redeploy. If caused by the latest deploy, roll back (PRODUCTION_DEPLOYMENT §7). |
| `/health/` ok, `/ready/` 503 | database unreachable | Railway PostgreSQL status; `DATABASE_URL` reference intact; connection limit; disk full. Do not restart the app repeatedly. |
| Many 500s after a deploy | code or migration problem | Read ERROR lines with `request_id`; roll back code (tier 1). If a migration ran, see tier 2. |
| Many 429 for different users | throttle keyed to the proxy | `TRUSTED_PROXY_COUNT` wrong (RAILWAY §5). |
| Users report "no reset email" | provider outage/credential | grep `delivery failed`; check provider dashboard and SPF/DKIM; fix `EMAIL_URL`. |
| Slow responses, `WORKER TIMEOUT` | slow query or DB load | `docs/PERFORMANCE.md` EXPLAIN procedure; check DB CPU; temporarily raise `WEB_CONCURRENCY` only if CPU/RAM allow. |
| Suspected account compromise | — | Deactivate the account in the admin (`is_active` off: its access tokens stop authenticating and its refresh tokens stop working); a password reset also revokes all its refresh tokens; review the audit log entries for the account in the admin. |
| Suspected secret leak | — | §7 immediately, then rotate dependent credentials. |
| Database restore needed | — | `docs/BACKUP_RESTORE.md` §4B. |

After an incident add a dated entry here (what happened, detection, fix, follow-up).

## 6. Dependency and secret scanning (run before each production deploy)

```bash
# Python (run in an environment with the app's requirements installed)
pip install pip-audit && pip-audit --path backend/.venv/lib/python3.13/site-packages
# npm
(cd web && npm audit --omit=dev && npm audit)
# Flutter
(cd mobile && flutter pub outdated)
# secrets in git history and the working tree (gitleaks)
gitleaks detect --source . --redact && gitleaks detect --no-git --source . --redact
```

Record anything new in `docs/SECURITY.md` "Dependency policy and scanning" with a disposition
(fixed / accepted with reason / deferred with trigger). The 12A results are recorded there.

## 7. Secrets and rotation

| Secret | Where it lives | Rotation effect |
| --- | --- | --- |
| `SECRET_KEY` | Railway variable (per environment) + owner's password manager | Invalidates all JWTs, reset/verification links and admin sessions. Everyone logs in again. Plan a quiet moment. |
| `DATABASE_URL` | Railway reference to the Postgres service | Rotate the database password in Railway; the reference follows; redeploy. |
| `EMAIL_URL` credential | Railway variable | Create a new provider key, set it, redeploy, revoke the old key. |
| Firebase service account (when activated) | mounted file path in `FIREBASE_CREDENTIALS_FILE` | Create a new key in the Firebase console, replace, redeploy, delete the old key. |
| Android release keystore | owner's secure storage (never in the repo) | Not rotatable after Play enrolment without Play's key-upgrade process. Back it up in two places. |
| Off-site backup bucket key | backup scheduler's secret store | Create new key, update scheduler, delete old key. |

If a secret was committed to git, rotating it is mandatory — deleting it from history is not
enough.

## 8. Access and accounts

- The Django admin is the only privileged interface. Create staff only with `createsuperuser` /
  the admin, never through the API (the API rejects privilege fields). The admin path can be changed
  with `ADMIN_URL_PATH` (obscurity, not a control). **Recommended before launch (owner decision):**
  strong unique passwords and, ideally, a 2FA layer in front of the admin; none is implemented.
- Railway and GitHub access: use individual accounts with 2FA; keep the project owner count minimal.
- Production data is never copied to developer machines or staging.

## 9. Scaling notes

One container, `WEB_CONCURRENCY=2` sync workers, per-process throttle counters and no shared cache.
Before adding replicas: move `migrate` to a pre-deploy step, replace the local-memory throttle
cache with a shared one (Redis would be the first justified use), and re-run the load harness. See
`docs/PERFORMANCE.md` for what was measured and what was not.
