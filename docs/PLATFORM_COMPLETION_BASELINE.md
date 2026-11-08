# Platform completion baseline (2026-11-06)

LOCAL ONLY. Branch `feat/local-racheeta-multiworkspace`. HEAD `0ecc7b1` (verified with
`git rev-parse HEAD`). Working tree clean at the start.

## Environment (verified)

| Check | Result |
|---|---|
| Disk | 16 GB free on `/System/Volumes/Data`. It was below 1 GB in the previous session; the space was freed outside this session. My own tooling's artifacts are under 0.5 GB. No user file was deleted. |
| Demo database backup | `local-demo/backups/racheeta_workspace_demo-0ecc7b1.dump` (git-ignored). Custom format, 0.7 MB, 99 table-data entries listed by `pg_restore -l`. |
| Backend `pytest` (full, sequential) | 2,242 passed, 1 skipped (optional firebase SDK) |
| Web `vitest` | 563 passed |
| `tsc -b` | clean |
| `oxlint` | 6 warnings, all pre-existing |
| Local servers | API `http://127.0.0.1:8010` → 200; web `http://127.0.0.1:5180` → 200 |

## Inventory (what exists, from the code)

- **Account types (registration):** 17. Patient; doctor, nurse, therapist; hospital, medical
  center, pharmacy, laboratory, beauty center; six business types; property owner and agent.
  One account has one role (PATIENT, PROVIDER, MEDICAL_COMPANY, REAL_ESTATE_SELLER, ADMIN).
  Organizations come from ownership and `OrganizationMember` / `EmployerMembership`.
- **Workspaces** (`apps/workspaces/services.py`): practitioner, facility, company (including the
  pharmacy store linked to its facility), property, employer, job seeker, admin, and a setup
  workspace. They are computed server-side from current memberships.
- **Dashboards** (`apps/workspaces/dashboard.py`, 1,125 lines): one composer with per-type
  builders (`_practitioner`, `_facility`, `_company`, `_property`, `_employer`, `_job_seeker`,
  `_patient`, `_admin`). They are backed by real queries, and a previous local API matrix passed
  285/285 checks across 36 account types (`docs/LOCAL_DEMO_TEST_MATRIX.md`).
- **Jobs:** 41 professions in 4 groups (HEALTHCARE, HEALTH_BUSINESS, TECHNOLOGY, BUSINESS).
  Healthcare comes first, and IT, accounting, sales, HR and engineering already exist. Employer
  organization types are healthcare plus university and recruitment agency. Any account can
  create one employer, which an administrator verifies.
- **Advertising:** targeted sponsored campaigns (`visible_to` = `targeted_for` + `selling_q`),
  provider offers (`apps/offers`), real-estate promotions, consent-gated outreach
  (`apps/preferences`).
- **Real estate:** listings with draft/publish/expire, owner scoping, promotions; no inquiries.
- **Reservations:** a full booking system. A partial flag `RACHEETA["RESERVATIONS_ENABLED"]`
  (default ON) is read only by the dashboard composer; about 15 web files show booking entry
  points.
- **Marketplace:** as accepted at `0ecc7b1` (`docs/local-commerce-implementation-matrix.md`).

## Gaps found (scope of this run)

| Phase | Gap |
|---|---|
| A | Registration has no dentist, midwife, employer/recruiter or general job-seeker choice; such users had to pick an unrelated type. Employer and job-seeker accounts get no setup step. |
| C | No education, management or operations professions; no "other profession" outside healthcare; no non-healthcare employer type, and no rule scoping what such an employer may post or search. |
| D | Targeting is implemented and tested; no laboratory or pharmacy-specific negative/positive matrix in one place. |
| E | No inquiry (lead) workflow between a property seeker and the owner. |
| F | The booking flag is not served to the web app, the web app shows booking entry points regardless, and new bookings are not refused when the flag is off. |
| B | Composer is large (1,125 lines). Per-type modules exist; verify the CTA paths and the absence of fake metrics. |
| G | Seed accounts for the new types; platform matrix; browser acceptance with the real login form at 390/768/1440 in AR/EN. |
