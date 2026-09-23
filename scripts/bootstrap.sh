#!/usr/bin/env bash
# One-shot local setup. Safe to re-run. See docs/DEVELOPMENT.md.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

echo "==> Python virtualenv"
[ -d backend/.venv ] || "$PYTHON" -m venv backend/.venv
backend/.venv/bin/pip install --quiet --upgrade pip
backend/.venv/bin/pip install --quiet -r backend/requirements/dev.txt

echo "==> .env"
if [ ! -f .env ]; then
  cp .env.example .env
  KEY="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(64))')"
  # Portable in-place replacement (BSD and GNU sed).
  sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=${KEY}|" .env && rm -f .env.bak
  echo "    created .env with a fresh SECRET_KEY — review DATABASE_URL before continuing"
else
  echo "    .env already exists, leaving it untouched"
fi

echo "==> Database"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d postgres
else
  echo "    docker not found: make sure PostgreSQL is running and DATABASE_URL in .env points to it"
fi

echo "==> Migrations"
( cd backend && .venv/bin/python manage.py migrate )

echo "==> Web dependencies"
( cd web && npm ci --no-audit --no-fund )

cat <<'MSG'

Done. Next:
  make backend-run    # http://localhost:8000/api/docs/
  make web-run        # http://localhost:5173
  make test
MSG
