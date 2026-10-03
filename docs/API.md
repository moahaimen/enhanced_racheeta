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

### Phase 5 — reviews and offers

See `REVIEWS_OFFERS.md`.

### Phase 6 — medical marketplace

See `MARKETPLACE.md` for the full table. Company self-service lives under
`/api/v1/marketplace/company…` (role `MEDICAL_COMPANY`), the targeted
catalogue under `/api/v1/marketplace/products…` (verified `PROVIDER`), the
category reference list at `/api/v1/marketplace/categories` (public; each
category carries a read-only, backend-derived `can_publish`) and the
verification control plane under `/api/v1/admin/marketplace/companies…`
(staff). New error codes: `company_not_verified` (403),
`category_unavailable` (409), `already_exists` (409), `invalid_product`,
`field_not_allowed` (validation, under `codes.<field>`).

### Phase 7 — medical real estate

See `REAL_ESTATE.md`. The public catalogue is under
`/api/v1/real-estate/listings…` (anyone; filters `transaction_type`,
`property_type`, `governorate`, `city`, `suitable_use`, `min_price`,
`max_price`, `min_area`, `max_area`, `search`; ordering `created_at`,
`-created_at`, `price`, `-price`, `area_sqm`, `-area_sqm`); seller self-service
is under `/api/v1/real-estate/owner…` (role `REAL_ESTATE_SELLER`). New error
codes: `seller_not_eligible` (403) and, as validation `codes.<field>`,
`title_required`, `invalid_choice`, `geography_inactive`, `city_inactive`,
`city_mismatch`, `area_required`, `area_invalid`, `coordinates_invalid`,
`suitable_use_required`, `duplicate_suitable_use`, `contact_phone_required`,
`contact_email_required`, `contact_email_invalid`, `expiry_required`,
`expiry_in_past`, `price_invalid`, `currency_unsupported`; plus the existing
`already_exists`, `invalid_transition`, `field_not_allowed`.

### Phase 8 — advertising and payments

See `ADVERTISING.md`. Company self-service is under
`/api/v1/advertising/company…` (role `MEDICAL_COMPANY`: dashboard, quote,
campaigns, submit, cancel), sponsored campaigns for providers at
`/api/v1/advertising/marketplace` (verified `PROVIDER`), and the administrator
payment control plane under `/api/v1/admin/advertising/campaigns…` (staff: list,
detail, `verify-payment`, `reject-payment`). New error codes: `pricing_unavailable`,
`campaign_not_editable`, `campaign_not_submittable`, `company_not_eligible` (403),
`product_unavailable`, `payment_not_pending`, `payment_quote_mismatch` (409), `campaign_ended`, plus per-field
validation codes (`dates_invalid`, `start_in_past`, `end_in_past`,
`governorate_inactive`, `specialty_inactive`, `product_not_found`,
`duplicate_target`, `reason_required`) and the existing `invalid_transition` and
`field_not_allowed`.

### Notifications (Phase 9A)

All authenticated and recipient-scoped; see `NOTIFICATIONS.md`.

| Method and path | Result |
| --- | --- |
| `GET /api/v1/notifications/` | Paginated (20/page), newest first: `id`, `category`, `event_type`, `title`, `body` (rendered in the request language), `resource_type`, `resource_id`, `is_read`, `read_at`, `created_at` |
| `GET /api/v1/notifications/unread-count/` | `{"count": N}` |
| `POST /api/v1/notifications/{id}/read/` | The notification, now read (idempotent; foreign or unknown id: `404`) |
| `POST /api/v1/notifications/read-all/` | `{"updated": N}` |
| `POST /api/v1/notifications/push-devices/` | Register/refresh this device's FCM token: body `{token, platform: ANDROID\|IOS\|WEB}` only (owner is the caller); `200 {id, platform, is_active, last_registered_at}`; the token is never returned. A token held by another account is transferred to the caller. Throttled (`push_devices`). See `PUSH.md`. |
| `POST /api/v1/notifications/push-devices/unregister/` | Body `{token}`; deactivates the caller's own registration; `204` whether the token is unknown, foreign or the caller's (no ownership disclosure). |

The `POST` actions take no client data: no body or `{}` only; anything else is
`field_not_allowed`. There is no create, update or delete endpoint.

### Dashboards (Phase 10)

All `GET`, authenticated, read-only, **parameterless** (ownership always comes from the signed-in
account; any query string is ignored), responses `Cache-Control: private, no-store`. Counts are
zero-filled so a missing key never has to be interpreted. See `DASHBOARDS.md`.

| Method and path | Who | Result |
| --- | --- | --- |
| `GET /api/v1/dashboards/` | any authenticated account | `{"dashboards": [...]}` — the keys this account can open now (`patient`, `doctor`, `facility`, `medical_company`, `real_estate_owner`, `recruiter`, `admin`) |
| `GET /api/v1/dashboards/patient` | `PATIENT` | `reservations` (`total`, `by_status`, `upcoming`), `upcoming[]` and `recent[]` (≤ 5, no private fields), `unread` |
| `GET /api/v1/dashboards/doctor` | `PROVIDER` with a practitioner profile | `profile`, `reservations`, `upcoming[]` (with `patient_name`, never the note), `reviews` (`average_rating` null when none, `review_count`, `distribution`), `offers` (`total`, `running_now`, `scheduled`), `unread` |
| `GET /api/v1/dashboards/facility` | `PROVIDER` with a facility profile | everything in `doctor` plus `practitioners` (`active`, `incoming_requests`, `outgoing_invitations`) |
| `GET /api/v1/dashboards/company` | `MEDICAL_COMPANY` with a company profile | `verification_status`, `can_publish`, `products`, `campaigns`, `payments` (by status); composes the existing marketplace and advertising summaries |
| `GET /api/v1/dashboards/recruiter` | active member (any role) of a recruiting organisation | `organization`, `jobs` (`total`, `by_status`, `open_now`), `applications_access` (`null`, `organization_not_verified` or `plan_required`), `applications` / `interviews` (null when withheld), `seats` |
| `GET /api/v1/dashboards/admin` | staff accounts | counts only: accounts by role/active, verification queues, jobs, reservations, products, listings, campaigns, payments, subscriptions, audit activity |
| `GET /api/v1/real-estate/owner/dashboard` (existing) | `REAL_ESTATE_SELLER` | unchanged; the web hub calls it directly |

A wrong role, a missing profile or a lapsed membership is `403`; anonymous is `401`. The existing
`/marketplace/company/dashboard` and `/advertising/company/dashboard` endpoints are unchanged.

## Mobile client conventions (Phase 11A)

The Flutter app (`mobile/`) consumes this API through one client (`lib/core/api/api_client.dart`): `Authorization: Bearer <access>` on authenticated calls, `Accept-Language: ar|en` from the UI language, bounded connect/send/receive timeouts, `{error:{code,message,details?}}` mapped to a typed exception, and `{count,next,previous,results}` mapped to `Page<T>` with `page`/`page_size`. Phase 11A integrates only `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` and `GET /me`. The login 200 response has no schema in `openapi.yaml`; the client relies on the documented `{access, refresh}` shape.

## Planned (not implemented)

The remaining modules of the master plan. Password change for logged-in users and admin account-management
endpoints are also not implemented yet.
