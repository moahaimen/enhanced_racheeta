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

- Backend: **269 passed** (was 175): billing entitlements/admin API,
  moderation detector, employers/memberships, job lifecycle and gating,
  seeker profile and applications, public search and talent, privacy
  assertions, race regression.
- Web: **129 passed** (was 87).
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

## Known Problems

- No notifications yet for recruitment events (Phase 9): parties must open
  the pages to see messages/interviews.
- Job expiry and subscription expiry are evaluated at read time; a periodic
  job can be added later without schema changes.
- Job-seeker paid plan (SEEKER_PLUS) exists without pricing or checkout — the
  owner has not decided seeker pricing.
- Agency "hiring employer" is entered by id in the job editor (no employer
  search UI yet).
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
