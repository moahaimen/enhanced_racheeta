# Specialized dashboard audit (2026-11-07)

LOCAL ONLY. The composer refactor (`bfb77e1`) kept 233/233 demo payloads identical. That proves the
refactor changed nothing; it does not prove each profession has every action it needs. This audit
checks that directly.

## Method

1. **Data.** Every workspace of every demo account (46 distinct kind/subtype/role/account-type
   shapes) was composed against the guarded local demo database, inside a transaction that was
   rolled back. Its actions and modules were recorded.
2. **Required workflows.** For each profession, the workflows the platform supports for it were
   listed and compared with what its dashboard offers (action or module link).
3. **Browser.** After logging in through the real form, the runner opened every primary action on
   the dashboard of 26 accounts: 112 destinations, 12 accounts in Arabic and 14 in English (each in
   its login language). Each had to end on a working page, with no refusal marker, no "not found"
   and no error state. 26/26 passed (`local-demo/platform_acceptance.mjs`, `dashboard actions
   open working pages`).
4. **Pinned.** `apps/workspaces/tests/test_dashboard_audit.py` pins the required actions per
   profession, with booking ON and OFF, and the three gaps below. 9 of its tests fail on the code
   before this audit; the other 19 pin behaviour that was already right.

Status key: **PASS** = every required workflow reachable from the dashboard ·
**PARTIAL** = reachable with a stated gap · **NOT IMPLEMENTED** = the platform has no such workflow.

## Gaps found and fixed

| # | Who | Gap | Fix |
|---|---|---|---|
| 1 | B2B-only sellers: scientific office, pharmaceutical company, pharma distributor, medical company | An accepted quote becomes an order (the demo's Ibn Sina office has one), but orders and the commission statement were shown only to retail sellers. The API already served them to these sellers. | Orders action and module (variant `b2b`, "Orders from accepted quotes") and the statement module for every seller whose role can see them. Inventory stays retail-only. |
| 2 | Finance staff | The dashboard had no way to reach the marketplace finance console. | "Marketplace finance" action for accounts with `ledger.change_settlementbatch`. The server still checks the permission on every call. |
| 3 | Anyone who asks about a property (patient, practitioner, facility or company owner) | Their own inquiries were only in the sidebar. The asker side was not on the dashboard. | "My property inquiries" action and module (open / answered / total and the latest five), shown once the account has asked. Organization staff never see the owner's personal inquiries. |

## Matrix

| Profession (demo account) | Primary actions | Modules | Status |
|---|---|---|---|
| Doctor (dr-ahmed-jabouri), dentist (dr-noor-dentist) | edit profile, offers, marketplace (verified only); appointments when booking is ON; my inquiries once asked | profile, medical services, offers, reviews, relevant products, my quotes, sponsored, promoted | PASS |
| Nurse (nr-hanan-saidi), midwife (mw-huda-midwife) | same as doctor | nursing services, facility connections (join requests) instead of reviews, suppliers | PASS |
| Therapist (th-layla-nuaimi) | same as doctor | therapy services, sessions, rehabilitation products | PASS |
| Pharmacy (amal-pharmacy) | Facility workspace: edit profile, offers, team, recruitment, marketplace. Store workspace: products, advertising, store orders, quote requests, team | facility: product categories, suppliers, my quotes, sponsored. Store: catalogue, inventory, orders, finance (20% commission), campaigns | PASS |
| Hospital (dijla-hospital) | edit profile, offers, team, recruitment, marketplace | departments, practitioners, team, recruitment, equipment suppliers, my quotes, sponsored. Appointments when booking is ON | PASS |
| Medical center (fayhaa-center) | same as hospital | clinics, practitioners, team, suppliers | PASS |
| Laboratory (zahraa-labs) | same as hospital | lab tests, lab supplies, sponsored (the live lab campaign now shows here) | PASS for the platform's workflows. Lab test orders and results: NOT IMPLEMENTED (no such platform feature) |
| Beauty center (lamsa-beauty) | same as hospital | aesthetic services, promotions (offers variant), equipment suppliers | PASS |
| Facility staff (reception, viewer, manager) | open workspace (team page scoped to their role) | only what their role allows | PASS |
| Retail seller (company-rehab-mobility, equipment and supplies offices) | products, advertising, store orders, quote requests, team | catalogue, inventory, orders, finance, quote requests, campaigns, team, recruitment | PASS |
| B2B-only seller (company-ibn-sina-scientific, pharma companies) | products, advertising, orders, quote requests, team | catalogue (restricted-B2B count), orders from accepted quotes, finance, quote requests, campaigns | PASS (fixed, gap 1) |
| Seller staff (finance, fulfillment, stock, editor, viewer) | per role capability | per role capability; finance only with `company.finance.view` | PASS |
| Healthcare employer (hospital, center, lab, company as employer) | employer workspace, post a job, find candidates | jobs, applicants, interviews, invitations, subscription and seats | PASS |
| Non-healthcare employer (employer-rafidain-tech) | same | same; talent scoped to non-clinical professions | PASS |
| Recruiter (recruiter-dijla) | same | same, within their membership | PASS |
| Job seeker (seeker-biomed-ali, seeker-ahmad) | edit résumé, find jobs, my applications | résumé, applications, interviews, invitations, matching jobs | PASS |
| Property owner / agent (seller-mansour-properties) | manage listings, inquiries | listings, promotions, inquiries (owner side) | PASS |
| Property asker (patient-sara, dr-dalia-tamimi) | my property inquiries | my property inquiries | PASS (fixed, gap 3) |
| Patient (patient-ali) | store, my orders, find a provider; my reservations when booking is ON | my orders, store, my reviews | PARTIAL: with booking OFF, past reservations are reached from the sidebar ("Reservation history"), and new reviews (written after a completed booking) stop with booking. This is the sunset by design. |
| Setup accounts (employer-setup-new, jobseeker-setup-new) | complete setup | setup step | PASS |
| Admin / support (local-admin, local-support) | admin console, review promotions | verification, moderation, campaigns, subscriptions, users, audit | PASS |
| Finance (local-finance) | + marketplace finance | same | PASS (fixed, gap 2) |

## Not covered

- **Mobile app:** its dashboards were not audited or changed.
- **Lab test orders and results, prescriptions, insurance:** these workflows do not exist on the
  platform. They are not reported as dashboard gaps.
