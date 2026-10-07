#!/usr/bin/env python
"""EXPLAIN (ANALYZE, BUFFERS) every SQL statement behind the hot read endpoints.

    cd backend && DATABASE_URL=postgres://localhost/racheeta_perf DEBUG=false ... \
        python ../scripts/perf/explain_api_queries.py [--analyze] [--full]

Run it against a LOCAL database filled by `manage.py seed_synthetic` (see docs/PERFORMANCE.md).
It issues real requests through Django's test client (no network), captures the SQL the views
produce, and asks PostgreSQL for the plan of each SELECT. Read-only; it refuses a non-local host.
Output is a compact summary per endpoint (--full also prints every plan). Nothing here is a
pass/fail threshold: it is evidence for deciding whether an index is justified.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from apps.accounts.models import Account  # noqa: E402
from apps.geography.models import Governorate  # noqa: E402

LOCAL = {"", "localhost", "127.0.0.1", "::1"}
SEQ = re.compile(r"Seq Scan on (\w+)")
EXEC = re.compile(r"Execution Time: ([\d.]+) ms")
ROWS = re.compile(r"Seq Scan on (\w+)\s+\(cost=[\d.]+\.\.[\d.]+ rows=(\d+)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze", action="store_true", help="run ANALYZE first (fresh stats)")
    parser.add_argument("--full", action="store_true", help="print every full plan")
    args = parser.parse_args()

    host = connection.settings_dict.get("HOST") or ""
    if host not in LOCAL and not host.startswith("/"):
        print(f"refusing: database host {host!r} is not local", file=sys.stderr)
        return 2
    if args.analyze:
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")

    gov = Governorate.objects.order_by("slug").first()
    user = Account.objects.filter(email__startswith="loadtest-user-").first()
    endpoints = [
        ("providers list", "/api/v1/providers", None),
        ("providers list, governorate filter", f"/api/v1/providers?governorate={gov.pk}", None),
        ("providers list, name search", "/api/v1/providers?search=Synthetic%20Provider%20ab", None),
        ("jobs list", "/api/v1/jobs", None),
        ("jobs list, governorate filter", f"/api/v1/jobs?governorate={gov.pk}", None),
        ("jobs list, text search", "/api/v1/jobs?q=nurse", None),
        ("real-estate listings", "/api/v1/real-estate/listings", None),
        (
            "real-estate listings, governorate filter",
            f"/api/v1/real-estate/listings?governorate={gov.pk}",
            None,
        ),
        ("geo governorates", "/api/v1/geo/governorates", None),
    ]
    if user is not None:
        endpoints += [
            ("notifications (many rows, one user)", "/api/v1/notifications/", user),
            ("notifications unread count", "/api/v1/notifications/unread-count/", user),
        ]

    client = APIClient()
    for label, url, account in endpoints:
        client.force_authenticate(user=account)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url, HTTP_HOST="localhost", secure=True)
        print(f"\n## {label}\n   GET {url} -> {response.status_code}, {len(captured)} queries")
        for n, query in enumerate(captured.captured_queries, 1):
            sql = query["sql"]
            if not sql.lstrip().upper().startswith("SELECT"):
                continue
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql)
                plan = "\n".join(row[0] for row in cursor.fetchall())
            ms = EXEC.search(plan)
            seqs = ", ".join(f"{t} (~{r} rows)" for t, r in ROWS.findall(plan)) or "none"
            kind = "count" if "COUNT(*)" in sql.upper() else "rows"
            print(f"   q{n} [{kind}] {ms.group(1) if ms else '?'} ms; seq scans: {seqs}")
            if args.full:
                print("      " + plan.replace("\n", "\n      "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
