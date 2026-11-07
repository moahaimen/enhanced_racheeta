# Platform completion matrix (2026-11-07, closure pass included)

LOCAL ONLY. Branch `feat/local-racheeta-multiworkspace`, baseline `0ecc7b1`
(`docs/PLATFORM_COMPLETION_BASELINE.md`). Nothing was pushed, merged or deployed; no Railway,
staging or production access.

**Verdict: local demo GO. Production NO-GO.** Production still needs the owner inputs and operator
steps in `docs/PRODUCTION_DEPLOYMENT.md`. Two more apply: a non-owner database role for the ledger
(`ledger_db_audit --strict`) and the mobile app, which this work did not change.

Status key: **PASS** = implemented and tested here · **PARTIAL** = works with a stated gap ·
**NOT IMPLEMENTED** = not done in this run.

## Commits since the baseline

| Commit | Phase | Subject |
|---|---|---|
| `6a806b4` | A | Dentist, midwife, employer and job-seeker onboarding types with setup steps |
| `25ad7f8` | C | All-profession taxonomy and scoped non-healthcare employers |
| `ae3c833` | F | Reversible booking sunset behind one server switch (default OFF) |
| `62e065d` | E | Property inquiries with owner answers, scoping and audit |
| `064c750` | D | Profession targeting matrix for sponsored products |
| `bfb77e1` | B | Dashboard composer split into a package by concern |
| `b8af846` | G | Local seed for new account types, a non-healthcare employer and inquiries |
| `719fbcb` | G | Matrix, docs, account-type label in the sidebar and account menu |
| `42d91bd` | Closure 1 | Footer lists live services instead of "coming soon" |
| `73415e1` | Closure 2 | Clear removes lazily created billing accounts of demo owners; unproven ones kept and reported |
| `696efcc` | Closure 3 | Live laboratory-targeted campaign with suppression tests |
| `dfa9709` | Closure 4 | Dashboard gaps found by the functional audit |
| `7421991` | Closure 5 | Profession taxonomy guarded across server, OpenAPI and web |
| `0c12ce5` | Closure 5 | How to add a profession, what catches a missed step, limitations |
| (this commit) | Closure 6 | Matrix, dashboard audit, handoff and progress |

## Evidence totals

| Check | Baseline `0ecc7b1` | A–G `719fbcb` | Closure (final) |
|---|---|---|---|
| Backend `pytest` (full, sequential, alone) | 2,242 passed, 1 skipped | 2,323 passed, 1 skipped | **2,368 passed, 1 skipped** |
| Web `vitest` | 563 | 583 | **591** |
| `tsc -b` / `vite build` | clean | clean | clean (the large-chunk notice was already there) |
| `oxlint` | 6 warnings | 6 | 6 (same ones) |
| `ruff check` / `ruff format --check` | clean | clean | clean |
| `makemigrations --check` | no changes | no changes | no changes (no new migration in the closure) |
| OpenAPI `spectacular --validate --fail-on-warn` | 0 / 0 | 0 / 0 | **0 / 0**, committed file in sync |
| Demo seed lifecycle | — | seed → seed → clear → seed | seed (2,398) → seed (no change) → clear (2,513 removed; 34 billing accounts kept) → seed (2,398) |
| Marketplace reconciliation | 11/11 | 11/11 | **11/11**; commission policy **20.00%** (unchanged) |
| Browser (real login form, AR+EN, 390/768/1440) | — | 362/362 | **539/539** on the final full run |
| Dashboard actions opened in the browser | — | — | **112 destinations from 26 accounts, all working** |

The first closure browser run scored 537/539. Both failures were in the runner, not the product:
the B2B check returned a DOM element instead of a boolean, which CDP cannot serialize. After the
runner was fixed, the affected account was rerun alone (26/26), then the whole run (539/539).

## Phase matrix

### A — Onboarding, identity, workspace navigation

| Item | Status | Evidence |
|---|---|---|
| Registration: patient, job seeker, employer; doctor, dentist, nurse, midwife, therapist; facilities; companies; property owner and agent | PASS | `RegisterPage.test.tsx` (exact option list, never ADMIN); browser `registration offers every account type` in AR and EN |
| Account type is a hint, never a permission | PASS | `test_onboarding_types.py::test_the_account_type_never_grants_access` |
| Dentist and midwife preselect doctor + dentistry and nurse + midwifery (new specialty) | PASS | `test_dentist_and_midwife_preset_existing_specialties`; `ProviderForm` preset |
| Employer and job-seeker setup steps until the workspace exists | PASS | onboarding tests; browser `employer-setup-new`, `jobseeker-setup-new` |
| Workspaces computed server-side; forged or revoked ids give 404; switcher at 390 px | PASS (existing) | `apps/workspaces/tests`; screenshots at 390 |
| Every module discoverable from navigation | PASS | Sidebar: reservation history, property inquiries (asker and owner), employer, résumé, store and orders |
| Sidebar and account menu show the registration type (e.g. "Employer") instead of the base role | PASS | Fixed during browser review |

### B — Distinct dashboards

| Item | Status | Evidence |
|---|---|---|
| One dashboard per workspace kind, each with real actions | PASS | `apps/workspaces/tests/test_dashboard.py`; browser dashboards for 19 accounts |
| Metrics are real queries; nothing estimated | PASS | Composer docstring rule; equivalence run |
| 1,176-line composer reviewed and split (primitives / modules / builders / policy) | PASS | `bfb77e1`, 233/233 identical payloads |
| Property dashboard shows inquiry counts | PASS | `_inquiries_module`; owner dashboard API contract test |
| Functional audit: every profession has its required actions | PASS (closure) | `docs/DASHBOARD_AUDIT.md`. 46 workspace shapes audited; 3 gaps fixed (B2B sellers' quote orders and statement; finance console action; asker-side property inquiries); `test_dashboard_audit.py` (28, 9 of them failing before the fix); 112 dashboard actions opened in the browser |

### C — Jobs for every profession

| Item | Status | Evidence |
|---|---|---|
| Taxonomy covers healthcare (first), health business, technology, business/management/operations, education, other; existing codes unchanged | PASS | `test_all_professions.py`; `jobs.types.test.ts`; grouped `<optgroup>` selects in 4 pages |
| Non-healthcare employer (BUSINESS): admin-verified, type frozen after verification, may only post, edit or submit non-clinical roles | PASS | 22 tests in `test_all_professions.py` |
| Talent search and detail hide clinical candidates from a BUSINESS employer; applicants stay visible to that employer only | PASS | tests; browser shows 10 non-clinical candidates, and the NURSE filter returns 0 |
| Demo candidates: doctor, nurse, dentist, pharmacist, lab and radiology technicians, biomedical engineers, software developer, cybersecurity, data analyst, accountant, sales, HR | PASS | Demo database |
| Healthcare employers (hospital, medical center, lab, company) and a non-healthcare employer with 4 published jobs and 3 applicants | PASS | Demo; browser `business employer jobs` |
| Filters, icons, translations, expiry, privacy, revocation, duplicates, cross-employer negatives | PASS (existing + new) | Jobs suite (576 tests) |
| Adding a new profession is supported and guarded | PASS (closure) | `docs/JOBS_PROFESSIONS.md`: 7-step procedure rehearsed with a clinical and a non-clinical profession; each omitted step is caught; migration is a PostgreSQL no-op. Limitations: static web copy (needs a web deploy), permanent codes, mobile not covered |

### D — Advertising, offers, notifications

| Item | Status | Evidence |
|---|---|---|
| «إعلان ممول» / "Sponsored" label on every sponsored item | PASS | `sponsored: true` asserted in the matrix test; browser checks the label |
| Server-derived targeting: dentist → dental, pharmacy → pharmacy, lab → lab, therapist → rehab; cardiologist sees no dental ads | PASS | `test_targeting_matrix.py` (12); browser compares each viewer's feed with the server rule (dentist, cardiologist, pending doctor, pharmacy, lab, therapist) |
| Unverified or suspended providers, consumers and anonymous visitors see no B2B price, photo or campaign | PASS | Matrix test; earlier marketplace review R2/R3 |
| Expired, future and unpaid campaigns and suspended sellers never show; regulated products cannot be promoted | PASS | Matrix test |
| Offers separate from campaigns and coupons | PASS (existing) | `apps/offers`, `apps/commerce` coupons, `apps/advertising` |
| Consent separation, property opt-out, transactional notices unaffected | PASS (existing) | `apps/preferences/tests`, `test_promotions.py::test_opting_out_hides_the_promotion_at_once` |
| Demo has a live lab campaign | PASS (closure) | "lab-live": Rafidain LabTech's hematology analyzer, narrowed to laboratories. Browser: zahraa-labs sees it with the «إعلان ممول» / "Sponsored" label in AR and EN; dijla-hospital (which may buy the category), fayhaa-center, lamsa-beauty, nr-hanan-saidi, both doctors and the pharmacy do not. `test_laboratory_campaign.py` (8): display opt-out, marketing opt-out (alert only), suspended lab, suspended seller and cancelled campaign suppress it |

### E — Medical real estate

| Item | Status | Evidence |
|---|---|---|
| Create, edit, publish, unpublish, expire, filters | PASS (existing) | `apps/real_estate/tests` |
| Inquiry: public listings only, own listing refused, one live inquiry per asker, 10/day cap, POST throttle | PASS | `test_inquiries.py` (17) |
| Lifecycle OPEN → ANSWERED → CLOSED; WITHDRAWN by the asker; final states enforced | PASS | tests; demo has all four states |
| Owner answers in the UI; asker sees the answer; contact shared only on opt-in | PASS | `Inquiries.test.tsx` (8); browser: send, refused duplicate, owner answers |
| Unpublish or expiry hides the listing immediately; history keeps a title snapshot only | PASS | tests |
| Audit and transactional notifications (listing title only) | PASS | tests |
| Mobile app | NOT IMPLEMENTED | Out of scope for this run |

### F — Reservations: reversible UI sunset

| Item | Status | Evidence |
|---|---|---|
| One server switch `RACHEETA["RESERVATIONS_ENABLED"]` (env `RESERVATIONS_ENABLED`), default OFF, served by the public `GET /api/v1/platform/features` | PASS | `test_reservations_flag.py` (15); security sweep public list |
| OFF: new booking, new slot and accepting a pending booking give 403 `service_disabled`; public availability is empty | PASS | tests |
| OFF: history reads unchanged; cancel, reject, complete and no-show allowed; no table or row deleted | PASS | tests; browser before/after counts (85 reservations, 280 slots unchanged) |
| Web: every booking CTA hidden (profile booking section, "Book now" chips, tagline, footer link, slot form, Accept, facility Confirm); history pages are "Reservation history" with a notice; no dead routes | PASS | `BookingSunset.test.tsx` and OFF cases; browser on anonymous, patient, doctor and facility pages |
| ON restores the previous behaviour | PASS | The full legacy booking suite runs with the switch ON (`config/test_settings.py`) and passes; `test_on_restores_booking`; web tests default to ON |
| Mobile app booking screens hidden | PARTIAL | Not changed. With the switch OFF its booking calls get `403 service_disabled` |

**How to configure:** set the environment variable `RESERVATIONS_ENABLED=true` (or `false`) and
restart the API. The default when it is unset is `false`. Locally, add the line to
`local-demo/.env.demo`. No migration or data change is needed either way
(`docs/RESERVATIONS.md` "Booking sunset switch").

### G — Quality, security, demo

| Item | Status | Evidence |
|---|---|---|
| Demo seed for all types; seed → seed → clear → seed; reconciliation 11/11 | PASS | Above |
| Marketplace regression (20% commission, immutable ledger, earlier fixes) | PASS | Full suite; reconciliation; browser merchant orders and finance console |
| Docs: HANDOFF, PROGRESS, RESERVATIONS, REAL_ESTATE, ADVERTISING, LOCAL_WORKSPACE_DEMO; `local-demo/DEMO_ACCOUNTS.md` (git-ignored, no secrets) | PASS | This commit |
| Public footer lists live services, no "coming soon" | PASS (closure) | `SiteFooter.test.tsx` (6, by role, AR and EN); browser checks for visitors and a provider in AR and EN; footer screenshots AR/EN at 390 and 1440 (`local-demo/screenshots-platform/footer/`) |
| Demo clean-up is safe and repeatable for billing accounts | PASS (closure) | `test_clear_billing.py` (7; 6 fail on the previous cleaner): lazily created billing accounts go with their demo owner; real, orphaned and non-demo-activated ones are kept or refuse the clear; 3 seed/clear cycles leave the set unchanged |

## Known gaps and blockers (honest list)

1. **Mobile app**: not updated for the booking switch, inquiries, the new account types, the
   dashboard fixes or newer professions (it shows the raw code). PARTIAL / NOT IMPLEMENTED above.
2. **34 billing accounts kept in the local demo database, on purpose.**
   - **33 orphans:** their employer no longer exists and none has a subscription, credit or usage
     row. 2 are provably former demo employers (their ids are registered in the `0ecc7b1` backup);
     31 were already orphans in that backup, and nothing in any table identifies their owner.
     Ownership cannot be proven from the database, so `clear_local_demo` keeps and reports them.
   - **1 belongs to "sami clinic"**, an employer a real (non-demo) account created. It is real data.

   None was deleted. The cleaner now removes the billing account together with its demo owner, so
   no new orphans appear: the final dry run would delete 4 (Rafidain's registered one and 3 created
   by the browser runs) and keep the 34.
3. **`ledger_db_audit`** flags that the local database role owns the ledger tables. This is
   expected locally; production must use a non-owner role (`docs/MARKETPLACE_COMMERCE.md`).
4. **Web bundle** has one chunk over 500 kB (pre-existing build notice).
5. **Lab test orders and results, prescriptions, insurance** do not exist on the platform; they
   are not dashboard gaps (`docs/DASHBOARD_AUDIT.md`).
6. **Patients with booking OFF** reach past reservations from the sidebar ("Reservation history")
   and cannot write new reviews, which follow a completed booking. This is the sunset by design
   (PARTIAL in the dashboard audit).

**Verdict: local demo GO. Production NO-GO.** It needs the owner inputs and operator steps in
`docs/PRODUCTION_DEPLOYMENT.md`, a non-owner database role for the ledger, and the mobile app work
above. Nothing was pushed, merged or deployed.

## Verified local URLs

- API: `http://127.0.0.1:8010` (`/health/` → 200, `/api/v1/platform/features` →
  `{"reservations_enabled": false}`).
- Web: `http://127.0.0.1:5180` (login, `/dashboard`, `/reservations`,
  `/real-estate/inquiries`, `/real-estate/owner/inquiries`, `/employer`, `/employer/talent`,
  `/jobs`, `/merchant/orders`, `/admin-finance`, `/store`).
- Accounts: `local-demo/DEMO_ACCOUNTS.md` (passwords only in `local-demo/.env.demo`).
- Browser evidence: `local-demo/platform-acceptance.json`, `local-demo/screenshots-platform/`
  (git-ignored; 363 page screenshots and 4 footer-only shots).
