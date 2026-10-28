# Final web readiness — Racheeta web platform (web + backend + staging)

**Date:** 2026-10-27 · **`main`:** `83ac6dd2363c6ce256402885d3fea10c0249248b` ·
**Branch under review:** `feat/phase12b-demo-data-final` (PR head in the PR description) ·
**Scope:** the web application, the backend and the Railway staging environment. The Flutter app,
Android/iOS builds, Firebase mobile clients and store submissions are **out of scope** for this
phase (nothing under `mobile/` changed; the existing CI mobile jobs run unchanged).

## 1. COMPLETE — product areas (merged on `main`)

| Area | State | Evidence |
| --- | --- | --- |
| Accounts & auth (register, login, refresh, logout, `/me`, password reset, e-mail verification, roles/capabilities) | complete | Phase 1, backend + web tests |
| Providers, facilities, services, memberships, verification; public directory & profile; booking discovery | complete | Phases 2, 4 |
| Reservations (availability slots, booking, lifecycle, provider management) | complete | Phase 4 |
| Reviews & provider offers | complete | Phase 5 |
| Medical marketplace (verified companies, categories, audience rules, B2B targeted products, company workspace) | complete | Phase 6 |
| Medical real estate (sellers, listings, owner workspace, public directory & detail) | complete | Phase 7 |
| Advertising campaigns & manual payment verification | complete | Phase 8 |
| Notifications & chat (persistent, reservation context) | complete | Phase 9A/9B |
| Billing, entitlements, medical jobs, employer workspace, applicants, talent search, job-seeker profile & applications | complete | Phase 3 |
| Role-aware dashboards, admin console (verification, billing, job review, advertising review, audit) | complete | Phase 10 |
| Production hardening (readiness, request ids, JSON logs, CSP/security headers, config checks, throttling, docs gating, backup/restore scripts, container smoke) | complete | Phase 12A, PR #20 |
| Resend HTTPS e-mail transport | complete | PR #21 |
| Premium public homepage (self-hosted Cairo, API-driven sections, workspace header menu, entitlement-aware CTAs) | complete | PR #23 |
| **Reversible fictional demo dataset** (`seed_demo_data` / `clear_demo_data`) | complete, **in this PR** | ported from PR #22; `docs/DEMO_DATA.md`, ADR-063 |

## 2. This PR (final web readiness) — what changed

1. **Demo dataset ported onto current `main`** (two cherry-picked commits; the only conflicts were
   in `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`, resolved by keeping both sides).
   Architecture unchanged: registry-owned rows, idempotency keys, one transaction per phase,
   fail-closed cleanup (ADR-063). Local lifecycle run: `seed --dry-run` → `seed` (1 469 registered
   rows) → `seed` again (no new rows) → `clear --dry-run --yes` → `clear --yes` (1 526 rows incl.
   side effects removed, "Staging is clean") → `seed` (1 469 again).
2. **CSP tightened** to `style-src 'self'; font-src 'self'` (`backend/apps/core/middleware.py`):
   Cairo is bundled since ADR-064, so no third-party origin remains in the policy; tests updated.
3. **Two mobile-width web defects fixed** (found by the audit in §3): the employer workspace tab
   strip and the advertising campaign form widened the page at 390 px (`1fr` grid tracks let a
   non-wrapping child grow the page; now `minmax(0, 1fr)` + `min-inline-size: 0` on form fields).
4. **"My applications" without a résumé** showed two generic "Something went wrong — Retry" blocks
   for an expected 403; it now shows one explained empty state with a link to create the résumé
   (test added).
5. **Documentation brought to reality**: `STAGING`, `RAILWAY`, `OPERATIONS`, `BACKUP_RESTORE`,
   `PERFORMANCE`, `PRODUCTION_DEPLOYMENT`, `DEMO_DATA`, `SECURITY`, `HANDOFF`, `PROGRESS`,
   ADR-063/064; new `docs/ACCOUNT_DELETION_REVIEW.md` (owner decision, nothing implemented).

No backend business logic, API contract (`docs/api/openapi.yaml` unchanged and fresh), migration
other than the ported `demo/0001`, or dependency changed. No mobile file changed.

## 3. VERIFIED — what was actually run (2026-10-27)

### 3.1 Backend (local, PostgreSQL 16)
`ruff check` clean · `ruff format --check` 361 files · `manage.py check` 0 issues ·
`makemigrations --check` no changes · OpenAPI regenerated = committed file ·
**full suite 1 981 passed, 1 skipped** (the skip: `firebase_admin` is a production-only dependency
not installed in the dev venv) · demo suite 49 tests (part of the total) including idempotency, atomic phase ownership under injected failures (registry write, deferred hook, mid-phase), credential non-rotation,
seed→clear→seed and real-data preservation (real booking on a demo provider, real application to a
demo job, real review of a demo provider, reference geography/specialties) · `git diff --check`
clean · gitleaks: no leaks.

### 3.2 Web (local)
`tsc -b` clean · `oxlint` 0 errors (the 5 pre-existing warnings on `main` are unchanged) ·
**499 tests passed in 45 files** · production build OK (JS 854 kB / CSS 80 kB, same as `main`).

### 3.3 End-to-end web audit against the seeded database (local, headless Chromium)
**248 page loads**: anonymous (homepage, directory, provider profile, facilities, jobs, job detail,
employer page, real estate, listing detail, login, register, forgot password), patient (dashboard,
reservations, notifications, messages + thread, profile, résumé, applications, provider profile with
booking), provider (dashboard, profile, reservations, offers, marketplace + product, messages,
notifications, employer entry), facility/employer owner (dashboard, employer workspace, job editor,
applicants, talent search, new job), medical company (dashboard, company workspace, advertising,
employer, notifications), real-estate seller (dashboard, owner workspace, profile), job seeker
(dashboard, résumé, applications), staff (dashboard, admin console) — Arabic at **1440, 1280, 1100,
768, 390** for the public/patient/provider sets and 1440 + 390 for the rest; English at 1440 + 390
for the public, patient and provider sets.

Checked per page: `scrollWidth == clientWidth`, exactly one `h1`, no unnamed button/link, no
unlabeled form control, no `<img>` without `alt`, every `<img>` with `width`/`height`, no broken
image, no third-party origin, console errors, failed requests. Result after the fixes in §2:
**no overflow, no unnamed/unlabeled control, no image defect, no external request, no console
error** other than the expected `401` before token refresh, the `404` "no employer organisation yet"
and the `403` entitlement/profile gates, each of which the UI presents as an explained state (the
talent-search gate says "Your current plan does not include this feature"; the homepage never links
there without entitlement — ADR-064). Heading levels skip h2→h4 inside long forms (fieldset
headings) on 6 pages — a structural nit, not a defect; left as is.
Keyboard: the header workspace menu opens with Enter, Tab enters it, Escape closes it and returns
focus (automated tests `SiteHeader.test.tsx`); focus rings are global (`:focus-visible`);
`prefers-reduced-motion` honoured in 13 stylesheets. Demo data populates every homepage section
(36 providers, 21 published jobs, 19 listings, 10 categories, 14 specialties), the dashboards,
notifications, chat, employer/company/provider workspaces (screenshots were reviewed; evidence files
are not committed, the audit is reproducible with the seeded database).

### 3.4 Assets / performance (homepage, PR #23)
Hero: WebP cut-out 24 kB (14 kB variant under 768 px) with `fetchPriority="high"`, `width`/`height`
set; six service pictures 5–13 kB WebP, `loading="lazy"`, `alt=""`; backdrop is inline SVG; Cairo
self-hosted (≈ 82 kB woff2 for the three subsets); no hotlink, no external request at all.

### 3.5 Staging (`https://racheeta-app-staging.up.railway.app`, from outside)
`/health/` 200 · `/ready/` 200 · HTTP→HTTPS 301 · HSTS, CSP, `X-Frame-Options: DENY`, `nosniff`,
COOP, Permissions-Policy, `Referrer-Policy: no-referrer` present · `/api/docs/` 404 ·
web bundle served = the bundle a local production build of `main` produces · Arabic (RTL) and
English (LTR) at 1440 and 390 on `/`, `/providers`, `/jobs`, `/real-estate`, `/login`: no overflow,
Cairo loaded, 0 console errors, 0 CSP violations. Database **unseeded** (counts 0). Full
classification: `docs/STAGING.md` §3/§5.

### 3.6 Backup / restore
`backup_restore_smoke.sh` on the local seeded database: dump + checksum + restore into a scratch
database + `migrate`/`check` + identical row counts + refusal of non-empty target and corrupted
dump — **7 s**. Also runs in CI on every push. Not yet run against the **staging** database
(needs its `DATABASE_URL` from the Railway dashboard; procedure in `docs/STAGING.md` §3.4).

### 3.7 Security closure (unchanged hardening, re-checked)
Object ownership and role gates are enforced server-side (permission classes + capability registry;
audited by the role walk in §3.3 — every cross-role page answered 403/404 and the UI never leaked
data) · CSRF trusted origins and CORS from environment, `SESSION/CSRF_COOKIE_SECURE` behind
`SECURE_PROXY_SSL` · CSP now self-only · throttles: auth 10/min, password reset 5/min, e-mail
verification 3/min, job/apply/talent/message rates per `settings.py` · log redaction of bearer/JWT/
`token=`/`password=`/e-mail · API docs off unless `API_DOCS_ENABLED` · health/readiness probes ·
no secret in git (gitleaks over 352 commits).

## 4. NOT VERIFIED — needs Railway dashboard / variable / shell access (engineer can do it)

| Item | How |
| --- | --- |
| Staging deploy log (`check`, migrations, gunicorn) | Railway deploy log |
| `scripts/smoke_http.sh https://racheeta-app-staging.up.railway.app` | any machine with curl (expected `SMOKE PASSED`) |
| `/ready/` 503 when Postgres is stopped; failed-deploy keeps the previous deployment | Railway dashboard, outside a demo |
| Backup/restore round trip against the staging database, measured RTO | `SOURCE_DATABASE_URL=<staging DATABASE_URL> scripts/backup/backup_restore_smoke.sh` (writes only to a new scratch DB) |
| `prune_expired_tokens --dry-run` in the service shell | `railway ssh` |
| Signed-in web walk on staging (dashboards, booking, chat, notifications) | after seeding (`docs/STAGING.md` §6) |
| Staging e-mail delivery (reset + verification mails, headers, broken-credential behaviour, no token in logs) | needs a mailbox the owner controls + the Railway variables; see §5 |
| Rollback rehearsal (tier 1, tier 3) | Railway dashboard |

## 5. E-mail classification

* Transport: Resend over HTTPS, in code and tested (PR #21). Whether `RESEND_API_KEY` /
  `DEFAULT_FROM_EMAIL` are set on the staging service is only visible in the dashboard.
* **Staging e-mail: functional-but-restricted at best** — until a sending domain is verified in
  Resend, Resend delivers only to the account owner's own address from its onboarding sender.
  That is acceptable for staging and **does not block the web demo** (demo accounts are
  pre-verified; no mail is needed to log in).
* **Production sending domain (SPF/DKIM/DMARC) and API key: OWNER prerequisite** for 12C.

## 6. OWNER — inputs and decisions (not engineering)

| Item | Needed for |
| --- | --- |
| Review + merge authorisation of this PR; then seed staging per `docs/STAGING.md` §6 (`DEMO_DATA_ENABLED=true`, `DEMO_PASSWORD`) | demo-ready staging |
| Mailbox/phone for the e-mail and two-network throttle checks on staging | closing §4 |
| Production domain + DNS; production Resend domain/key; Railway production plan approval; off-site backup destination; monitoring recipients; admin 2FA/access policy; privacy policy / terms / retention statement; on-call person | production (12C) — `docs/PRODUCTION_DEPLOYMENT.md` §1 |
| Account-deletion policy decision (`docs/ACCOUNT_DELETION_REVIEW.md`) | required before any store submission; recommended before production for the web too |
| Image-rights confirmation for the derived homepage photographs (`docs/PROVENANCE.md`) | before production launch |
| Visual direction of the optional warm-cream / teal design exploration (local branch `wip/warm-cream-redesign`, not in any PR) | optional |

## 7. REMAINING ENGINEERING (after this PR)

* Seed staging and run the signed-in staging walk (§4) — one hour with dashboard access.
* Account deletion (if the owner picks option B): one bounded PR (service + endpoint + two screens +
  public page + tests).
* Optional: heading-level tidy-up in long forms; load test on staging (`docs/PERFORMANCE.md`).
* Mobile phase (out of scope here): `docs/MOBILE_RELEASE.md` §13 blockers remain as documented.

## 8. Verdict

* **ENGINEERING READY — yes** for the web platform: code complete, tests green, demo dataset ported
  and proven locally, documentation accurate.
* **STAGING READY — yes, pending seed**: the environment is live and verified from outside; it
  becomes *demo-ready* once this PR is merged, deployed and seeded (§6, first row). The dashboard-only
  checks in §4 are not blockers for a demo but must be closed before production.
* **SUBMISSION / PRESENTATION READY (web) — yes for a staging presentation**; **not production** —
  production is blocked only by OWNER inputs (§6), not by engineering.
