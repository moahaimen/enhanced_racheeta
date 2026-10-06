# RACHEETA 2.0 — MASTER BUILD PLAN

## 1. Project Goal

Build **Racheeta 2.0 from scratch** as a secure, professional, low-cost, maintainable platform fully owned by **Moahaimen Talib**.

The legacy Racheeta / `virach` codebase may be inspected only as a **read-only requirements/reference source**.

Do **not** rebuild on top of the legacy architecture.

Do **not** reproduce previous architectural mistakes.

The new system must be:

- Fully owned by the project owner.
- Secure.
- Well documented.
- Easy to maintain.
- Easy to hand over between AI coding assistants or developers.
- Portable between hosting providers.
- Optimized for low Railway cost.
- Built so mobile, web, dashboards, and backend use one clean API.

---

# 2. Core Ownership Principle

Racheeta must never depend on hidden knowledge held by a developer.

Everything required to operate the platform must exist in:

- Source code.
- Database migrations.
- Configuration.
- Documentation.
- Tests.
- Infrastructure configuration.
- Git history.

The owner must be able to replace any developer or AI coding assistant without losing control of the project.

Avoid vendor lock-in wherever practical.

---

# 3. Project Name

Create a completely new project:

```text
racheeta-platform
```

Suggested monorepo structure:

```text
racheeta-platform/
├── backend/
├── web/
├── mobile/
├── docs/
├── infrastructure/
├── scripts/
├── .github/
├── .env.example
├── docker-compose.yml
├── README.md
└── LICENSE
```

Do not modify the legacy `virach` repository.

---

# 4. Target Architecture

Use a **Modular Monolith**, not microservices.

## Backend

Use:

- Python.
- Django.
- Django REST Framework.
- PostgreSQL.
- ASGI-ready architecture.
- OpenAPI documentation.
- pytest.
- Environment-based configuration.

## Web Application

Use:

- React.
- TypeScript.
- Vite.
- Responsive UI.
- Arabic RTL support from the beginning.
- English-ready localization.
- API-driven architecture.

## Mobile

Use Flutter later.

The new mobile application must consume exactly the same:

```text
/api/v1/
```

API used by the web application.

## Initial Deployment Shape

```text
                   Racheeta
                      |
             Django Application
              /             \
         REST API        React Build
              |
          PostgreSQL
```

Initial Railway deployment should use:

- One Railway application service.
- One Railway PostgreSQL database.
- No Redis unless actually required.
- No permanent Celery worker unless actually required.
- No Elasticsearch.
- No Kafka.
- No unnecessary microservices.
- No unnecessary paid infrastructure.

Media should eventually use S3-compatible object storage such as:

- Cloudflare R2.
- Backblaze B2.

Do not permanently store user uploads on Railway local filesystem.

Firebase Cloud Messaging may be used for push notifications.

Design modules so Redis, background workers, WebSockets, or additional services can be added later without redesigning the whole system.

---

# 5. Non-Negotiable Security Rules

Never put secrets in source code.

Never commit:

- Passwords.
- JWT tokens.
- Firebase private keys.
- Database credentials.
- API keys.
- Admin credentials.
- Payment credentials.

Never log:

- Complete access tokens.
- Complete refresh tokens.
- Passwords.

Never expose password fields in API responses.

Never allow client applications to send privilege fields such as:

```text
is_staff
is_superuser
permissions
groups
```

Never place administrator credentials inside mobile or web applications.

Never trust:

- Client-side payment success.
- Client-side advertisement activation.
- Client-side pricing.
- Client-side privilege decisions.

All security-sensitive business rules must be enforced by the backend.

Use separate read/write serializers or DTOs where appropriate.

---

# 6. Authentication Design

Racheeta must have one canonical account/session architecture.

Create one:

```text
Account
```

model.

Do not create separate authentication systems for:

- Doctor.
- Patient.
- Pharmacy.
- Hospital.
- Nurse.
- Laboratory.
- Medical center.
- Any other provider type.

Roles and profiles belong underneath the Account.

Support architecture for:

- Email/password.
- Google/Firebase.
- Phone/Firebase.

Firebase authentication should eventually follow:

```text
Firebase ID Token
        |
        v
Racheeta Backend Verifies Token
        |
        v
Racheeta Access Token + Refresh Token
```

Never generate fake passwords for Firebase users.

Canonical endpoints should eventually include:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/firebase/exchange

GET  /api/v1/me
PATCH /api/v1/me
```

`/api/v1/me` must be the canonical source of the current user's:

- Identity.
- Profile.
- Role.
- Provider identity.
- Permissions.

Do not reproduce the legacy approach of storing many IDs such as:

- doctor_id.
- hospital_id.
- pharmacy_id.
- laboratory_id.
- medical_center_id.
- etc.

inside the client.

---

# 7. Account and Provider Domain

Design one Account system with profiles and permissions.

Racheeta users may include:

- Patient.
- Doctor.
- Nurse.
- Therapist.
- Pharmacy.
- Laboratory.
- Hospital.
- Medical Center.
- Beauty Center.
- Medical Company / Supplier.
- Real Estate Owner / Agent.
- Job Seeker.
- Racheeta Administrator.

Do not duplicate every common provider field in separate unrelated tables.

Use shared provider abstractions where appropriate.

Suggested conceptual design:

```text
Account

PatientProfile

ProviderProfile
   |
   +-- Practitioner
   |      Doctor
   |      Nurse
   |      Therapist
   |
   +-- Facility
          Hospital
          Pharmacy
          Laboratory
          MedicalCenter
          BeautyCenter

MedicalCompany

RealEstateSeller

JobSeekerProfile
```

Use memberships/relationships for practitioners working with facilities.

Example:

```text
ProviderMembership
- practitioner
- facility
- status
- joined_at
- ended_at
```

---

# 8. Required Business Modules

The final system must support these modules:

```text
accounts
patients
providers
facilities
practitioners
specialties
services
availability
reservations
reviews
offers
advertising
jobs
applications
jobseekers
medical_marketplace
medical_companies
products
real_estate
chat
notifications
payments
media
dashboard
analytics
audit
```

These are modules inside one modular monolith.

They are **not** separate Railway services.

---

# 9. Reservation System

Reservations must use controlled state transitions.

Example:

```text
PENDING
   |
   +--> CONFIRMED
   |        |
   |        +--> COMPLETED
   |        +--> CANCELLED
   |        +--> NO_SHOW
   |
   +--> REJECTED
   +--> CANCELLED
```

Every important transition must record:

- Who performed it.
- Previous state.
- New state.
- Timestamp.
- Optional reason.

Clients must not be allowed to send arbitrary reservation status strings.

---

# 10. Medical Services

Patients must eventually be able to discover and interact with:

- Doctors.
- Hospitals.
- Medical centers.
- Pharmacies.
- Laboratories.
- Nurses.
- Therapists.
- Beauty centers.
- Other approved medical providers.

Search should eventually support:

- Provider type.
- Specialty.
- Governorate.
- City.
- Location.
- Availability.
- Rating.
- Services.
- Price where relevant.

Location architecture should be ready for PostgreSQL/PostGIS if geographical search later requires it.

Do not add PostGIS until that feature is implemented.

---

# 11. Offers

Healthcare providers may publish offers.

Offer should eventually support fields such as:

- Provider.
- Title.
- Description.
- Original price.
- Discounted price.
- Start date.
- Expiration date.
- Image.
- Applicable service.
- Target audience.
- Active status.

Offer activation and expiration must be server-controlled.

---

# 12. Reviews

Reviews must be backend-controlled.

Prepare for rules such as:

- Only valid users may review.
- Optional reservation verification.
- One review per eligible interaction if business rules require it.
- Rating range validation.
- Moderation status.
- Abuse reporting.

---

# 13. Job Marketplace

Support:

Healthcare organization -> publishes job.

Job seeker -> creates professional profile.

Job seeker -> searches jobs.

Job seeker -> applies.

Organization -> reviews applications.

Application state machine should include something similar to:

```text
SUBMITTED
REVIEWING
SHORTLISTED
INTERVIEW
ACCEPTED
REJECTED
WITHDRAWN
```

Do not use arbitrary status strings.

---

# 14. Medical Marketplace

Create a B2B medical marketplace.

Medical companies and suppliers may publish products such as:

- Dental equipment.
- Dental consumables.
- Medicines.
- Laboratory equipment.
- Imaging equipment.
- Hospital equipment.
- Rehabilitation equipment.
- Beauty / aesthetic equipment.
- Pharmacy supplies.
- Medical furniture.
- Medical software.
- General medical supplies.

Products must support targeted audiences.

Example:

```text
Dental Equipment
        |
        +--> Dentists
        +--> Dental Centers
```

Example:

```text
Laboratory Equipment
        |
        +--> Laboratories
        +--> Relevant Medical Centers
```

Targeting must be determined by backend rules.

The company must not be able to manipulate the frontend to expose advertisements to unauthorized audiences.

Prepare entities similar to:

```text
MedicalCompany
ProductCategory
Product
ProductImage
ProductAudience
ProductCampaign
```

---

# 15. Medical Real Estate

Create a dedicated Medical Real Estate module.

Owners or agents may advertise:

- Clinic.
- Apartment suitable for clinic.
- Medical building.
- Pharmacy location.
- Laboratory location.
- Medical center.
- Hospital building.
- Commercial property suitable for medical use.
- Land for medical investment.

Support:

```text
SALE
RENT
```

Listing fields should eventually include:

- Owner.
- Title.
- Description.
- Property type.
- Governorate.
- City.
- District.
- Coordinates when available.
- Area.
- Price.
- Sale / rent.
- Images.
- Suitable medical uses.
- Facilities.
- Contact method.
- Publication status.
- Expiration date.

---

# 16. Advertising

Advertising must be completely redesigned.

Never allow frontend code to decide that payment succeeded.

Correct conceptual flow:

```text
Create Campaign
      |
      v
Backend Determines Price
      |
      v
Create Payment
      |
      v
Payment Provider
      |
      v
Verified Backend Callback / Webhook
      |
      v
Campaign Becomes ACTIVE
```

Advertisement targeting should support:

- Provider type.
- Medical specialty.
- Geography.
- Company/product category.
- Campaign dates.

---

# 17. Chat and Notifications

Do not over-engineer realtime communication initially.

Design clean domain models first.

Use:

- REST for initial message/history loading.
- FCM for push notifications.
- WebSockets later where realtime UX actually requires it.

Do not introduce Redis purely because WebSockets may be used in the future.

---

# 18. Dashboards

Never show fabricated dashboard statistics.

All values must come from backend APIs.

Examples:

- Reservations today.
- Pending reservations.
- Completed reservations.
- Active offers.
- Profile views.
- Job applications.
- Campaign performance.
- Products.
- Real estate listings.
- Notifications.
- Revenue where supported.

Create dedicated summary endpoints instead of forcing clients to download large datasets and calculate totals locally.

---

# 19. Mandatory Loading Rule

This requirement applies everywhere.

Any page that loads information from the backend must visibly show loading state.

Any button that sends or fetches backend information must display a circular progress indicator while the request is running.

During backend mutations:

- Disable the button.
- Prevent duplicate submission.
- Replace or accompany button content with a circular progress indicator.
- Properly handle success.
- Properly handle API errors.
- Restore button state after completion.

Create reusable UI components such as:

```text
ApiActionButton
AsyncPage
LoadingOverlay
```

Do not implement backend-connected buttons without loading feedback.

This rule applies to:

- Web application.
- Flutter mobile application.
- Dashboards.

---

# 20. API Rules

All public application APIs must live under:

```text
/api/v1/
```

Use consistent:

- Pagination.
- Filtering.
- Ordering.
- Validation errors.
- Authentication errors.
- Permission errors.
- Not-found responses.
- Timestamps.
- Identifiers.

Generate OpenAPI documentation.

OpenAPI must become the API contract/source of truth.

---

# 21. Database Rules

Use PostgreSQL.

Use proper:

- Foreign keys.
- Indexes.
- Uniqueness constraints.
- Transactions.
- Check constraints where appropriate.
- Timestamps.
- Soft deletion only where it has a clear business purpose.

Do not solve integrity rules only in frontend code.

Create migrations for every schema change.

Never manually change production schema without a migration.

---

# 22. Auditing

Create architecture that supports an audit log.

Important events should eventually be traceable, including:

- Account permission changes.
- Reservation status changes.
- Advertisement activation.
- Payment status changes.
- Provider verification.
- Application status changes.
- Important administrator actions.

---

# 23. Documentation — Mandatory

Create and continuously maintain:

```text
docs/ARCHITECTURE.md
docs/DATABASE.md
docs/API.md
docs/AUTHENTICATION.md
docs/SECURITY.md
docs/PERMISSIONS.md
docs/RAILWAY.md
docs/DEVELOPMENT.md
docs/BACKUP_RESTORE.md
docs/DECISIONS.md
docs/PROGRESS.md
docs/HANDOFF.md
```

Documentation must describe what really exists.

Do not describe unimplemented functionality as completed.

---

# 24. Handoff Protocol — Critical

The project may switch between:

- Claude.
- ChatGPT.
- Codex.
- Another developer.

Therefore no coding session may finish without updating:

```text
docs/HANDOFF.md
```

`HANDOFF.md` must always contain:

```text
# Current State

Date:
AI/Engineer:
Branch:
Last Commit SHA:

## Goal of This Work Session

## Completed

## Files Added

## Files Modified

## Database Migrations

## API Endpoints Added/Changed

## Architecture Decisions

## Security Decisions

## Tests Run

## Test Results

## Known Problems

## Incomplete Work

## Required Manual Actions

## Environment Variables Added/Changed

## Railway/Infrastructure Impact

## Exact Next Step

## Recommended Next Prompt
```

Also update:

```text
docs/PROGRESS.md
```

with milestone progress.

And update:

```text
docs/DECISIONS.md
```

whenever an important architectural decision is made.

Do not rely on conversational memory.

The repository is the persistent memory.

---

# 25. Git Rules

Make small, meaningful commits.

Examples:

```text
chore: initialize racheeta platform
feat(auth): add account authentication
feat(reservations): add reservation state machine
test(auth): add authentication API tests
docs: update architecture handoff
```

Never commit secrets.

Never commit:

- `.env`.
- Credentials.
- IDE caches.
- Build artifacts.
- Generated temporary files.

Maintain a professional `.gitignore`.

At each stable checkpoint report:

- Branch.
- Commit SHA.
- Git status.
- Tests executed.

---

# 26. CI

Create lightweight GitHub Actions CI.

## Backend

Run:

- Formatting/lint checks.
- Django checks.
- Migration check.
- pytest.

## Web

Run:

- TypeScript check.
- Lint.
- Tests.
- Production build.

CI must not contain production secrets.

---

# 27. Railway Strategy

Optimize for low operating cost.

Initial Railway resources:

```text
Racheeta Application
PostgreSQL
```

No Redis initially.

No permanent worker initially.

No unnecessary microservices.

Use environment variables for configuration.

Provide:

```text
GET /health/
```

for Railway health checks.

The application must be stateless except for:

- PostgreSQL.
- External object storage.

Prepare backup/restore documentation.

Avoid architecture that prevents moving from Railway later.

---

# 28. Development Phases

## Phase 0 — Foundation

- Initialize monorepo.
- Git hygiene.
- Documentation skeleton.
- Docker local development.
- PostgreSQL.
- Django project.
- React project.
- CI.
- Environment configuration.
- `/health/`.
- OpenAPI.
- Initial tests.

## Phase 1 — Accounts and Authentication

- Custom Account model.
- Authentication.
- Refresh.
- Logout.
- `/me`.
- Roles.
- Permissions.
- Tests.

## Phase 2 — Providers and Medical Services

- Provider profiles.
- Practitioner/facility relationships.
- Specialties.
- Services.
- Provider discovery.
- Filters.
- Availability.

## Phase 3 — Billing & Entitlements Foundation + Medical Jobs & Talent Marketplace (CURRENT — done)

> Roadmap correction (owner decision, 2026-09-23): Medical Jobs is Racheeta's
> highest-priority competitive service and must generate revenue, so it moved
> ahead of Reservations together with the reusable billing foundation.
> Reservations follow in Phase 4 and remain free.

- Billing foundation (`apps/billing`): plans, entitlements (capability keys), subscriptions with manual Super Admin activation, credits, atomic usage accounting. No gateway, no prices seeded. See `BILLING.md`.
- Employer organisations, verification, memberships with seats.
- Structured job-seeker résumé (no file uploads).
- Job posts with admin-reviewed publication and entitlement gating.
- Public job search, applications with snapshots and transition history.
- Entitlement-gated talent search ("one billable search" rule), saved candidates, invitations, interview requests, text-only in-app messaging.
- Contact-leak detection on all recruitment text (`MODERATION.md`).
- Super Admin control plane and audit log.

## Phase 4 — Reservations (done)

- Reservation model.
- Reservation state machine.
- Appointment availability.
- Patient reservations.
- Provider reservation management.
- Notification hooks.
- Free for patients and providers (owner decision); no entitlement gating.

## Phase 5 — Reviews and Offers (done — merged via PR #6)

- Reviews.
- Ratings.
- Offers.
- Expiry.
- Provider management.

## Phase 6 — Medical Marketplace (done — merged via PR #7)

- Medical companies.
- Categories.
- Products.
- Targeting.
- Company dashboards.

## Phase 7 — Medical Real Estate (done — merged via PR #8)

- Property listings.
- Sale/rent.
- Suitability.
- Search/targeting.
- Owner dashboard.

## Phase 8 — Advertising and Payments (done — merged via PR #9)

- Campaigns.
- Backend pricing.
- Payment records.
- Payment verification architecture.
- Advertisement targeting.

Do not integrate a paid payment gateway until the owner selects it.

## Phase 9 — Chat and Notifications (done)

- **9A Persistent notifications — done and merged via PR #10.**
- **9B Generic conversations/messages via REST.**
  - Generic Conversation / ConversationParticipant / immutable Message domain.
  - Initial authorized context is Reservation only; participants are derived by the backend.
  - No arbitrary account-to-account conversation creation.
  - Sequence-based read state; clients acknowledge only messages they actually rendered.
  - Existing recruitment `RecruitmentMessage` remains unchanged.
- **9B — done and merged via PR #11.**
- **9C Firebase push — done and merged via PR #12** (merge commit `3ff9cdd05b3b6851c78c80359f6c71683fd3d6fe`, post-merge CI #295 green). Delivered as:
  - `PushDevice` token registry (globally unique token, server-owned account, bounded platforms, transfer on account switch).
  - Authenticated register/unregister API; `PushSender` boundary over the Firebase Admin SDK (one `send_batch` operation per recipient, one multicast call, hard 3 s deadline, bounded in-flight work); after-commit best-effort fan-out.
  - Pushes for newly created persistent notifications and for new chat messages (other participant only); privacy-preserving content.
  - Web/mobile token acquisition deferred (no Firebase client in the repo). No worker, Redis, Celery or WebSockets. See `PUSH.md`.
- Realtime/WebSockets remain deferred unless UX later justifies them; no Redis/Celery added for chat.

## Phase 10 — Dashboards and Analytics (done — merged via PR #13)

Create dashboards for:

- Patient.
- Doctor.
- Facility.
- Medical company.
- Real estate owner.
- Recruiter.
- Administrator.

**Implementation (branch `feat/phase10-dashboards-analytics`, see `DASHBOARDS.md`, ADR-051):**

- Model-less `apps.dashboards`: role-scoped, read-only, parameterless summary endpoints under `/api/v1/dashboards/` plus a server-decided index; reuses the existing company, advertising and real-estate owner summaries.
- Only metrics backed by real records; revenue/views/impressions/conversions/trends are deferred.
- Web: one role-aware `/dashboard` hub (Arabic RTL and English) on the existing design system.
- No migrations, no new infrastructure.
- Merged via PR #13 (merge commit `94dc2e39572a984d5e1d68b0602fe74de34096d8`, post-merge CI #298 successful).

## Phase 11 — Mobile Integration (CURRENT — 11E implemented, awaiting review)

Build a new Flutter architecture with:

- One API client.
- Secure token storage.
- Unified session.
- Loading-state components.
- Feature migration.

Delivered as independently reviewed subphases (each its own branch and draft PR; the owner authorizes every merge):

| Subphase | Scope | Status |
| --- | --- | --- |
| 11A | Flutter foundation, authentication and session management (config, one API client, secure storage, navigation, shared UI, localization, login/logout/restore, account screen, CI job) | merged via PR #14 (merge `9282db373239d65ddc4dd7f1ea17e8721a8a0855`, post-merge CI #301 green) |
| 11B | Patient discovery and reservations | merged via PR #15 (accepted head `0acaf51950410daac12e5975d2f59157e521e531`, merge `82ae94d020394158ddcd8f1c6a85ffa7134e6b0a`, post-merge CI #308 green) |
| 11C | Provider & facility workspace | merged via PR #16 (accepted head `fa0d74135d527b8e50f2f8ac04fc90fe796e2c20`, merge `2899900b88062f539281b566c28c428baae07c1e`, post-merge CI #313 green) |
| 11D | Marketplace, jobs and real estate | merged via PR #17 (accepted head `ed99dae41ccc4cb6fe1ce0f7e680b3c61b571f8e`, merge `47bbaeb815357d396b47c91565cfa053e509b7c0`, post-merge CI #318 green) |
| 11E | Chat, notifications and FCM device registration | implemented on `feat/phase11e-chat-notifications-fcm` (draft PR, not merged; awaiting independent review) |
| 11F | Release hardening (signing, store builds, performance, accessibility audit) | not started |

**11A implementation (see `mobile/README.md`, ADR-052/053, `AUTHENTICATION.md` "Mobile client", `SECURITY.md` "Mobile client"):** Flutter 3.47.6, Riverpod, go_router, dio, flutter_secure_storage; access token in memory only, rotating refresh token in secure storage; single-flight refresh; stale-response protection across logout and account switching; role-aware navigation derived from `/me`; Arabic (RTL) and English. No feature beyond sign-in, session, home and account is exposed; no FCM registration, no Firebase login.

**11B implementation (see `mobile/README.md`, ADR-054, `RESERVATIONS.md` "Mobile (Phase 11B)", `SECURITY.md` "Mobile patient flows"):** patient-only provider discovery (search, filters, pagination), provider detail, appointment booking from backend availability, "My appointments" and cancellation, all on the 11A client/session. Backend authoritative; no backend change; timezone policy explicit (UTC on the wire, device-local display); reservation creation is never retried automatically. Not in 11B: provider-side screens (11C), marketplace/jobs/real estate (11D), chat/notifications/FCM (11E), payments.

**11C implementation (see `mobile/README.md`, ADR-055, `RESERVATIONS.md` "Mobile provider and facility (Phase 11C)", `SECURITY.md` "Mobile provider and facility flows"):** the provider/facility dashboard (server-chosen from `GET /dashboards/`), appointment availability (list, add, remove), received bookings (list, detail, status transitions), all on the 11A client/session and the 11B time policy. Shown only to accounts whose `/me` lists `reservations.manage_received`; the backend still requires a provider profile. Backend authoritative, no backend change; every mutation is account-scoped (a late answer of account A is dropped under account B), never retried and duplicate-protected. Not in 11C: profile/service editing, facility membership management and any facility-wide practitioner aggregation (no API relation), marketplace/jobs/real estate (11D), chat/notifications/FCM (11E), payments.

**11D implementation (see `mobile/README.md`, ADR-056, `MARKETPLACE.md` / `JOBS.md` / `REAL_ESTATE.md` "Mobile (Phase 11D)", `SECURITY.md` "Mobile marketplace, jobs and real-estate flows"):** an *Explore* section on Home (the bottom bar is unchanged) leads to three domains. **Real estate:** public catalogue (search, transaction/property/governorate filters, ordering, pagination), listing detail, and the seller workspace (dashboard, own listings, publish/unpublish). **Marketplace:** the provider catalogue (category filter, pagination, detail) and the medical-company workspace (dashboard, own products, activate/deactivate). **Jobs:** public search/detail, internal application (cover note only), "My applications" with withdraw, and the recruiter workspace (organisation dashboard, organisation jobs with a status filter, detail, close). Everything uses existing endpoints only (no backend, migration, permission or OpenAPI change); the backend stays authoritative; every mutation captures the initiating account and a late answer of account A is dropped under account B (the generalized `runAsAccount`); no mutation is retried and duplicate taps are blocked; destructive actions are confirmed; errors map to fixed localized text. Not in 11D: create/edit forms, applicant management, résumé/profile editing, uploads/images, external links, payments/cart/checkout, chat/notifications/FCM (11E), release hardening (11F).

**11E implementation (see `mobile/README.md`, ADR-057, `NOTIFICATIONS.md` / `CHAT.md` / `PUSH.md` "Mobile (Phase 11E)", `SECURITY.md` "Mobile notifications, chat and push flows"):** the persistent notification centre (list, unread count, mark one / all read), generic conversations (list, thread, composer, send, read cursor, "Message" from a reservation) and the FCM client (Firebase Messaging behind a `PushSource` interface, account-safe token registration, foreground refresh, tap and cold-start routing through one coordinator into the existing `GoRouter`). Existing 9A–9C APIs only (no backend, migration, endpoint or OpenAPI change). Persistent backend state stays the source of truth; push is a delivery hint (a foreground push only refreshes). Every mutation is account-scoped through `runAsAccount`; the token lifecycle is keyed by `(account, epoch)`; the device is unregistered before logout. Without `FIREBASE_*` build defines push is disabled and everything else works. Not in 11E: attachments, group chat, starting a conversation other than from a reservation, local-notification display, background data handlers, iOS push setup, release signing (11F).

## Phase 12 — Production Hardening

- Security review.
- Performance tests.
- Database indexes.
- Backups.
- Monitoring.
- Staging.
- Railway production deployment.
- Data migration if required.

---

# 29. First Task — Start Here

Do not attempt to build all business features immediately.

Start only with **Phase 0 and the foundation portion of Phase 1**.

Perform these tasks first:

1. Initialize the new `racheeta-platform` monorepo.
2. Create professional `.gitignore`.
3. Create `.editorconfig`.
4. Create `.env.example`.
5. Create README.
6. Create documentation structure.
7. Create Django backend.
8. Configure environment-based settings for:

```text
DEBUG
SECRET_KEY
DATABASE_URL
ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS
```

9. Configure PostgreSQL.
10. Create a custom Account model before production migrations accumulate.
11. Use email as canonical login identifier.
12. Never expose passwords in API responses.
13. Prepare clean role/permission architecture.
14. Add Django REST Framework.
15. Add OpenAPI/schema documentation.
16. Add:

```text
GET /health/
```

Example response:

```json
{
  "status": "ok"
}
```

17. Create initial `/api/v1/` routing.
18. Configure pytest.
19. Add backend smoke tests.
20. Add tests for the health endpoint.
21. Add tests for Account creation/security behavior.
22. Create React + TypeScript + Vite web skeleton.
23. Configure Arabic RTL support from the beginning.
24. Create a reusable frontend API layer placeholder.
25. Create reusable backend-action loading component pattern.
26. Set up GitHub Actions CI.
27. Create local `docker-compose.yml` for PostgreSQL development.
28. Document exact local setup commands.
29. Create/update all mandatory documentation.
30. Run all tests and builds.
31. Fix failures before declaring the phase complete.
32. Make a clean Git commit.
33. Update `docs/HANDOFF.md`.
34. Update `docs/PROGRESS.md`.
35. Return a concise final report containing:

```text
Branch
Commit SHA
Files created
Architecture implemented
Tests run
Test results
Known issues
Exact next step
```

Do not start Phase 2 until Phase 0/Foundation is demonstrably clean.

---

# 30. Working Rules for Claude / Codex / Any Future Engineer

Do not ask questions for trivial implementation choices.

Choose the conservative professional option and document the decision.

Stop and ask the owner only when:

- Credentials are required.
- Destructive actions are required.
- Financial/payment decisions are required.
- Account ownership decisions are required.
- The business requirement is genuinely ambiguous.

Do not deploy to production yet.

Do not touch the old production database.

Do not modify the old Racheeta application.

Do not migrate old data yet.

Build the new foundation cleanly first.

---

# 31. Continuity Rule Between AI Assistants

At the beginning of every new AI coding session:

1. Read `docs/ARCHITECTURE.md`.
2. Read `docs/DECISIONS.md`.
3. Read `docs/PROGRESS.md`.
4. Read `docs/HANDOFF.md`.
5. Check current Git branch.
6. Check latest commit.
7. Check `git status`.
8. Run relevant tests.
9. Continue from the exact next step recorded in `HANDOFF.md`.

At the end of every session:

1. Run tests.
2. Fix failures.
3. Commit stable changes.
4. Update `docs/HANDOFF.md`.
5. Update `docs/PROGRESS.md`.
6. Update `docs/DECISIONS.md` if architecture changed.
7. Report branch, commit SHA, tests, known issues, and exact next step.

The repository must always contain enough information for another AI assistant to continue without relying on chat history.

---

# 32. Final Principle

Keep Racheeta as the product.

Keep the useful business requirements.

Keep selected UI ideas where appropriate.

Rebuild the engineering foundation correctly.

The new Racheeta must be:

**Owner-controlled, secure, documented, portable, low-cost, testable, maintainable, and independent of any single developer or AI assistant.**
