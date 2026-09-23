# Progress

Phases from `MASTER_PLAN.md` §28. Status: `done` · `partial` · `not started`.

| Phase | Status | Notes |
| --- | --- | --- |
| 0 — Foundation | **done** | Monorepo, git hygiene, docs, docker-compose, Django, React, CI, env config, `/health/`, OpenAPI, tests. Dockerfile not yet built locally (no Docker on the dev machine). |
| 1 — Accounts & Authentication | **done** | Custom `Account`, email login, register/login/refresh/logout, `/me` (GET/PATCH), roles + capability registry, permission classes, password reset, email verification (timestamp state, no gating), Firebase exchange behind an adapter (disabled until the owner provides credentials — activation is configuration only), web routing + session layer + login/register/profile/forgot/reset/verify pages, full test coverage, docs. Deferred to later phases by design: admin account-management endpoints (Phase 10 admin dashboard), phone-only Firebase sign-in (ADR-018), password change for logged-in users. |
| 2 — Providers & Medical Services | not started | Next. |
| 3 — Reservations | not started | |
| 4 — Reviews & Offers | not started | |
| 5 — Jobs | not started | |
| 6 — Medical Marketplace | not started | |
| 7 — Medical Real Estate | not started | |
| 8 — Advertising & Payments | not started | Gateway choice is the owner's decision. |
| 9 — Chat & Notifications | not started | |
| 10 — Dashboards & Analytics | not started | Includes admin account management. |
| 11 — Mobile (Flutter) | not started | `mobile/README.md` records the constraints. |
| 12 — Production Hardening | not started | Includes CSP, httpOnly refresh cookie evaluation, email provider, background email sending, blacklist pruning job. |

## Milestone log

- **2026-09-23** — Phase 0 complete; Phase 1 foundation (Account, JWT auth, `/me`) complete. 57 backend tests, 12 web tests. Pushed to https://github.com/moahaimen/enhanced_racheeta; CI green on `30f23ab`.
- **2026-09-23** — Phase 1 complete on branch `feat/phase1-auth-completion`: password reset, email verification, Firebase adapter, web routing/session/auth pages. 104 backend tests, 49 web tests. Browser walkthrough against the local backend: register → verify email → edit profile → logout → login → reset password → login with new password.
