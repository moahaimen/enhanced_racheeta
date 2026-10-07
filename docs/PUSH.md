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
* `push_service.deliver` never raises and targets the recipient's ≤10 active devices.
* **Invalid tokens:** per-token Firebase `UnregisteredError` / `SenderIdMismatchError`
  deactivate that local device only. Everything else (quota, unavailable, invalid argument,
  network, auth, unknown) is transient and **never** deactivates. A batch that is refused,
  times out or fails as a whole says nothing about any token, so every registration is kept.
* No worker, queue, Redis, Celery, WebSocket or Channels exists.

### Why the request cannot hang on Firebase

`transaction.on_commit` is a hook, **not** asynchronous execution: the callback runs inside
the request that caused it, so push latency is request latency. The delivery path is built so
that cost is a constant, never `devices × timeout`:

1. **One operation per delivery.** `PushSender` has a single method, `send_batch(tokens,
   message)`; there is no per-token `send` to loop over. `FirebaseAdminPushSender` makes one
   `firebase_admin.messaging.send_each_for_multicast(MulticastMessage, app=...)` call and gets
   back a `BatchResponse` whose `responses[i]` (`.success`, `.exception`) answers `tokens[i]`.
2. **What the SDK really does (firebase-admin 7.7.0, measured, not assumed).** The old HTTP
   batch endpoints (`send_all`/`send_multicast`) no longer exist; `send_each*` sends the
   tokens **concurrently** on its own thread pool, one request per token. Ten tokens at 0.5 s
   per request finished in 0.53 s (not 5 s). But its limits are *not* a strict bound: the
   timeout is per socket operation and the retry policy is not configurable, so a server that
   never answers cost 2× the timeout (4 s at `httpTimeout=2`) and a 503 storm ~7 s (retries with
   back-off), and an OAuth token refresh can wait up to google-auth's own 120 s default.
3. **Hard caller-side deadline** (`BoundedCallRunner`, `PUSH_BATCH_DEADLINE_SECONDS = 3`).
   The SDK call runs on a fixed pool and the request waits at most the deadline. A blocked
   call cannot be interrupted, so it is *abandoned*: it finishes in the background and its
   result is discarded (the next delivery re-attempts; nothing is lost that PostgreSQL does
   not already hold). This is the only mechanism that bounds retries and token refresh too.
4. **Bulkhead.** At most `PUSH_MAX_INFLIGHT_BATCHES = 4` batches are in flight per process
   (a semaphore taken without waiting). A batch keeps its slot until it really finishes, so a
   hung Firebase can never accumulate threads or memory: further deliveries are refused
   instantly (`PushBusy`). Worst case per process: 4 pool threads + the SDK's own ≤10 threads
   per batch.
5. **Fail-fast window.** After a missed deadline, deliveries are refused instantly
   (`PushPaused`) for `PUSH_COOLDOWN_SECONDS = 10`, then the next one probes again. An outage
   therefore costs one deadline per window per process, not one per notification, and a
   request that notifies two people (e.g. an admin-driven status change) pays one deadline,
   not two.

**Bound:** a delivery adds at most `PUSH_BATCH_DEADLINE_SECONDS` (3 s) + two small queries to
the originating request, independent of the number of devices; during an outage most
deliveries add nothing. (A request triggers at most two deliveries, one per participant.)

**Lifecycle / reliability of the background work.** The pool is fixed-size and created lazily
in the serving process; its threads never touch the database or any request state (they run
only the SDK call over plain tokens and the message), so there is no connection to leak or
transaction to confuse. An abandoned or unfinished call can only lose a best-effort hint. At
worker shutdown the interpreter joins the pool, so exit may be delayed by the SDK's remaining
timeouts (a few seconds; gunicorn's graceful timeout still applies).

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

Delivery bounds are code constants in `apps/notifications/push.py` (no new environment
variables): `PUSH_BATCH_DEADLINE_SECONDS = 3`, `PUSH_HTTP_TIMEOUT_SECONDS = 2` (SDK per-request
timeout; limits how long abandoned work lingers), `PUSH_MAX_INFLIGHT_BATCHES = 4`,
`PUSH_COOLDOWN_SECONDS = 10`.

`firebase-admin` is pinned in `requirements/production.txt` (`MulticastMessage.tokens` is marked
deprecated in 7.7.0 in favour of Firebase Installation IDs but remains supported; revisit before
upgrading the pin). System checks: `E003`
(sender cannot be loaded), `E004` (Firebase sender without credentials), `W001`
(production with push disabled: safe, nothing is sent). Development and CI never send.

## Client integration status

The repository's web app has no Firebase client SDK or service worker, and `mobile/` is
not started (Phase 11). Web/mobile token acquisition is therefore **deferred**; the
backend is platform-ready (`WEB`, `ANDROID`, `IOS`). A future client must: request
permission from an explicit user action only, register via `POST push-devices/`, call
unregister before logout/account change, and open pushes through authenticated APIs.

## Tests

No test contacts Firebase.

* `test_push.py` — registration/ownership/transfer/IDOR, DB uniqueness and concurrency (thread
  races), fan-out, permanent vs transient errors, after-commit and rollback behavior, chat and
  notification recipients, privacy of content, admin masking, system checks.
* `test_push_delivery_bounds.py` — the latency contract: the sender interface has no per-token
  send; one sender call for 1/3/10 devices; delivery latency does not scale with device count;
  the real `FirebaseAdminPushSender` over a **fake SDK** makes exactly one multicast call and maps
  mixed per-token results (misaligned responses are never trusted); `BoundedCallRunner` deadline,
  bulkhead, thread bound, release-after-finish and fail-fast window; end-to-end: with a hung
  Firebase and 10 devices, a chat send, a booking and a two-recipient request all return within
  the deadline while the `Message` / `Notification` and every device registration are intact.
* `test_firebase_sdk_contract.py` — the same claims against the **real** firebase-admin SDK with a
  loopback server in place of FCM (concurrent multicast, typed per-token errors, SDK retry policy
  vs the deadline). Skipped when `firebase-admin` is not installed (the default CI image); run it
  locally with the SDK on the path.
* OpenAPI contract tests for the device endpoints.

## Mobile (Phase 11E)

The app registers its FCM token with `POST /notifications/push-devices/` (idempotent upsert, `platform: ANDROID`) for the signed-in account once OS notification permission is granted, again on a token refresh, and unregisters it with `POST /notifications/push-devices/unregister/` before logout (best effort, 3 s bound). Because the register endpoint transfers the token to the caller with no client ordering, all ownership requests are serialised, not aborted by the session ending, and re-asserted for the current account after any stale or unobserved request (ADR-057); notification permission is re-checked on every sync, including token refreshes. Firebase is initialised from `--dart-define FIREBASE_API_KEY, FIREBASE_APP_ID, FIREBASE_MESSAGING_SENDER_ID, FIREBASE_PROJECT_ID`; without them push is disabled. Payload handling: `type=notification` → open the notification centre; `type=chat_message` + valid `conversation_id` → open that thread; unknown or malformed → ignored; a foreground push only refreshes backend state. See ADR-057.
