# Authentication

One `Account` model, one session mechanism, for every client (web, mobile,
dashboards). There are no per-role authentication systems.

## Mechanism (implemented)

JSON Web Tokens via `djangorestframework-simplejwt`.

| Token | Lifetime (env) | Storage guidance |
| --- | --- | --- |
| Access | `ACCESS_TOKEN_LIFETIME_MINUTES` (default 15) | Memory only. Sent as `Authorization: Bearer …`. |
| Refresh | `REFRESH_TOKEN_LIFETIME_DAYS` (default 14) | Web: `localStorage` (Phase 0 trade-off, see `SECURITY.md`). Mobile: secure storage (Keychain/Keystore). |

- Refresh tokens **rotate**: every call to `/auth/refresh` returns a new pair
  and blacklists the old refresh token. Reusing an old one fails with
  `token_not_valid`.
- Logout blacklists the refresh token. Access tokens simply expire.
- `last_login` is updated on login.
- The JWT `sub` claim is the account UUID.
- Login is case-insensitive on email (`AccountManager.get_by_natural_key`).
- Auth endpoints are throttled at `10/min` per client IP/user (`auth` scope).

## Flows

### Register

```
POST /api/v1/auth/register
{ "email", "password", "full_name", "phone_number"?, "role"?, "preferred_language"? }
→ 201 { "account": {...}, "tokens": { "access", "refresh" } }
```

`role` may be `PATIENT` (default), `PROVIDER`, `MEDICAL_COMPANY` or
`REAL_ESTATE_SELLER` (`settings.RACHEETA["SELF_REGISTRATION_ROLES"]`). `ADMIN`
is rejected. Provider-type accounts will require administrator verification
before they can publish anything **(planned, Phase 2)**.

Password rules: min 8 chars, not too similar to email/name, not a common
password, not purely numeric (Django validators).

### Login / refresh / logout

```
POST /api/v1/auth/login    { "email", "password" }   → 200 { "access", "refresh" }
POST /api/v1/auth/refresh  { "refresh" }             → 200 { "access", "refresh" }
POST /api/v1/auth/logout   { "refresh" }             → 204
```

### Current user

```
GET   /api/v1/me           → account + role + permissions
PATCH /api/v1/me           { "full_name"?, "phone_number"?, "preferred_language"? }
```

## Web client behaviour (`web/src/api/client.ts`)

1. Attach the access token if present.
2. On 401, call `/auth/refresh` once (single in-flight refresh shared by
   concurrent requests), store the new pair, retry the original request.
3. If refresh fails, clear the session (`tokenStore.clear()`); UI subscribers
   are notified.

## Firebase (planned)

```
Firebase ID token → POST /api/v1/auth/firebase/exchange → backend verifies with
Firebase Admin SDK → finds/creates Account (unusable password) → returns
Racheeta access + refresh tokens.
```

Never generate fake passwords for Firebase users: `create_user(password=None)`
already sets an unusable password.

## Django admin

The admin site (`/admin/` by default, `ADMIN_URL_PATH` to change) uses Django's
session authentication and requires `is_staff`. It is an operations tool, not
a client of the API.
