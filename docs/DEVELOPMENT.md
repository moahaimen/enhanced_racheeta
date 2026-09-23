# Development

## Prerequisites

- Python 3.12+ (3.13 used in CI and Docker)
- Node.js 22+ and npm
- PostgreSQL 16 — via Docker (`docker compose up -d`) or a local install
- `make` (optional convenience)

## First-time setup

```bash
git clone <repo> racheeta-platform
cd racheeta-platform
./scripts/bootstrap.sh
```

The script creates `backend/.venv`, installs dependencies, copies
`.env.example` to `.env` with a generated `SECRET_KEY`, starts PostgreSQL via
Docker if available, runs migrations and installs web dependencies.

Without Docker: run PostgreSQL yourself, create a database, and set
`DATABASE_URL` in `.env` (e.g. `postgres://<user>@localhost:5432/racheeta_dev`).

## Manual equivalent

```bash
# backend
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements/dev.txt
cp .env.example .env            # then edit SECRET_KEY and DATABASE_URL
cd backend && .venv/bin/python manage.py migrate && cd ..

# web
cd web && npm ci && cd ..
```

## Run

```bash
make backend-run   # http://localhost:8000  (API docs: /api/docs/, admin: /admin/)
make web-run       # http://localhost:5173  (proxies /api and /health to :8000)
```

Create an administrator:

```bash
cd backend && .venv/bin/python manage.py createsuperuser
```

## Test, lint, build

```bash
make backend-test     # pytest (creates test_<db> automatically)
make backend-lint     # ruff check + format check
make backend-check    # django check + missing migrations
make web-test         # vitest
make web-lint         # tsc + oxlint
make web-build        # production build to web/dist
make check            # everything CI runs
make openapi          # regenerate docs/api/openapi.yaml (commit the result)
```

Format Python: `make backend-format`.

## Environment variables

All documented in `.env.example`. A single `.env` at the repository root serves
both backend (django-environ) and web (Vite `envDir: '..'`; only `VITE_*`
variables reach the browser).

## Conventions

- Python: ruff (line length 100), type hints on public functions, tests next to
  the module in `apps/<app>/tests/`, cross-cutting tests in `backend/tests/`.
- TypeScript: strict mode, `noUncheckedIndexedAccess`; every `fetch` goes
  through `web/src/api/client.ts`; every backend-connected button uses
  `ApiActionButton`; every data page uses `AsyncPage`.
- Commits: conventional style (`feat(accounts): …`, `docs: …`, `chore: …`).
- Every session ends by updating `docs/HANDOFF.md` and `docs/PROGRESS.md`.

## Serving the web build from Django locally

```bash
cd web && npm run build && cd ..
SPA_DIST_DIR=$PWD/web/dist make backend-run   # http://localhost:8000/
```
