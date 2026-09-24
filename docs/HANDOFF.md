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

- Backend: **383 passed** (was 175): billing entitlements/admin API,
  moderation detector, employers/memberships, job lifecycle and gating,
  seeker profile and applications, public search and talent, privacy
  assertions, race regression.
- Web: **155 passed** (was 87).
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
