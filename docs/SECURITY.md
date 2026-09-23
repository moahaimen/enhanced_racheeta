# Security

## Non-negotiables (from the master plan) and where they are enforced

| Rule | Enforcement |
| --- | --- |
| No secrets in source | `SECRET_KEY`, `DATABASE_URL` etc. are required environment variables (`config/settings.py`). `.gitignore` excludes `.env`, keys, Firebase service-account files. CI uses throwaway values. |
| Never log tokens or passwords | No code logs request bodies, `Authorization` headers, reset/verification tokens or passwords (`apps/accounts/services.py` logs account ids only; a test asserts the reset token never reaches the log). gunicorn access logs contain method + path; tokens are never put in query strings for the API (email links carry them to the SPA, which posts them in a JSON body). The console email backend is refused in production (`racheeta.E001`). |
| Never expose password fields | `AccountSerializer` has an explicit field allow-list without `password`. Tests assert no hash leaks. `has_password` is a boolean only. |
| Clients cannot send privilege fields | `ForbidPrivilegeFieldsMixin` rejects `is_staff`, `is_superuser`, `is_active`, `permissions`, `groups`, `user_permissions`, `email_verified`, `email_verified_at`, `firebase_uid`, `last_login` (+ `role`, `email`, `password`, `id` on `/me`). `create_user` refuses staff/superuser/ADMIN. DB check constraint: ADMIN ⇒ staff. Registration and Firebase exchange accept only `SELF_REGISTRATION_ROLE_CHOICES`. |
| No admin credentials in clients | None exist. Admin is the Django admin site with session auth. |
| Backend decides pricing/payment/activation | No such features yet; the rule is recorded in `DECISIONS.md` for Phase 8. |
| Separate read/write serializers | `AccountSerializer` (read) vs `AccountUpdateSerializer` / `RegisterSerializer` / reset & verification serializers (write). |
| Loading state on every backend call (web) | `ApiActionButton` disables + spinner + duplicate-click guard; `AsyncPage` for every data page. Tests cover pending state for login, register, profile save, verification resend, reset request and logout. |

## Phase 1 security review (2026-09-23)

| Topic | Finding | Status |
| --- | --- | --- |
| Privilege escalation via API bodies | All privilege/identity fields rejected with 400; DB constraint for ADMIN⇒staff. | covered by tests |
| Registration role assignment | Only four self-service roles; ADMIN rejected server-side; web never offers it. | covered |
| Login enumeration | Wrong email and wrong password both return 401 `no_active_account` with the same message. | covered |
| Password-reset enumeration | Same 202 body for known/unknown/inactive emails. Timing: sending is synchronous through the console/SMTP backend, so a slow provider could leak existence via latency. Mitigation planned: send from a background task when a worker exists. | documented |
| Reset-token expiry / reuse | 60 min (env); single-use by hash design; cross-account misuse impossible (hash includes pk). | covered |
| Email-verification expiry / reuse | 24 h (env); invalidated by email change and by verification; idempotent after success. | covered |
| JWT rotation / refresh reuse | Rotation + blacklist; reused refresh → 401. Reset revokes all refresh tokens. | covered |
| Logout | Blacklists refresh; malformed token → 400 without detail leakage; web clears local session regardless. | covered |
| `/me` permissions | Capabilities are informational; every module must enforce with permission classes. | documented |
| API error leakage | Uniform envelope; DRF default 500 handling; `DEBUG=false` in CI/prod; `manage.py check` in CI. | covered |
| Token / password logging | See table above; regression test `test_reset_flow_does_not_log_token`. | covered |
| CORS / CSRF | API uses bearer tokens (no cookies) → CSRF does not apply to `/api/v1/`; CSRF protection remains for the admin site. CORS allow-list from env; credentials not shared. Production web is same-origin. | documented |
| Duplicate submissions | `useAsyncAction` ignores runs while pending; buttons disabled; tests click twice. | covered |
| Frontend auth guards | Centralised in `app/guards.tsx`; guards are UX only — the backend rejects unauthenticated calls with 401 regardless. | covered |
| Firebase account takeover | Unverified Firebase email can never link to an existing account (403); phone numbers already in use are not copied. | covered |
| Throttling | `auth` 10/min, `password_reset` 5/min, `email_verification` 3/min; local-memory cache (per process). | covered |

No weakening of earlier decisions was needed to make tests pass.

## HTTP hardening (`DEBUG=false`)

`SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`, secure/HttpOnly session
and CSRF cookies, `Referrer-Policy: same-origin`. With `SECURE_PROXY_SSL=true`
(Railway): trust `X-Forwarded-Proto`, redirect to HTTPS, HSTS 30 days
(raise to a year after verifying HTTPS works everywhere).

## CORS

Only origins in `CORS_ALLOWED_ORIGINS`. Credentials are not shared cross-origin
(bearer tokens, not cookies). In production the web app is same-origin so the
list can be empty.

## Rate limiting

Scoped throttles listed above, backed by Django's local-memory cache — per
process. Adequate for one container; switch to a shared cache if replicas are
added.

## Token storage trade-off (web)

Access token in memory; refresh token in `localStorage`. This keeps the
session across reloads with zero infrastructure, at the cost of XSS exposure
of the refresh token. Mitigations today: no `dangerouslySetInnerHTML`, no
inline scripts, dependencies pinned. A strict CSP is **not** yet set (Phase
12). Candidate upgrade: refresh token in an httpOnly, SameSite cookie with
CSRF protection. Recorded in `DECISIONS.md` (ADR-009).

## Passwords

Django's default PBKDF2-SHA256 hasher. Validators: min length 8, similarity,
common-password list, numeric-only. Enforced on registration and on reset
confirmation. Tests use MD5 for speed only (`config/test_settings.py`).

## Email links

Reset and verification links carry an opaque `uid` (base64 UUID) and an HMAC
token. They are only ever sent to the address on the account. The SPA posts
them in a JSON body; they never appear in API access logs.

## Dependency policy

All Python and npm dependencies are pinned (`requirements/*.txt`,
`package-lock.json`). Upgrade deliberately; run the full CI.

## Reporting

Security issues: contact the owner directly. Do not open public issues.
