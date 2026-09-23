# Progress

Phases from `MASTER_PLAN.md` §28. Status: `done` · `partial` · `not started`.

| Phase | Status | Notes |
| --- | --- | --- |
| 0 — Foundation | **done** | Monorepo, git hygiene, docs, docker-compose, Django, React, CI, env config, `/health/`, OpenAPI, tests. Dockerfile written but not built locally (no Docker on the dev machine); CI/Railway will be the first real build. |
| 1 — Accounts & Authentication | **partial** | Done: custom `Account`, email login, register/login/refresh/logout, `/me` (GET/PATCH), roles + capability registry, permission classes, tests. Not done: Firebase token exchange, email verification, password reset, admin account-management endpoints, web login/register pages. |
| 2 — Providers & Medical Services | not started | |
| 3 — Reservations | not started | |
| 4 — Reviews & Offers | not started | |
| 5 — Jobs | not started | |
| 6 — Medical Marketplace | not started | |
| 7 — Medical Real Estate | not started | |
| 8 — Advertising & Payments | not started | Gateway choice is the owner's decision. |
| 9 — Chat & Notifications | not started | |
| 10 — Dashboards & Analytics | not started | |
| 11 — Mobile (Flutter) | not started | `mobile/README.md` records the constraints. |
| 12 — Production Hardening | not started | |

## Milestone log

- **2026-09-23** — Phase 0 complete; Phase 1 foundation (Account, JWT auth, `/me`) complete. 57 backend tests, 12 web tests. Pushed to https://github.com/moahaimen/enhanced_racheeta; CI green on `30f23ab`.
