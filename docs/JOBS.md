# Medical Jobs and Talent Marketplace

Racheeta's highest-priority commercial service (owner decision). Backend module
`backend/apps/jobs`, web pages under `web/src/pages/jobs`, `web/src/pages/employer`
and `web/src/pages/admin`. Commercial gating comes from `BILLING.md`; contact
protection from `MODERATION.md`.

## Actors

| Actor | How they exist | What they do |
| --- | --- | --- |
| Job seeker | any `Account` that creates a `JobSeekerProfile` | maintains a structured résumé, searches and applies, answers interviews/invitations, messages inside applications |
| Employer organisation | `Employer` created by an account (owner), optionally linked to a Phase 2 facility `ProviderProfile` | verified by Super Admin, then posts jobs, reviews applicants, searches talent within its plan |
| Employer members | `EmployerMembership(role OWNER|RECRUITER|VIEWER, status ACTIVE|ENDED)` | one live membership per account; seats limited by `recruiter.seats` |
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

`submit` requires a VERIFIED organisation with ACTIVE recruitment, the
`jobs.post` capability and a free `jobs.active_limit` slot; it re-scans text
for contact data. The slot check and the transition run under a row lock on
the employer, so concurrent submissions cannot exceed the limit. `restore`
(SUSPENDED → PUBLISHED) re-runs exactly the same gate and fails with
`usage_limit_reached` when the employer used the freed slot meanwhile.
Featuring requires `jobs.featured` and a `jobs.featured_limit` slot; a job is
featured only while `featured_until > now` (see `BILLING.md`, Featured window).

Application: `SUBMITTED → REVIEWING → SHORTLISTED → INTERVIEW → ACCEPTED`,
`REJECTED` from any open state (employer), `WITHDRAWN` from any open state
(seeker). Every change is a `JobApplicationTransition`.

Invitation: `PENDING → ACCEPTED | DECLINED | CANCELLED`, `EXPIRED` at read
time (`expire_overdue_invitations`, run by both invitation lists and before
every new invitation, so an elapsed PENDING row never blocks re-inviting;
the expired row stays in history and the new one consumes a new unit). Accepting an invitation does **not** create an application; the seeker
applies from the job page. Each invitation consumes one `talent.invite_limit`
unit keyed by its own id; each application attempt consumes one
`applications.limit` unit keyed by the application id.

Interview: `PROPOSED → ACCEPTED | DECLINED | CANCELLED`; proposing one moves
the application to `INTERVIEW`.

Every state change on an application, interview or invitation takes a row
lock (`SELECT … FOR UPDATE`) and re-reads the status before validating, so two
recruiters acting at once cannot both win: the second gets the typed
`invalid_transition` error and the history always matches the final status.

## Talent search and the "one billable search" rule

Talent search is available only with `talent.search` and consumes
`talent.search_limit`. The filter set is validated first: a request with an
invalid `profession`, `language_level`, `availability`, degree, UUID or number
is rejected with 400 and consumes nothing. `language` and `language_level`
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
  employer-side messages) runs the single `jobs.application_review` gate
  (`_require_application_review`) in addition to ownership scoping, so a
  direct object URL cannot bypass the plan.

## Endpoints (all under `/api/v1`)

Public: `GET /jobs` (filters `q, employer, profession, specialty, governorate, city, degree, min_experience, max_experience, employment_type, work_mode, shift_type, salary_available, ordering`), `GET /jobs/{id}`, `GET /employers/{id}`.

Seeker (bearer): `GET|POST|PATCH /jobs/me/profile`, child collections
`/jobs/me/profile/{experiences|education|skills|languages|credentials}[/{id}]`,
`POST /jobs/{id}/apply`, `GET /jobs/me/applications[/{id}]`,
`POST /jobs/me/applications/{id}/withdraw`, `POST /jobs/me/interviews/{id}/respond`,
`GET /jobs/me/invitations`, `POST /jobs/me/invitations/{id}/respond`.

Both parties: `GET|POST /recruitment/applications/{id}/messages`. The thread is
bounded to the newest 200 messages, returned in chronological order (so the
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

## Typed error codes

`job_not_open`, `already_applied`, `already_invited`, `already_saved`,
`organization_not_verified`, `invalid_transition`, `already_member`,
`contact_information_not_allowed` (validation), and the billing codes. The web
localises all of them (`apiErrors.*`).

## Web pages

| Route | Guard | Page |
| --- | --- | --- |
| `/jobs`, `/jobs/:id`, `/employers/:id` | public | search with URL-backed filters, job detail with apply block, employer page |
| `/jobs/profile` | auth | structured résumé (onboarding + sections) |
| `/jobs/my-applications` | auth | applications paginated from the URL (`?page=`), interviews, invitations paginated independently (`?invites_page=`), message threads |
| `/employer` | auth | organisation onboarding, verification, paginated jobs (`?jobs_page=`), server-side `active_jobs` statistic, plan/usage meters, plan request, team |
| `/employer/jobs/new`, `/employer/jobs/:id` | auth | job editor, lifecycle actions, moderation flags, history |
| `/employer/jobs/:id/applications` | auth | applicants, transitions, interview requests, messages |
| `/employer/talent`, `/employer/talent/:id` | auth | talent search (quota note), candidate detail, save, invite (job picker loads further pages of published jobs on demand) |
| `/admin-console` | staff | organisations, job review with contact findings, subscriptions, credits |

Every action uses `ApiActionButton` (disable, spinner, stable size, restore);
every page load uses `AsyncPage`/`useAsyncData` with skeleton/error/retry.

## Deferred (not in Phase 3)

Notifications on recruitment events (Phase 9), analytics dashboards, saved
searches/alerts, recruiter invitations by name, job-seeker paid plans pricing,
scheduled expiry jobs (read-time expiry is sufficient today), reservations
(Phase 4, free).
