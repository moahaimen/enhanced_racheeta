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
- Lists are paginated: `?page=N&page_size=M` (default 20, max 100) →
  `{"count", "next", "previous", "results"}`.
- Filtering uses query parameters per endpoint (django-filter); ordering with
  `?ordering=field` / `?ordering=-field`; search with `?search=`.
- Unknown `/api/v1/*` paths return a JSON 404 in the standard envelope.

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
| 403 | `permission_denied` | Authenticated but not allowed. |
| 404 | `not_found` | |
| 405 | `method_not_allowed` | |
| 429 | `throttled` | Rate limit (auth endpoints: 10/min per client). |

Handler: `backend/apps/core/exceptions.py`.

## Endpoints (implemented)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health/` | none | Liveness. `{"status":"ok"}` |
| POST | `/api/v1/auth/register` | none | Create account → `{account, tokens}` (201) |
| POST | `/api/v1/auth/login` | none | Email + password → `{access, refresh}` |
| POST | `/api/v1/auth/refresh` | none | `{refresh}` → new `{access, refresh}`; old refresh is blacklisted |
| POST | `/api/v1/auth/logout` | none | `{refresh}` → 204; refresh token blacklisted |
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
  "is_staff": false,
  "permissions": ["accounts.edit_self", "accounts.view_self", "providers.search", "reservations.create_own", "reviews.create_own"],
  "created_at": "2026-09-23T13:45:00.123456Z",
  "last_login": null
}
```

`password` never appears in any response. Sending `is_staff`, `is_superuser`,
`is_active`, `permissions`, `groups`, `role` (on `/me`), `email` (on `/me`) or
`email_verified` in a request body returns a 400 with the offending field in
`details` — the request is rejected wholesale, never partially applied.

## Planned (not implemented)

`POST /api/v1/auth/firebase/exchange` and every business module listed in the
master plan. Do not document them as existing until they are.
