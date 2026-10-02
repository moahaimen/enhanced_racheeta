# Dashboards and Analytics (Phase 10)

> Every number on a dashboard is computed by PostgreSQL from authoritative rows, scoped to the
> authenticated caller **before** it is aggregated. Nothing is fabricated: where the data to
> support a metric does not exist, the metric is deferred (see *Deferred metrics*).

## 1. Inventory (state of `main` at `3ff9cdd`)

### What already existed (reused, not rebuilt)

| Capability | Where | How Phase 10 uses it |
|---|---|---|
| Medical-company marketplace summary (`products_total/active/inactive/exposable`, `can_publish`) | `GET /api/v1/marketplace/company/dashboard` → `marketplace.services.dashboard_summary` | Called by the new company summary service (same function, no copy); the web hub renders the same `StatCard` layout |
| Advertising campaign summary (`campaigns_*` by status, live, ended) | `GET /api/v1/advertising/company/dashboard` → `advertising.services.dashboard_summary` | Same: reused by the company summary service |
| Real-estate owner summary (`listings_*`: draft, published, expired, sale, rent, visible) | `GET /api/v1/real-estate/owner/dashboard` → `real_estate.services.dashboard_summary` | The hub's owner section calls this existing endpoint unchanged (no duplicate endpoint) |
| Unread counts | `notifications.services.unread_count`, `chat.services.unread_count` | Called by the patient / doctor / facility summaries |
| Rating aggregate (`Avg`/`Count` over `reviews__rating`) | `providers/views.py` annotations on `Review` | Same source (`reviews_review`), computed for the caller's own profile |
| Authorization | `apps.accounts.permissions.has_role`, `IsAdminAccount` (staff flag), `marketplace.permissions.HasMedicalCompany`, `jobs.permissions.IsEmployerMember`, `jobs.services.membership_for` | Composed; no new auth mechanism |
| Entitlements | `jobs.services.employer_entitlements(...).can(Keys.JOBS_APPLICATION_REVIEW)` and `Keys.RECRUITER_SEATS` | Recruiter summary mirrors the existing applicant-read gate |
| Web building blocks | `StatCard`, `DashboardBlock`/`SectionCard`, `Tabs`, `AsyncPage`/`useAsyncData`, `LoadingState`/`ErrorState`/`EmptyState`, `RequireAuth`, i18n (ar RTL / en) | The only components used; no second design system |
| Existing workspaces that already show a dashboard block | `/company`, `/company/advertising`, `/real-estate/owner` | Unchanged; the hub links to them |

### What was missing

Patient, doctor, facility, recruiter and administrator dashboards; a role-aware entry point; a
payment-status view for the company; any administrator operational summary.

### Statistics backed by real records (implemented)

| Dashboard | Metric | Authoritative source |
|---|---|---|
| Patient | Reservation counts by status; upcoming (PENDING/CONFIRMED, `starts_at >= now`); recent | `reservations_reservation` (`patient = caller`) |
| Patient / doctor / facility | Unread notifications and messages | `notifications_notification`, `chat_*` (existing services) |
| Doctor / facility | Received reservations by status, completed, upcoming | `reservations_reservation` (`provider = caller's profile`) |
| Doctor / facility | Average rating, review count, 1–5 distribution | `reviews_review` (`provider = caller's profile`) |
| Doctor / facility | Offers running now / scheduled | `offers_offer` (`provider = caller's profile`, public window rule) |
| Facility | Practitioner memberships: active, incoming/outgoing pending | `providers_membership` (`facility = caller's profile`) |
| Company | Products (existing summary), campaigns (existing summary), campaign payments by status | `marketplace_product`, `advertising_campaign`, `advertising_campaignpayment` |
| Real-estate owner | Listings by status, expired, sale/rent | existing summary (unchanged) |
| Recruiter | Organisation state, jobs by status, applications by status, awaiting review, interviews, applications in the last 7 days, seats | `jobs_*`, billing entitlements |
| Administrator | Accounts by role and active state; verification queues (providers, companies, employers); jobs by status; reservations by status; products; listings; campaigns and payments by status; subscriptions by status; audit events in the last 24 h / 7 days | counts only over the same tables |

### Deferred metrics (insufficient authoritative data)

| Proposed metric | Why it is deferred |
|---|---|
| Reservation revenue / patient spend | Reservations are free and payments are off-platform; `price_snapshot` is a quoted price, not money received |
| Profile views, search impressions, offer views | No analytics event store exists |
| Advertising impressions, clicks, conversions, ROI | No tracking exists (already stated by the advertising dashboard) |
| Real-estate views / enquiries | No tracking exists |
| Facility totals of its practitioners' reservations | A reservation belongs to the profile that was booked; there is no authoritative practitioner↔facility reservation relation, so combining them would invent one |
| Recruiter time-to-hire, funnel conversion over time | Needs transition-history analytics and a time-series design; out of scope for the first dashboard slice |
| Unread recruitment messages | `RecruitmentMessage` has no per-reader read state (and is deliberately untouched) |
| Time-series / trend charts | Counts only in this phase; no unbounded history is sent to the browser |

## 2. Architecture

New backend app `apps.dashboards` with **no models and no migrations**.

```
apps/dashboards/
  access.py           ONE source of "who may open which dashboard" (permissions + the index)
  permissions.py      IsPatientAccount, IsPractitionerProvider, IsFacilityProvider, HasCompanyProfile,
                      IsRecruitingOrganizationMember (current database state, never client ids)
  services/           one small module per domain; each returns a plain dict of aggregates
    common.py         status_counts (one conditional-aggregate query, zero-filled), list limits
    reservations.py   patient and provider shapes: counts, upcoming, recent
    providers.py      review aggregate, offers, facility memberships
    company.py        composes the existing marketplace and advertising summaries + payments
    recruiter.py      organisation, jobs, applications, interviews, seats
    admin.py          counts-only operational summary
  serializers.py      explicit output contracts (OpenAPI); undeclared fields cannot leave the server
  views.py            one small view per dashboard
  urls.py
```

All endpoints are `GET`, authenticated, `/api/v1/dashboards/…`, read-only, and accept **no client
parameters** (no ids, no filters). Ownership always comes from `request.user` and current
database state (profile, membership, staff flag).

## 3. Authorization and isolation

| Endpoint | Allowed | Isolation |
|---|---|---|
| `GET /dashboards/` | any authenticated account | lists only the dashboards that account can open now |
| `GET /dashboards/patient` | role `PATIENT` | rows where `patient = request.user` |
| `GET /dashboards/doctor` | `PROVIDER` with a PRACTITIONER profile | rows of that profile only |
| `GET /dashboards/facility` | `PROVIDER` with a FACILITY profile | rows of that profile only; memberships where it is the facility |
| `GET /dashboards/company` | `MEDICAL_COMPANY` with a company profile | `request.user.medical_company` |
| `GET /dashboards/recruiter` | active `EmployerMembership` (any member role) | the membership's organisation, read fresh from the database |
| `GET /dashboards/admin` | `is_staff` | none (aggregates); no personal data in the payload |
| `GET /real-estate/owner/dashboard` (existing) | `REAL_ESTATE_SELLER` with a seller profile | unchanged |

Authorization is applied before any aggregation; the aggregation queries are filtered by the
caller's own foreign key, never by a request value. Aggregate payloads exclude private data:
no `patient_note`, no contact data, no tokens. Provider upcoming lists show only what the
existing provider reservation API already shows the provider (patient name), never the note.

## 4. Performance

* Each dashboard is a fixed, small number of queries (single `GROUP BY` / conditional
  aggregates), independent of data volume; query-count regression tests pin the numbers.
* Lists are bounded (`UPCOMING_LIMIT = RECENT_LIMIT = 5`); no response grows with the data.
* Existing indexes serve the filters (`reservations_patient_idx`, `reservations_provider_idx`,
  `reviews_provider_idx`, `offers_public_idx`, `providers_membership_fac_idx`,
  `jobs_post_employer_idx`, `jobs_application_job_idx`, `jobs_membership_employer_idx`).
  **No migration or new index is required.** The administrator summary scans whole domain tables
  with grouped counts; these are small, low-cardinality scans today and are noted for Phase 12
  hardening if the tables grow.
* No Redis, Celery or Elasticsearch; no polling in the web app.

### Measured query budget

Queries per request, measured under `force_authenticate` (JWT adds one user lookup in production),
pinned as upper bounds by the tests, and **constant** as the data grows (the tests add 15–30 rows
and assert the count does not move):

| Endpoint | Queries | Composition |
|---|---|---|
| `GET /dashboards/` | 1 | membership lookup (role/profile checks that need no query are skipped) |
| patient | 5 | status+upcoming counts, upcoming list, recent list, unread notifications, unread messages |
| doctor | 7 | profile, counts, upcoming list, reviews, offers, 2 unread |
| facility | 8 | doctor + memberships |
| company | 7 | profile + existing marketplace summary (3) + existing advertising summary (1) + payments |
| recruiter | 12 | membership, entitlement resolution (plan, subscription, entitlements), jobs, applications, interviews, members |
| admin | 12 | one conditional aggregate per domain block |

## 5. Web

`/dashboard` (`web/src/pages/dashboard/`) is one role-aware hub under `RequireAuth`:

* it asks `GET /dashboards/` which dashboards the account can open (never inferred from the role in
  the browser) and shows a tab list only when there is more than one;
* only the selected dashboard loads (its first request happens when it is opened); nothing polls;
* every load uses `AsyncPage` (loading state, error with retry), lists have explicit empty states,
  and there are no mutations (so no action buttons that could double-submit);
* the hub is keyed by the signed-in account id, so a response that arrives after logout or an
  account switch is discarded with its component and never rendered for the next account;
* labels reuse the existing i18n groups (`reservationStatus`, `jobStatus`, `verification`, …); Arabic
  RTL and English; a Dashboard link appears in the header (desktop and mobile) for signed-in accounts.

## 6. Tests

* Backend (`apps/dashboards/tests`, 79): authentication, per-dashboard authorization and
  role/kind mismatches, current-state re-checks (ended membership, deleted profile), cross-account
  and cross-organisation isolation (including smuggled ids in query/headers), correct aggregation,
  empty datasets, status filtering, date boundaries (upcoming `starts_at >= now`, offer window end
  exclusive, 7-day applications, 24 h/7 d audit), no private or fabricated fields, constant and
  bounded query counts, OpenAPI contract (read-only, parameterless, authenticated, no forbidden
  property) and a guard that the new schema cannot shadow the existing `CompanyDashboard`.
* Web (`DashboardPage.test.tsx`, 21): loading, success for every dashboard, empty states, API
  failure with retry, index failure, no-dashboard onboarding, withheld recruiter data, tabs and lazy
  loading, logout + different login without leaking the previous account's late response, no
  polling, header link (desktop/mobile/anonymous), Arabic and English.
