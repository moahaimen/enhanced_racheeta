# Platform completion matrix (2026-11-07)

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
| (this commit) | G | Matrix, docs, account-type label in the sidebar and account menu |

## Evidence totals

| Check | Baseline | Final |
|---|---|---|
| Backend `pytest` (full, sequential) | 2,242 passed, 1 skipped | **2,323 passed, 1 skipped** |
| Web `vitest` | 563 | **583** |
| `tsc -b` / `vite build` | clean | clean (the large-chunk notice was already there) |
| `oxlint` | 6 warnings | 6 warnings (same ones) |
| `ruff check` / `ruff format --check` | clean | clean |
| `makemigrations --check` | no changes | no changes. New migrations: accounts 0004, specialties 0003, jobs 0003, real_estate 0003, notifications 0006 |
| OpenAPI `spectacular --validate` | 0 warnings / 0 errors | **0 / 0**, regenerated |
| Demo seed lifecycle | — | seed → seed (no change, 2,485 rows) → clear (0 registry rows) → seed (2,395 rows) |
| Marketplace reconciliation | 11/11 | **11/11**; commission policy still 20% |
| Browser (real login form, AR+EN, 390/768/1440) | — | **362/362 checks** (107 functional steps, 255 screenshots with overflow and direction checks) |
| Composer refactor equivalence | — | 233/233 demo dashboard payloads identical before and after |

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

### C — Jobs for every profession

| Item | Status | Evidence |
|---|---|---|
| Taxonomy covers healthcare (first), health business, technology, business/management/operations, education, other; existing codes unchanged | PASS | `test_all_professions.py`; `jobs.types.test.ts`; grouped `<optgroup>` selects in 4 pages |
| Non-healthcare employer (BUSINESS): admin-verified, type frozen after verification, may only post, edit or submit non-clinical roles | PASS | 22 tests in `test_all_professions.py` |
| Talent search and detail hide clinical candidates from a BUSINESS employer; applicants stay visible to that employer only | PASS | tests; browser shows 10 non-clinical candidates, and the NURSE filter returns 0 |
| Demo candidates: doctor, nurse, dentist, pharmacist, lab and radiology technicians, biomedical engineers, software developer, cybersecurity, data analyst, accountant, sales, HR | PASS | Demo database |
| Healthcare employers (hospital, medical center, lab, company) and a non-healthcare employer with 4 published jobs and 3 applicants | PASS | Demo; browser `business employer jobs` |
| Filters, icons, translations, expiry, privacy, revocation, duplicates, cross-employer negatives | PASS (existing + new) | Jobs suite (576 tests) |

### D — Advertising, offers, notifications

| Item | Status | Evidence |
|---|---|---|
| «إعلان ممول» / "Sponsored" label on every sponsored item | PASS | `sponsored: true` asserted in the matrix test; browser checks the label |
| Server-derived targeting: dentist → dental, pharmacy → pharmacy, lab → lab, therapist → rehab; cardiologist sees no dental ads | PASS | `test_targeting_matrix.py` (12); browser compares each viewer's feed with the server rule (dentist, cardiologist, pending doctor, pharmacy, lab, therapist) |
| Unverified or suspended providers, consumers and anonymous visitors see no B2B price, photo or campaign | PASS | Matrix test; earlier marketplace review R2/R3 |
| Expired, future and unpaid campaigns and suspended sellers never show; regulated products cannot be promoted | PASS | Matrix test |
| Offers separate from campaigns and coupons | PASS (existing) | `apps/offers`, `apps/commerce` coupons, `apps/advertising` |
| Consent separation, property opt-out, transactional notices unaffected | PASS (existing) | `apps/preferences/tests`, `test_promotions.py::test_opting_out_hides_the_promotion_at_once` |
| Demo has a live lab campaign | PARTIAL | The demo data has none, so the lab feed is correctly empty in the browser; the lab positive case is proven by the API matrix |

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

## Known gaps and blockers (honest list)

1. **Mobile app**: not updated for the booking switch, inquiries or the new types (PARTIAL / NOT
   IMPLEMENTED above).
2. **Demo clean-up leaves 34 lazily created employer billing accounts** in the demo database. They
   predate this run: the `0ecc7b1` backup already has 34. Employer pages create them by id link,
   not foreign key, so `clear_local_demo` cannot prove ownership and leaves them. The new seed
   registers its own billing account, so it does not add to them. I did not delete them.
3. **Footer "Coming next: Offers / Medical marketplace"** is out of date (both exist). This was
   already there before this run; it is a content fix.
4. **`ledger_db_audit`** flags that the local database role owns the ledger tables. This is
   expected locally; production must use a non-owner role (`docs/MARKETPLACE_COMMERCE.md`).
5. **Web bundle** has one chunk over 500 kB (pre-existing build notice).

## Verified local URLs

- API: `http://127.0.0.1:8010` (`/health/` → 200, `/api/v1/platform/features` →
  `{"reservations_enabled": false}`).
- Web: `http://127.0.0.1:5180` (login, `/dashboard`, `/reservations`,
  `/real-estate/inquiries`, `/real-estate/owner/inquiries`, `/employer`, `/employer/talent`,
  `/jobs`, `/merchant/orders`, `/admin-finance`).
- Accounts: `local-demo/DEMO_ACCOUNTS.md` (passwords only in `local-demo/.env.demo`).
- Browser evidence: `local-demo/platform-acceptance.json`, `local-demo/screenshots-platform/`
  (git-ignored).
