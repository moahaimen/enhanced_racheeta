# Authentication

One `Account` model, one session mechanism, for every client (web, mobile,
dashboards). There are no per-role authentication systems.

## Mechanism (implemented)

JSON Web Tokens via `djangorestframework-simplejwt`.

| Token | Lifetime (env) | Storage guidance |
| --- | --- | --- |
| Access | `ACCESS_TOKEN_LIFETIME_MINUTES` (default 15) | Memory only. Sent as `Authorization: Bearer …`. |
| Refresh | `REFRESH_TOKEN_LIFETIME_DAYS` (default 14) | Web: `localStorage` (interim, ADR-009). Mobile: secure storage (Keychain/Keystore). |

- Refresh tokens **rotate**: every call to `/auth/refresh` returns a new pair
  and blacklists the old refresh token. Reusing an old one fails with
  `token_not_valid`.
- Logout blacklists the refresh token. Access tokens simply expire.
- A completed password reset blacklists **every** outstanding refresh token
  of the account; access tokens issued before the reset stay valid for at
  most `ACCESS_TOKEN_LIFETIME_MINUTES`.
- `last_login` is updated on login.
- The JWT `sub` claim is the account UUID.
- Login is case-insensitive on email (`AccountManager.get_by_natural_key`).
- Throttles (per client IP for anonymous calls, per user otherwise):
  `auth` 10/min (register, login, refresh, logout, Firebase exchange),
  `password_reset` 5/min, `email_verification` 3/min.
- Validation messages are localised per request from `Accept-Language`
  (`LocaleMiddleware`; default Arabic). The web client sends the UI language.

## Flows

### Register

```
POST /api/v1/auth/register
{ "email", "password", "full_name", "phone_number"?, "role"?, "preferred_language"? }
→ 201 { "account": {...}, "tokens": { "access", "refresh" } }
```

`role` may be `PATIENT` (default), `PROVIDER`, `MEDICAL_COMPANY` or
`REAL_ESTATE_SELLER` (`SELF_REGISTRATION_ROLE_CHOICES`, mirrored in
`settings.RACHEETA["SELF_REGISTRATION_ROLES"]`). `ADMIN` is rejected.
Provider-type accounts will require administrator verification before they
can publish anything **(planned, Phase 2)**.

Password rules: min 8 chars, not too similar to email/name, not a common
password, not purely numeric (Django validators). Violations come back under
`details.password`.

### Login / refresh / logout

```
POST /api/v1/auth/login    { "email", "password" }   → 200 { "access", "refresh" }
POST /api/v1/auth/refresh  { "refresh" }             → 200 { "access", "refresh" }
POST /api/v1/auth/logout   { "refresh" }             → 204   (400 token_invalid if malformed/already revoked)
```

### Current user

```
GET   /api/v1/me           → account + role + permissions + email_verified(_at) + has_password
PATCH /api/v1/me           { "full_name"?, "phone_number"?, "preferred_language"? }
```

### Password reset

```
POST /api/v1/auth/password-reset/request  { "email" }
  → 202 { "detail": "If an account exists for this email, a reset link has been sent." }
POST /api/v1/auth/password-reset/confirm  { "uid", "token", "new_password" }
  → 200 { "detail": "Password updated. Please log in again." }
  → 400 details.token       (invalid, expired, already used, wrong account, inactive)
  → 400 details.new_password (password rules; the link stays usable)
```

- The request endpoint answers identically whether or not the email exists
  and only emails active accounts. Firebase-only accounts (no password) may
  also reset, which gives them a password login.
- The email links to `{FRONTEND_URL}/reset-password?uid=…&token=…`.
- Token design: Django's `PasswordResetTokenGenerator` with a project salt.
  It is an HMAC (keyed by `SECRET_KEY`) over a timestamp and a snapshot of
  `(pk, password hash, last_login, email)`. It never contains the password,
  expires after `PASSWORD_RESET_TIMEOUT_MINUTES` (default 60), and is
  single-use because the password hash changes on success. Nothing is stored
  in the database.
- Completing a reset also marks the email as verified (mailbox control proven)
  and revokes all refresh tokens.

### Email verification

```
POST /api/v1/auth/email-verification/request   (bearer)  → 202 { "detail" }
                                               → 400 non_field_errors when already verified
POST /api/v1/auth/email-verification/confirm   { "uid", "token" } → 200 { "detail" }
                                               → 400 details.token
```

- `Account.email_verified_at` (timestamp, null = unverified) is the state;
  `/me` exposes both `email_verified` and `email_verified_at`.
- Token: `EmailVerificationToken` (own salt) over `(pk, email,
  email_verified_at)`; expires after `EMAIL_VERIFICATION_TIMEOUT_HOURS`
  (default 24). Any link issued before verification works until one is used;
  after success the confirm endpoint is idempotent (200) so a double click on
  the link is harmless. Changing the email invalidates outstanding links.
- Verification is **not** required for any existing functionality. A
  business rule that gates a feature on it must be documented in
  `PERMISSIONS.md` when it is introduced.
- The link goes to `{FRONTEND_URL}/verify-email?uid=…&token=…`.

### Firebase (adapter implemented, provider not activated)

```
POST /api/v1/auth/firebase/exchange  { "id_token", "role"? }
  → 200 { "account", "tokens", "created": false }   existing account
  → 201 { "account", "tokens", "created": true }    account created
  → 401 firebase_token_invalid  · 403 email_not_verified  · 400 details.id_token (email_required)
  → 503 firebase_not_configured (default until the owner enables it)
```

Server-side verification is mandatory; the endpoint only sees a
`FirebaseIdentity` produced by the configured `FirebaseVerifier`
(`apps/accounts/firebase.py`). Linking rules:

1. Account with this Firebase `uid` → sign in.
2. Otherwise the identity must carry an email (phone-only sign-in is not
   supported yet, ADR-018).
3. Account with that email exists → link **only if Firebase reports the email
   as verified**; otherwise 403. An attacker cannot claim an existing
   Racheeta account by creating an unverified Firebase user with its email.
4. Otherwise create the account with an **unusable password** (never a fake
   one), the requested self-registration role (default PATIENT), and
   `email_verified_at` set when Firebase verified the email.

**To activate** (owner action, outside this repository):

1. `pip install firebase-admin` and add it to `backend/requirements/base.txt`.
2. Provide the service-account JSON to the runtime (Railway: a file mounted
   from a secret, or written from an env var at start-up) and set
   `FIREBASE_CREDENTIALS_FILE=/path/to/it`.
3. Set `FIREBASE_VERIFIER=apps.accounts.firebase.FirebaseAdminVerifier`.
4. `manage.py check` verifies the verifier loads (`racheeta.E002` otherwise).
5. Run an end-to-end test with a real ID token from the Flutter/web client
   before announcing the feature.

Nothing in the repository contains Firebase credentials, and CI never needs them.

## Email provider

Emails go through Django's email backend configured by `EMAIL_URL`
(django-environ syntax). Development uses `consolemail://`, which prints the
message, including the reset link, to stdout. A system check
(`racheeta.E001`) makes `manage.py check` fail when the console or locmem
backend is configured with `DEBUG=false`, so a production deployment cannot
silently log tokens.

Choosing and configuring the production provider is an owner decision
(`RAILWAY.md`). The integration point is only `EMAIL_URL` and
`DEFAULT_FROM_EMAIL`; templates live in `apps/accounts/emails.py`.

## Web client behaviour

- `web/src/auth/AuthContext.tsx` is the single session layer: status
  (`restoring` → `anonymous` | `authenticated`), account from `/me`, login,
  register, logout, session restoration, subscription to the token store.
- `web/src/app/guards.tsx` holds every route guard: `RequireAuth` (protected
  pages; anonymous users go to `/login` with the return path), `PublicOnly`
  (login/register; authenticated users are sent on), and the restoration
  loading state.
- `web/src/api/client.ts`: attach the access token; on 401 refresh once
  (single in-flight refresh) and retry; if refresh fails, clear the session,
  which the AuthProvider observes.
- Logout clears the local session first and then calls `/auth/logout`; a
  backend "already invalid" answer is swallowed so the user is always logged
  out locally.

## Django admin

The admin site (`/admin/` by default, `ADMIN_URL_PATH` to change) uses Django's
session authentication and requires `is_staff`. It is an operations tool, not
a client of the API.
