# Current State

Date: 2026-09-23
AI/Engineer: Claude (Fable 5.1) via Claude Code
Branch: `feat/phase2-providers` (pushed) — **stacked on `feat/phase1-auth-completion`** because PR #1 (Phase 1 → `main`) was still open when this session started
Last Commit SHA: `1445821` (the commit adding this handoff follows; see `git log -1`)
Remote: `git@github.com:moahaimen/enhanced_racheeta.git` (https://github.com/moahaimen/enhanced_racheeta)

> New session? Read `ARCHITECTURE.md`, `DECISIONS.md`, `PROGRESS.md`, then this
> file. Then run `make check`. Continue from **Exact Next Step**.

## Goal of This Work Session

Phase 2 — Providers and Medical Services: shared provider architecture,
verification, memberships, specialties, services, geography, public
discovery, provider self-management (API + web). No reservations.

## Completed

- **Precondition note:** `main` still lacks Phase 1 (PR #1 open). Phase 2 was
  branched from the Phase 1 branch so it contains everything; merge PR #1
  first, then this branch's PR merges cleanly (or retarget it to `main`
  after #1 lands — GitHub does this automatically).
- Backend apps `geography`, `specialties`, `providers` with migrations,
  seeds (Iraq: 19 governorates, 46 cities; 29 specialties), constraints,
  indexes, permissions, query-count tests. See `ARCHITECTURE.md`,
  `DATABASE.md`, `API.md`, `PERMISSIONS.md`.
- Public discovery (`GET /providers`, `GET /providers/{id}`) limited to
  verified + visible + active providers; filters and ordering; no ratings.
- Owner self-management under `/providers/me` (profile, verification
  request, services, memberships) and an administrator verification endpoint;
  Django admin actions for verification.
- Web: `/providers` (filters in URL, cards, pagination, empty/error states),
  `/providers/:id`, `/provider/profile` (onboarding, edit, verification
  request, services, memberships) — all through `AsyncPage`/`ApiActionButton`;
  `RequireRole` guard; bilingual reference data from the API.
- Browser check against the local backend: discovery list with real seeded
  filters, type filter, public detail, provider login → onboarding → create
  profile → add service.
- Docs updated; ADR-023 … ADR-027 appended; OpenAPI regenerated
  (32 operations) and CI-checked.
- Bug found in the walkthrough and fixed: `/auth/refresh` for a deleted
  account returned 500; now 401 (`RefreshSerializer`, regression tests).

## Files Added

Backend: `apps/geography/*` (+ `seed_iraq.py`, migrations 0001–0002),
`apps/specialties/*` (+ `seed.py`, migrations 0001–0002),
`apps/providers/{types,models,permissions,services,serializers,filters,views,urls,admin}.py`,
`apps/providers/migrations/0001_initial.py`, tests under each app's `tests/`.
Web: `src/api/providers.types.ts`, `src/api/endpoints/{providers,reference}.ts`,
`src/i18n/localized.ts`, `src/pages/providers/{ProvidersPage,ProviderDetailPage,ProviderProfilePage,ProviderForm,ProviderBadges}.tsx`
and tests, `src/test/providerFixtures.ts`.

## Files Modified

`backend/config/{settings,api_v1}.py`, `web/src/app/{routes,guards,AppLayout}.tsx`,
`web/src/api/index.ts`, `web/src/i18n/locales/*`, `web/src/styles/index.css`,
`docs/*`.

## Database Migrations

`geography.0001_initial`, `geography.0002_seed_iraq`,
`specialties.0001_initial`, `specialties.0002_seed_specialties`,
`providers.0001_initial` (tables `providers_profile`, `providers_membership`,
`providers_service`, M2M `providers_profile_specialties`). Applied locally;
run automatically on deploy.

## API Endpoints Added/Changed

Geography (3), specialties (1), providers public (2), self-management (10),
admin (1) — listed in `API.md`. No Phase 1 endpoint changed.

## Architecture Decisions

ADR-023 one provider table with two kinds; ADR-024 discovery = verified +
visible; ADR-025 membership workflow with partial unique index; ADR-026
reference data seeded by migrations, no PostGIS; ADR-027 price + currency.

## Security Decisions

Phase 2 review table in `SECURITY.md`: writes only via `/providers/me`,
admin fields rejected (400), type locked after verification, non-discoverable
profiles 404 everywhere, membership counterpart must be discoverable and of
the other kind, third parties 404, no fabricated statistics, https-only image
URLs, bounded query counts.

## Tests Run

```
make check   # ruff, django check, migrations check, pytest; tsc, oxlint, vitest, vite build
./scripts/export_openapi.sh && git diff --exit-code docs/api/openapi.yaml
```

## Test Results

- Backend: **175 passed** (was 104), ruff clean, checks clean, no migration drift.
- Web: **66 passed** (was 49), tsc clean, oxlint clean, build OK (≈435 kB JS, 132 kB gzip).
- CI: see the Actions run for the branch push (link in the final report).

## Known Problems

- PR #1 (Phase 1) is not merged; this branch's PR must land after it.
- Membership requests take the counterpart's public id (copied from its
  profile page); a name search/invitation UX is deferred.
- Provider logos are https URLs until the media module exists.
- No distance-based search; coordinates are stored only.
- Verification is done through the API/Django admin; the admin dashboard UI
  is Phase 10.
- Throttling and email notes from Phase 1 still apply.

## Incomplete Work

None required by Phase 2. Deferred: see PROGRESS.md (distance search, media
uploads, membership notifications, invitation UX, admin dashboard).

## Required Manual Actions

1. Merge PR #1 (Phase 1), then open/merge the PR for `feat/phase2-providers`:
   https://github.com/moahaimen/enhanced_racheeta/compare/main...feat/phase2-providers?expand=1
2. Verify providers through Django admin (`/admin/`) or
   `POST /api/v1/admin/providers/{id}/verification` — nothing is public until then.

## Environment Variables Added/Changed

None. (`settings.RACHEETA["CURRENCIES"]` is code, not env.)

## Railway/Infrastructure Impact

Five migrations run at container start (seed data included). No new services.

## Exact Next Step

After both PRs merge, start **Phase 3 — Reservations** on `feat/phase3-reservations`:

1. `apps/availability`: provider weekly schedules + exceptions, slot
   generation on the server (no client-side slot math).
2. `apps/reservations`: Reservation with the master-plan state machine
   (PENDING → CONFIRMED → COMPLETED/CANCELLED/NO_SHOW; PENDING → REJECTED/
   CANCELLED), transition log (who/from/to/when/reason), patient booking of a
   ServiceOffering slot, provider management, notification hooks (no-op until
   Phase 9).
3. Web: patient booking flow from the provider detail page; provider
   reservation list under `/provider/profile`; patient reservations under
   `/profile`. All through `AsyncPage`/`ApiActionButton`.
4. Tests, OpenAPI, docs, HANDOFF.

## Recommended Next Prompt

> Read docs/HANDOFF.md, docs/PROGRESS.md, docs/DECISIONS.md and
> docs/ARCHITECTURE.md in racheeta-platform. Confirm PR #1 and the Phase 2 PR
> are merged into `main` and `make check` is green. Then start Phase 3 on
> `feat/phase3-reservations`: availability schedules with server-side slot
> generation, the Reservation model with the controlled state machine and a
> transition log, patient booking and provider management APIs, web booking
> and reservation pages using AsyncPage/ApiActionButton, comprehensive tests,
> regenerated docs/api/openapi.yaml, updated docs (new ADRs), small commits,
> and a final docs/HANDOFF.md + docs/PROGRESS.md update. Do not add payments
> or notifications beyond no-op hooks.
