# API

The OpenAPI document is the contract: `docs/api/openapi.yaml` (regenerate with
`make openapi`; CI fails when it is stale). Interactive docs run at
`/api/docs/`, raw schema at `/api/schema/`.

## Conventions

- Base path: `/api/v1/`. No trailing slashes on API paths (`/api/v1/me`, not `/api/v1/me/`).
- JSON only. Requests: `Content-Type: application/json`. Multipart is accepted for uploads.
- Authentication: `Authorization: Bearer <access token>` (see `AUTHENTICATION.md`).
- Identifiers are UUID strings.
- Timestamps are ISO-8601 in UTC with `Z`, e.g. `2026-09-23T13:45:00.123456Z`.
- Field names are `snake_case`.
- Enumerations are upper-case string codes (`PATIENT`, `CONFIRMED`).
- Human-readable messages are localised from `Accept-Language` (`ar` default, `en`).
- Lists are paginated: `?page=N&page_size=M` (default 20, max 100) →
  `{"count", "next", "previous", "results"}`.
- Filtering uses query parameters per endpoint (django-filter); ordering with
  `?ordering=field` / `?ordering=-field`; search with `?search=`.
- Unknown `/api/v1/*` paths return a JSON 404 in the standard envelope.
- Simple success bodies use `{"detail": "..."}`.

## Error envelope

Every non-2xx response has this body:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Validation failed.",
    "details": { "email": ["An account with this email already exists."] }
  }
}
```

| HTTP | `code` | When |
| --- | --- | --- |
| 400 | `validation_error` | Field or request validation. `details` maps field → messages; request-level messages are under `non_field_errors`. |
| 401 | `not_authenticated` | Missing/invalid access token. |
| 401 | `no_active_account` | Login with wrong credentials or inactive account. |
| 401 | `token_not_valid` | Expired, blacklisted or malformed token. |
| 401 | `firebase_token_invalid` | Firebase ID token rejected by the verifier. |
| 403 | `permission_denied` | Authenticated but not allowed. |
| 403 | `email_not_verified` | Firebase exchange: unverified email matches an existing account. |
| 404 | `not_found` | |
| 405 | `method_not_allowed` | |
| 429 | `throttled` | Rate limit. |
| 503 | `firebase_not_configured` | Firebase exchange called while disabled. |

Handler: `backend/apps/core/exceptions.py`.

## Endpoints (implemented)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health/` | none | Liveness. `{"status":"ok"}` |
| POST | `/api/v1/auth/register` | none | Create account → `{account, tokens}` (201) |
| POST | `/api/v1/auth/login` | none | Email + password → `{access, refresh}` |
| POST | `/api/v1/auth/refresh` | none | `{refresh}` → new `{access, refresh}`; old refresh is blacklisted |
| POST | `/api/v1/auth/logout` | none | `{refresh}` → 204; refresh token blacklisted |
| POST | `/api/v1/auth/password-reset/request` | none | `{email}` → 202, enumeration-safe |
| POST | `/api/v1/auth/password-reset/confirm` | none | `{uid, token, new_password}` → 200; revokes refresh tokens |
| POST | `/api/v1/auth/email-verification/request` | bearer | Send/resend verification link → 202 |
| POST | `/api/v1/auth/email-verification/confirm` | none | `{uid, token}` → 200 |
| POST | `/api/v1/auth/firebase/exchange` | none | `{id_token, role?}` → `{account, tokens, created}` (200/201); 503 while disabled |
| GET | `/api/v1/me` | bearer | Current account: identity, role, `permissions` |
| PATCH | `/api/v1/me` | bearer | Update `full_name`, `phone_number`, `preferred_language` only |

### Account representation

```json
{
  "id": "5d5c…",
  "email": "someone@example.com",
  "full_name": "Someone",
  "phone_number": "",
  "role": "PATIENT",
  "preferred_language": "ar",
  "email_verified": false,
  "email_verified_at": null,
  "has_password": true,
  "is_staff": false,
  "permissions": ["accounts.edit_self", "accounts.view_self", "providers.search", "reservations.create_own", "reviews.create_own"],
  "created_at": "2026-09-23T13:45:00.123456Z",
  "last_login": null
}
```

`password` never appears in any response. `has_password` is false for
accounts created through Firebase that never set a password.

Sending `is_staff`, `is_superuser`, `is_active`, `permissions`, `groups`,
`user_permissions`, `email_verified`, `email_verified_at`, `firebase_uid`,
`last_login`, or (on `/me`) `role`, `email`, `password`, `id` in a request
body returns a 400 with the offending field in `details` — the request is
rejected wholesale, never partially applied.

### Geography and specialties (public, unpaginated, no auth)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/geo/countries` | Active countries |
| GET | `/api/v1/geo/governorates?country=` | Active governorates |
| GET | `/api/v1/geo/cities?governorate=` | Active cities |
| GET | `/api/v1/specialties` | Active specialties (`parent` for hierarchy) |

### Providers — public discovery (no auth)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/providers` | Paginated cards of **verified, visible** providers. Filters: `type`, `kind` (PRACTITIONER/FACILITY), `specialty` (slug), `governorate`, `city` (ids), `search` (name); `ordering` = `display_name`, `-display_name`, `created_at`, `-created_at`. |
| GET | `/api/v1/providers/{id}` | Public profile: contact, location, specialties, active `services`, `related_providers` (active memberships that are themselves public). 404 when not discoverable. |

Ratings and statistics are **not** part of these responses. Reviews arrive
in Phase 4 and will add fields then; nothing is fabricated meanwhile.

### Providers — self-management (bearer, role PROVIDER)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/providers/me` | Own profile incl. verification fields (404 until created) |
| POST | `/api/v1/providers/me` | Create profile (onboarding) → 201 |
| PATCH | `/api/v1/providers/me` | Update `display_name`, `about`, `phone`, `public_email`, `website`, `governorate`, `city`, `address`, `latitude`, `longitude`, `image_url`, `specialty_ids`, `is_visible`; `provider_type` only while not VERIFIED |
| POST | `/api/v1/providers/me/verification/request` | UNVERIFIED/REJECTED → PENDING |
| GET/POST | `/api/v1/providers/me/services` | List / add service offerings |
| GET/PATCH/DELETE | `/api/v1/providers/me/services/{id}` | Own services only (foreign ids → 404) |
| GET/POST | `/api/v1/providers/me/memberships` | List both sides / request-or-invite (`counterpart` = other provider's public id) |
| POST | `/api/v1/providers/me/memberships/{id}/accept` | Counterpart of the initiator, PENDING → ACTIVE |
| POST | `/api/v1/providers/me/memberships/{id}/reject` | Either party, PENDING → REJECTED (initiator = withdraw) |
| POST | `/api/v1/providers/me/memberships/{id}/end` | Either party, ACTIVE → ENDED |

Sending `verification_status`, `verification_note`, `verified_at`,
`verification_requested_at`, `verification_changed_at`, `account` or `id` to
`/providers/me` returns 400 `field_not_allowed`.

### Administrators (bearer, `is_staff`)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/admin/providers/{id}/verification` | `{status: VERIFIED|REJECTED|SUSPENDED|UNVERIFIED, note?}` |

### Phase 3 — jobs, talent, billing, audit

The full route list is in `JOBS.md` (public, seeker, employer, admin groups)
and `BILLING.md` (plans, admin subscription actions, credits). `GET
/api/v1/admin/audit` lists audit events (filters `action`, `target_type`,
`target_id`, `actor`). New error codes: `subscription_required`,
`entitlement_required`, `usage_limit_reached` (402, with `meta`),
`organization_not_verified`, `job_not_open`, `already_applied`,
`already_invited`, `already_saved`, `invalid_transition`, `already_member`,
`contact_information_not_allowed` (validation, under `codes.<field>`).

## Planned (not implemented)

Reservations/availability (Phase 4, free), reviews and offers (Phase 5) and the
remaining modules of the master plan. Password change for logged-in users and admin account-management
endpoints are also not implemented yet.
