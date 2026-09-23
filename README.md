# Racheeta Platform

Racheeta 2.0 — a medical services platform (providers, reservations, offers,
jobs, medical marketplace, medical real estate, advertising) rebuilt from
scratch as a secure, low-cost, owner-controlled modular monolith.

**Owner:** Moahaimen Talib. All rights reserved — see [LICENSE](LICENSE).

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.13 · Django 5.2 LTS · Django REST Framework · PostgreSQL 16 · JWT |
| Web | React 19 · TypeScript · Vite · Arabic-first RTL · i18next |
| Mobile | Flutter (planned) — same `/api/v1/` API |
| Hosting | One container (Dockerfile) + one PostgreSQL on Railway |

## Quick start

```bash
./scripts/bootstrap.sh     # venv, deps, .env, PostgreSQL (docker), migrations, npm ci
make backend-run           # http://localhost:8000/api/docs/
make web-run               # http://localhost:5173
make check                 # lint, checks, tests, build — same as CI
```

Full instructions: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Documentation

| Document | Content |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System shape, repository layout, module conventions |
| [docs/API.md](docs/API.md) | Conventions, error envelope, implemented endpoints |
| [docs/api/openapi.yaml](docs/api/openapi.yaml) | The API contract (generated, CI-checked) |
| [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) | Tokens, flows, client behaviour |
| [docs/PERMISSIONS.md](docs/PERMISSIONS.md) | Roles and capability codes |
| [docs/SECURITY.md](docs/SECURITY.md) | Rules and where each is enforced |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema and migration rules |
| [docs/RAILWAY.md](docs/RAILWAY.md) | Deployment configuration |
| [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) | Database backup and restore |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup and commands |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision log |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Milestone progress |
| [docs/HANDOFF.md](docs/HANDOFF.md) | **Start here** for every new working session |

## Working rules

The repository is the memory. Every coding session — human or AI — starts by
reading `docs/HANDOFF.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md` and
`docs/ARCHITECTURE.md`, and ends by updating `docs/HANDOFF.md` and
`docs/PROGRESS.md`. Secrets never enter git. See the master plan for the full
rule set.
