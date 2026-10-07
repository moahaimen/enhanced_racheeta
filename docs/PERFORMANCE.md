# Performance

What was measured in Phase 12A, how to repeat it, and what it does and does not prove.

**Read this first.** Every number below comes from one developer laptop (Apple M3, 8 cores, 8 GB,
PostgreSQL 16 on the same machine, other applications running) against **synthetic** data. They
are evidence that nothing is pathological at the tested size, not a capacity claim and not a
promise for Railway hardware. No production or staging system has been measured, because none
exists. Re-run the harness against staging (12B) and record the results here before relying on any
of it.

## 1. Tools (all in the repository, all safe by construction)

| Tool | Purpose | Safety |
| --- | --- | --- |
| `manage.py seed_synthetic --confirm-synthetic --providers N --jobs N --listings N --notifications N` | Bulk-creates obviously fake data (`…@synthetic.invalid`, names starting "Synthetic"). | Refuses non-local database hosts unless `--allow-nonlocal-host`; refuses without `--confirm-synthetic`; password from `SYNTHETIC_PASSWORD` or random. Tested in `tests/test_ops_tools.py`. |
| `scripts/perf/explain_api_queries.py [--analyze] [--full]` | Issues the hot read requests through Django's test client, captures the real SQL, and prints `EXPLAIN (ANALYZE, BUFFERS)` summaries (add `--full` for the plans). | Read-only; refuses non-local hosts. |
| `scripts/loadtest/loadtest.py` | Fixed mix of read endpoints for a fixed time at fixed concurrency; prints counts, errors, status codes and p50/p95/p99/max per endpoint. | Standard library only; read-only (one login for the authenticated endpoint); refuses anything but localhost, `*.test`, `*.invalid`, `*.localhost` unless `--allow-host <exact host>`; concurrency capped at 64; **never point it at production**. |
| `tests/test_query_scaling.py`, `apps/jobs/tests/test_query_scaling.py`, `apps/real_estate/tests/test_query_scaling.py` | CI guard: the number of SQL statements for a list endpoint must be the same for 3 rows and 15 rows (no N+1) and lists stay paginated at 20. Existing tests do the same for providers, marketplace, advertising and dashboards. | Count queries only — no wall-clock thresholds, so they are stable on shared CI runners. |

## 2. Reproduce

```bash
# 1. a local, disposable database
createdb racheeta_perf
cd backend
export DATABASE_URL=postgres://localhost/racheeta_perf DEBUG=false SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(64))") \
  EMAIL_URL=smtp://localhost:25 FRONTEND_URL=https://app.example.test CSRF_TRUSTED_ORIGINS=https://app.example.test \
  ALLOWED_HOSTS=localhost,127.0.0.1 SECURE_PROXY_SSL=true TRUSTED_PROXY_COUNT=1 SYNTHETIC_PASSWORD='choose-a-throwaway'
python manage.py migrate
python manage.py seed_synthetic --confirm-synthetic --providers 5000 --jobs 5000 --listings 3000 --notifications 5000

# 2. query plans
python ../scripts/perf/explain_api_queries.py --analyze

# 3. HTTP load (production-mode gunicorn, as Railway runs it)
gunicorn config.wsgi:application -c config/gunicorn.conf.py -b 127.0.0.1:8125 &
LOADTEST_EMAIL='loadtest-user-<tag>@synthetic.invalid' LOADTEST_PASSWORD="$SYNTHETIC_PASSWORD" \
  python ../scripts/loadtest/loadtest.py --base-url http://127.0.0.1:8125 --forwarded-proto-https --concurrency 8 --duration 20
```

(`seed_synthetic` prints the `<tag>` of the notification user. Set `DEBUG=false` explicitly: a
developer `.env` with `DEBUG=true` otherwise leaks in and changes the behaviour being measured.)

## 3. Data set used

5,000 provider profiles (+5,000 accounts), 5,000 published jobs (100 verified employers), 3,000
published real-estate listings (150 sellers), 5,000 notifications for one user (half read), 19
governorates. Database size ≈ 28 MB. This is deliberately modest: it is enough to expose missing
joins/indexes, not enough to predict behaviour at a million rows.

## 4. Query plans (EXPLAIN ANALYZE, warm cache, `ANALYZE` run first)

| Endpoint | Queries | Timings (ms) | Plan notes |
| --- | --- | --- | --- |
| `GET /providers` | 3 | count 3.6 · rows 16.4 · specialties prefetch 0.02 | Sequential scan of 5,000 profiles joined to accounts + sort by `display_name` (the default order) then `LIMIT 20`. The sort is the cost. |
| `…?governorate=` | 3 | 1.4 · 2.7 · 0.01 | Filtered; fast. |
| `…?search=` | 1 | 4.0 | Returned 0 rows for the test term; one count. |
| `GET /jobs` | 4 | count 1.4 · rows 0.3 | No sequential scan of `jobs_post`; the page comes from an index. |
| `…?governorate=` | 4 | 0.3 · 0.3 | |
| `…?q=nurse` (text search) | 4 | count 2.2 · rows **22.4** | `ILIKE '%…%'` over title, description, detailed specialty and employer name: sequential scan of every published job, ~10k buffer hits for one page. This is the only query that is O(table). |
| `GET /real-estate/listings` | 3 | 1.4 · 3.2 · 0.2 | Existing indexes used. |
| `…?governorate=` | 3 | 0.8 · 0.9 · 0.2 | |
| `GET /geo/governorates` | 1 | 0.01 | 19 rows. |
| `GET /notifications/` (5,000 rows, one user) | 2 | 0.5 · 0.01 | Index on `(recipient, -created_at)` serves the page; the count scans because every row belongs to the user. |
| `GET /notifications/unread-count/` | 1 | 0.4 | |

Sequential scans reported on small tables (governorates, cities, specialties, sellers, employers)
are the correct plan for tables that fit in a few pages.

### Index decisions

**No index was added in 12A** and no migration was written. The rule is that an index needs
evidence: a query whose plan is a problem at a realistic size. At 5,000 rows nothing exceeds ~25 ms.

Watch list with triggers (re-run `explain_api_queries.py` against staging data first):

1. **Job text search (`q`)** grows linearly with published jobs. When the published-job count passes
   roughly 50,000 *or* the `q` query exceeds ~100 ms in staging, add a `pg_trgm` GIN index
   (needs `CREATE EXTENSION pg_trgm` — confirm the host allows it) on the searched expressions, or move
   search to PostgreSQL full-text. Same pattern applies to provider/real-estate search.
2. **Provider list default sort** (`display_name`): if the plan shows a large sort, an index on
   `(display_name)` restricted to visible, verified profiles may help; the filtered queries are
   already fast.
3. **Admin and dashboard aggregates** (counts over whole tables) were not part of this audit; they
   are admin-only and query-count-tested, not size-tested.

## 5. Load results (single run, indicative only)

Setup: production-mode gunicorn (`config/gunicorn.conf.py`, 2 sync workers, `SECURE_PROXY_SSL`,
`TRUSTED_PROXY_COUNT=1`), harness at concurrency 8 for 20 s over loopback, the data set above,
laptop otherwise idle (load average 2–5).

```
requests=2551 (127.1/s) non-2xx=0
endpoint            n   p50 ms   p95 ms   p99 ms   max ms
providers         366     66.7    112.8    131.1    154.0
jobs              364     67.1    114.7    134.2    142.6
jobs-search       365     93.7    135.2    143.8    164.3
listings          365     60.9    101.7    116.5    128.2
governorates      363     47.1     84.4    103.1    125.0
ready             364     42.8     81.2    105.9    127.5
notifications     364     47.6     83.9    104.9    126.5
```

**How to read it.** Eight clients against two synchronous workers means requests queue: even
`/ready/` (one trivial query) shows a 43 ms median, so most of every figure is queueing and
Python/middleware/JSON work, not SQL (the SQL for these endpoints is 0.01–25 ms, §4). The
throughput ceiling of one container is therefore ≈ workers ÷ mean service time; here ≈ 125
requests/s at 2 workers on an M3. Railway's smallest instances are slower than this laptop; expect
a lower number and measure it. Zero errors and no growth in latency over the run were observed;
that is all that is claimed.

## 6. Capacity planning (what to do, not a forecast)

- Measure in staging with the harness at several concurrency levels (4, 8, 16, 32); the p95 knee
  shows when queueing starts.
- If CPU on the instance is the limit, raise `WEB_CONCURRENCY` to about `2 × vCPU` only if memory
  allows (each worker ≈ 100–150 MB). If the database is the limit, look at §4 first.
- Per-process throttle counters mean the real login limit is `10/min × workers`; acceptable now,
  revisit before replicas (`docs/OPERATIONS.md` §9).
- The web bundle is one 820 kB (219 kB gzip) script. Code splitting is a possible later optimisation,
  not needed for correctness. Cache headers and compression of the SPA assets served by WhiteNoise
  were not audited in 12A; check them in staging (`curl -I` on `/assets/…`) and add a note here.

## 7. Known gaps

- No measurement on Railway/staging hardware; no soak test; no write-heavy or mixed read/write
  scenario (the harness is read-only by design); no test with a cold database cache.
- No million-row data set; trigger thresholds in §4 are judgement calls to be revisited with real
  numbers.
- Mobile app performance (startup, scrolling) is covered by `docs/MOBILE_RELEASE.md`, not here.
