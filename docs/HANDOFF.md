# Current State

Date: 2026-09-24
AI/Engineer: Claude (Fable 5.1) via Claude Code
Branch: `feat/phase3-medical-jobs` (from `main` at `9f19e33`, after PR #3 merged)
Last Commit SHA: see `git log -1` (the docs commit adding this handoff is the last one)
Remote: `git@github.com:moahaimen/enhanced_racheeta.git` (https://github.com/moahaimen/enhanced_racheeta)

> New session? Read `ARCHITECTURE.md`, `DECISIONS.md` (ADR-033..039),
> `PROGRESS.md`, `BILLING.md`, `JOBS.md`, `MODERATION.md`, `PROVENANCE.md`,
> then this file. Run `make check`. Continue from **Exact Next Step**.

## Goal of This Work Session

Phase 3 — Billing & Entitlements Foundation + Medical Jobs & Talent
Marketplace, per the owner's reprioritised roadmap (Jobs before
Reservations; Reservations stay free). **Phase 4 (Reservations) was not
started, by instruction.**

## Owner decisions honoured (all 16)

Jobs first · revenue from commercial users · subscription/entitlement/usage
controls on employer features · reservations free later · no CV uploads ·
no job attachments · structured profile is the résumé · no unnecessary
storage · no new attack surface · no direct contact exchange · value stays
inside Racheeta · Super Admin controls activation/verification/publication ·
ordinary workflow needs no admin clicks · no payment gateway · no new
infrastructure · loading contract on every action. No prices, no fake data,
no seeded employers/jobs/candidates.

## Completed

Backend (`apps/audit`, `apps/billing`, `apps/moderation`, `apps/jobs`):

- Audit log with admin read endpoint.
- Billing: plans + entitlements (capability keys), billing accounts per
  subject, subscriptions (PENDING→ACTIVE by Super Admin, suspend/cancel/
  reject, read-time expiry), minimal payment records, credits, atomic and
  idempotent usage counters, `EntitlementService.require/check_concurrent/
  consume`, default TRIAL / SEEKER_FREE plans, seed migration without prices.
- Moderation: `ContactLeakDetector` (phone incl. Arabic/Persian digits,
  e-mail, WhatsApp, Telegram, URLs) enforced by every recruitment serializer;
  jobs re-scanned at submit with flags for the admin.
- Jobs: Employer + memberships (OWNER/RECRUITER/VIEWER, seat limits),
  JobSeekerProfile with children, JobPost state machine with admin review,
  public search with filters, applications with immutable snapshots and
  transition history, interviews, text-only messages, talent search with the
  "one billable search per employer/filters/day" rule, saved candidates,
  invitations (accept ≠ apply), Super Admin control plane, typed error codes
  with `codes`/`meta` in the envelope, throttles.
- OpenAPI regenerated (warning-free), 130+ operations.

Web:

- API clients and DTOs, typed error localisation, design-system additions
  (`JobCard`, `TalentCard`, `UsageMeter`, status badges, `LinkButton state`).
- Pages: `/jobs`, `/jobs/:id`, `/employers/:id`, `/jobs/profile`,
  `/jobs/my-applications`, `/employer`, `/employer/jobs/new|:id`,
  `/employer/jobs/:id/applications`, `/employer/talent[/:id]`,
  `/admin-console` (RequireStaff). Header/footer links, home Jobs section with
  "ابحث عن وظيفة" / "ابحث عن كوادر".
- Vitest coverage for guards, search, apply flow and typed errors, my
  applications, résumé, employer workspace/plan request, job editor limits and
  flags, talent search/invite, admin console actions, home section.

Docs: `BILLING.md`, `JOBS.md`, `MODERATION.md` (new); `MASTER_PLAN.md`
roadmap correction; `ARCHITECTURE`, `DATABASE`, `API`, `SECURITY` (Phase 3
review), `PERMISSIONS`, `DECISIONS` (ADR-033..039), `DESIGN_SYSTEM`,
`PROVENANCE`, `PROGRESS`, this file.

## Database Migrations

`audit/0001_initial`, `billing/0001_initial`, `billing/0002_seed_plans`
(data: 7 plans, no prices), `jobs/0001_initial` (17 tables). See
`DATABASE.md`.

## API Endpoints Added

See `JOBS.md` (public, seeker, employer, talent, admin groups) and
`BILLING.md` (plans, admin subscription actions, credits, account summary),
plus `GET /api/v1/admin/audit`.

## Tests Run

```
make check   # ruff, django check, migrations check, pytest; tsc, oxlint, vitest, vite build
```

## Test Results

- Backend: **671 passed** (was 175): billing entitlements/admin API,
  moderation detector, employers/memberships, job lifecycle and gating,
  seeker profile and applications, public search and talent, privacy
  assertions, race regression.
- Web: **228 passed** (was 87).
- Build: OK.

## Browser Walkthrough Results

Local Django + Vite, three temporary accounts (staff, employer, seeker) and
the data they created — all deleted afterwards. Arabic RTL desktop unless
noted.

| Flow | Result |
| --- | --- |
| Home | Jobs section with both actions; anonymous "ابحث عن كوادر" goes to login and returns to `/employer`. Jobs no longer "قريباً". |
| Employer onboarding | Description with a phone number rejected with the Arabic contact message; clean submit created the organisation; verification requested → "قيد المراجعة". |
| Plan request | PROFESSIONAL requested; cards show "السعر يُحدَّد بالتواصل مع رشيتة" (no prices). Usage meters render from the API. |
| Job draft before verification | Draft saved; submit blocked with "يجب توثيق المؤسسة وتفعيلها أولاً". |
| Admin console | Organisation verified with a note; subscription activated with a payment reference (ACTIVE, ends in 30 days); job with clean text approved; every step audited (checked in DB). |
| Contact leak in job text (API) | PATCH with e-mail + WhatsApp + phone rejected at write time with the three categories. |
| Seeker résumé | Onboarding form created the profile; discoverable flag set. |
| Apply | Telegram handle in the cover text rejected; clean application accepted; "طلباتي" shows the application. |
| Messaging | Seeker → employer and employer → seeker text messages; employer sees candidate by professional title only. |
| Applicant review | Shortlist → interview request (in-person, location text) → status "مقابلة" with history. |
| Talent search | First load returned 500 (race between double-fired identical requests) → fixed (claim-first consumption, `get_or_create`), counter shows exactly 1 search. Results show no contact data. |
| Candidate detail | Layout was squeezed into the workspace sidebar column → fixed. Save and invite work. |
| Invitation to an applicant | Rejected with "لقد قدّمت على هذه الوظيفة مسبقاً" (the candidate had already applied) — correct typed error, localised. |
| Mobile 375px (Arabic) | Jobs search and home stack in one column, header collapses to the menu button, no horizontal overflow (`scrollWidth === innerWidth`). |
| English LTR | `dir=ltr`; jobs search, job detail and header mirror correctly; Arabic content stays readable inside LTR layout. |

Fixes made during the walkthrough: usage-consumption race (500), candidate
page layout, stray retry button in the team block, duplicated heading on the
résumé page, payment record when activating with a reference only.

## PR #4 review fixes (2026-09-24, same branch)

| Finding | Fix |
| --- | --- |
| P1 application quota reference `apply:{job}:{profile}` | Application row is created first (duplicates stopped by the active-application constraint), then usage is consumed with `apply:<application id>`. Withdraw + reapply consumes a new unit, retries do not. |
| P1 concurrent active-job limit bypass | `_submit_job` locks the `jobs_employer` row (`select_for_update`) before counting and transitioning; threaded regression test with a barrier. |
| P2 restore without limit re-check | `restore_job` runs the same `_require_active_job_slot` gate under the lock; typed `usage_limit_reached`; audit kept. |
| P2 featured expiry | Rule `is_featured AND featured_until > now` (`JobPost.is_actively_featured`); read-time `expire_featured_jobs` normalisation, serializer rule, live-window slot counting. |
| P2 elapsed subscription blocks renewal | `request_subscription` expires elapsed ACTIVE rows itself, under a billing-account row lock; duplicate live rows map to a typed error. |
| Audit: invitations reused `invite:{job}:{profile}` | Same attempt-based rule with the invitation id. |
| Audit: seats and plan requests unlocked | `add_member` locks the employer row; `request_subscription` is atomic with an IntegrityError guard. |
| Cleanup | Dead duplicate block left in `consume` by the earlier race fix removed. |

Backend tests 284, web tests 129, no new migration, OpenAPI unchanged.

## PR #4 review, round two (2026-09-24, review 5301558683 on `267fca0`)

| Finding | Fix |
| --- | --- |
| P1 `detailed_specialty` leak | `validate_no_contact_info` on the job write serializer and the field added to `contact_flags`; parametrised tests for e-mail, Iraqi phone, `+964`, URL, WhatsApp, Telegram, and normal text. |
| P1 message thread beyond 200 | Newest 200 messages queried, reversed to chronological order (`MESSAGE_THREAD_LIMIT`); test with 205 messages. |
| P1 my-applications page 1 only | URL-backed pagination (`?page=`) with the design-system `Pagination`, count line, empty-final-page state; tests for page 1/2, next/previous, loading, withdrawal on page 2. |
| P1 `jobs.application_review` bypass | One gate `_require_application_review` inside `_employer_applications` (list, detail, transition, interview) and in the employer branch of `_application_for_party` (messages); tests for every route with/without the capability, other organisations, VIEWER role. |
| P2 quota before filter validation | `TalentSearchView.list` validates the filterset before `record_talent_search`; `language_level` and `availability` are strict (case-insensitive) choice filters; tests: invalid profession/level/availability → 400 and zero usage. |
| P2 language + level on different rows | `TalentFilter` uses one EXISTS subquery over `LanguageSkill` for both parameters (also for `skill`), no `distinct()` needed; tests for mixed profiles and counts. |
| P2 no admin controls for SUSPENDED | Reactivate (existing `activate` action) and Cancel with `ApiActionButton`; tests for rendering, calls, pending state. |
| P2 employer workspace page 1 only | Paginated jobs (`?jobs_page=`) and a server-side `active_jobs` field on `GET /jobs/employer` (OpenAPI updated) used for the statistic; tests for paging, loading and the statistic staying authoritative. |
| P2 language name leak | `validate_no_contact_info` on `LanguageSkillSerializer.language`; tests for leaks and legitimate names in Arabic, English, Kurdish, Persian. |

Targeted audit: all other public free-text fields already carried the
validator; saved-candidate and invitation lists remain capped at 200 without
pagination (management screens, no data loss below that; noted below).

Backend tests 309, web tests 137, no migration, OpenAPI changed (`active_jobs`).

## PR #4 review, round three (2026-09-24, review 5301950655 on `d221abf`)

| Finding | Fix |
| --- | --- |
| P1 withdrawal reason leak | `validate_no_contact_info` on `RecruitmentReasonSerializer.reason`; `withdraw_application` and `transition_application` also refuse leaks at the service boundary; tests for e-mail, phone, `+964`, URL, WhatsApp, Telegram, ordinary text and stored history. |
| P1 expired invitations block re-inviting | `expire_overdue_invitations` (read/action-time UPDATE) runs in both invitation lists and before the duplicate check in `invite_candidate`; the UPDATE locks the stale row and the conditional unique constraint keeps one live row under concurrency; threaded test. |
| P1 reactivation next to a PENDING request → 500 | `activate_subscription` locks the billing account, re-reads the status, cancels any other ACTIVE **and** PENDING row as superseded (audited), and maps a constraint failure to a typed `SubscriptionError`. Policy documented in `BILLING.md`. |
| P1 concurrent application transitions | `_lock_application` (`SELECT … FOR UPDATE` + status refresh) in withdraw, transition and interview request; interview and invitation responses and subscription transitions lock the same way; threaded ACCEPTED/REJECTED test, stale-instance test. |
| P2 invitation picker capped at 20 | Picker keeps page 1 from the page load and appends further pages of PUBLISHED jobs through a "show more" `ApiActionButton`; count hint; tests for page 2 selection, loading state, empty state. |
| P2 seeker invitations page 1 only | `?invites_page=` (independent of `?page=`), `LoadingState` while paging, `Pagination`, empty final page; tests for paging, accept/decline on page 2. |

Targeted audit: interview notes/responses, invitation messages, employer
transition reasons and recruitment messages were already validated; jobs,
featured windows, subscriptions and now invitations all normalise at read
time; no other hard-coded first page remains in management pages.

Backend tests 327, web tests 142, no migration, OpenAPI unchanged.

## PR #4 review, round four (2026-09-24, review 5302331819 on `53698f6`)

| Finding | Fix |
| --- | --- |
| P1 verified identity mutable | `EmployerWriteSerializer` rejects changes to `name`, `organization_type`, `governorate`, `provider_profile`, `is_recruitment_agency` with `identity_locked` while PENDING or VERIFIED (same value allowed; description/city/discoverability free); web form disables those fields and sends only editable ones; tests for each field, provider unlink, presentation edits, review/rejected states, admin path and the job gate. |
| P1 no withdrawal during INTERVIEW | `INTERVIEW` added to `SEEKER_WITHDRAWABLE`; withdrawal cancels PROPOSED interviews atomically; web shows Withdraw in INTERVIEW; tests for history, interview state, terminal states, loading contract. |
| P2 interview answers after closure | Policy: terminal transitions (accept/reject/withdraw) cancel PROPOSED interviews; `respond_to_interview` locks the parent application first and refuses with `application_closed` (409); web hides answers on terminal applications; tests per closer. |
| P2 stale job lifecycle validation | `_lock_job` (row lock + status refresh) in submit, approve, reject, suspend, restore, close, archive, expiry and featuring, always after the employer lock; threaded approve/reject and close/suspend tests, stale-instance and sequential tests. |
| P2 invitation guidance on PENDING | Guidance rendered per ACCEPTED invitation only; PENDING shows accept/decline; other statuses show neither; tests for all five statuses and the accept flow. |

Targeted audit: no other identity-defining employer field exists; messages
already close on WITHDRAWN/REJECTED; invitations answered on apply; job
state gates application actions through `is_open`; all five state machines
now use the same lock-then-validate pattern; no other status message was
conditioned on the wrong state.

Backend tests 346, web tests 150, no migration, OpenAPI unchanged.

## PR #4 review, round five (2026-09-24, review 5302630948 on `750ef64`)

| Finding | Fix |
| --- | --- |
| P1 job edits vs lifecycle | `services.edit_job`: job row lock, editability checked on the refreshed status, `update_fields` limited to the edited columns; the view's unlocked check is only an early exit. Tests: threaded PATCH vs submit, stale PATCH after submit (`job_locked`, no revert, `submitted_at` intact), sequential draft edits. |
| P1 identity edits vs verification | `services.update_employer` locks the employer row and checks identity fields against it; `request_employer_verification`, `set_employer_verification` and `set_employer_recruitment_status` lock and refresh the row before writing (`update_fields`). Tests: threaded PATCH vs VERIFY (verify always applies to the identity it saw; the losing edit gets `identity_locked`), stale instance, admin decisions not clobbering. |
| P2 saved candidates readable without entitlement | `_require_talent_access` (verified + active organisation, then the capability) on `GET /talent/saved` (`talent.save_candidate`), and analogously on `GET /talent/{id}` (`talent.search`) and `GET /talent/invitations` (`talent.invite`). Tests: entitled, expired, suspended subscription, recruitment suspended, TRIAL plan, POST unchanged, isolation, detail and invitations. |

Targeted audit: candidate detail and the sent-invitations list were the
analogous read bypasses and are gated now; no other verification-status
write used a stale instance.

Backend tests 360, web tests 150, no migration, OpenAPI unchanged.

## PR #4 review, round six (2026-09-24, review 5302884006 on `06e30b6`)

| Finding | Fix |
| --- | --- |
| P1 suspended employers keep applicant workflows | `_require_recruiting` runs first inside `_require_application_review` (list, detail, transition, interview) and in the employer branch of the message resolver; typed `organization_not_verified` (403). Tests for recruitment- and verification-suspended organisations on every route, seeker reads/withdrawal intact, isolation. |
| P1 apply uses a stale open job | `apply_to_job` locks the employer row, then the job row, re-reads both and only then creates the application and consumes usage; `invite_candidate` does the same. Threaded apply-vs-close and apply-vs-suspend tests: when the closer wins nothing is created or charged; stale-instance tests for closed jobs and suspended employers. |
| P2 submit checks recruiting before the lock | `_submit_job` re-checks `can_recruit` on the locked employer row before the slot check; threaded submit-vs-suspend test, stale-instance test, typed 403 over HTTP, no transition on a blocked submit. Featuring re-checks the same way. |
| P2 public employer page shows page 1 only | Employer header loads once; the jobs block is its own `AsyncPage` paginated from `?jobs_page=` with skeleton loading, count, `Pagination` and an empty-final-page state. Tests for page 1/2, next/previous, loading with the header kept, empty states, not found. |

Targeted audit: talent search/detail/saved/invitations already required a
recruiting organisation (round five); invitation creation now validates
under the same locks as applying; no usage is consumed on any rejected
attempt; no other public listing has a hard-coded first page.

Backend tests 373, web tests 155, no migration, OpenAPI unchanged.

## PR #4 review, round seven (2026-09-24, review 5303137536 on `b666379`)

| Finding | Fix |
| --- | --- |
| P2 stale subscription expiry | `expire_subscription` is atomic, locks the row, and transitions only if still ACTIVE and elapsed; threaded expire-vs-suspend, expire-vs-cancel and expire-vs-expire tests (one event, newer admin state kept), entitlement lookup after normalisation. |
| P2 expired invitation marked ACCEPTED on apply | `apply_to_job` locks the seeker's PENDING invitations for the job and marks a live one ACCEPTED, an elapsed one EXPIRED; tests for both, history, no double transition, application still created. |
| P2 raw query strings hashed for billing | `canonical_talent_params` mirrors the filter semantics (folded text, upper-cased choices, trimmed slugs/enums, numeric experience, folded UUIDs, unknown/paging/ordering keys ignored); `q`/`detailed_specialty` filters collapse whitespace too; tests for equivalent and different filters, paging, invalid filters, duplicate equivalent HTTP searches consuming once. |

Targeted audit: job expiry and invitation expiry already re-check under
locks; no other billable signature exists.

Backend tests 383, web tests 155, no migration, OpenAPI unchanged.

## PR #4 review, round eight (2026-09-24, review 5303372106 on `ec62133`)

| Finding | Fix |
| --- | --- |
| P2 retained hiring fields on non-agencies | Serializer validates the resulting job (`not_an_agency` per field); `edit_job` (now under the employer lock too) and `_submit_job` re-check `_require_agency_invariant` on the locked employer flag and job. Tests: agency creates both kinds, flag change before verification, retained fields block unrelated edits and submit, clearing restores, plain jobs unaffected, stale employer instance cannot bypass. |
| P2 accepting an invitation on a closed job | `respond_to_invitation` locks employer, job and invitation, normalises expiry, and refuses acceptance when the job is not open or the organisation cannot recruit (`invitation_unavailable`, 409); the invitation stays PENDING and can still be declined. Tests per cause, expiry, threaded accept-vs-close/suspend. |
| P2 saving candidates while suspended | `POST /talent/saved` runs the same `_require_talent_access` gate as GET, and `save_candidate` re-checks `can_recruit` on the refreshed row. Tests: entitled save, recruitment/verification/subscription suspended, service-level stale instance, viewer role, isolation, no row on rejection. |

Targeted audit: search, detail, saved (GET/POST), invitation lists and
invitation creation all enforce the recruiting gate consistently now.

Backend tests 401, web tests 155, no migration, OpenAPI unchanged.

## PR #4 review, round nine (2026-09-24, review 5305174384 on `0e399c1`)

| Finding | Fix |
| --- | --- |
| P2 pending subscriptions missing from the billing summary | Entitlement resolution and billing UI state are now separate. `EntitlementService.pending_subscription` resolves PENDING only; `billing_summary` adds `pending_subscription` beside the unchanged `subscription` (ACTIVE only). A PENDING row still grants nothing — `plan`, `get()` and every capability check are untouched. The workspace reads the new field, so after a reload it shows the pending notice, hides the request form and cannot produce a duplicate request. Tests: pending-only summary, default entitlements without a subscription, ACTIVE effective with the duplicate request refused, SUSPENDED + PENDING coexistence, suspended/cancelled/rejected/expired never reported as pending, admin activation clears it; web: pending survives reload, form and radios gone, ACTIVE shows no pending, suspended is not pending. |
| P2 retained hiring fields unclearable in the UI | `JobEditorPage` warns about the retained values (`retained-hiring-notice`) and, on every save of an **existing** non-agency job, submits `hiring_employer: null` and `hiring_organization_name: ""`. Nothing else is touched; a non-agency **create** still sends no agency-only value and an agency keeps both editable fields. Tests: repair warns + clears + `ApiActionButton` loading contract, clean job shows no warning, create stays clean, agency edit preserved; backend: clearing both in one save unblocks the later submit. |
| P2 `provider_profile` missing from employer onboarding | `EmployerForm` fetches the caller's own profile from `GET /providers/me` (404/403 = nothing to choose), offers it only when it is a FACILITY, and sends `provider_profile` in create/update. No new endpoint and no global provider list: the backend stays authoritative (own profile, facility kind, not already linked). Locked once verification is PENDING/VERIFIED, matching the existing identity rule. Tests: eligible profile offered and sent, practitioner never offered, existing link loaded and disabled when locked, empty state, loading state. |
| P2 `jobs_create` throttle applied to GET | `_ThrottledOnWrite.get_throttles()` selects `ScopedRateThrottle` for unsafe methods only; safe methods fall through to `DEFAULT_THROTTLE_CLASSES` (`throttle_classes` is deliberately unset). Applied to `EmployerJobListView`. POST limits unchanged. Tests: 30 GETs leave the whole creation allowance, the 31st POST is 429 at the configured rate, listing still works once creation is exhausted. |

Targeted audit: `InvitationListView` had the same misuse — `talent_invite`
(a write quota) on a GET+POST view — and was fixed the same way, with a test
that GET does not consume it and POST still does. `ApplicationMessagesView`
(`recruitment_messages`, GET+POST) has the same *shape* but its scope is a
resource name rather than a write verb, so it falls outside the stated audit
criterion and was **left unchanged**; it is listed under Known Problems.
Every other scoped throttle (`auth`, `password_reset`, `email_verification`,
`jobs_apply`, `talent_search`) is on a POST-only view, so no other change was
needed. Noted but not changed: `billing.services.request_subscription` carries
`@transaction.atomic` twice (harmless — the inner one is a no-op savepoint).

Backend tests 415, web tests 169, no migration, **OpenAPI regenerated**
(`BillingSummary.pending_subscription`).

## PR #4 review, round ten (2026-09-25, review 5305876644 on `8fa90f8`)

| Finding | Fix |
| --- | --- |
| P2 restore skips business eligibility | One `_require_publication_eligibility` helper (recruiting status → agency invariant → capability and slot) now runs for both `_submit_job` and `restore_job` on the locked employer and job rows. Tests: eligible restore, unverified / recruitment-suspended / verification-suspended organisations, former agency with retained hiring fields (blocked, then allowed after clearing), capacity, missing `jobs.post`, threaded restore-vs-suspend; refused restores write no transition. |
| P2 admin cannot see the identity being verified | `EmployerAdminSerializer.provider_profile` is a read-only reference (`id`, `display_name`, `provider_type`, `verification_status`; no contact/owner data) and the console row shows the agency flag, city, linked facility (name · type, id secondary) or a clear "no linked facility", and the verification request time. OpenAPI regenerated. Tests on both sides. |
| P2 `updated_at` labelled "Submitted" | The job row renders `submitted_at` (with "Not submitted yet" for drafts), shows `published_at` when present, and labels `updated_at` as "Last updated". Tests for pending, published/rejected/suspended and draft jobs. |

Targeted audit: the employer row now shows `verification_requested_at`;
no other timestamp in the moderation UI was mislabelled.

Backend tests 425, web tests 177, no migration, **OpenAPI regenerated**
(`EmployerAdmin.provider_profile`).

## PR #4 review, round eleven (2026-09-25, review 5315446119 on `fe0e3ee`)

| Finding | Fix |
| --- | --- |
| P1 approval skips eligibility | `approve_job` locks the employer row first, then the job, checks it is still pending and clean, and runs the same `_require_publication_eligibility` as submit and restore (recruiting status, agency invariant, deadline, `jobs.post`, active slot). Tests: eligible approval, recruitment-/verification-suspended and unverified organisations, lapsed subscription, missing capability, reduced limit, former agency, threaded approve-vs-suspend; refused approvals write no history. |
| P2 approval after the deadline | The shared gate refuses `application_deadline < today` (`deadline_passed`, 409; the deadline day itself is still open, matching `is_open`) for submit, approve and restore. Tests: future, today, past, no PUBLISHED history. |
| P2 overdue jobs counted as active | `_require_active_job_slot` normalises the organisation's overdue PUBLISHED jobs under the employer lock (job rows locked in turn, one EXPIRED transition), and `_active_job_count` ignores elapsed PUBLISHED jobs regardless. Applies to submit, approve and restore. Tests: overdue job frees the slot, fresh job still counts, submit/approve/restore share the semantics, concurrent normalisation writes one transition. |
| P2 N+1 on job cards | `with_public_relations` also selects `employer__provider_profile` and the hiring employer's governorate, city and provider profile. Query-count tests for a 20-card page with linked facilities and agency jobs, and for page-size growth. |

Backend tests 444, web tests 177, no migration, OpenAPI unchanged.

## PR #4 review, round twelve (2026-09-25, review 5315871704 on `0dddd00`)

| Finding | Fix |
| --- | --- |
| P1 activation on a retired plan | `activate_subscription` re-reads the plan under lock inside the activation transaction and refuses (typed `SubscriptionError`) when it is inactive, before cancelling anything; no ACTIVE event, no payment record. Tests: active plan activates, retired plan blocks activation and reactivation, state unchanged, entitlements still ignore inactive plans, threaded activate-vs-deactivate. |
| P2 decision notes exceed the transition column | `AdminDecisionSerializer.note` max 500 (reason serializers already 500). Tests for approve, restore, reject, suspend at 500/501 with no transition on rejection. |
| P2 messages race closure | `send_message` is atomic and locks/refreshes the application before the closed check. Tests: open, after REJECTED, after WITHDRAWN, threaded message-vs-reject and message-vs-withdraw with no partial row. |
| P2 public detail of an elapsed job | `JobPost.objects.public()` excludes PUBLISHED jobs whose deadline elapsed (same boundary as `is_open`), so search, detail and apply agree; employer/admin reads unchanged; listing still normalises history once. Tests for future/today/past deadlines and repeated reads. |

Backend tests 460, web tests 177, no migration, **OpenAPI regenerated** (`AdminDecision.note` maxLength 500).

## PR #4 review, round thirteen (2026-09-25, review 5316217187 on `5c1bb4b`)

| Finding | Fix |
| --- | --- |
| P2 Django admin as a second state machine | `SubscriptionAdmin`: lifecycle/identity fields read-only, no add/delete, read-only event and payment inlines; `Plan.code`/`audience` frozen after creation; `UsageCounter` read-only. Tests: change form without editable status/plan/account/dates, POST cannot flip PENDING→ACTIVE, service activation and API actions unchanged. |
| P2 saved cards ignore discoverability | `_visible_candidates(employer)` (active account, discoverable or applied to this employer) shared by talent detail and the saved list; the relation stays stored. Tests: hidden without application disappears, prior applicant stays, other employer's applicant hidden, inactive hidden, isolation, re-enable restores. |
| P2 saved list truncated at 200 | `SavedCandidateListView` is a `ListCreateAPIView` on the standard pagination (newest first). Tests: 205 rows across pages, count, next/previous, ordering, page 2 ids, privacy + pagination. OpenAPI regenerated. |
| P2 no unsave in the UI | Talent detail exposes `saved_candidate_id` (own record only); the candidate page shows Remove-from-saved via `ApiActionButton` and reloads. Backend tests: own id, null when unsaved, other employer's id never leaked, DELETE scoped; web tests: save → saved, remove → unsaved, duplicate clicks, error keeps state. |

Targeted audit: delete reachability is restored by pagination plus the
detail id; isolation, discoverability, recruiting and entitlement gates are
enforced on every saved-candidate path. Found while wiring unsave:
`ApiActionButton` treated an `undefined` result as "no success", so every
void action (unsave, and the seeker profile's delete buttons) never fired
`onSuccess`/reload. `useAsyncAction.run` now returns a `DUPLICATE_CALL`
sentinel for ignored clicks and the button reports every completed action,
with a design-system test.

Backend tests 471, web tests 181, no migration, **OpenAPI regenerated**
(paginated saved candidates, `TalentDetail.saved_candidate_id`).

## PR #4 review, round fourteen (2026-09-25, review 5317147760 on `1daeec7`)

| Finding | Fix |
| --- | --- |
| P2 lossy experience in the billing signature | Experience is an integer column, so `min_experience`/`max_experience` are now `IntegerFilter`s (fractional input → 400, nothing consumed) on both the talent and public job filter sets, and the signature normaliser canonicalises exactly as `forms.IntegerField` parses (`05` and `5.0` → `5`) without any `int(float())` truncation. Tests: `5.9`/`5.5` rejected with no quota, `05` and `5.0` are the same search as `5`, `6` and `max_experience=5` differ, parameter order irrelevant, quota unchanged. |
| P2 sent invitations ignore discoverability | `InvitationListView.get_queryset` filters `job_seeker__in=_visible_candidates(employer)` — the same predicate as talent detail and saved candidates — before serialisation; rows stay stored. Tests: hidden without application disappears, prior applicant stays, other employer's applicant hidden, inactive hidden, isolation, re-enable restores, row kept. |
| P2 sent invitations truncated at 200 | `InvitationListView` is a `ListCreateAPIView` on the standard pagination, newest first, client ordering disabled; POST unchanged. Tests: 205 rows across pages, count, links, ordering, page 2 ids, visibility + count, gates. OpenAPI regenerated. |

Targeted audit: talent detail, saved candidates and sent invitations share
`_visible_candidates`; both employer collections are paginated; no `[:200]`
slice remains on them; no billing normaliser is lossy.

Backend tests 478, web tests 181, no migration, **OpenAPI regenerated**
(paginated sent invitations).

## PR #4 review, round fifteen (2026-09-25, review 5317937828 on `ed45278`)

| Finding | Fix |
| --- | --- |
| P2 restore revives featured state over quota | `_live_featured_count` / `_require_featured_slot` shared by featuring and restore; restore keeps a retained featured flag only if the window is open, `jobs.featured` is still enabled and a slot is free, otherwise restores as a normal published job (audit `featured_kept`). Tests: preserved, slot taken meanwhile, entitlement lost, limit reduced, window elapsed, threaded restore-vs-feature, plain restore unchanged, active-slot check intact. |
| P2 featuring an elapsed job | `set_featured` refuses `application_deadline < today` (`deadline_passed`) under the locks before any slot is checked; EXPIRED rows already fail the status check. Tests: future, today, past, EXPIRED, no slot consumed, entitlement/limit still enforced, threaded expiry-vs-feature. |
| P2 ACCEPTED invitation allows a duplicate | `ACTIVE_INVITATION_STATUSES = (PENDING, ACCEPTED)` used by the duplicate check, which runs under the employer lock before creation and consumption. Tests: PENDING/ACCEPTED block, DECLINED/EXPIRED/CANCELLED allow, application still blocks, refused duplicate consumes nothing, legitimate reinvite consumes, threaded duplicates. |
| P2 VIEWER sees New Job | Workspace shows New Job and talent search only to OWNER/RECRUITER (unknown role gets nothing); the editor renders read-only with a notice for a VIEWER reaching it by URL. Web tests per role. Backend 403s unchanged. |

Targeted audit: no path can exceed `jobs.featured_limit` or feature an
elapsed job; expired windows occupy no capacity; PENDING and ACCEPTED both
block duplicates while terminal states permit reinvites; failed duplicates
consume nothing; VIEWER is read-only in the UI with the backend authoritative.

Backend tests 497, web tests 186, no migration, OpenAPI unchanged.

## PR #4 review, round sixteen (2026-09-25, review 5319207695 on `eca49d0`)

| Finding | Fix |
| --- | --- |
| P1 retiring a plan with ACTIVE subscribers | `Plan.save()` refuses `is_active` true → false while ACTIVE subscriptions reference the plan, under a lock on the plan row (the lock `activate_subscription` takes first), raising a `ValidationError`; `PlanAdminForm.clean()` shows the same as a field error. Tests: zero/one/several ACTIVE, PENDING/SUSPENDED/EXPIRED/CANCELLED do not block, plan and subscriptions unchanged on refusal, price edits fine, retirement after suspension, activation on a retired plan still refused, threaded activation-vs-retirement. |
| P2 re-verification republishes invalid jobs | `set_employer_verification(VERIFIED)` locks the employer, then each PUBLISHED job, and suspends (transition + audit, clear reason) any that fails `_require_agency_invariant` under the current identity; valid jobs stay published. Tests: agency → unverified → non-agency → re-verified hides the old job from search and detail, history, mixed valid/invalid handled atomically, no-job and unchanged-identity verifications. |
| P2 concurrent membership add → 500 | `add_member` locks the employer row, then the target account row, re-checks the active membership, and maps only the one-active-membership constraint violation to typed `already_member`. Tests: normal add, same/other employer duplicates, threaded two-employer race (one success, one typed error, one row), seats, reassignment after ending. |

Lock orders: billing account → subscription → plan (activation) vs plan
row alone (retirement); employer → job (verification, submit, approve,
restore, edit); employer → account (membership). No path takes them in
reverse.

Backend tests 527, web tests 186, no migration, OpenAPI unchanged.

## PR #4 review, round seventeen (2026-09-25, review 5321643473 on `153493f`)

| Finding | Fix |
| --- | --- |
| P2 `BillingAccount` mutable in the admin | `InspectionOnlyAdmin` base (all concrete fields read-only, no add/change/delete, no bulk actions) applied to `BillingAccount` with read-only subscription and credit inlines. Tests: identity fields not editable, POSTs to change identity refused (403) and nothing rebound, add/delete/bulk delete refused, data still inspectable, services unaffected. |
| P2 `CreditBalance` movable/deletable in the admin | Same base for `CreditBalance`, `CreditTransaction`, `UsageCounter`, `UsageEvent`, `SubscriptionEvent`, `PaymentRecord`; `Subscription` loses bulk actions. Tests: no editable field, POST refused, add/delete refused, `grant_credits` still ledgers correctly, history rows append-only. |
| P2 concurrent `POST /jobs/employer` → 500 | `create_employer` locks the owner account row (shared `_lock_account`, the policy `add_member` uses) before the membership check, inserts the OWNER membership through the shared savepoint helper that maps only the one-active-membership violation to `already_member`; Employer row and audit roll back with it. Tests: normal creation, typed 409 for existing members, rollback leaves no orphan, other IntegrityErrors propagate, ended membership frees the account, threaded same-account double creation (one 201, one 409, one Employer, one OWNER membership), threaded create-vs-add_member race. |
| P2 VIEWER sees applicant mutation controls | `ApplicantsPage` loads the membership (`getMyEmployer`) with the job and applications and gates transition, interview, reason field and the message thread on OWNER/RECRUITER; VIEWER and unknown roles see a read-only note and the applicant data. Web tests: OWNER/RECRUITER see the controls, VIEWER/unknown see none but keep the data, loading/error states unchanged. |

Sibling audit (bounded): billing admin models classified and locked as above;
account → organisation assignment paths (`create_employer`, `add_member`,
`end_membership`) share one serialisation policy; employer pages checked for
VIEWER write controls — workspace, job editor and applicants page gate them,
talent search/detail, saved candidates and invitations are `CanRecruit`-only
surfaces the workspace does not link for a VIEWER and that fail closed with a
403 error state if reached by URL.

Backend tests 550, web tests 191, no migration, OpenAPI unchanged.

## PR #4 review, round eighteen — Phase 3 closure (2026-09-25, review 5322161319 on `1ef2e74`)

| Finding | Fix |
| --- | --- |
| P2 owner PATCH decides on a stale employer instance | `update_employer` re-reads the whole row under `select_for_update` and uses that locked instance for the frozen-identity rule, every identity comparison and the write; the caller's instance is only synchronised afterwards. Tests: unverified edits, each frozen identity field on a verified employer, the stale-instance scenario for every identity field category, non-identity edits, agency/non-agency verification, threaded stale edit vs edit+verification. |
| P2 recruitment mutations trust the view pre-check | `_require_recruitment_mutation` locks the employer row first, re-reads it, re-runs `can_recruit` and the gating entitlements; used by `transition_application`, `request_interview` (and its nested transition) and employer-side `send_message` before the application lock (order employer → application → interview). Tests: eligible actions, suspension after the pre-check for each action (no row, no audit change, typed error), lost entitlement for each action, API 403s, candidate actions unaffected, threaded transition vs suspension. |
| P2 elapsed ACTIVE rows listed and actionable as ACTIVE | `expire_all_elapsed_subscriptions()` (reuses `expire_subscription`, bounded to elapsed rows, idempotent) runs in the admin list `get_queryset` before filtering and serialisation; `suspend_subscription`/`cancel_subscription` expire an elapsed term first and then refuse with the typed error; `activate_subscription` expires the account's elapsed rows before superseding. Tests: expired before response, event written once across repeated lists, status filters, future ACTIVE untouched, SUSPENDED/CANCELLED/EXPIRED not rewritten, actions after listing, direct paths, live terms still suspend/cancel, activation over an elapsed row. Round-seven's stale-expiry test now decides on a live term (an elapsed one can no longer be suspended). |

Bounded audit: every other employer-entering service already decides on the
locked row (`_lock_employer` fresh instance or `_refresh_employer_status` for
status-only decisions); `invite_candidate` and `save_candidate` re-check the
locked employer, `cancel_invitation` only retracts; subscription list, suspend,
cancel and activate all normalise elapsed terms. No directly analogous defect
is known to remain in these three families.

Backend tests 586, web tests 191, no migration, OpenAPI unchanged.

## Phase 3 production-closure audit (2026-09-25, on `eb028ea`)

One systematic pass over every Phase 3 mutation, queryset, admin surface and
web control, with four read-only audit tracks (authorization/visibility,
concurrency/lifecycle, billing/entitlements, web role controls) and a
scripted end-to-end smoke test (`apps/jobs/tests/test_phase3_smoke.py`,
thirteen workflows). Blockers fixed:

| Area | Blocker | Fix |
| --- | --- | --- |
| Privacy | Invitation cancel returned the candidate card of a candidate the visibility rule hides, and worked for a suspended organisation | `InvitationCancelView` runs the talent gate and renders `candidate: null` unless `_visible_candidates` allows it; `SavedCandidateDeleteView` runs the gate too |
| Privacy | A non-discoverable organisation's profile (incl. description) was published through an agency job's `hiring_employer` | Only verified, discoverable organisations can be named; public cards/detail render `hiring_employer: null` once the named organisation is not public; the agency and admins still see it |
| Visibility | Public employer page stayed public while recruitment was SUSPENDED | Same rule as `public()`: recruitment ACTIVE required |
| Concurrency | The featured-window sweep ran unscoped under the employer lock (row locks on other organisations' jobs → Postgres deadlock → 500) | `expire_featured_jobs(employer=…)` is scoped whenever a lock is held; the unscoped sweep stays on listing paths |
| Lifecycle | Suspending a job past its deadline created a row nobody could restore, edit, close or archive | `suspend_job` normalises overdue jobs first; `restore_job` turns a suspended job whose deadline elapsed into EXPIRED (one transition, audited) |
| Lifecycle | `_lock_job` refreshed only the status; deadline, hiring fields, featured window and content were decided on the caller's instance | `_lock_job` re-reads the whole row; submit re-scans contact data on the locked row |
| Conflict → 500 | Double-submitted seeker profile (and child rows) hit the unique constraint uncaught | Account row lock + re-check + constraint mapped to the typed `already_exists`/`duplicate` error |
| Billing | A SUSPENDED subscription outlived the activation of a newer paid one; "reactivating" it cancelled the paid row | Activation supersedes SUSPENDED rows as well (cancelled, audited) |
| Billing | Retiring or deleting the default plan revoked every unsubscribed account's capabilities with one checkbox | `Plan.save()` and the admin form refuse retiring the default; the admin cannot delete it |
| Billing | Reported usage ignored the perpetual bucket `consume()` increments for `period=NONE` limits | `get()` reads the same bucket for every LIMIT row |
| Billing | Payment record written outside the activation transaction | Activation view is atomic |
| Stale state | Non-VERIFIED decisions wrote a stale `verified_at`; ending a membership had no transaction/lock; cancelling an elapsed invitation recorded CANCELLED; job PATCH mapped every domain error to 409; deactivated candidates could be saved/invited | Each fixed in the service or view |
| Web | VIEWER linked to the recruiter-only talent page; plan request form shown while a subscription is ACTIVE (always refused) | Plain text for viewers; live-subscription notice instead of the form |

Backlog (not production-blocking, unchanged): no saved-candidates / sent-invitations
UI (API exists); credits on concurrent keys are permanent capacity (document);
UTC period boundaries; docs still say 402 for entitlement errors (they are
403) and seats "non-owner" (owner counts); `term_days=0` yields a perpetual
term; reactivation grants a fresh term (policy); no renewal while ACTIVE; plan
retirement counts not-yet-normalised elapsed rows; ACCEPTED invitations never
expire; PENDING jobs past deadline hold a slot; withdrawn applications keep
the candidate visible (documented policy); deactivated seeker's live card on
applicant rows; UI-only apply role gate not enforced server-side; a few
ApiActionButton nits (interview toggle, ClientValidationError).

Backend tests 609, web tests 191, no migration, OpenAPI regenerated (two fields now nullable).

## PR #4 review, round nineteen (2026-09-26, review 5322623760 on `5c3ebcb`)

| Finding | Fix |
| --- | --- |
| P2 public `hiring_employer` ignored recruitment status | One rule: `EmployerQuerySet.public()` / `Employer.is_public` (VERIFIED + recruitment ACTIVE + discoverable) backs the public employer page, the choice of organisations an agency may name, and the public/job-seeker rendering of `hiring_employer` (`null` otherwise). Internal representations (`JobEmployerSerializer`, admin, the agency's invitation views via `internal` context) keep it. Tests: five-state matrix where page, list and detail agree, internal views, write refusal. |
| P2 `PlanEntitlement` shape editable in the admin | `PlanEntitlement.validate_shape()` enforces `KNOWN_KEYS` (kind, period) from `clean()` and `save()`; unknown keys keep a free shape. Tests: canonical shapes save and stay editable, each mismatch refused, admin inline shows the error, a reshaped limit cannot bypass `consume()`, every persisted known row matches the registry (seed and dev database audited: no mismatch, no data migration). |
| P2 concurrent child-row renames → 500 | `perform_update` (and `perform_create`) of the job-seeker child views map only the model's own unique constraints to the typed `duplicate` error; other IntegrityErrors propagate. Tests: normal and duplicate PATCH, threaded rename race for skills and languages, unrelated IntegrityError propagates. |
| P2 Save/Unsave shown without `talent.save_candidate` | `TalentDetailPage` loads the billing summary with the profile and shows Save/Unsave only when `talent.save_candidate` is enabled and Invite only when `talent.invite` is enabled (missing rows fail closed); the profile stays readable. Web tests cover both capabilities, saved state, disabled save, missing rows and a refused role. |

Backend tests 631, web tests 196, no migration, OpenAPI unchanged.

## PR #4 review, round twenty (2026-09-26, review 5325002128 on `bf5edf4`)

| Finding | Fix |
| --- | --- |
| P2 default plan deletable in bulk | Verified that Django 5.2's `delete_selected` already refuses a selection containing a default plan through the per-object `has_delete_permission`; hardened anyway: `PlanAdmin.get_deleted_objects` reports default plans as protected (the whole selection is refused), and a `pre_delete` guard on `Plan` raises `ProtectedError` for every ORM path (instance and queryset deletes, which did bypass the admin rule). Tests: unused non-default plan deletes, default plan refused via admin, instance and queryset delete, default-only and mixed bulk selections delete nothing and keep entitlements, bulk delete of non-default plans works. |
| P2 concurrent salary edits → 500 | `edit_job` re-runs the cross-field rules on the locked row with the edit applied (`_require_job_field_invariants`: salary range and city-in-governorate) and the PATCH view maps the typed `JobFieldsInvalid` to the serializer's field-error shape. Tests: single-bound and null-bound edits, invalid single request, stale opposite-bound and stale governorate/city edits refused, threaded opposite-bound PATCHes (one 200, one 400, valid row), unrelated IntegrityError propagates. |
| P2 Talent action shown without `talent.search` | The workspace gates the Talent action on role + recruiting state + `talent.search`, and each job's Applicants link on `jobs.application_review`, from the billing summary it already loads (shared `entitled()` helper, fails closed while loading). Tests: OWNER/RECRUITER with and without the capability, TRIAL-shaped plan, VIEWER, unknown state, applicants link. |
| P2 activation payment status chosen by the client | `ActivationPaymentSerializer` has no `status` input and a client-supplied one is refused (`field_not_allowed`); the view records the payment `VERIFIED` inside the activation transaction. Tests: full and minimal payment objects → VERIFIED, REJECTED/RECORDED/VERIFIED inputs refused with nothing written, reference-only still VERIFIED, retired-plan activation writes no payment, a payment failure rolls the activation back. |

Backend tests 650, web tests 201, no migration, OpenAPI regenerated (activation `payment` request schema without `status`).

## PR #4 round twenty follow-up: default-plan invariant (2026-09-26, on `bb800a8`)

Invariant: for each audience, application-supported operations cannot commit
a state with zero or multiple default plans. `Plan._validate_default_identity()`
(run from `save()` and `clean()`) makes `is_default` and `audience` immutable
once a plan exists and refuses a second default at creation; the admin shows
`is_default` read-only for existing plans and a field error on a duplicate
default at creation; delete and retire guards from earlier rounds stand.
Default switching is intentionally unsupported (documented). `QuerySet.update()`
is not used for these columns by any application path.

Backend tests 657, web tests 201, no migration, OpenAPI unchanged.

## PR #4 review, round twenty-one (2026-09-26, review 5325140837 on `db9b02d`)

| Finding | Fix |
| --- | --- |
| P2 concurrent employer PATCHes commit a city outside the governorate | `update_employer` applies the edit to the locked row and re-runs the shared location invariant (`_require_location_invariant`, also used by `edit_job`) before saving; the PATCH view maps the typed `FieldsInvalid` to the serializer's field error. The identity lock still runs first. Tests: valid update, foreign city, governorate change clearing city, stale city and stale governorate edits refused, threaded races in both orders (no 500, row always valid, verification afterwards exposes no mismatch), identity lock unchanged. |
| P2 Feature shown without `jobs.featured` | `JobEditorPage` loads the billing summary (failure → null → no capability) and shows Feature only with `jobs.featured`; an already-featured job keeps Unfeature regardless. Sibling: Submit needs `jobs.post` and is gated the same way. Web tests: OWNER/RECRUITER with the capability, disabled/TRIAL/BASIC/missing/unloadable summaries, VIEWER, Unfeature with and without the entitlement (and it still works), Submit without `jobs.post`. |

Backend tests 665, web tests 212, no migration, OpenAPI unchanged.

## PR #4 review, round twenty-two (2026-09-26, review 5325616543 on `cefad96`)

| Finding | Fix |
| --- | --- |
| P2 `invite_candidate` trusted a stale candidate instance | The candidate profile row is locked and re-read inside the invitation transaction (order employer → job → candidate → invitation rows); eligibility (discoverable, active account) is decided on that row and the caller's instance is synchronised so the response is rendered from current state. Tests: discoverable invited and duplicates still refused, non-discoverable refused without a card, prior applicant readable but not invitable, stale instance refused, threaded opt-out vs invitation (an invitation exists only if it won). |
| P2 TalentDetail offered Invite to non-invitable candidates | `TalentDetailSerializer.can_invite` (computed: currently discoverable and active) is exposed; the page shows Invite only with `talent.invite` and `can_invite` true (missing → hidden), while the detail stays readable. OpenAPI regenerated for the new field. |
| P2 JobEditor Applicants link ignored the read gate | The link renders only for a VERIFIED, recruitment-ACTIVE organisation with `jobs.application_review` (any member, matching the backend's read semantics; VIEWER included); loading or missing summary hides it. |
| P2 ApplicantsPage composer ignored `recruitment.messaging` | The page loads the billing summary; actions need `jobs.application_review`, the thread is shown to OWNER/RECRUITER with it, and the composer (`MessagesThread canSend`) only with `recruitment.messaging` as well; the seeker side is unchanged. |

Backend tests 671, web tests 228, no migration, OpenAPI regenerated (`can_invite` on the talent detail).

## Known Problems

- No notifications yet for recruitment events (Phase 9): parties must open
  the pages to see messages/interviews.
- Job expiry and subscription expiry are evaluated at read time; a periodic
  job can be added later without schema changes.
- Job-seeker paid plan (SEEKER_PLUS) exists without pricing or checkout — the
  owner has not decided seeker pricing.
- Agency "hiring employer" is entered by id in the job editor (no employer
  search UI yet).
- Saved candidates and sent invitations are returned as arrays capped at 200
  (no pagination yet); paginate when an employer approaches that volume.
- Talent search language filter matches by free text; language names are
  not normalised across Arabic/English spellings.
- `ApplicationMessagesView` applies the `recruitment_messages` scope
  (60/h) to GET as well as POST, so repeatedly opening a thread consumes the
  send allowance. Left as-is in round nine because the scope is named after
  the resource, not the write; decide whether reads should have their own
  scope before Phase 9 notifications make polling common.

## Deferred (deliberately)

Phase 4 Reservations (free), recruitment notifications, analytics
dashboards, saved searches/alerts, media uploads, payment gateway (Phase 8),
scheduled expiry job.

## Exact Next Step

1. Owner merges PR (feat/phase3-medical-jobs → main) after review.
2. Owner sets IQD prices on plans in the Django admin (`billing_plan`) and
   decides seeker pricing.
3. Start Phase 4 — Reservations (free): reservation model + state machine
   on top of Phase 2 services; no entitlement gating.
