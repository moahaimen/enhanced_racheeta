# Medical Jobs and Talent Marketplace

Racheeta's highest-priority commercial service (owner decision). Backend module
`backend/apps/jobs`, web pages under `web/src/pages/jobs`, `web/src/pages/employer`
and `web/src/pages/admin`. Commercial gating comes from `BILLING.md`; contact
protection from `MODERATION.md`.

## Actors

| Actor | How they exist | What they do |
| --- | --- | --- |
| Job seeker | any `Account` that creates a `JobSeekerProfile` | maintains a structured résumé, searches and applies, answers interviews/invitations, messages inside applications |
| Employer organisation | `Employer` created by an account (owner), optionally linked to a Phase 2 facility `ProviderProfile` | verified by Super Admin, then posts jobs, reviews applicants, searches talent within its plan. One public-presence rule for organisations (`Employer.objects.public()` / `is_public`: VERIFIED, recruitment ACTIVE, discoverable) backs the public employer page, which organisations an agency may name as `hiring_employer`, and the public and job-seeker rendering of that field (`null` once the organisation is not public; the agency and administrators still see it). Suspending a job normalises an elapsed deadline first (it becomes EXPIRED, never SUSPENDED), and restoring a suspended job whose deadline elapsed turns it into EXPIRED so the employer can archive it. Under any lock the featured-window sweep is scoped to the locked organisation. Verifying an organisation re-checks each of its PUBLISHED jobs against the agency invariant under the current identity (lock order employer → job) and suspends, with a transition and audit record, any job that no longer holds, so re-verification never makes an invalid job public again. Owner edits decide on the locked employer row re-read in full under `select_for_update` (never on the instance the request loaded), so a submitted identity value is compared with its current committed value and the city-in-governorate rule is re-run on the resulting row (as for job edits); every employer-side recruitment mutation (application transitions, interview requests, employer messages) locks the employer row first, re-reads it, and re-runs recruiting eligibility and the gating entitlements before locking the application (order: employer → application → interview), so a suspension or plan change that commits after the view's pre-check still refuses the mutation with a typed error. Once verification is requested (PENDING) or granted (VERIFIED), the identity fields the administrator reviewed — `name`, `organization_type`, `governorate`, `provider_profile`, `is_recruitment_agency` — are locked for owners (`identity_locked`, 400); description, city and discoverability stay editable. Changing identity needs an administrator. |
| Invitation eligibility | `TalentDetail.can_invite` (computed) | A candidate visible through a past application stays readable, but a NEW invitation needs current discoverability; `invite_candidate` decides on the locked candidate row (order employer → job → candidate → invitation). |
| Employer members | `EmployerMembership(role OWNER|RECRUITER|VIEWER, status ACTIVE|ENDED)` | one live membership per account (DB constraint; every assignment path — creating an organisation as OWNER, adding a member — locks the target account row before the membership check, `add_member` after the employer row, so concurrent assignments of one account get one success and one typed `already_member`, and a refused creation rolls its Employer row back); seats limited by `recruiter.seats` |
| Super Admin | `Account.is_staff` | verifies organisations, approves/rejects/suspends jobs, activates subscriptions, grants credits |

There is no CV upload, no attachments, no new storage (owner decisions 5–8).
The structured profile *is* the résumé.

## Models

- `Employer`, `EmployerMembership`
- `JobSeekerProfile` + children `WorkExperience`, `Education`, `Skill` (`name_normalized` for matching), `LanguageSkill`, `Credential`
- `JobPost`, `JobPostTransition`
- `JobApplication` (immutable `snapshot` of the profile at apply time, never contact data), `JobApplicationTransition`
- `InterviewRequest`, `RecruitmentMessage` (text only, immutable, scoped to an application)
- `SavedCandidate`, `JobInvitation`, `TalentSearchQuery`

## State machines

Job:

```
DRAFT ─submit─▶ PENDING_ADMIN_REVIEW ─approve─▶ PUBLISHED ─close─▶ CLOSED
   ▲                    │ reject                  │ suspend ▶ SUSPENDED ─restore─▶ PUBLISHED
   └──── REJECTED ◀─────┘                        │ deadline passed (read time) ▶ EXPIRED
DRAFT / CLOSED / EXPIRED / REJECTED ─archive─▶ ARCHIVED
```

`submit`, an administrator `approve` (PENDING_ADMIN_REVIEW → PUBLISHED) and an
administrator `restore` (SUSPENDED → PUBLISHED) share one gate,
`_require_publication_eligibility`, evaluated on the locked employer and job
rows (employer first, then job): the organisation must be VERIFIED with ACTIVE
recruitment (`organization_not_verified`), the agency invariant must hold for
the current identity (`not_an_agency`), the application deadline must not have
elapsed — the deadline day itself is still open, exactly as `is_open`
(`deadline_passed`, 409) — and the plan must carry `jobs.post` with a free
`jobs.active_limit` slot (`entitlement_required` / `usage_limit_reached`).
Approval therefore never publishes what a fresh submission would refuse, no
matter how long the job waited in review, and a refused transition writes no
history. Submission also re-scans text for contact data.

Featured slots have one definition, `_live_featured_count`: PUBLISHED jobs
whose featured window is still open (suspended jobs and elapsed windows occupy
nothing). Featuring requires a genuinely open job — the same deadline boundary
as public search and applying (`deadline_passed` for an elapsed one), so an
expired job can never take a slot. An administrator restore re-validates a
retained featured flag against the *current* plan and capacity: the job is
always restored, and its featured state survives only if `jobs.featured` is
still enabled, a slot is free and the window has not elapsed; otherwise it
comes back as a normal published job (the audit event records
`featured_kept`). Restore therefore never exceeds `jobs.featured_limit`.

Active-slot capacity is authoritative and independent of read endpoints: the
gate first normalises this organisation's overdue PUBLISHED jobs to EXPIRED
(each job row locked, one transition), and the count itself ignores PUBLISHED
jobs whose deadline elapsed.
Featuring requires `jobs.featured` and a `jobs.featured_limit` slot; a job is
featured only while `featured_until > now` (see `BILLING.md`, Featured window).

Application: `SUBMITTED → REVIEWING → SHORTLISTED → INTERVIEW → ACCEPTED`,
`REJECTED` from any open state (employer), `WITHDRAWN` from any open state
including `INTERVIEW` (seeker). Every change is a `JobApplicationTransition`.
When an application reaches a terminal state (ACCEPTED, REJECTED, WITHDRAWN)
every still-PROPOSED interview is cancelled in the same transaction, and the
interview-response endpoint independently refuses answers on a terminal
application (`application_closed`, 409).

Invitation: `PENDING → ACCEPTED | DECLINED | CANCELLED`, `EXPIRED` at read
time (`expire_overdue_invitations`, run by both invitation lists and before
every new invitation, so an elapsed PENDING row never blocks re-inviting;
the expired row stays in history and the new one consumes a new unit). A
duplicate is refused while an invitation for the same job and candidate is
still live outreach — PENDING **or** ACCEPTED (`ACTIVE_INVITATION_STATUSES`);
declined, expired and cancelled ones allow a fresh invitation. The check runs
under the employer lock before anything is created, so a refused duplicate
consumes no quota.
Applying to the job answers a still-live PENDING invitation as ACCEPTED under
a row lock; an invitation whose window already closed becomes EXPIRED instead,
never "accepted outreach". Accepting explicitly is validated the same way under
the employer, job and invitation locks: the job must still be open and the
organisation able to recruit, otherwise `invitation_unavailable` (409) and the
invitation stays PENDING (declining remains possible). Accepting an invitation does **not** create an application; the seeker
applies from the job page. Each invitation consumes one `talent.invite_limit`
unit keyed by its own id; each application attempt consumes one
`applications.limit` unit keyed by the application id.

Interview: `PROPOSED → ACCEPTED | DECLINED | CANCELLED`; proposing one moves
the application to `INTERVIEW`.

Applying and inviting validate against locked state: the employer row is
locked, then the job row, the job's open status and the employer's recruiting
status are re-read, and only then is the application/invitation created and
the usage unit consumed — a close, suspension or employer suspension that
commits first makes the attempt fail (`job_not_open`) with nothing created or
charged. Job submission re-checks `can_recruit` on the locked employer row
before the slot check; the view's unlocked check is only an early exit.

A job may name a `hiring_employer` or `hiring_organization_name` only while
its organisation **is** a recruitment agency. The rule is checked on the
resulting job (not only the fields in the request) at edit time and again at
submit time on the locked employer and job rows (`not_an_agency`, 400), so a
draft created while the organisation was an agency must clear those fields
before it can be changed or published. The editor hides those two inputs for a
non-agency, so it now sends the clearing values (`hiring_employer: null`,
`hiring_organization_name: ""`) on every save of an existing non-agency job and
warns the owner first — otherwise such a draft could not be repaired from the
web at all. A non-agency **create** still sends no agency-only value.

Employer job edits (`PATCH /jobs/employer/jobs/{id}`) go through
`services.edit_job`: the employer row is locked, then the job row, editability (DRAFT/REJECTED) is
checked on the refreshed status, and only the edited columns are written, so a
stale edit can neither revert a submitted job nor change reviewed content
(`job_locked`, 409). Owner organisation edits go through
`services.update_employer` under the employer row lock, and administrator
verification/recruitment decisions lock and refresh the same row first, so a
decision always applies to the identity that was visible while it held the
lock.

Every state change on a job, application, interview or invitation takes a
row lock (`SELECT … FOR UPDATE`) and re-reads the status before validating, so
two actors acting at once (approve vs reject, close vs suspend, accept vs
reject) cannot both win: the second gets the typed `invalid_transition` error
and the history always matches the final status. Lock order is always the
employer row (when a commercial slot is involved), then the job row; and the
application row before its interview row.

## Talent search and the "one billable search" rule

Saved candidates (`GET /talent/saved`) and sent invitations
(`GET /talent/invitations`) use the standard paginated envelope (`count`,
`next`, `previous`, `results`, newest first by `created_at` then id). The saved relation and the invitation row stay
stored when a candidate hides their profile, but a row is listed and its card
returned only while the one shared visibility rule (`_visible_candidates`,
also used by talent detail) allows it, so `count` only counts visible rows: an active account that is currently discoverable, or that
applied to one of this employer's jobs. Talent detail exposes
`saved_candidate_id` for the requesting employer's own record (null when not
saved, never another organisation's id) so the web can unsave in place.

Paid recruitment reads and writes share one gate: talent search and candidate
detail need `talent.search`, listing **and saving** candidates need
`talent.save_candidate`, the sent-invitations list and inviting need
`talent.invite`, and all of them need a VERIFIED organisation with ACTIVE
recruitment (`organization_not_verified`, 403), checked in the view and again
in the service on the refreshed employer row. Losing the plan or being
suspended closes the lists and the actions alike.

Talent search is available only with `talent.search` and consumes
`talent.search_limit`. The filter set is validated first: a request with an
invalid `profession`, `language_level`, `availability`, degree, UUID or number
is rejected with 400 and consumes nothing. `min_experience` and
`max_experience` are integers (years, like the stored value): `05` and `5.0`
parse as 5, while a fractional bound such as `5.9` is rejected rather than
silently truncated. `language` and `language_level`
apply to the same language row (EXISTS subquery, no duplicate rows), so
"English BASIC + Arabic ADVANCED" never matches "English ADVANCED". To be fair to employers, **one billable search is one
(employer, normalised filter signature, calendar day)**: the same filters on the
same day, including pagination and re-ordering, count once (`TalentSearchQuery`
unique row, consumption `reference = signature:date`). Changing any filter is a
new search. Only profiles with `discoverable_by_employers=true` appear, and
never with e-mail, phone or account identity.

## Privacy rules (enforced by serializers and tests)

- Public/employer-facing serializers never expose `Account` e-mail, phone,
  Firebase ids, staff flags or permissions.
- Application snapshots store professional facts only.
- Employer public page shows name, type, description, location and verification
  badge; the owner's account is never exposed.
- IDs are never trusted from the client: every employer endpoint is scoped by
  the caller's membership; seeker endpoints by `request.user`.
- Applicant data is a paid capability: every employer-side endpoint that lists,
  reads or changes applications (list, detail, transition, interview request,
  employer-side messages) runs the single `_require_application_review` gate —
  the organisation must still be allowed to recruit (VERIFIED and ACTIVE,
  otherwise `organization_not_verified`, 403) **and** the plan must carry
  `jobs.application_review` — in addition to ownership scoping, so a direct
  object URL cannot bypass the plan or a suspension. Seekers keep reading and
  withdrawing their own applications regardless.

## Endpoints (all under `/api/v1`)

Public visibility (`JobPost.objects.public()`, used by search, detail and
apply) requires PUBLISHED, a verified active organisation **and** a deadline
that has not elapsed (the deadline day is still open), so a job past its
deadline is gone from direct detail exactly when it is gone from search, even
before a listing normalises it to EXPIRED. Employer and administrator reads
still see it.

Public: `GET /jobs` (filters `q, employer, profession, specialty, governorate, city, degree, min_experience, max_experience, employment_type, work_mode, shift_type, salary_available, ordering`), `GET /jobs/{id}`, `GET /employers/{id}`.

Seeker (bearer): `GET|POST|PATCH /jobs/me/profile`, child collections
`/jobs/me/profile/{experiences|education|skills|languages|credentials}[/{id}]`,
`POST /jobs/{id}/apply`, `GET /jobs/me/applications[/{id}]`,
`POST /jobs/me/applications/{id}/withdraw`, `POST /jobs/me/interviews/{id}/respond`,
`GET /jobs/me/invitations`, `POST /jobs/me/invitations/{id}/respond`.

Both parties: `GET|POST /recruitment/applications/{id}/messages`. Sending
locks and refreshes the application first, so a rejection or withdrawal that
commits first closes the thread (`application_closed`, 409) even under
concurrency. The thread is bounded to the newest 200 messages, returned in chronological order (so the
latest message is always visible); there is no unbounded thread endpoint.

Employer (bearer + membership): `GET|POST|PATCH /jobs/employer`,
`POST /jobs/employer/verification/request`, `GET|POST /jobs/employer/members`,
`POST /jobs/employer/members/{id}/end`, `GET /jobs/employer/billing`,
`POST /jobs/employer/billing/request`, `GET|POST /jobs/employer/jobs`,
`GET|PATCH /jobs/employer/jobs/{id}`, `POST .../{id}/{submit|close|archive|feature}`,
`GET .../{id}/applications`, `GET /jobs/employer/applications/{id}`,
`POST .../{id}/transition`, `POST .../{id}/interviews`,
`GET /talent`, `GET /talent/{id}`, `GET|POST /talent/saved`, `DELETE /talent/saved/{id}`,
`GET|POST /talent/invitations`, `POST /talent/invitations/{id}/cancel`.

Admin (`is_staff`): `GET /admin/recruitment/employers`,
`POST .../{id}/verification`, `POST .../{id}/recruitment/{ACTIVE|SUSPENDED}`,
`GET /admin/recruitment/jobs[/{id}]`, `POST .../{id}/{approve|reject|suspend|restore}`,
plus billing and audit endpoints (`BILLING.md`).

Throttle scopes: `jobs_create 30/h`, `jobs_apply 20/h`, `talent_search 60/min`,
`talent_invite 30/h`, `recruitment_messages 60/h`.

A scope named after a write is spent by that write only. `jobs_create` and
`talent_invite` sit on views that also serve GET (`GET|POST /jobs/employer/jobs`,
`GET|POST /talent/invitations`), so they select the throttle per request
(`_ThrottledOnWrite.get_throttles`): POST consumes the quota, GET does not.
Listing and paginating the workspace therefore never exhausts the creation
allowance, and the POST limits are unchanged. Safe methods fall through to
`DEFAULT_THROTTLE_CLASSES`.

## Typed error codes

`job_not_open`, `already_applied`, `already_invited`, `already_saved`,
`organization_not_verified`, `invalid_transition`, `already_member`,
`not_an_agency`, `contact_information_not_allowed` (validation), and the
billing codes. The web
localises all of them (`apiErrors.*`).

## Web pages

| Route | Guard | Page |
| --- | --- | --- |
| `/jobs`, `/jobs/:id`, `/employers/:id` | public | search with URL-backed filters, job detail with apply block, employer page with its published jobs paginated (`?jobs_page=`) |
| `/jobs/profile` | auth | structured résumé (onboarding + sections) |
| `/jobs/my-applications` | auth | applications paginated from the URL (`?page=`), interviews, invitations paginated independently (`?invites_page=`), message threads |
| `/employer` | auth | organisation onboarding (including the optional link to the account's own facility provider profile, locked once verification starts), verification, paginated jobs (`?jobs_page=`), server-side `active_jobs` statistic, plan/usage meters, plan request — replaced by the pending notice while `pending_subscription` is set — team |
| `/employer/jobs/new`, `/employer/jobs/:id` | auth | job editor, lifecycle actions, moderation flags, history |
| `/employer/jobs/:id/applications` | auth | applicants, transitions, interview requests, messages |
| `/employer/talent`, `/employer/talent/:id` | auth | talent search (quota note), candidate detail, save / remove from saved, invite (job picker loads further pages of published jobs on demand) |
| `/admin-console` | staff | organisations, job review with contact findings, subscriptions, credits |

Every action uses `ApiActionButton` (disable, spinner, stable size, restore);
every page load uses `AsyncPage`/`useAsyncData` with skeleton/error/retry.

## Deferred (not in Phase 3)

Notifications on recruitment events (Phase 9), analytics dashboards, saved
searches/alerts, recruiter invitations by name, job-seeker paid plans pricing,
scheduled expiry jobs (read-time expiry is sufficient today), reservations
(Phase 4, free).
