# Security

## Non-negotiables (from the master plan) and where they are enforced

| Rule | Enforcement |
| --- | --- |
| No secrets in source | `SECRET_KEY`, `DATABASE_URL` etc. are required environment variables (`config/settings.py`). `.gitignore` excludes `.env`, keys, Firebase files. CI uses throwaway values. |
| Never log tokens or passwords | Nothing in the codebase logs request bodies or `Authorization` headers. gunicorn access logs contain method + path only; tokens are never put in query strings. Keep it that way. |
| Never expose password fields | `AccountSerializer` has an explicit field allow-list without `password`. Tests assert no hash leaks. |
| Clients cannot send privilege fields | `ForbidPrivilegeFieldsMixin` rejects `is_staff`, `is_superuser`, `is_active`, `permissions`, `groups`, `user_permissions`, `email_verified`, `last_login` (+ `role`, `email`, `password` on `/me`). `create_user` refuses staff/superuser/ADMIN. DB check constraint: ADMIN ⇒ staff. |
| No admin credentials in clients | None exist. Admin is the Django admin site with session auth. |
| Backend decides pricing/payment/activation | No such features yet; the rule is recorded in `DECISIONS.md` for Phase 8. |
| Separate read/write serializers | `AccountSerializer` (read) vs `AccountUpdateSerializer` / `RegisterSerializer` (write). |

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

Auth endpoints: `10/min` (`REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["auth"]`).
Backed by Django's local-memory cache — per process. Adequate for one
container; switch to a shared cache if replicas are added.

## Token storage trade-off (web)

Access token in memory; refresh token in `localStorage`. This keeps the
session across reloads with zero infrastructure, at the cost of XSS exposure
of the refresh token. Mitigations today: strict CSP is **not** yet set (add in
Phase 12), no `dangerouslySetInnerHTML`, dependencies pinned. Candidate
upgrade: refresh token in an httpOnly, SameSite cookie with CSRF protection.
Recorded in `DECISIONS.md`.

## Passwords

Django's default PBKDF2-SHA256 hasher. Validators: min length 8, similarity,
common-password list, numeric-only. Tests use MD5 for speed only
(`config/test_settings.py`).

## Dependency policy

All Python and npm dependencies are pinned (`requirements/*.txt`,
`package-lock.json`). Upgrade deliberately; run the full CI.

## Reporting

Security issues: contact the owner directly. Do not open public issues.
