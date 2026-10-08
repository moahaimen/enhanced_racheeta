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
| Password-reset enumeration | Same 202 body for known/unknown/inactive emails. Timing: sending is synchronous, so a slow provider could leak existence via latency. Phase 12A bounds the send (`EMAIL_TIMEOUT`, 10 s) and makes a failing provider indistinguishable from success on the public endpoint (ADR-059); a background worker is deliberately not added. | bounded in 12A |
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

## Phase 2 security review (2026-09-23)

| Topic | Finding | Status |
| --- | --- | --- |
| Cross-account edits | Only `/providers/me` writes; querysets scoped to `request.user.provider_profile`; foreign ids → 404. | covered by tests |
| Verification fields | `ForbidAdminFieldsMixin` rejects admin fields with 400; admin endpoint requires `is_staff`. | covered |
| Provider type after verification | Locked for the owner (`type_locked`); admin-only afterwards. | covered |
| Unverified providers leaking | `discoverable()` filter on list and detail; non-discoverable detail → 404; related providers filtered the same way. | covered |
| Membership abuse | Counterpart must be discoverable; kinds must differ; not-self and one-live-row DB constraints; third parties get 404; initiator cannot self-accept. | covered |
| Fabricated data | No rating/statistics fields exist in provider responses. | covered |
| Invalid filter input | django-filter returns 400 for unknown enum/UUID values; ordering restricted to `display_name`/`created_at`. | covered |
| Image URL | https only. Uploads (media module) will replace free URLs. | covered |
| Query amplification | list ≤ 4 queries, detail ≤ 6 regardless of rows (asserted). | covered |
| Refresh after account deletion | Found in the browser walkthrough: `/auth/refresh` with a token of a deleted account raised a 500. Now 401 `token_not_valid` (`RefreshSerializer`); deactivated accounts also 401. | fixed + tests |

No weakening of earlier decisions was needed to make tests pass.

## Phase 3 security review (2026-09-24)

| Topic | Finding | Status |
| --- | --- | --- |
| Client-supplied IDs | Every employer route resolves the organisation from the caller's ACTIVE membership (`request.employer`); jobs, applications, invitations and saved candidates are filtered by that employer, seeker routes by `request.user`; foreign ids → 404. | covered by tests |
| Contact-data exfiltration | All recruitment text validated by `ContactLeakDetector` at write time (Arabic/Persian digits, separators, WhatsApp/Telegram words, `@handles`, links); jobs re-scanned at submit with flags for the admin; messages text-only. | covered (`apps/moderation/tests`, jobs tests) |
| Identity leakage | Public/employer serializers expose no e-mail, phone, Firebase id, staff flag or permissions; talent responses carry the profile id only; application snapshots hold professional facts only; tests assert absence. | covered |
| Commercial bypass | Gating lives in the service layer (`submit_job`, `set_featured`, `record_talent_search`, `invite_candidate`, `add_member`, `apply_to_job`), not in views; consumption is atomic under `select_for_update`; idempotent references stop double-charging; limits are re-checked on approve/restore. | covered (`apps/billing/tests`) |
| Privilege boundaries | Admin routes require `is_staff` (role ADMIN alone is not enough); VIEWER members cannot write; only OWNER edits the organisation, members and plan requests; seekers cannot transition applications; employers cannot withdraw. | covered |
| Admin abuse trail | Every verification, moderation, subscription and credit decision writes an `AuditEvent` with actor and reason. | covered |
| Abuse throttles | Scoped throttles: job creation 30/h, applications 20/h, talent search 60/min, invitations 30/h, messages 60/h. | configured |
| Invalid input | django-filter/serializers return 400 with typed codes; unknown enum values, negative limits and malformed UUIDs never reach the ORM. | covered |
| Query amplification | List endpoints use `select_related`/`prefetch_related`; applicant and job lists are paginated (20). | reviewed |
| Storage/attack surface | No uploads, no external services, no new infrastructure; payments recorded as plain rows. | by design (owner decisions 5–9, 14–15) |
| Web guards | `RequireAuth`/`RequireStaff` are UX only; every data call still fails with 401/403 server-side. | covered |

No weakening of earlier decisions was needed to make tests pass.

## Phase 7 security review (2026-09-30)

- **Non-disclosure:** a hidden listing (draft, expired, seller role lost, account inactive, geography inactive) answers the same plain 404 as an unknown id; list and detail share `publicly_visible()`, and filters only narrow it.
- **Contact and identity:** the public response returns only the contact values the listing's contact method makes public, a seller summary by profile id, and never the account e-mail/id, roles or staff flags.
- **Ownership:** owner endpoints resolve the seller from `request.user`; a foreign id is a 404; `account`/`seller` are refused in payloads and immutable in the model; Django admin is inspection-only.
- **Server-owned lifecycle:** status, `published_at`, derived state, targeting, payment, advertising and image fields are refused (`field_not_allowed`).
- **Current-state checks:** seller and account are locked fresh in each mutation; role loss or account deactivation blocks publication and hides listings at once (regression tests with a second connection).
- **No uploads, no payment, no new infrastructure.**

## Phase 8 security review (2026-09-30)

- **Server-owned commerce:** price, quote, payment state, status, company and verification are never client input (`field_not_allowed`); the amount is computed from the active rate under lock and snapshotted; a later rate change cannot alter it.
- **No payment trust from the browser:** only an administrator's locked `verify_campaign_payment` activates a campaign, atomically with the payment, after company, product, target and date checks on current state; there is no gateway, webhook or test endpoint, and no payment credentials are stored.
- **Current-state visibility:** `visible_to()` re-reads company, product, category, audience, provider and dates on every request; campaign targeting only narrows Phase 6 product targeting.
- **Concurrency:** one lock order (company+account → campaign → payment → product/rate); races (verify vs reject, stale company role, product deactivation, rate change, row locks) are proven with real second connections.
- **Ownership:** company from `request.user`; foreign campaigns 404; Django admin inspection-only except the rate.
- **Review hardening:** targeted specialties must be active to produce exposure; submit/cancel reject any client field (`field_not_allowed`) instead of ignoring it; payment verification proves payment ↔ quote snapshot coherence on the locked rows (`payment_quote_mismatch`) so a bypassed model guard cannot activate a campaign; rate activation locks the rows it swaps and leaves the unique constraint as the final guard.
- **No uploads, no analytics, no new infrastructure.**

## Notifications (Phase 9A)

- **Backend-only creation:** no endpoint creates, edits or deletes a notification; Django admin is inspection-only. Mark-read actions accept no client data (`field_not_allowed`, mapping semantics) and the server sets `read_at`.
- **Recipient isolation:** every query is scoped to `request.user`; another user's id is the same plain `404` as a missing one, and read-all touches only the caller's rows.
- **Privacy by construction:** the stored payload is an allow-list of non-sensitive snapshot facts; `patient_note`, contact details, tokens and account data cannot be stored. The API never exposes `recipient`, `dedupe_key` or the raw payload.
- **Replay safety:** a unique `dedupe_key` makes duplicate events harmless; rolled-back reservations never notify (post-commit signals).
- **Receiver isolation:** a failing receiver is logged and cannot break the committed business action.
- **No new attack surface in 9A:** no push tokens, third-party credentials, sockets or workers (push arrived in 9C, below).

## Push notifications (Phase 9C)

- **Token ownership is server-owned and DB-enforced:** `PushDevice.token` is globally unique; the owner is always `request.user` (no account field accepted); registering a token held by another account transfers it, so the previous owner stops receiving pushes (account switch / shared browser).
- **Ordered ownership:** `ownership_seq` is compared under the row lock; stale/equal/unsequenced requests on a sequenced token change nothing; a stale register answers a typed `409 stale_ownership` that discloses neither the token nor the owner; the sequence is never returned and never recorded on another account's registration; ordering markers are bounded per account.
- **No IDOR:** unregister only touches the caller's own device and answers `204` for unknown/foreign tokens alike; no list/read/delete-by-id API exists; tokens are never returned.
- **Credential hygiene:** tokens are never logged in full, never in audit rows or payloads; admin is inspection-only with masked tokens; Firebase credentials stay in `FIREBASE_CREDENTIALS_FILE` (platform-injected, never committed).
- **Best-effort, after commit, bounded:** pushes are scheduled with `transaction.on_commit`, never raise, and cannot fail or roll back the domain action; rolled-back changes never push. Because `on_commit` runs inside the request, delivery is one SDK multicast under a hard 3 s deadline with a bulkhead and a fail-fast window, so a Firebase outage cannot hold a request or accumulate threads.
- **Privacy:** lock-screen text is generic (no message bodies, notes, contact data, service/provider names); `data` carries only opaque ids and is never an authorization input.
- **Stale tokens:** only permanent Firebase rejections deactivate a device; transient errors never do. See `PUSH.md`.

## Dashboards (Phase 10)

- **Server-enforced scope, applied before aggregation:** each endpoint resolves the caller's own profile, company or active membership from the database on every request (never from the client) and filters by that foreign key; no endpoint accepts an id, filter or query parameter. A lapsed membership, deleted profile or wrong role is `403` on the very next request.
- **Cross-account / cross-organisation isolation** is tested for patients, providers, companies and organisations, including requests that smuggle other accounts' ids in the query string and headers.
- **No private data in aggregates:** lists select an explicit column allow-list (`patient_note`, contact data and tokens can never be selected); response serializers declare every field, so an accidental extra column cannot leave the server; the administrator dashboard is counts only (no row, e-mail or name is ever selected).
- **Entitlement-aware:** recruiter applicant aggregates follow the existing applicant-read gate (organisation may recruit AND plan carries `jobs.application_review`); otherwise they are `null` with an explicit reason, never zero.
- **Read-only:** no dashboard mutates domain data and none offers an administrator mutation; responses are `private, no-store`.
- **Nothing is fabricated:** no revenue, views, impressions or conversions exist, so none are reported (see the deferred list in `DASHBOARDS.md`).
- Entitlement resolution, shared with every existing entitlement read, may normalise an elapsed subscription; that behaviour predates Phase 10.

## Mobile client (Phase 11A)

- **Tokens:** access token in memory only; refresh token in the platform keystore (`flutter_secure_storage`), never in shared preferences (which only holds the UI language); rotated refresh tokens are persisted before use; logout and a rejected refresh clear storage.
- **No logging of secrets:** `SafeLogger` writes only method, path, status and duration in debug builds and redacts bearer tokens, JWTs, e-mail addresses and password/token key-value pairs; it is a no-op in release.
- **Transport:** `https` is required except for debug builds of the `development` environment (emulator host); release builds reject `http`, and reject the `development` environment. TLS verification is never disabled and there is no certificate-bypass code.
- **No secrets in the app:** no admin credentials, database URLs, Firebase service-account files or payment keys; no hardcoded tokens; the API base URL comes from `--dart-define` and is not a secret. Signing keys and Firebase config files are git-ignored/absent.
- **Stale data:** requests of an ended session are cancelled and their results dropped (logout, session expiry, account switching).
- **Authorization:** the app hides destinations by role and permission codes from `/me` but the backend re-checks every action; the app never decides access.
- Android/iOS platform hardening (backup rules, certificate pinning decision, obfuscation) is Phase 11F.

## Mobile patient flows (Phase 11B)

- **No new secrets or permissions:** the screens use the existing session; no payment, FCM or provider-side capability. Patient-only endpoints are also only *offered* to accounts whose `/me` lists the capability; the backend still enforces PATIENT (403 otherwise) and scopes every reservation query to the caller (foreign ids are a plain 404, shown as one generic text).
- **No duplicate or foreign bookings:** `POST /reservations` is never retried automatically, duplicate taps are ignored while a request is pending, and a taken slot refetches availability instead of resubmitting.
- **Account isolation:** patient state is keyed on the account id; logout, expiry and account switching rebuild it and drop late responses (tested with a slow answer for the previous account).
- **Privacy in the client:** the patient note is sent only on booking and shown only to its owner; logs carry method/path/status only; `Reservation.toString` carries no personal data; server error bodies are never displayed.
- **Clock correctness:** timestamps without an offset are rejected so an appointment can never be silently read in the wrong zone.

## Mobile provider and facility flows (Phase 11C)

- **Authorization stays on the server.** The workspace is shown only when `/me` lists `reservations.manage_received` (a hint, followed live through permission changes, logout and account switching); every call is still authorized by the backend (PROVIDER role and a provider profile, ownership from the token). A deep link to a workspace route as a patient shows a refusal and sends no request.
- **No cross-account state.** Provider data is keyed by the signed-in account id, list notifiers rebuild on an account change, and screen-local input/messages are reset. Mutations capture the initiating account: if another account is signed in when the call finishes, the result is dropped (no success or error text, no invalidation). Tested with the account switched through a `/me` refresh while the screen stays mounted and the new account's response held back.
- **Scoped 404.** Another provider's reservation or slot is a plain 404 and is shown as one generic text; the existence of a record is never disclosed.
- **No retry of mutations, no double submits.** Slot creation, removal and status transitions are single requests; buttons show progress and ignore further taps; destructive transitions need a confirmation.
- **Privacy:** only fields of the provider reservation schema are shown (the patient's name and note, as the web provider screen does); contact fields the contract does not define are not rendered; logs carry method/path/status only and `ProviderReservation.toString` carries no personal data.

## Mobile marketplace, jobs and real-estate flows (Phase 11D)

- **Authorization stays on the server.** Explore entries and workspaces are shown from `/me` capabilities (marketplace browse, company, seller) and, for recruiters, from the server's dashboard index; they are hints, followed live through logout and account switching. Every call is authorized by the backend (verified provider for the catalogue, medical-company/seller/organisation ownership for workspaces, active membership for recruiter calls).
- **No cross-account state.** Marketplace, jobs and real-estate data are keyed by account id; list notifiers and search forms rebuild or reset on an account change; typed application notes, messages and "applied" state are discarded; buttons are keyed per account so a request still pending for A cannot disable B's button. Mutations capture the initiating account (`runAsAccount`): another account (or an unmounted screen) when the answer arrives means the result is dropped, nothing is invalidated and no message is shown.
- **Scoped 404.** Another organisation's job, another company's product or another seller's listing is a plain 404, shown as one generic text.
- **No retry of mutations, no double submits.** Apply, withdraw, close, publish/unpublish and activate/deactivate are single requests; buttons show progress and ignore further taps; withdraw, close, unpublish and deactivate need a confirmation.
- **Error privacy.** Server `detail`/messages are never shown; typed codes map to fixed localized text. Logs carry method/path/status only.
- **Data minimization.** The seeker's résumé `snapshot` of an application is never modelled or shown; recruiter application figures that the backend withholds stay hidden (never shown as zero); contact values appear only as the API returns them (the listing's own public contact method) and are not turned into links.
- **No uploads, no external links.** No media is requested and no URL is opened; there is nothing to leak via referrers or intents.

## Mobile notifications, chat and push flows (Phase 11E)

- **Server-scoped, account-keyed.** The backend scopes notifications and conversations to the caller; the app keys every list, thread, count, composer draft and message to the signed-in account, so another account's data, draft or in-flight send never appears after `/me` changes on a mounted route. Sending, marking read and opening a conversation use `runAsAccount` (one request, late success/error dropped, nothing invalidated).
- **Push never bypasses authorization.** A push is a hint; its data is validated (known `type`, UUID ids) and only selects a normal route whose own gate and the backend still apply. The tap coordinator holds a tap only while the session restores, never across a sign-out, and delivers it once.
- **Token handling.** The FCM token is held in memory only, never logged or persisted by the app, registered only for the signed-in account (OS permission re-checked on every sync, token refreshes included) and unregistered before logout. Every ownership operation (register AND unregister) carries a persisted, strictly increasing `ownership_seq` and the server applies it only if it is newer than the stored one under the token lock, so the final owner is independent of request arrival or commit order: an older request — including one the client gave up on — can never take the token back from, or resurrect, a newer state (ADR-057). Ownership requests are also serialised on the client and not aborted by the session ending. No Firebase Admin credential, `google-services.json` or key is in the repository; client identifiers come from build defines.
- **Privacy.** Message bodies are never logged (`ChatMessage.toString` omits them); server messages are never shown (blank/too-long map to fixed text); a conversation of someone else is a plain 404 shown as one generic text; the notification list never carries the raw payload, recipient or dedupe key.
- **No retry of mutations.** Mark read, mark all, send and open-conversation are single requests; the automatic read cursor is one attempt per newly observed sequence.

## Mobile release hardening (Phase 11F)

- **Configuration:** release builds require an explicit https API origin; development environment, loopback/emulator hosts and credential-bearing URLs are rejected; the development fallback is not compiled into release (`docs/MOBILE_RELEASE.md` §1).
- **Signing:** no keystore, password or `key.properties` in Git (ignored, guarded by a test); release builds fail without credentials; the smoke-signing switch is explicit and non-production.
- **Android surface:** permissions limited to `INTERNET`, `POST_NOTIFICATIONS` and the FCM-merged ones; only the launcher activity is exported by the app and library receivers are permission-protected; not debuggable; `usesCleartextTraffic=false` (debug-only opt-in); `allowBackup=false` with empty extraction rules.
- **Privacy:** release builds log nothing (`SafeLogger` is debug-only); no code prints; no log call interpolates a token, e-mail, body or payload (source-scan test); no URL launcher/WebView/analytics package.
- **Artifact verification:** `mobile/tool/verify_release_apk.py` and the CI job `mobile-release` check the compiled release APK.
- **Not covered:** certificate pinning (not implemented), root/jailbreak detection (out of scope), real-device penetration testing.

## Phase 12A security review (2026-10-07)

Scope: the whole HTTP surface, configuration and deployment path, reviewed by this implementation pass (not an independent audit; the independent review of the 12A pull request follows). Method: read every route and permission class; a **reflection test** (`tests/test_security_sweep.py`) walks every `/api/v1/` URL pattern, evaluates the DRF permission classes per HTTP method and pins the exact list of public operations — a new public endpoint fails the test until it is added deliberately — and sends an anonymous request to every other operation, which must answer 401/403; targeted tests for each finding below.

| # | Finding | Severity | Resolution | Regression test |
| --- | --- | --- | --- | --- |
| 1 | One-time reset/verification tokens sit in the query string of the page URL; gunicorn's default access log records the request line and `Referer`, so they would reach platform logs (and a page could forward them in `Referer`). | P2 | Custom gunicorn access-log format (path only, no referer); `Referrer-Policy: no-referrer`. | `test_phase12a_hardening.py` (log format, header) |
| 2 | If the mail provider failed, the public password-reset request raised a 500 only for **existing** accounts — an account-existence oracle during outages. | P2 | Failure is swallowed and logged; identical 202 for known/unknown/failing. Authenticated verification request answers typed `503 email_unavailable`. | `test_email_resilience.py` |
| 3 | Mail had no timeout (Django default: none): a stalled SMTP server would hold a worker until gunicorn killed it. | P2 | `EMAIL_TIMEOUT` (10 s) + `racheeta.E008`. | `test_phase12a_hardening.py` |
| 4 | Behind Railway's proxy every client shares one address, so the login throttle would lock out everyone at once (or, if misconfigured the other way, be bypassed with a forged `X-Forwarded-For`). | P2 | `TRUSTED_PROXY_COUNT` → `NUM_PROXIES`; `racheeta.E005` refuses an unconfigured proxy; staging verification procedure. | `test_phase12a_hardening.py`, `test_checks.py` |
| 5 | No Content-Security-Policy / Permissions-Policy. | P3 (hardening) | Added (see HTTP hardening). | `test_phase12a_hardening.py`, browser check |
| 6 | `/api/docs/` and `/api/schema/` were public in production. | P3 | Off unless `DEBUG`/`API_DOCS_ENABLED`; W003 warns if exposed. | `test_phase12a_hardening.py` |
| 7 | No readiness endpoint: a release whose database was unreachable still passed `/health/`. | P3 | `/ready/`; Railway health check switched to it. | `test_phase12a_hardening.py` |
| 8 | `SECURE_SSL_REDIRECT` would have failed Railway's plain-HTTP deployment probe; `healthcheck.railway.app` was not an allowed host. | P3 (would block first deploy) | Redirect exemption for the two probe paths; host added when behind TLS. | `test_phase12a_hardening.py` |
| 9 | PyJWT 2.14.0 advisories (not exploitable here). | P3 | Pinned 2.15.1. | `pip-audit` |
| 10 | Refresh-token revocation rows grow forever (`token_blacklist_*`). | P3 (operational) | `manage.py prune_expired_tokens` (batched, `--dry-run`); cadence in `docs/OPERATIONS.md`. | `test_phase12a_hardening.py` |
| 11 | A weak or placeholder `SECRET_KEY` produced only a warning, and `start.sh` runs a plain `manage.py check`; SimpleJWT signs tokens with `SECRET_KEY`, so a guessable key lets anyone forge logins. (Found in independent review of PR #20.) | P1 | `racheeta.E009` is an Error for `DEBUG=false`; the Docker build generates an ephemeral build-only key instead of committing a placeholder. | `test_phase12a_hardening.py` (subprocess `manage.py check` per bad value) |
| 12 | A non-https production `FRONTEND_URL` produced only a warning, so reset/verification links carrying one-time tokens could be generated over cleartext HTTP. (Independent review.) | P2 | `racheeta.E010` is an Error for `DEBUG=false` (https origin only). | `test_phase12a_hardening.py` |

Reviewed and unchanged: object-level isolation (covered since Phases 2–10 by per-app tests); privilege fields rejected on writes; admin reachable only with staff session (path configurable, not a security control); no file uploads exist (no upload attack surface; the media deferral is in `docs/PRODUCTION_DEPLOYMENT.md`); CORS allow-list empty in production (same origin); mass-assignment protected by explicit serializer field lists; logging and error envelopes do not expose internals. **No open P1/P2 findings remain from this pass.** Residual risks: refresh token in `localStorage` (ADR-061), per-process throttle counters, synchronous mail, no WAF/CDN, no 2FA for admin accounts (owner decision; recommended before production).

## HTTP hardening (`DEBUG=false`)

| Control | Where | Notes |
| --- | --- | --- |
| `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy` | Django security middleware | |
| `Referrer-Policy: no-referrer` | `SECURE_REFERRER_POLICY` | E-mail links carry one-time tokens in the query string; no page may forward them. |
| `Content-Security-Policy` | `apps/core/middleware.py` (`SecurityHeadersMiddleware`) | SPA: `default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'` (+ `upgrade-insecure-requests` behind TLS). No `unsafe-eval`, no `unsafe-inline` for scripts or styles (React applies `style` through the CSSOM; checked in a real browser with zero violations). API: `default-src 'none'`. Admin: first-party scripts, inline styles allowed (Django admin needs them). API docs paths carry no CSP (Swagger UI loads from a CDN) and are off in production. Extra API origins: `CSP_CONNECT_SRC`. |
| `Permissions-Policy` | same | accelerometer, camera, geolocation, gyroscope, magnetometer, microphone, payment, usb, interest-cohort all denied. |
| HTTPS redirect, HSTS (30 days, include subdomains, no preload), secure cookies | `SECURE_PROXY_SSL=true` | `/health/` and `/ready/` are exempt (the platform probe is plain HTTP). Raise HSTS to a year and consider preload only after a stable HTTPS deployment (preload is a one-way public commitment). |
| Config guard rails | `apps/core/checks.py`, run by `scripts/start.sh` | E001 console/locmem mail; E005 proxy without `TRUSTED_PROXY_COUNT`; E006 wildcard/empty hosts; E007 non-https CSRF origins; E008 no mail timeout; **E009 weak/placeholder `SECRET_KEY`** (under 50 characters, `change-me…`, `build-time-placeholder…`, `django-insecure-…`, or almost no character variety — it is SimpleJWT's HMAC signing key, so this is an authentication failure, not advice); **E010 `FRONTEND_URL` not a plain https origin** (rejects http, missing scheme/host, credentials, query, fragment, path; reset/verification links carry one-time tokens); W003 API docs exposed. All `E…` ids stop `scripts/start.sh` before migrations. Neither value is ever echoed in the message. Development (`DEBUG=true`) is unaffected. (The earlier warning `W002` no longer exists.) `check --deploy` is exercised with fake values in `tests/test_phase12a_hardening.py`. |

Request ids (`X-Request-ID`, validated) tie a user report to a log line; JSON logs redact bearer tokens, `token=`/`password:` pairs and e-mail addresses and never emit `extra` fields. 5xx responses use a fixed body (no stack trace, no settings).

## CORS

Only origins in `CORS_ALLOWED_ORIGINS`. Credentials are not shared cross-origin
(bearer tokens, not cookies). In production the web app is same-origin so the
list can be empty.

## Rate limiting

Audit (12A). The cache is Django's local-memory cache, so counters are **per process**: with `WEB_CONCURRENCY=2` the effective limit is up to twice the rate, and a redeploy resets them. Acceptable for one container; move to a shared cache before adding replicas.

| Scope | Rate | Applies to |
| --- | --- | --- |
| `auth` | 10/min | register, login, refresh, logout, Firebase exchange (keyed by client IP) |
| `password_reset` | 5/min | reset request + confirm |
| `email_verification` | 3/min | verification request + confirm |
| `jobs_create` / `jobs_apply` | 30/h / 20/h | job creation, applications |
| `talent_search` / `talent_invite` | 60/min / 30/h | employer talent search, invitations |
| `recruitment_messages` | 60/h | recruitment messaging |
| `chat_messages` | 120/h | sending chat messages (POST only) |
| `push_devices` | 60/h | push-token register/unregister |
| `user_writes` (default, 12A) | 600/h | every other authenticated write (POST/PUT/PATCH/DELETE) per account; reads and anonymous requests are untouched |

Behind a proxy, DRF reads the client IP from `X-Forwarded-For` using `TRUSTED_PROXY_COUNT`. Wrong values fail in one of two directions: too low and every user shares the proxy's address (one attacker locks everyone out); too high and a client can forge the header to dodge the limit. `racheeta.E005` stops the container from starting with a proxy and a count of 0; the right value (Railway: 1) is verified in staging (`docs/STAGING.md`). Public anonymous reads (lists, detail) have no throttle; they are paginated (page size 20) and the load harness (`docs/PERFORMANCE.md`) measures them.

## Token storage trade-off (web)

Access token in memory; refresh token in `localStorage`. This keeps the session across reloads with zero infrastructure, at the cost of XSS exposure of the refresh token. Mitigations: no `dangerouslySetInnerHTML`, no inline scripts, dependencies pinned, and (12A) a strict Content-Security-Policy that blocks inline script and `eval`. The httpOnly-cookie alternative was **evaluated in 12A and deferred** (ADR-061): the mobile app needs the body-delivered token anyway, so a cookie would be a second auth path with new CSRF surface, and it should be designed against the final domain layout.

## Passwords

Django's default PBKDF2-SHA256 hasher. Validators: min length 8, similarity,
common-password list, numeric-only. Enforced on registration and on reset
confirmation. Tests use MD5 for speed only (`config/test_settings.py`).

## Email links

Reset and verification links carry an opaque `uid` (base64 UUID) and an HMAC
token. They are only ever sent to the address on the account. The SPA posts
them in a JSON body to the API. The *page* URL that the link opens does
contain them in its query string, so the gunicorn access log records the path
without the query string and without the `Referer` (`config/gunicorn.conf.py`),
and `Referrer-Policy: no-referrer` stops browsers forwarding them (a test pins
both). A reverse proxy or CDN in front of the app may log full URLs; the
platform's own request logs are the owner's to review (`docs/OPERATIONS.md`).

## Dependency policy and scanning

Direct Python and npm dependencies are pinned (`requirements/*.txt`, `package-lock.json`, `mobile/pubspec.lock`); PyJWT, a transitive dependency of SimpleJWT, is pinned too (12A). Upgrade deliberately; run the full CI. Not yet done: a fully hash-pinned lock of every transitive Python package (`pip-compile --generate-hashes`) — deferred, tracked in `docs/PRODUCTION_DEPLOYMENT.md` "Known gaps".

Scan results, 2026-10-07 (re-run before each production deploy; commands in `docs/OPERATIONS.md`):

| Scanner | Scope | Result | Disposition |
| --- | --- | --- | --- |
| `pip-audit` | installed backend environment | PyJWT 2.14.0: PYSEC-2026-4141 (`PyJWKClient` crash on deeply nested payload) and PYSEC-2026-4183 (OKP private-JWK import) | **Fixed**: pinned `PyJWT==2.15.1`. Neither code path is used (HS256 only, no JWKS client, no JWK import). `pip-audit` now reports none. |
| `npm audit` | production dependencies | 0 vulnerabilities | none |
| `npm audit` | full tree | 1 high: `source-map-js` event-loop DoS via crafted source-map section offsets (transitive of `postcss` via Vite, and `css-tree` via jsdom) | **Accepted**: build/test tooling only, never shipped to browsers or the production runtime image; exploitation needs an attacker-controlled source map fed to the build. No fixed release is published on the registry yet (`1.2.2` is latest). Re-check at each dependency update. |
| `flutter pub outdated` | mobile | `shared_preferences` 2.5.5 → 2.5.6 and four transitive packages behind | **Deferred**: no known advisory; upgrades change the lockfile and need a device pass. |
| `gitleaks` | whole git history + working tree | One finding on this branch: a fake JWT string in a redaction test (annotated `gitleaks:allow` and fingerprinted in `.gitleaksignore`, so a history scan is clean). Working-tree-only hits are the developer's gitignored `.env` and a third-party sample key inside `mobile/build/` (gitignored build output). Main's 340 earlier commits are clean. | none outstanding |

Dependency scanning is **not** wired into CI as a blocking job: advisories appear without code changes, which would make unrelated pull requests fail. Run the commands above at release time (documented in the production runbook).

## Reporting

Security issues: contact the owner directly. Do not open public issues.
