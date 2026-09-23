#!/usr/bin/env bash
# Regenerates docs/api/openapi.yaml — the committed API contract. CI fails if stale.
set -euo pipefail
cd "$(dirname "$0")/../backend"
mkdir -p ../docs/api
.venv/bin/python manage.py spectacular --file ../docs/api/openapi.yaml --validate --settings=config.test_settings
echo "wrote docs/api/openapi.yaml"
