# Local demo test matrix (PASS / FAIL / NOT IMPLEMENTED)

Branch `feat/local-racheeta-multiworkspace`. Disposable local database `racheeta_workspace_demo`,
API `127.0.0.1:8010`, web `127.0.0.1:5180`. Generated 2026-10-31 from a clean seed. Local only:
nothing was pushed or deployed. No remote service was used.

## 1. Live end-to-end matrix (real login, real HTTP, every user type)

`local-demo/api_matrix.py` signs in through `/api/v1/auth/login` as each account type, then runs
workflows and negative cases. **198/198 PASS.**

| User type | Checks | Result | Workflows covered |
|---|---|---|---|
| anonymous | 7 | PASS | public store lists consumer products; restricted medicine hidden from store; suspended/pending business products hidden; /api/v1/workspaces requires sign-in; /api/v1/orders requires sign-in; /api/v1/me/preferences requires sign-in; /api/v1/real-estate/promoted requires sign-in |
| patient | 11 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); checkout without governorate rejected; place order: server price, tampered price ignored; card payment / over-limit quantity refused; my orders list; professional B2B catalogue denied; sponsored professional ads denied; cancel confirmed order restores stock |
| patient (second) | 6 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); IDOR: another buyer's order -> 404; IDOR: cancel another buyer's order -> 404 |
| assistive device store | 7 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); confirm incoming order; invalid jump CONFIRMED->DELIVERED refused; merchant quotes inbox loads |
| equipment supplier (rival) | 7 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); tenant isolation: rival's order -> 404; tenant isolation: ?company=other -> 403; own advertising campaigns load |
| patient (unverified e-mail) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); ordering requires verified e-mail |
| patient (suspended) | 1 | PASS | suspended account cannot sign in |
| doctor - dentist | 11 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); sponsored feed shows dental campaign; pharmacy campaign not shown to dentist; opted-in property promotion visible; my quote requests (seeded QUOTED); request quote on targeted product; withdraw own quote request; sponsored alert labelled 'Sponsored' |
| doctor - cardiologist | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dental campaign invisible; pharmacy campaign invisible; property promotion hidden (opted out); dental products absent from catalogue |
| doctor - dentist (display off) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); sponsored feed empty when display switched off |
| nurse | 4 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen) |
| therapist | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); rehab campaign targeted to therapists |
| doctor (pending verification) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); unverified provider gets no ads |
| doctor (suspended) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); suspended provider denied B2B catalogue |
| pharmacy | 7 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); pharmacy campaign visible to pharmacy; opted-in property promotion visible; accepted quote visible |
| hospital (owner) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); owner sees team (staff + viewer) |
| medical center (owner) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); facility quote request (REQUESTED) |
| laboratory | 4 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen) |
| hospital staff | 7 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); tenant A reservations visible; tenant B workspace -> 404; staff cannot view team |
| hospital viewer | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); viewer cannot change reservations |
| medical center manager | 6 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); manager views team; manager cannot add members (owner only) |
| multi-organization staff | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); facility STAFF + business VIEWER |
| store manager (staff) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); staff sees business orders via ?company= |
| former staff (ended) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); ended membership has no access |
| pharmaceutical company | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); advertising campaigns load |
| scientific office | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); advertising campaigns load |
| pharma distributor | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); advertising campaigns load |
| medical supplies office | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); incoming quote requests (minimal requester data) |
| property owner | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); promoted feed is for providers only |
| property agent | 6 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); own promotions (active/requested/rejected); cannot open admin promotion review |
| recruiter | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); employer workspace opens |
| job seeker - IT developer | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); résumé with SOFTWARE_DEVELOPER profession |
| job seeker - pharmacist | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); applications load |
| job seeker - lab technician | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); applications load |
| administrator (local only) | 6 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); promotion review queue; advertising review list |

## 2. Seeded negative cases (checked in the database after seeding and after reseeding)

| Case | Result |
|---|---|
| Dental campaign visible to dentist, invisible to cardiologist | PASS |
| Pharmacy campaign visible only to the pharmacy | PASS |
| Rehab campaign visible to therapist | PASS |
| Expired / rejected / pending-payment / suspended-company campaigns hidden | PASS |
| Restricted medicine, B2B-only, suspended and pending products absent from the public store | PASS |
| Property promotion visible to opted-in pharmacy, hidden from opted-out cardiologist | PASS |
| Requested and rejected promotions never shown | PASS |
| Sponsored alert reached only the opted-in dentist (display-only dentist and cardiologist excluded) | PASS |
| Tenant A staff can open Dijla; denied Nakheel (tenant B) | PASS |
| Viewer cannot manage reservations; ended staff has no access | PASS |
| Orders seeded in all 5 states; quotes in REQUESTED / QUOTED / ACCEPTED | PASS |

27/27 PASS (`local-demo/verify_negative_cases.py`).

## 3. Automated suites

| Suite | Result |
|---|---|
| Backend `pytest` (full) | PASS: 2078 passed, 1 skipped (optional `firebase_admin` SDK contract) |
| New backend tests: commerce (tampering, restricted, stock, cancel/restore, COD, IDOR, staff roles) | PASS |
| Concurrency: last unit sold once under parallel checkouts (3 rounds) | PASS |
| Quotes: targeting (cardiologist 404), duplicate open, unverified/patient denied, viewer cannot respond, rival 404 | PASS |
| Workspaces: tenant isolation (facility + company), multi-org, ended membership, owner-only member management, deactivated owner | PASS |
| Preferences and outreach: defaults, audit, unknown fields, display gate, opt-in only, daily cap, send cap, dedupe, inactive accounts, transactional independence | PASS |
| Promotions: full flow, opt-out hides at once, expired listing drops, request rules, admin-only decisions, seller isolation | PASS |
| Registration account types (all 17), role mismatch, no self-change | PASS |
| Professions endpoint and grouping | PASS |
| Security sweep: anonymous refusal, reviewed public surface | PASS |
| Local guard: opt-in, Railway vars, remote hosts, non-demo name, missing marker, no credential leak, no live-settings mutation | PASS |
| `ruff check`, `ruff format --check`, `manage.py check`, `makemigrations --check` | PASS |
| OpenAPI regenerated (`docs/api/openapi.yaml`) and validated | PASS |
| Web `tsc -b` | PASS (0 errors) |
| Web `oxlint` | PASS (0 errors; 6 warnings that predate this branch) |
| Web `vitest` | PASS: 511 tests in 46 files |
| Web `vite build` | PASS |
| Seed lifecycle `seed → seed → clear --dry-run → clear → seed` | PASS (1646 → 1646 no-op → all removed → 1646) |

## 4. Screenshots

160 PNGs in the git-ignored `local-demo/screenshots/<ar|en>/<390|768|1024|1440>/`: 20 pages × 2 languages × 4 widths.
Every page was captured signed in as the relevant user, and no image is a login-page fallback.
The approved UI is unchanged: `#E9EEF2` page, `#148283` teal, white cards, Cairo, RTL Arabic.

Pages: public store · register (account types) · patient dashboard · patient orders · dentist dashboard with «إعلان ممول» ad and promoted property · dentist quotes · preferences · cardiologist dashboard (no dental ads) · hospital owner workspaces · hospital owner team · hospital staff workspace · hospital viewer (read only) · multi-org switcher · store merchant orders · supplier quotes · pharma company dashboard · property agent promotions · pharmacy dashboard · IT job seeker · admin promotions.

## 5. NOT IMPLEMENTED (deliberately deferred)

| Item | Status |
|---|---|
| Refresh token in an HttpOnly cookie | NOT IMPLEMENTED: design and required tests in `docs/LOCAL_WORKSPACE_DEMO.md` §7 |
| External e-mail / push marketing | NOT IMPLEMENTED (in-app only, by instruction) |
| Card or online payments | NOT IMPLEMENTED (by design; COD / manual transfer recorded as demo) |
| Delivery pricing, taxes | NOT IMPLEMENTED |
| Pagination controls on merchant and quote pages | NOT IMPLEMENTED (API paginates; pages show the first 20) |
| Enforcing account type against provider or business type at later profile creation | NOT IMPLEMENTED |
| Ad impressions / clicks metrics | NOT IMPLEMENTED (no fabricated metrics) |
| Flutter / mobile | Out of scope (not touched) |
