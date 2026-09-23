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
| Entitlement | `PlanEntitlement(key, kind BOOLEAN|LIMIT, enabled, limit null=unlimited, period NONE|DAILY|MONTHLY|SUBSCRIPTION)` | Editable in the admin without code changes. |
| Subscription | `Subscription(status PENDING|ACTIVE|SUSPENDED|CANCELLED|EXPIRED|REJECTED)` | One live (PENDING or ACTIVE) subscription per account (DB constraint). Activation cancels any other ACTIVE one. |
| History | `SubscriptionEvent` | Every status change with actor and reason. |
| Payment | `PaymentRecord` | Optional; recorded by the admin on activation (amount/method/reference). |
| Credits | `CreditBalance`, `CreditTransaction` | Admin-granted top-ups per key; consumed only after the plan limit is exhausted. |
| Usage | `UsageCounter(key, period_start, used)`, `UsageEvent(reference)` | Atomic increments (`select_for_update`); a `reference` makes consumption idempotent. |

Capability keys live in `apps.billing.types.Keys`:

| Key | Kind | Used by |
| --- | --- | --- |
| `jobs.post` | BOOLEAN | creating/submitting jobs |
| `jobs.active_limit` | LIMIT (concurrent) | jobs in PENDING_ADMIN_REVIEW or PUBLISHED |
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

`consume` runs inside a transaction with a row lock on the counter, so parallel
requests cannot exceed the limit. When the plan limit is exhausted and credits
exist, only the overflow is charged to credits (`min(amount, used + amount - limit)`).

Exceptions map to the uniform error envelope with typed codes and `meta`:

| Code | HTTP | `meta` |
| --- | --- | --- |
| `subscription_required` | 402 | `key` |
| `entitlement_required` | 402 | `key` |
| `usage_limit_reached` | 402 | `key`, `limit`, `used` |

## Lifecycle

1. Employer owner picks a public plan on the workspace page → `POST /jobs/employer/billing/request` → `Subscription(PENDING)`.
2. Owner pays off-platform and tells Racheeta the reference.
3. Super Admin verifies the payment in the console → `POST /admin/billing/subscriptions/{id}/activate` with optional `term_days`, `reference`, `note`, `payment{amount,currency,method,reference}` → ACTIVE with `ends_at = starts_at + term_days`.
4. Read-time check: an ACTIVE subscription past `ends_at` is treated as expired (`expire_subscription`) and the default plan applies again.
5. Admin can `reject` (PENDING), `suspend`/`cancel` (ACTIVE) and re-activate a SUSPENDED one; every step is audited.

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
