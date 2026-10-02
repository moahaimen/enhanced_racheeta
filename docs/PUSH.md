# Push notifications (Phase 9C — FCM)

> PostgreSQL is authoritative. A push is a best-effort **hint** that something can be
> fetched. If FCM is down, misconfigured or a device is offline, nothing in the
> application breaks: the `Notification` / chat `Message` row already exists.

## Three separate concepts

| Concept | Where | Authoritative? |
|---|---|---|
| Domain state | `notifications_notification`, `chat_message` | **Yes** |
| Delivery registration | `notifications_pushdevice` (FCM token ownership) | For *who may be pushed*, not for what exists |
| Delivery attempt | `apps.notifications.push` (Firebase Admin SDK) | **Never** |

## Data model — `PushDevice`

`account` (FK, CASCADE), `token` (≤1024, opaque credential-like value), `platform`
(`ANDROID` / `IOS` / `WEB`, bounded choices), `is_active`, `last_registered_at`, timestamps.
No device name/model/fingerprint is collected. Database constraints: **`token` is globally
unique** (one token → at most one owner) and non-empty.

## Token ownership and account switching

* The owner is always `request.user`; no endpoint accepts an account/user id (undeclared
  fields are rejected with `field_not_allowed`).
* Registering a token already held by another account **transfers** it (row locked,
  unique constraint as the final guard against races): the previous owner can no longer
  receive pushes through it, even if the app never called unregister. Recorded in the
  audit log as `push_device.transferred` (no token in audit data).
* Registration is an idempotent upsert; repeated calls refresh `last_registered_at` and
  reactivate an unregistered device. At most 10 active devices per account (oldest are
  deactivated) which also bounds fan-out.
* Unregister deactivates only the caller's own registration. Unknown and foreign tokens
  are answered identically (`204`), so ownership cannot be probed.
* Tokens are never returned by any API, never logged in full (last 6 chars at most),
  never placed in payloads or audit rows, and masked in Django admin (inspection-only).

## API (`/api/v1/notifications/`, authenticated, throttled `push_devices` 60/hour)

| Endpoint | Body | Result |
|---|---|---|
| `POST push-devices/` | `{token, platform}` | `200 {id, platform, is_active, last_registered_at}` |
| `POST push-devices/unregister/` | `{token}` | `204` |

Clients should call unregister **before** logout. Logout itself never depends on
Firebase or on this call; the transfer rule covers a missed call.

## Delivery

* Triggers register with `transaction.on_commit`: a rolled-back change never pushes.
  * Persistent notifications: `services.create_notification` pushes only when a row is
    **newly created** (replays do not repush). Self-notification rules of Phase 9A are
    inherited because push piggybacks on the row's recipient.
  * Chat: `apps.chat.hooks.message_sent` (post-commit signal) → receiver in
    `apps.notifications` → the **other** participant(s) from backend-owned membership.
    The sender never receives their own message; nothing about read cursors changes.
* `push_service.deliver` never raises. Fan-out is sequential over ≤10 active devices of
  an active account; one failing token does not stop the others.
* **Invalid tokens:** Firebase `UnregisteredError` / `SenderIdMismatchError` deactivate the
  local device. Everything else (quota, unavailable, network, auth, unknown) is transient
  and **never** deactivates.
* The Firebase sender uses its own named SDK app with a 5 s HTTP timeout, so a hanging FCM
  cannot hold a request thread for the SDK default; worst case is bounded by 10 × 5 s.
* No worker, queue, Redis, Celery, WebSocket or Channels exists. Delivery is bounded and
  inline after commit; the `PushSender` boundary lets a future worker take it over.

## Privacy rules

Lock screens are visible to bystanders. Push text is generic and localized
(`preferred_language`): notification title (e.g. "Reservation confirmed", no service or
provider name) + "Open Racheeta to view the details."; chat: "New message". The `data`
map carries only opaque ids (`type`, `notification_id`, `event_type` / `conversation_id`).
No message body, patient note, phone, e-mail or URL. Push data is **not** authorization:
opening a conversation re-authorizes through the normal participant-scoped API.

## Configuration

| Variable | Meaning |
|---|---|
| `PUSH_SENDER` | `apps.notifications.push.DisabledPushSender` (default, sends nothing) or `apps.notifications.push.FirebaseAdminPushSender` |
| `FIREBASE_CREDENTIALS_FILE` | Existing variable (service-account JSON, platform-injected, never committed); reused by FCM |

`firebase-admin` is pinned in `requirements/production.txt`. System checks: `E003`
(sender cannot be loaded), `E004` (Firebase sender without credentials), `W001`
(production with push disabled: safe, nothing is sent). Development and CI never send.

## Client integration status

The repository's web app has no Firebase client SDK or service worker, and `mobile/` is
not started (Phase 11). Web/mobile token acquisition is therefore **deferred**; the
backend is platform-ready (`WEB`, `ANDROID`, `IOS`). A future client must: request
permission from an explicit user action only, register via `POST push-devices/`, call
unregister before logout/account change, and open pushes through authenticated APIs.

## Tests

`apps/notifications/tests/test_push.py` uses an injected `RecordingSender` (no network):
registration/ownership/transfer/IDOR, DB uniqueness and concurrency (thread races),
fan-out, permanent vs transient errors, after-commit and rollback behavior, chat and
notification recipients, privacy of content, admin masking, system checks; plus OpenAPI
contract tests.
