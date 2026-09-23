# Racheeta Platform — developer shortcuts.
# Every target is a thin wrapper; the real commands are documented in docs/DEVELOPMENT.md.

PY      := backend/.venv/bin/python
PIP     := backend/.venv/bin/pip
MANAGE  := cd backend && .venv/bin/python manage.py

.PHONY: help bootstrap db-up db-down backend-install backend-migrate backend-run backend-test backend-lint backend-format backend-check openapi web-install web-run web-test web-lint web-build test check

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

bootstrap: ## One-shot local setup (venv, deps, .env, migrations)
	./scripts/bootstrap.sh

db-up: ## Start local PostgreSQL via docker compose
	docker compose up -d postgres

db-down: ## Stop local PostgreSQL
	docker compose down

backend-install: ## Install backend dependencies into backend/.venv
	python3 -m venv backend/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements/dev.txt

backend-migrate: ## Apply database migrations
	$(MANAGE) migrate

backend-run: ## Run Django dev server on :8000
	$(MANAGE) runserver 0.0.0.0:8000

backend-test: ## Run backend tests
	cd backend && .venv/bin/python -m pytest

backend-lint: ## Ruff lint + format check
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .

backend-format: ## Ruff auto-format + autofix
	cd backend && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

backend-check: ## Django system checks + missing-migration check
	$(MANAGE) check
	$(MANAGE) makemigrations --check --dry-run

openapi: ## Regenerate docs/api/openapi.yaml from code
	./scripts/export_openapi.sh

web-install: ## Install web dependencies
	cd web && npm ci

web-run: ## Run Vite dev server on :5173
	cd web && npm run dev

web-test: ## Run web unit tests
	cd web && npm test

web-lint: ## TypeScript check + lint
	cd web && npm run typecheck && npm run lint

web-build: ## Production build of the web app
	cd web && npm run build

test: backend-test web-test ## Run all tests

check: backend-lint backend-check backend-test web-lint web-test web-build ## Everything CI runs
