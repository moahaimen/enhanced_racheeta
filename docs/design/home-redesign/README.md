# Homepage redesign — evidence (Phase 12B, review round 2)

Screenshots of the **real rendered application**: Vite dev server on `127.0.0.1:5173` against the
Django API with a local PostgreSQL database filled by `seed_demo_data` (the demo-data tooling of
PR #22, run locally only) plus three temporary local accounts (patient, provider, medical company),
captured with headless Chromium at the **exact viewport sizes in the file names** (device scale 1,
full resolution, JPEG). Layout checks ran on the live page at each size: `scrollWidth ===
clientWidth` (no horizontal overflow), no header item outside the viewport, no overlapping header
items, no console errors (besides the expected unauthenticated `401` before token refresh and the
`404` of "no employer yet").

| File | View (viewport) |
| --- | --- |
| `ar-desktop-anonymous-1440.jpg` | Arabic RTL, anonymous, hero — 1440 × 900 |
| `ar-desktop-anon-section-1…6.jpg` | Arabic RTL anonymous page, top to bottom — 1440 × 900 each |
| `ar-desktop-patient-1440.jpg` / `-menu.jpg` | Patient, bar and Workspace menu open — 1440 × 900 |
| `ar-desktop-provider-1440.jpg` / `-menu.jpg` | Provider, bar and menu — 1440 × 900 |
| `ar-desktop-company-1440.jpg` / `-menu.jpg` | Medical company, bar and menu — 1440 × 900 |
| `ar-desktop-provider-1280.jpg` | Provider at 1280 × 800 |
| `ar-desktop-provider-1100-menu.jpg` | Provider at the narrowest desktop width (1100 × 800), menu open |
| `ar-mobile-anonymous-390.jpg`, `ar-mobile-anon-section-1…4.jpg` | Arabic mobile, anonymous — 390 × 844 |
| `ar-mobile-provider-390.jpg` / `-menu.jpg` | Provider on mobile, menu panel with every link — 390 × 844 |
| `en-desktop-provider-1440.jpg` / `-menu.jpg` | English LTR, provider — 1440 × 900 |

Header measurements (all passed): anonymous / patient / provider / company at 1440, provider at 1280 and 1100, provider at 390 — no overflow, nothing clipped, nothing
overlapping. Keyboard: Enter on the Workspace button opens the menu (`aria-expanded=true`), Tab moves
into the first link (`/dashboard`), Escape closes it and returns focus to the button.

Hero: the approved direction is `04_final_merged_direction.png` (not stored in the repository; see
`docs/PROVENANCE.md`). The hero now follows it: aqua orb and towers with palms behind a smiling
practitioner, floating "better health for a better life" chip, headline, subtitle, call to action
and three trust points on the other side, and the search surface overlapping the hero. The
practitioner and service-card pictures are derived WebP images; all text, buttons, search, cards
and navigation are real HTML.

Data sources of each section:

| Section | Endpoint |
| --- | --- |
| Search governorate list | `GET /api/v1/geo/governorates` |
| Platform numbers | `count` of `GET /providers`, `GET /jobs`, `GET /real-estate/listings`; length of `GET /marketplace/categories` |
| Featured doctors | `GET /providers?kind=PRACTITIONER&page_size=12` (top 4 by rating among the page) |
| Hospitals & centers | `GET /providers?kind=FACILITY&page_size=6` |
| Specialty chips | `GET /specialties` |
| Latest jobs | `GET /jobs?page_size=6` |
| Latest properties | `GET /real-estate/listings` |
| Product categories (everyone but providers) | `GET /marketplace/categories` |
| Products (signed-in providers only) | `GET /marketplace/products` (backend-targeted) |
| Hiring call to action | `GET /jobs/employer` + `GET /jobs/employer/billing` for signed-in accounts only |
