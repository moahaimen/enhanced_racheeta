# Billing and Entitlements

Phase 3 introduced a reusable commercial foundation in `backend/apps/billing`.
It is deliberately decoupled from jobs: any module (jobs today, marketplace or
advertising later) asks the billing layer "may this subject do X, and how many
times?" through capability keys. Reservations will stay free (owner decision).

## Owner constraints honoured

- No payment gateway. Payments happen off-platform; a Super Admin verifies them
  and activates the subscription manually. No receipt uploads.
- No prices are seeded. `Plan.price_amount` is `null` until the owner sets IQD
  prices in the Django admin; the web shows "price on request".
- No new infrastructure (no Redis/Celery). Expiry is evaluated at read time.
- Minimal payment records for bookkeeping only.

## Concepts

| Concept | Model | Notes |
| --- | --- | --- |
| Subject | `BillingAccount(subject_type, subject_id, audience)` | One billing account per employer organisation (`organization`) or per job seeker account (`account`). Created lazily. |
| Plan | `Plan(code, audience, is_default, is_public, billing_period, term_days, price_amount?)` | `is_default` plans apply automatically when no subscription is live (TRIAL for employers, SEEKER_FREE for seekers). |
| Entitlement | `PlanEntitlement(key, kind BOOLEAN|LIMIT, enabled, limit null=unlimited, period NONE|DAILY|MONTHLY|SUBSCRIPTION)` | Values editable in the admin without code changes; for every known key the shape (kind, period) is fixed by `KNOWN_KEYS` and enforced on every write. |
| Subscription | `Subscription(status PENDING|ACTIVE|SUSPENDED|CANCELLED|EXPIRED|REJECTED)` | One live (PENDING or ACTIVE) subscription per account (DB constraint). Activation cancels any other ACTIVE one. |
| History | `SubscriptionEvent` | Every status change with actor and reason. |
| Payment | `PaymentRecord` | Optional; recorded by the admin on activation (amount/method/reference). |
| Credits | `CreditBalance`, `CreditTransaction` | Admin-granted top-ups per key; consumed only after the plan limit is exhausted. |
| Usage | `UsageCounter(key, period_start, used)`, `UsageEvent(reference)` | Atomic increments (`select_for_update`); a `reference` makes consumption idempotent. |

Capability keys live in `apps.billing.types.Keys`:

| Key | Kind | Used by |
| --- | --- | --- |
| `jobs.post` | BOOLEAN | creating/submitting jobs |
| `jobs.active_limit` | LIMIT (concurrent) | jobs in PENDING_ADMIN_REVIEW, or PUBLISHED with a deadline that has not elapsed (overdue ones are normalised to EXPIRED before every capacity check) |
| `jobs.featured`, `jobs.featured_limit` | BOOLEAN + LIMIT (concurrent) | featured jobs |
| `jobs.application_review` | BOOLEAN | applicant list, transitions, interviews |
| `talent.search`, `talent.search_limit` | BOOLEAN + LIMIT (monthly) | talent search (see the billable-search rule in `JOBS.md`) |
| `talent.invite`, `talent.invite_limit` | BOOLEAN + LIMIT (monthly) | invitations |
| `talent.save_candidate` | BOOLEAN | saved candidates |
| `recruiter.seats` | LIMIT (concurrent) | non-owner active memberships |
| `recruitment.messaging` | BOOLEAN | text messages on applications |
| `applications.limit` | LIMIT (monthly) | job seeker applications (SEEKER_FREE: 15/month) |

## Service API (`apps/billing/services.py`)

```python
svc = entitlements_for("organization", employer.id, Audience.EMPLOYER)
svc.require(Keys.TALENT_SEARCH)                      # BOOLEAN → EntitlementRequired / SubscriptionRequired
svc.check_concurrent(Keys.JOBS_ACTIVE_LIMIT, current=n)  # concurrent LIMIT → UsageLimitReached
svc.consume(Keys.TALENT_SEARCH_LIMIT, reference=sig)  # periodic LIMIT: plan limit first, then credits
svc.summary()                                        # [{key, kind, enabled, limit, period, used, credits, remaining}]
```

`consume` runs inside a transaction: the `UsageEvent` for the reference is
inserted first as the idempotency claim (a unique-constraint failure means
another transaction already consumed it), then the counter row is locked and
incremented. Parallel or retried requests therefore never exceed the limit or
double-charge. When the plan limit is exhausted and credits exist, only the
overflow is charged to credits (`min(amount, used + amount - limit)`).

### Reference rules (what counts as "the same" consumption)

| Key | Reference | Meaning |
| --- | --- | --- |
| `applications.limit` | `apply:<application id>` | one unit per application **attempt**: a new application after a withdrawal is a new attempt; an HTTP retry is stopped earlier by the one-active-application rule, so it never reaches `consume` |
| `talent.invite_limit` | `invite:<invitation id>` | one unit per invitation; re-inviting after decline/expiry/cancel is a new unit |
| `talent.search_limit` | `talent:<employer>:<day>:<filter signature>` | one unit per (employer, filters, day). The signature is built from the filter values **canonicalised the way the filter set matches them** (`canonical_talent_params`: case/whitespace-folded text for `q`, `skill`, `language`, `detailed_specialty`; upper-cased choice values; trimmed slugs/enums; integer experience in canonical text, never truncated — fractional input is rejected by validation; UUIDs case-folded; parameter order irrelevant), so `skill=Nursing`, `skill=nursing` and a padded value are one search; pagination, ordering and unknown parameters never change it; nothing is consumed unless the filter set validates and the search can execute |

References are never built from `(job, seeker)` alone: that would make a
legitimate later attempt look like a retry of the first one.

### Concurrent limits (`check_concurrent`)

Active jobs, featured jobs and recruiter seats are check-then-commit
decisions. The jobs service takes a row lock on the `jobs_employer` row
(`SELECT … FOR UPDATE`) before counting and transitioning, so two submissions,
two feature requests or two seat additions for the same organisation are
serialised by the database. No process-local locks, no Redis. The same gate
runs for `submit` and for an administrator `restore` of a suspended job, since
a suspended job holds no slot.

### Featured window

A job is featured only while `is_featured` **and** `featured_until > now`.
The public/employer listings normalise stale rows at read time (one indexed
UPDATE in `expire_featured_jobs`, called from `expire_overdue_jobs`), the
serializer applies the same rule, and `set_featured` counts only live windows,
so expired windows stop occupying `jobs.featured_limit` slots.

Exceptions map to the uniform error envelope with typed codes and `meta`:

| Code | HTTP | `meta` |
| --- | --- | --- |
| `subscription_required` | 402 | `key` |
| `entitlement_required` | 402 | `key` |
| `usage_limit_reached` | 402 | `key`, `limit`, `used` |

## Summary contract

`GET /jobs/employer/billing` (and the administrator's `GET /admin/billing/accounts/{id}`)
return two distinct subscription fields:

| Field | Meaning |
| --- | --- |
| `subscription` | The **ACTIVE** subscription the entitlements resolve through, or `null`. Entitlement resolution is unchanged: ACTIVE subscription plan → default plan of the audience → nothing. |
| `pending_subscription` | The request waiting for an administrator (status PENDING only), or `null`. **It never grants an entitlement.** |

A PENDING request used to be invisible: the summary said `subscription: null`,
so after a reload the workspace offered the request form again and the second
submit failed on the one-live-subscription rule. Keeping the two apart lets the
client show the pending state across reloads while entitlements stay exactly
where they were. A SUSPENDED, CANCELLED, REJECTED or EXPIRED row appears in
neither field.

ACTIVE and PENDING cannot coexist (the one-live-subscription DB constraint), so
in practice at most one of the two fields is set — except after a suspension,
which does not block a new request: then `subscription` is `null` (the default
plan applies) and `pending_subscription` carries the new request.

## Lifecycle

1. Employer owner picks a public plan on the workspace page → `POST /jobs/employer/billing/request` → `Subscription(PENDING)`. The summary reports it as `pending_subscription` until an administrator decides.
2. Owner pays off-platform and tells Racheeta the reference.
3. Super Admin verifies the payment in the console → `POST /admin/billing/subscriptions/{id}/activate` with optional `term_days`, `reference`, `note`, `payment{amount,currency,method,reference,note}` (the payment is always recorded VERIFIED by the server; a client-supplied `status` is refused) → ACTIVE with `ends_at = starts_at + term_days`. The plan is re-read under lock inside the activation transaction: if it was retired (`is_active=false`) since the request, activation and reactivation are refused with a typed error, nothing is cancelled, no ACTIVE event and no payment record are written — an ACTIVE row on a retired plan would silently resolve to the default entitlements.
4. Read-time check: an ACTIVE subscription past `ends_at` is expired (`expire_subscription`, which locks the subscription row and transitions only if it is still ACTIVE and elapsed, so a concurrent administrator decision is never overwritten and concurrent lookups write one event) whenever entitlements are resolved **and** at the start of every `request_subscription`, under a row lock on the billing account, so a renewal is never rejected as "already active" because nobody had opened a billing page since the term ended. The default plan applies again after expiry.
5. Admin can `reject` (PENDING), `suspend`/`cancel` (ACTIVE) and re-activate a SUSPENDED one; every step is audited. An ACTIVE row whose term has ended is EXPIRED first, never suspended or cancelled: the staff subscription list normalises every elapsed ACTIVE row through `expire_subscription` (one locked, evented transition per row, bounded by the rows not yet normalised, idempotent) before filtering and serialising, and the direct suspend/cancel service paths and activation of another row do the same before they decide, so `?status=ACTIVE` never lists an elapsed term and the console never offers actions on one. Activation runs under a row lock on the billing account and re-reads the subscription status. Policy: **the administrator's activation supersedes any other live row** — another ACTIVE subscription, any SUSPENDED one and any newer PENDING request are cancelled (audited as `billing.subscription.cancelled`, reason "superseded by activation of …") before the row becomes ACTIVE, so the one-live-subscription constraint can never surface as a 500. Every status transition re-reads the row under a lock.

Credits: `POST /admin/billing/credits {billing_account, key, amount, note}`; negative amounts revoke.

## Seeded plans (limits, no prices)

| Plan | Audience | Active jobs | Talent searches / month | Invites / month | Seats | Featured |
| --- | --- | --- | --- | --- | --- | --- |
| TRIAL (default) | employer | 1 | none | none | 1 | no |
| BASIC | employer | 3 | 20 | 10 | 2 | no |
| PROFESSIONAL | employer | 10 | 100 | 50 | 5 | 2 |
| BUSINESS | employer | 30 | 500 | 200 | 15 | 5 |
| ENTERPRISE | employer | unlimited | unlimited | unlimited | unlimited | unlimited |
| SEEKER_FREE (default) | job seeker | 15 applications / month | | | | |
| SEEKER_PLUS | job seeker | unlimited applications | | | | |

These are starting limits; the owner adjusts them in the admin. Job-seeker
pricing is not decided; SEEKER_PLUS exists so the model is proven, not as a
commitment.

## Extending to another module

Add keys to `Keys` and `KEY_SPECS`, add them to plans (migration or admin),
call `require/check_concurrent/consume` from the module's service layer, and
translate the key in `entitlements.*` on the web. Nothing in `billing` imports
`jobs`.

## Django admin

The Django admin is for inspection only. `Subscription` lifecycle and identity
fields (`billing_account`, `plan`, `status`, `starts_at`, `ends_at`,
`requested_by`, `requester_note`, `activated_by`, `admin_reference`) are
read-only, subscriptions cannot be added or deleted there, and the event and
payment inlines are read-only; every state change goes through
`apps.billing.services` (locked, evented, audited) via the admin console API.
The Django admin is split by what a model is: **configuration** (`Plan`,
`PlanEntitlement`) is editable within the rules below; **lifecycle state**
(`BillingAccount`, `Subscription`) and **ledger/history** (`CreditBalance`,
`CreditTransaction`, `UsageCounter`, `UsageEvent`, `SubscriptionEvent`,
`PaymentRecord`) are inspection-only: no add, no change, no delete, no bulk
actions, every field read-only. A billing account is created by services on
first use and is never re-bound to another subject or deleted from the admin;
credits move only through `grant_credits()` (locked, ledgered, audited).

`Plan` prices, limits and flags remain editable (that is how the owner sets
IQD prices), but a plan's `code` and `audience` are frozen once created, and
the default plan of an audience can be neither retired nor deleted (a `pre_delete` guard covers every ORM path, including admin bulk actions), and retiring a plan (`is_active` true → false) is refused — by the model, so on
every path, and shown as a normal field error in the admin — while ACTIVE
subscriptions still reference it. Subscribers are never downgraded, migrated,
cancelled or expired automatically; move them through the lifecycle first.
Retirement locks the plan row, the same lock activation takes before it
re-reads the plan, so an ACTIVE subscription on a retired plan cannot be
committed from either side.
`UsageCounter` rows are read-only.
