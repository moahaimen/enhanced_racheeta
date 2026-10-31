# Local demo test matrix (PASS / FAIL / NOT IMPLEMENTED)

Branch `feat/local-racheeta-multiworkspace`. Disposable local database `racheeta_workspace_demo`,
API `127.0.0.1:8010`, web `127.0.0.1:5180`. Updated 2026-10-31 (dashboards round). Local only:
nothing was pushed or deployed. No remote service was used.

## 1. Live end-to-end matrix (real login, real HTTP, every user type)

`local-demo/api_matrix.py` signs in through `/api/v1/auth/login` as each account type, then runs
workflows and negative cases. **285/285 PASS.**

| User type | Checks | Result | Workflows covered |
|---|---|---|---|
| anonymous | 7 | PASS | public store lists consumer products; restricted medicine hidden from store; suspended/pending business products hidden; /api/v1/workspaces requires sign-in; /api/v1/orders requires sign-in; /api/v1/me/preferences requires sign-in; /api/v1/real-estate/promoted requires sign-in |
| patient | 14 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; checkout without governorate rejected; place order: server price, tampered price ignored; card payment / over-limit quantity refused; my orders list; professional B2B catalogue denied; sponsored professional ads denied; cancel confirmed order restores stock |
| patient (second) | 6 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); IDOR: another buyer's order -> 404; IDOR: cancel another buyer's order -> 404 |
| assistive device store | 10 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; confirm incoming order; invalid jump CONFIRMED->DELIVERED refused; merchant quotes inbox loads |
| equipment supplier (rival) | 10 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; tenant isolation: rival's order -> 404; tenant isolation: ?company=other -> 403; own advertising campaigns load |
| patient (unverified e-mail) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); ordering requires verified e-mail |
| patient (suspended) | 1 | PASS | suspended account cannot sign in |
| doctor - dentist | 14 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; sponsored feed shows dental campaign; pharmacy campaign not shown to dentist; opted-in property promotion visible; my quote requests (seeded QUOTED); request quote on targeted product; withdraw own quote request; sponsored alert labelled 'Sponsored' |
| doctor - cardiologist | 11 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; dental campaign invisible; pharmacy campaign invisible; property promotion hidden (opted out); dental products absent from catalogue |
| doctor - dentist (display off) | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; sponsored feed empty when display switched off |
| nurse | 7 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404 |
| therapist | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; rehab campaign targeted to therapists |
| doctor (pending verification) | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; unverified provider gets no ads |
| doctor (suspended) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); suspended provider denied B2B catalogue |
| pharmacy | 10 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; pharmacy campaign visible to pharmacy; opted-in property promotion visible; accepted quote visible |
| hospital (owner) | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; owner sees team (staff + viewer) |
| medical center (owner) | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; facility quote request (REQUESTED) |
| laboratory | 7 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404 |
| beauty center | 6 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); aesthetic services, offers (promotions), equipment suppliers; beauty-equipment campaign targeted |
| hospital staff | 10 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; tenant A reservations visible; tenant B workspace -> 404; staff cannot view team |
| hospital viewer | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; viewer cannot change reservations |
| medical center manager | 9 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; manager views team; manager cannot add members (owner only) |
| multi-organization staff | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; facility STAFF + business VIEWER |
| store manager (staff) | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; staff sees business orders via ?company= |
| former staff (ended) | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); ended membership has no access |
| pharmaceutical company | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; advertising campaigns load |
| scientific office | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; advertising campaigns load |
| pharma distributor | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; advertising campaigns load |
| medical supplies office | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; incoming quote requests (minimal requester data) |
| property owner | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; promoted feed is for providers only |
| property agent | 9 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; own promotions (active/requested/rejected); cannot open admin promotion review |
| recruiter | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; employer workspace opens |
| job seeker - IT developer | 8 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; résumé with SOFTWARE_DEVELOPER profession |
| job seeker - pharmacist | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); applications load |
| job seeker - lab technician | 5 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); applications load |
| administrator (local only) | 9 | PASS | sign in (real login endpoint); identity: role + account type; workspace switcher loads; dashboards populated (server-chosen); dashboard composition (server-decided modules); every listed workspace dashboard opens; forged / foreign workspace ids -> 404; promotion review queue; advertising review list |

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
| Backend `pytest` (full) | PASS: 2092 passed, 1 skipped (optional `firebase_admin` SDK contract) |
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
| Web `vitest` | PASS: 519 tests in 48 files |
| Web `vite build` | PASS |
| Seed lifecycle `seed → seed → clear --dry-run → clear → seed` | PASS (1668 → 1668 no-op → all removed → 1668) |

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

## 6. Specialized dashboards (module framework, `GET /workspaces/dashboard`)

Rendered in headless Chromium after a **real login** for each account, in Arabic at 390 and 1440 px.
54 screenshots are in `local-demo/screenshots-dashboards/ar/`. All **27/27** rendered with no error
(`local-demo/screenshots-dashboards-report.json`).

| Shot | Account | Workspace | Modules rendered (server-composed) |
|---|---|---|---|
| `d01-patient` | patient-sara | patient | my_orders, reservations, store, my_reviews, notifications, account |
| `d02-doctor-dentist` | dr-dalia-tamimi | practitioner | profile, services, reservations, offers, reviews, products, my_quotes, notifications, account · sponsored ads: 1 · promoted: 1 |
| `d03-doctor-cardiologist-no-dental-ads` | dr-karim-saadi | practitioner | profile, services, reservations, offers, reviews, products, my_quotes, notifications, account |
| `d04-nurse` | nr-hanan-saidi | practitioner | profile, services, reservations, offers, connections, products, my_quotes, notifications, account |
| `d05-therapist` | th-layla-nuaimi | practitioner | profile, services, reservations, offers, reviews, products, my_quotes, notifications, account · sponsored ads: 1 |
| `d06-hospital` | dijla-hospital | facility | profile, services, practitioners, reservations, offers, team, recruitment, products, my_quotes, notifications, account |
| `d07-medical-center` | nakheel-dental | facility | profile, services, practitioners, reservations, offers, team, recruitment, products, my_quotes, notifications, account · sponsored ads: 1 · promoted: 1 |
| `d08-pharmacy` | amal-pharmacy | facility | profile, offers, team, recruitment, categories, products, my_quotes, notifications, account · sponsored ads: 1 · promoted: 1 |
| `d09-laboratory` | zahraa-labs | facility | profile, services, reservations, offers, team, recruitment, products, my_quotes, notifications, account |
| `d10-beauty-center` | lamsa-beauty | facility | profile, services, reservations, offers, team, recruitment, products, my_quotes, notifications, account · sponsored ads: 1 |
| `d11-pharmaceutical-company` | company-dijla-pharma | company | catalogue, quote_requests, campaigns, team, recruitment, notifications, account |
| `d12-scientific-office` | company-ibn-sina-scientific | company | catalogue, quote_requests, campaigns, team, recruitment, notifications, account |
| `d13-equipment-supplier` | company-sharq-devices | company | catalogue, inventory, store_orders, quote_requests, campaigns, team, recruitment, notifications, account |
| `d14-medical-supplies-office` | company-nakhla-dental-supply | company | catalogue, inventory, store_orders, quote_requests, campaigns, team, recruitment, notifications, account |
| `d15-assistive-device-store` | company-rehab-mobility | company | catalogue, inventory, store_orders, quote_requests, campaigns, team, recruitment, notifications, account |
| `d16-pharma-distributor` | company-kurdistan-medicines | company | catalogue, quote_requests, campaigns, team, recruitment, notifications, account |
| `d17-property-agent` | seller-mansour-properties | property | listings, promotions, notifications, account |
| `d18-job-seeker` | seeker-it-mustafa | job_seeker | resume, applications, interviews, invitations, relevant_jobs, notifications, account |
| `d19-recruiter` | recruiter-dijla | employer | jobs, applicants, interviews, invitations, subscription, notifications, account |
| `d20-administrator` | local-admin | admin | verification, moderation, campaigns_admin, subscriptions, users, audit, notifications, account |
| `d21-hospital-staff-default-landing` | staff-dijla-reception | facility | profile, services, practitioners, reservations, offers, notifications, account |
| `d22-hospital-viewer` | staff-dijla-viewer | facility | profile, services, practitioners, reservations, offers, notifications, account |
| `d23-medical-center-manager` | staff-nakheel-manager | facility | profile, services, practitioners, reservations, offers, team, notifications, account |
| `d24-store-manager-staff` | staff-rehab-store | company | catalogue, inventory, store_orders, quote_requests, campaigns, team, notifications, account |
| `d25-multi-org-default` | staff-multi-org | facility | profile, services, practitioners, reservations, offers, notifications, account |
| `d26-multi-org-switched-to-business` | staff-multi-org | company | catalogue, inventory, store_orders, quote_requests, notifications, account |
| `d27-doctor-pending-verification` | dr-pending-samer | practitioner | profile, services, reservations, offers, reviews, notifications, account |

### Dashboard functions: PASS / FAIL / NOT IMPLEMENTED

| Dashboard | Function | Result |
|---|---|---|
| Doctor | profile · medical services · offers · relevant products · reviews · appointments · sponsored · promoted (opt-in) | PASS |
| Nurse | nursing services · offers · relevant suppliers · professional connections | PASS |
| Therapist | therapy services · sessions · rehabilitation products · offers | PASS |
| Hospital | departments · practitioners · staff · recruitment · equipment suppliers · offers | PASS |
| Medical center | services · practitioners · team · offers · recruitment · suppliers | PASS |
| Pharmacy | business profile · eligible categories · suppliers · offers · team | PASS |
| Laboratory | services · equipment & supplies · offers · staffing | PASS |
| Beauty center | aesthetic services · staff · equipment suppliers · offers/promotions · targeted campaign | PASS |
| Beauty center | rule restricting which aesthetic services are "permitted" | NOT IMPLEMENTED (services are free text; no permitted-service list exists) |
| Businesses (6 types) | product management · campaigns · quote requests · team · recruitment | PASS |
| Retail businesses | inventory & stock (low / out) · store orders | PASS |
| Businesses | stock / sale channel / restricted editing in the web product form | PASS (added in this round; server keeps the rules) |
| Property owner/agent | listings · publication · promotions | PASS |
| Property owner/agent | inquiries | NOT IMPLEMENTED (no inquiry model exists) |
| Job seeker | profile · applications · interviews · invitations · relevant jobs · notifications | PASS |
| Patient | profile · store orders · reservations · store · reviews | PASS |
| Patient | "relevant services" recommendations | NOT IMPLEMENTED (only a "find a provider" action; no recommendation logic) |
| Employer/recruiter | jobs · applicants · interviews · invitations · subscription · seats | PASS |
| Administrator | verification queues · jobs/promotions review · campaigns · subscriptions · users · audit | PASS |
| Administrator | user-reported content moderation queue | NOT IMPLEMENTED (no report model; moderation is automatic contact-leak blocking) |
| All | workspace switcher · staff default landing · stale-data protection on switch and account change | PASS (web tests + browser) |
| All | reservation modules switchable off (`RESERVATIONS_ENABLED`) | PASS (backend test) |

### Dashboard security tests (backend `apps/workspaces/tests/test_dashboard.py`, web tests)

| Case | Result |
|---|---|
| Anonymous refused | PASS |
| Forged / foreign workspace id → 404 (patient, owner of another business) | PASS |
| Revoked membership → 404, falls back to personal | PASS |
| Suspended organization (owner deactivated) → 404 | PASS |
| Role escalation: STAFF / VIEWER never get team, campaigns, recruitment, owner feeds | PASS |
| MANAGER gets team + campaigns, never recruitment | PASS |
| Facility member never gets sponsored / promoted / B2B catalogue / buyer quotes | PASS |
| Sponsored and promoted follow verification and preferences (unverified: none) | PASS |
| Tenant isolation of store statistics | PASS |
| No buyer e-mail, phone or address in the dashboard payload | PASS |
| `Cache-Control: private, no-store` | PASS |
| Web: switching workspace never shows the previous organization; forged id shows refusal only | PASS |
| Web: logout and login as another account never shows the previous account's data | PASS |
| Live matrix: every listed workspace opens; forged ids 404 for every user type | PASS |
