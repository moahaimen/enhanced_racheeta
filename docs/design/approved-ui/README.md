# Approved web UI — implementation evidence (ADR-065)

Screenshots of the **real application** (Vite dev server against the Django API with a local
PostgreSQL database filled by `seed_demo_data`), captured with headless Chromium at the exact
viewport in each file name (device scale 1). Data on every card comes from the existing APIs.

| File | View |
| --- | --- |
| `home-ar-1440.jpg`, `home-ar-1440-full.jpg` | Homepage, Arabic RTL, 1440 × 900 (first screen / full page) |
| `home-ar-1024.jpg` | Homepage, laptop 1024 × 768 |
| `home-ar-768.jpg` | Homepage, tablet 768 × 1024 |
| `home-ar-390-full.jpg` | Homepage, phone 390 × 844 (full page) |
| `home-en-1440.jpg` | Homepage, English LTR, 1440 × 900 |
| `providers-ar-1440.jpg`, `providers-ar-390.jpg` | Doctor/provider directory (filter sidebar; filters collapse on phones) |
| `provider-profile-ar-1440.jpg` | Provider profile |
| `jobs-ar-1440.jpg` | Jobs directory |
| `login-ar-1440.jpg` | Login |
| `dashboard-patient-ar-1440.jpg`, `dashboard-patient-ar-390.jpg` | Patient dashboard with the workspace sidebar (phone: menu) |
| `company-ar-1440.jpg` | Medical-company workspace |
| `provider-reservations-ar-1440.jpg` | Provider appointments & reservations |

Automated layout audit at the time of capture: 142 page loads (every role's main pages; Arabic at
1440/1024/768/390, English at 1440/390) — `scrollWidth == clientWidth`, no element outside the
viewport, body background `#E9EEF2` on every page, exactly one `h1`, no unnamed button/link, no
unlabeled form control, no console error besides the expected 401/403/404 gates.
