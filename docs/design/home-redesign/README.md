# Homepage redesign — evidence (Phase 12B)

Screenshots of the **real rendered application** (production build served by Django, a local
database filled by `seed_demo_data`), captured in the built-in browser at 1440 px (desktop) and
390 px (mobile). They are the downsized captures the tool produces (≈ 800 px wide); the layout
checks (no horizontal overflow, console, network) were done on the live page.

| File | View |
| --- | --- |
| `ar-desktop-1-hero.jpg` … `ar-desktop-6-why-cta.jpg` | Arabic RTL desktop, top to bottom |
| `ar-mobile-1-hero.jpg` … `ar-mobile-4-facilities.jpg` | Arabic RTL mobile (390 px) |
| `en-desktop-1-hero.jpg`, `en-desktop-2-doctors.jpg` | English LTR desktop |

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

Reference: the approved concept art (`04_final_merged_direction.png`) is not stored in the repository.
