# Persistent Notifications (Phase 9A)

Notifications are **persistent, recipient-owned records in PostgreSQL**. The
database row is the source of truth; any future delivery channel (FCM push in
Phase 9C) is best-effort and never authoritative. Phase 9A delivers only the
persistent layer, the REST API and the web notification center. There is no
realtime transport, no push, no chat and no background worker (see *Not in this
phase*).

## Model (`apps/notifications`, migration `notifications/0001_initial`)

`Notification` extends `BaseModel` (UUID id, `created_at`, `updated_at`).

| Field | Notes |
| --- | --- |
| `recipient` | FK to `Account`, `CASCADE`. Every read and write is scoped to it. |
| `category` | `RESERVATION` (the only category today). |
| `event_type` | `RESERVATION_CREATED`, `RESERVATION_STATUS_CHANGED`. The new status is in the payload, not in a per-status event type. |
| `resource_type`, `resource_id` | Optional reference to the thing the event is about (`RESERVATION` + its UUID). No `GenericForeignKey`. The check constraint `notification_resource_coherent` requires both to be empty or both populated. |
| `payload` | JSON of **safe facts only** (below). |
| `dedupe_key` | Backend-only idempotency key with a database **unique constraint** `notification_dedupe_key_unique`. Never serialized. |
| `read_at` | Null while unread; set once by the server. |

Indexes: `(recipient, read_at)` (unread count / read-all) and
`(recipient, -created_at)` (newest-first list).

### Safe payload

`services.safe_payload` stores only these keys: `reservation_id`,
`service_title`, `provider_name`, `starts_at`, `previous_status`, `status`. They
are built from the reservation's **snapshot** columns. A notification never
contains `patient_note`, phone numbers, e-mail addresses, contact details,
tokens or any `Account` data, and unknown keys are dropped at the service
boundary, so a future caller cannot leak by accident.

### Appointment time is not rendered in prose

`starts_at` stays in the payload (for future delivery and navigation) but is
**intentionally not printed** in any notification title or body. It is a UTC
instant and Phase 9A has no canonical recipient timezone, so a clock value in
the text would be wrong for readers outside UTC (a 09:30 UTC appointment is
12:30 in Baghdad). The reservation pages localize the real timestamp on the
client (`toLocaleString`) and remain the authoritative place to read it. A
timezone-aware presentation may be introduced with push delivery (Phase 9C)
once a real timezone policy exists; the project must not hardcode a country
timezone or label UTC as local.

### No stored prose

Titles and bodies are **not** persisted. `apps.notifications.presentation.render(event_type, payload, language)`
is the single mapping to localized `title`/`body` (Arabic and English; every
reservation status PENDING, CONFIRMED, COMPLETED, REJECTED, CANCELLED, NO_SHOW).
It never raises: an unknown event type or a malformed payload renders a generic
safe message ("إشعار جديد" / "New notification"). The REST API renders in the
request language (`Accept-Language`); a future push would render in
`recipient.preferred_language`. Changing wording therefore changes every
existing notification and needs no data migration.

## Creation and deduplication

Rows are created only by backend code (`services.create_notification`, reached
from event receivers). There is no client create, update or delete endpoint.
Creation is `get_or_create` on `dedupe_key` inside a transaction, backed by the
unique constraint, so a replayed event never produces a second row:

- `reservation:<reservation_id>:created:<recipient_id>`
- `reservation:<reservation_id>:status:<status>:<recipient_id>`

## Reservation integration

`apps/notifications/receivers.py` subscribes to the existing Phase 4 signals
`reservation_created` and `reservation_status_changed` in
`NotificationsConfig.ready()` (stable `dispatch_uid`s, so repeated registration
is harmless). The reservations module is unchanged and knows nothing about
notifications. The signals are emitted through `transaction.on_commit`, so a
rolled-back reservation creates no notification.

| Event | Recipients |
| --- | --- |
| Reservation created | the reservation's **provider account** only (resolved from the committed row; no recipient if the provider was deleted) |
| Status changed, actor is the provider's account | the **patient** |
| Status changed, actor is the patient | the **provider** account |
| Status changed, actor is neither participant | both participants |

The acting account (`actor_id` on the event) is never notified. Receivers make
no authorization decision; they only turn a committed event into recipients. A
failure inside a receiver is logged and swallowed: it must never break a
reservation action that has already committed.

## REST API (`/api/v1/notifications/`)

All endpoints require authentication (`401` otherwise) and are scoped to the
caller. Lists use `StandardPagination` (20 per page by default, `?page=N`, `?page_size=M` capped at 100), ordered
`-created_at, -id`. The OpenAPI contract documents both `page` and `page_size` on `GET /notifications/` (declared explicitly because the view paginates by hand; values come from `StandardPagination`).

| Method and path | Behaviour |
| --- | --- |
| `GET /notifications/` | Paginated list. Fields: `id`, `category`, `event_type`, `title`, `body`, `resource_type`, `resource_id`, `is_read`, `read_at`, `created_at`. `recipient`, `dedupe_key` and the raw `payload` are never exposed. |
| `GET /notifications/unread-count/` | `{"count": N}` from one SQL `COUNT` of the caller's rows with `read_at IS NULL`. |
| `POST /notifications/<uuid>/read/` | Marks one of the caller's notifications read and returns it. Idempotent: an already-read row keeps its original `read_at`. Unknown ids and other users' ids are the same plain `404`. |
| `POST /notifications/read-all/` | One bounded `UPDATE` of the caller's unread rows with a single server timestamp; returns `{"updated": N}`. |

The two `POST` actions take **no client data**: no body or `{}` is accepted;
any key, and any non-object JSON body (`[]`, `false`, `0`, `""`, `null`), is
refused with the typed `field_not_allowed` error (mapping semantics, not
truthiness, the same rule as the advertising lifecycle actions). Clients cannot
choose `read_at`.

Django admin lists notifications for inspection only (no add, change or delete).

## Web

- `web/src/api/notifications.types.ts` and `web/src/api/endpoints/notifications.ts`, exported through `web/src/api/index.ts`.
- `/notifications` (authenticated): loading, error with retry, empty state, pagination, unread/read distinction, **Mark as read** per row and **Mark all as read** (both `ApiActionButton`s, disabled while in flight). The *View* link is derived on the client from `resource_type` and the viewer's role (RESERVATION: patient → `/reservations`, provider → `/provider/reservations`); unknown resources get no link. No URL is stored in the database.
- `SiteHeader`: an authenticated **Notifications** entry (bell) with an unread badge (hidden at 0, `99+` cap) in the desktop and mobile navigation. `NotificationsProvider` (inside `AppLayout`) fetches `GET unread-count/` when an account signs in, on every **authenticated SPA navigation** (a `pathname` change; query-string-only changes such as pagination do not refetch) and after each mark-read action, and clears on logout. Each load aborts the previous one (`AbortController`), logout/account switch/unmount abort the current one, and a response is applied only while it is still the latest request for the current account; a failed refresh keeps the last known count. There is **no polling, no timer, no full-list fetch, and no locally computed count**: the badge always shows the backend's answer, and a page that stays open makes no periodic requests.
- **Language:** title and body are rendered by the backend for the request's `Accept-Language`; the page never translates them in the browser. The list depends on the active language, so switching language while on `/notifications` re-requests the **same page** (an in-flight request in the old language is aborted/ignored) and the rows change language together with the page chrome.
- **Mark all as read** is always available on a page that lists notifications. It is not gated on the (possibly stale) badge count: the backend is authoritative and `read-all` is idempotent (`{"updated": 0}` when nothing is unread). `ApiActionButton` disables it only while the request is in flight, and the count is re-fetched from the backend afterwards.

## Not in this phase

- Generic chat / conversations / messages (Phase 9B); `RecruitmentMessage` is untouched.
- FCM / Firebase push, device tokens, `FIREBASE_*` settings (Phase 9C). The existing Firebase *authentication* adapter is unchanged.
- WebSockets, Channels, ASGI consumers, Redis, Celery or any worker.
- Notifications for other modules (jobs, invitations, interviews, offers, reviews, advertising, marketplace, real estate).
- Per-user notification preferences, e-mail or SMS delivery, retention/pruning of old rows.
