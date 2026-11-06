# Multi-vendor marketplace and the 20% commission

Status: LOCAL DEMO. Every payment, refund and payout in this system is **simulated**. No payment
provider is connected and no real money moves. The feature-by-feature status is in
`docs/local-commerce-implementation-matrix.md`.

## Decision

- Every eligible, verified seller runs its own store: products, inventory, sales and coupons,
  quotations, orders and returns, from its own dashboard. Owners and authorized staff use it.
- Racheeta keeps central control of seller verification, product compliance, the commission policy,
  payment confirmation, completion, refunds, disputes and seller payouts.
- Racheeta's commission is exactly **20% of eligible net merchandise sales**.
- All money is computed by the backend. The ledger is append-only and concurrency-safe.

## Eligibility (fail closed)

A line can be bought only when all of these hold at the moment of checkout (`commerce/checkout.purchase_channel`):

1. The product and its category are active.
2. The seller is a VERIFIED business on an active business account.
3. The product is not restricted, and its category's compliance class is neither
   `RESTRICTED_PENDING_REVIEW` nor `PROHIBITED`. A new or unknown category defaults to pending
   review, so it is not purchasable.
4. The buyer is active, e-mail-verified, has a buying role, and is not the seller itself.
5. The route is one of:
   - **B2C**: the product is in the public store (`B2C_ALLOWED`, a retail business type, a
     consumer channel).
   - **B2B**: a professional channel in a `B2B_VERIFIED_ONLY` category (an explicit
     classification: `B2C_ALLOWED` does not grant direct B2B purchase), where the buyer's provider
     profile is verified and THE targeting rule shows it the product. A professional-channel
     product in any other category is sold by quotation only.
   - `QUOTE_ONLY` products are bought only through an accepted quotation.

Regulated products are never advertised either (`advertising.services._advertisable`).

## Pricing and the commission base (`commerce/pricing.py`)

All amounts are Decimal, in whole Iraqi dinars, rounded ROUND_HALF_UP. Per line:

```
line_total        = unit_price × quantity
seller_discount   = product sale (seller-funded %) + share of a store coupon
merchandise_net   = line_total − seller_discount          ← commission base
platform_discount = share of a Racheeta coupon (paid by Racheeta)
buyer_paid        = merchandise_net − platform_discount
commission        = round(merchandise_net × 20%)
seller_payable    = merchandise_net − commission
```

- Coupons are split across lines by value with the largest-remainder method, so line amounts add up
  exactly.
- Stacking: one store coupon per store order, one Racheeta coupon per checkout, one use per buyer.
- A cancelled order releases its coupon uses.

Worked examples (tests and seeded orders):

| Case | Buyer pays | Commission | Seller payable |
|---|---|---|---|
| 100,000 IQD, no discount | 100,000 | 20,000 | 80,000 |
| 100,000 with a 10,000 store discount (sale or coupon) | 90,000 | 18,000 | 72,000 |
| 100,000 with a 10,000 Racheeta coupon | 90,000 | 20,000 | 80,000 (Racheeta absorbs the 10,000) |

Every order and line keeps a snapshot of: list value, seller and platform discounts, net, buyer
paid, rate, policy version, commission and payable. A later policy version never changes an
existing order.

## Lifecycle (`commerce/lifecycle.py`)

```
PLACED ─seller accept─▶ CONFIRMED ─seller ship─▶ SHIPPED ─buyer (or finance) confirm─▶ DELIVERED ─finance complete─▶ COMPLETED
   │                       │
   └─buyer cancel / seller decline─▶ CANCELLED   (stock released once; coupons released;
                                                  if already paid → REFUND_PENDING → finance refund)
Payment (separate axis): UNPAID ─finance verify (simulated)─▶ PAID ─▶ PARTIALLY_REFUNDED / REFUNDED
Returns: REQUESTED ─seller approve─▶ APPROVED ─seller received (restock)─▶ RECEIVED ─finance refund─▶ REFUNDED
Disputes: OPEN ─finance resolve─▶ RESOLVED_REFUND | RESOLVED_REJECTED
```

- **Completion** requires PAID and DELIVERED, with no open return or dispute. It posts the accrual
  exactly once and is the only point where the commission is earned.
- Sellers can never mark an order paid, delivered or completed.
- **Stock**: checkout reserves units (row lock, in product-id order, so it cannot oversell),
  shipping consumes them, cancellation releases them once, and a received return restocks them.
  Sellers may adjust on-hand stock (with a reason) but never below the reserved units.

## Ledger (`apps/ledger`)

Double entry. Every entry balances and has a unique reference (idempotency).

| Event | Debit | Credit |
|---|---|---|
| Payment verified (`order:<id>:payment`) | PLATFORM_CASH | CUSTOMER_FUNDS_HELD |
| Completed (`order:<id>:accrual`) | CUSTOMER_FUNDS_HELD (buyer paid) + PLATFORM_PROMO_EXPENSE (Racheeta coupon) | SELLER_PAYABLE[seller] + COMMISSION_REVENUE |
| Refund before completion | CUSTOMER_FUNDS_HELD | PLATFORM_CASH |
| Refund after completion (proportional) | SELLER_PAYABLE[seller] (up to what is still held) + SELLER_RECEIVABLE[seller] (the rest) + COMMISSION_REVENUE | PLATFORM_PROMO_EXPENSE + PLATFORM_CASH |
| Completed while the seller owes (offset) | as above, but the seller part credits SELLER_RECEIVABLE first, then SELLER_PAYABLE | |
| Payout (`settlement:<id>:payout`) | SELLER_PAYABLE[seller] | PLATFORM_CASH |
| Recovery (`recovery:<id>`, finance, simulated) | PLATFORM_CASH | SELLER_RECEIVABLE[seller] |

Rules:

- **Refund after payout**: the seller payable never goes negative. The part of a refund that is no
  longer held for the seller becomes SELLER_RECEIVABLE (the seller owes Racheeta).
  - It is netted first against the seller's next completed sales.
  - Finance can also record a simulated recovery (`POST admin/ledger/recoveries`, never more than
    owed).
  - Payouts are only ever of a positive payable.
- **Locks**: every decision about one seller's balances (accrual, refund, payout, recovery) holds
  that seller's row lock. The lock order is order rows → seller row → payout batch, so no deadlocks.
- **Database protection**: triggers refuse UPDATE, DELETE and TRUNCATE (of a non-empty table) on
  `ledger_entry`, `ledger_line`, `ledger_recovery` and `ledger_commission_policy`.
  - There is no session-level bypass. The old `racheeta.ledger_purge` setting was removed in
    `ledger 0004`, because any session could set it.
  - An UPDATE that changes nothing is allowed. For a policy, only its timestamps may be re-saved.
  - Corrections are always new entries.
- Refund amounts use cumulative rounding, so returning units one at a time adds up exactly to
  returning them all at once.
- `settlement.reconciliation()` re-derives all five balances from the order, refund and payout
  snapshots, and also checks that every entry balances, that no seller payable is negative, that
  every paid order has a payment entry, and that each order has a single accrual.
- **Payouts**: finance prepares a payout of everything owed, then confirms it with a (simulated)
  transfer reference. A payout can never exceed the amount owed at confirmation; for example, a
  refund after preparation makes the draft stale.
- **Finance operator**: a staff account WITH the permission `ledger.change_settlementbatch`. Staff
  without it are refused.

## Database roles (production requirement)

PostgreSQL lets a superuser or the table owner disable triggers. The ledger is therefore only as
safe as the role the application connects with. Production must:

1. Run migrations with an owner role.
2. Run the application with a separate runtime role that is not a superuser, does not own the
   tables, and holds only SELECT and INSERT on the append-only ledger tables (UPDATE as well on
   `ledger_settlement`). The statements: `manage.py ledger_db_audit --grant-sql <role>`.
3. Run `manage.py ledger_db_audit --strict` against the runtime connection before go-live. It
   exits non-zero if the role is a superuser or owner, holds UPDATE, DELETE, TRUNCATE or TRIGGER on
   an append-only table, a trigger is missing or disabled, or the trigger function has a bypass.

Verified on 2026-11-06 on a throwaway database, as a restricted login role:
- `--strict` passes;
- a purge flag + DELETE gives "permission denied";
- DISABLE TRIGGER gives "must be owner";
- TRUNCATE gives "permission denied".

Locally the developer role owns everything, so the command reports that, on purpose.

**Demo cleanup**: `scripts/local_demo.sh clear` still removes the demo ledger rows.
- It works only when the registry owns ledger rows and `local_guard` accepts the database again.
- It uses `ALTER TABLE … DISABLE TRIGGER` (owner-only) inside its single transaction, and the
  triggers come back before the commit; a rollback or dry run also restores them.
- Ownership of rows created in walkthroughs is proven transitively: every reference chain must end
  in registered demo rows. Accounts are never inferred, so a real user's row is always refused.

## Seller roles (`workspaces/types.py`)

| Capability | Roles |
|---|---|
| orders view | OWNER, MANAGER, STAFF, VIEWER, FULFILLMENT, FINANCE, STOCK_MANAGER |
| accept / decline / ship | OWNER, MANAGER, STAFF, FULFILLMENT |
| returns (approve, received) | OWNER, MANAGER, FULFILLMENT |
| products edit | OWNER, MANAGER, PRODUCT_EDITOR |
| stock adjust / alert level | OWNER, MANAGER, STOCK_MANAGER |
| coupons and sales | OWNER, MANAGER |
| statement (finance view) | OWNER, FINANCE |

The specialist roles exist only for businesses, never for facilities.

## API (all under `/api/v1`)

**Buyer**
- `POST checkouts/preview`
- `POST checkouts` (with `idempotency_key`)
- `GET orders`
- `POST orders/<id>/cancel | confirm-delivery | returns | disputes`
- A reused `idempotency_key` replays the first checkout only for the SAME request (lines in any
  order). A different request is refused with 409 `idempotency_conflict`.
- `POST quotes/<id>/order`

**Seller** (`?company=` for staff)
- `merchant/orders` and `…/transition`
- `merchant/returns` and `…/decide`, `…/received`
- `merchant/inventory` and `…/adjust`, `…/threshold`, `…/movements`
- `merchant/coupons`
- `merchant/offers`
- `merchant/finance`

**Finance**
- `admin/commerce/orders` and `…/verify-payment`, `…/confirm-delivery`, `…/complete`, `…/refund-cancelled`
- `admin/commerce/returns/<id>/refund`
- `admin/commerce/disputes/<id>/resolve`
- `admin/commerce/coupons`
- `admin/ledger/{reconciliation, entries, payables, settlements, settlements/prepare, settlements/<id>/confirm|cancel, recoveries, policy, statements/<company>}`

The contract is in `docs/api/openapi.yaml`.

## Migrations and rollback

| Migration | Content |
|---|---|
| `marketplace 0004` | Compliance class (existing categories: consumer → B2C_ALLOWED, others → QUOTE_ONLY), reserved stock, reorder threshold, reserved ≤ on hand |
| `commerce 0003` | Checkout, financial snapshots, coupons, sales, stock movements, returns, refunds, disputes; backfills legacy orders (net = paid = payable = total, REFUND_DUE → REFUND_PENDING) |
| `ledger 0001`, `0002` | Ledger tables, immutability trigger, policy v1 = 20.00% from 2026-01-01 |
| `workspaces 0002` | Seller roles |
| `notifications 0005` | New event types |
| `ledger 0003` | SELLER_RECEIVABLE account, RECOVERY entries, `ledger_recovery` table |
| `ledger 0004` | Strict immutability: no session bypass, TRUNCATE triggers, recovery and policy tables protected |
| `marketplace 0005` | Legacy tightening: inactive legacy consumer categories, or ones containing a restricted product → RESTRICTED_PENDING_REVIEW |
| `commerce 0004` | `Checkout.request_hash` (idempotency-key reuse with a different request → 409) |

To roll back the audit migrations only:
- `migrate ledger 0002`;
- `migrate marketplace 0004`;
- `migrate commerce 0003`.

This was verified on 2026-11-06 on a throwaway database. The 0002 trigger function, with its
bypass, comes back, so do this only for a local rollback.

To roll back on the local demo database:
1. `scripts/local_demo.sh clear` (removes the demo ledger rows inside the guarded transaction).
2. `manage.py migrate ledger zero`.
3. `migrate commerce 0002`.
4. `migrate marketplace 0003`.
5. `migrate workspaces 0001`.
6. `migrate notifications 0004`.

Verified on 2026-11-06 on a throwaway local database: migrate, then roll back all five steps, then re-migrate, all succeed.

With data, first remove the orders that use the new statuses (`COMPLETED`, `PARTIALLY_REFUNDED`, `REFUND_PENDING`). The old columns cannot hold those values, and the legacy-order backfill has a no-op reverse.

## Legal and payment constraints (NOT legal clearance)

- This is a technical demo. Nothing here claims legal clearance in Iraq.
- Real sales of medicines, prescription items, controlled supplies or regulated devices need
  external legal review, seller licensing, buyer-eligibility rules and regulator approval before any
  production use. Prescription items are blocked by default.
- **Collecting the 20%**: it is only guaranteed if the money passes through Racheeta, either
  through a licensed payment partner with split settlement, or through a trusted cash-on-delivery
  courier who remits the cash to Racheeta. If sellers collect cash themselves, the 20% becomes an
  invoice with collection risk, and automatic deduction is not enforceable.
- **Payment custody, refunds and seller payouts** need a licensed payment or e-money partner and
  bank agreements. The demo only records simulated evidence such as `SIM-…` references.
- Marketplace money is a separate accounting domain from advertising payments and subscriptions.
