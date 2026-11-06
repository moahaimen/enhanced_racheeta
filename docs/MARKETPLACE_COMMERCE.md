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
   - **B2B**: a professional channel in a `B2B_VERIFIED_ONLY` or `B2C_ALLOWED` category, where the
     buyer's provider profile is verified and THE targeting rule shows it the product.
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
| Refund after completion (proportional) | SELLER_PAYABLE[seller] + COMMISSION_REVENUE | PLATFORM_PROMO_EXPENSE + PLATFORM_CASH |
| Payout (`settlement:<id>:payout`) | SELLER_PAYABLE[seller] | PLATFORM_CASH |

Rules:

- A PostgreSQL trigger refuses UPDATE and DELETE on ledger rows. Corrections are new entries.
- The only bypass is the guarded demo cleaner, which sets the transaction-local flag
  `racheeta.ledger_purge`.
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
- `admin/ledger/{reconciliation, entries, payables, settlements, settlements/prepare, settlements/<id>/confirm|cancel, policy, statements/<company>}`

The contract is in `docs/api/openapi.yaml`.

## Migrations and rollback

| Migration | Content |
|---|---|
| `marketplace 0004` | Compliance class (existing categories: consumer → B2C_ALLOWED, others → QUOTE_ONLY), reserved stock, reorder threshold, reserved ≤ on hand |
| `commerce 0003` | Checkout, financial snapshots, coupons, sales, stock movements, returns, refunds, disputes; backfills legacy orders (net = paid = payable = total, REFUND_DUE → REFUND_PENDING) |
| `ledger 0001`, `0002` | Ledger tables, immutability trigger, policy v1 = 20.00% from 2026-01-01 |
| `workspaces 0002` | Seller roles |
| `notifications 0005` | New event types |

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
