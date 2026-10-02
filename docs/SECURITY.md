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
| Password-reset enumeration | Same 202 body for known/unknown/inactive emails. Timing: sending is synchronous through the console/SMTP backend, so a slow provider could leak existence via latency. Mitigation planned: send from a background task when a worker exists. | documented |
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
- **No IDOR:** unregister only touches the caller's own device and answers `204` for unknown/foreign tokens alike; no list/read/delete-by-id API exists; tokens are never returned.
- **Credential hygiene:** tokens are never logged in full, never in audit rows or payloads; admin is inspection-only with masked tokens; Firebase credentials stay in `FIREBASE_CREDENTIALS_FILE` (platform-injected, never committed).
- **Best-effort, after commit:** pushes are scheduled with `transaction.on_commit`, never raise, and cannot fail or roll back the domain action; rolled-back changes never push.
- **Privacy:** lock-screen text is generic (no message bodies, notes, contact data, service/provider names); `data` carries only opaque ids and is never an authorization input.
- **Stale tokens:** only permanent Firebase rejections deactivate a device; transient errors never do. See `PUSH.md`.

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

Scoped throttles listed above, backed by Django's local-memory cache — per
process. Adequate for one container; switch to a shared cache if replicas are
added.

## Token storage trade-off (web)

Access token in memory; refresh token in `localStorage`. This keeps the
session across reloads with zero infrastructure, at the cost of XSS exposure
of the refresh token. Mitigations today: no `dangerouslySetInnerHTML`, no
inline scripts, dependencies pinned. A strict CSP is **not** yet set (Phase
12). Candidate upgrade: refresh token in an httpOnly, SameSite cookie with
CSRF protection. Recorded in `DECISIONS.md` (ADR-009).

## Passwords

Django's default PBKDF2-SHA256 hasher. Validators: min length 8, similarity,
common-password list, numeric-only. Enforced on registration and on reset
confirmation. Tests use MD5 for speed only (`config/test_settings.py`).

## Email links

Reset and verification links carry an opaque `uid` (base64 UUID) and an HMAC
token. They are only ever sent to the address on the account. The SPA posts
them in a JSON body; they never appear in API access logs.

## Dependency policy

All Python and npm dependencies are pinned (`requirements/*.txt`,
`package-lock.json`). Upgrade deliberately; run the full CI.

## Reporting

Security issues: contact the owner directly. Do not open public issues.
