#!/usr/bin/env python3
"""Small, reproducible synthetic load test for Racheeta (standard library only).

    python scripts/loadtest/loadtest.py --base-url http://127.0.0.1:8000 \
        --concurrency 8 --duration 20 [--host-header localhost]

What it does: N worker threads repeatedly GET a fixed mix of read endpoints (public lists plus,
when LOADTEST_EMAIL / LOADTEST_PASSWORD are set, an authenticated notifications list), for a fixed
duration, and prints measured request counts, error counts, status histogram and latency
percentiles per endpoint. It reports ONLY what it measured: no thresholds, no extrapolation. Run it
before and after a change, on the same machine, with the same seed.

Safety:
  * target must be localhost / 127.0.0.1 / ::1 / *.test / *.invalid, otherwise pass
    --allow-host HOSTNAME explicitly (a disposable staging stack you own). It will never be
    pointed at production by default.
  * read-only GETs (plus one login to obtain a token); no writes, no uploads.
  * credentials come from the environment, never from arguments or files; use the synthetic user
    printed by `manage.py seed_synthetic` and the SYNTHETIC_PASSWORD you chose for that run.
  * a built-in ceiling (--max-concurrency, default 64) prevents accidental denial of service.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

SAFE_SUFFIXES = (".test", ".invalid", ".localhost")
SAFE_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}

PUBLIC_MIX = [
    ("providers", "/api/v1/providers"),
    ("jobs", "/api/v1/jobs"),
    ("jobs-search", "/api/v1/jobs?q=nurse"),
    ("listings", "/api/v1/real-estate/listings"),
    ("governorates", "/api/v1/geo/governorates"),
    ("ready", "/ready/"),
]
AUTH_MIX = [("notifications", "/api/v1/notifications/")]


def check_target(base_url: str, allow_host: str | None) -> str:
    host = urllib.parse.urlsplit(base_url).hostname or ""
    if host in SAFE_HOSTS or host.endswith(SAFE_SUFFIXES) or host == allow_host:
        return host
    sys.exit(
        f"refusing to load-test {host!r}: not a local/test host. If this is a disposable stack "
        f"you own, pass --allow-host {host}. Never point this at production."
    )


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def login(base: str, headers: dict, email: str, password: str) -> str | None:
    request = urllib.request.Request(
        base + "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)["access"]
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"login failed ({exc}); skipping authenticated endpoints", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--duration", type=float, default=10.0, help="seconds")
    parser.add_argument("--host-header", help="Host header to send (must be in ALLOWED_HOSTS)")
    parser.add_argument("--forwarded-proto-https", action="store_true",
                        help="send X-Forwarded-Proto: https (backend runs with SECURE_PROXY_SSL)")
    parser.add_argument("--allow-host", help="explicitly allow one non-local hostname")
    parser.add_argument("--max-concurrency", type=int, default=64)
    args = parser.parse_args()

    if not 1 <= args.concurrency <= args.max_concurrency:
        sys.exit(f"--concurrency must be between 1 and {args.max_concurrency}")
    base = args.base_url.rstrip("/")
    check_target(base, args.allow_host)

    headers: dict[str, str] = {"Accept": "application/json"}
    if args.host_header:
        headers["Host"] = args.host_header
    if args.forwarded_proto_https:
        headers["X-Forwarded-Proto"] = "https"

    mix = list(PUBLIC_MIX)
    email, password = os.environ.get("LOADTEST_EMAIL"), os.environ.get("LOADTEST_PASSWORD")
    token = login(base, headers, email, password) if email and password else None
    auth_headers = {**headers, "Authorization": f"Bearer {token}"} if token else None
    if auth_headers:
        mix += AUTH_MIX

    lock = threading.Lock()
    latencies: dict[str, list[float]] = defaultdict(list)
    statuses: dict[str, Counter] = defaultdict(Counter)
    deadline = time.monotonic() + args.duration

    def worker(offset: int) -> None:
        i = offset
        while time.monotonic() < deadline:
            name, path = mix[i % len(mix)]
            i += 1
            request = urllib.request.Request(
                base + path, headers=auth_headers if name in dict(AUTH_MIX) else headers
            )
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    response.read()
                    code = response.status
            except urllib.error.HTTPError as exc:
                code = exc.code
            except (urllib.error.URLError, TimeoutError, OSError):
                code = 0  # connection error / timeout
            elapsed = (time.perf_counter() - started) * 1000
            with lock:
                latencies[name].append(elapsed)
                statuses[name][code] += 1

    started = time.monotonic()
    threads = [threading.Thread(target=worker, args=(n,)) for n in range(args.concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.monotonic() - started

    total = sum(len(v) for v in latencies.values())
    bad = sum(c for s in statuses.values() for code, c in s.items() if not 200 <= code < 300)
    print(f"target={base} concurrency={args.concurrency} duration={wall:.1f}s")
    print(f"requests={total} ({total / wall:.1f}/s) non-2xx={bad}")
    print(f"{'endpoint':<14}{'n':>7}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'max ms':>9}  statuses")
    for name in (n for n, _ in mix):
        v = latencies.get(name)
        if not v:
            continue
        print(
            f"{name:<14}{len(v):>7}{statistics.median(v):>9.1f}{percentile(v, 95):>9.1f}"
            f"{percentile(v, 99):>9.1f}{max(v):>9.1f}  {dict(statuses[name])}"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
