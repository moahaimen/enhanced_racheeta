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

## Sellers and onboarding (`marketplace/sellers.py`)

Seller categories (`BusinessType`): pharmacy, pharmaceutical company, scientific office, medical
company, medical equipment supplier, medical supplies office, assistive-device store and
pharmaceutical distributor. Retail types (equipment supplier, supplies office, assistive-device
store, pharmacy) may sell allowed products to the public; the others sell to verified
professionals (direct B2B or quotation).

**A pharmacy keeps its identity.** A PROVIDER account whose own profile is a PHARMACY opens its
store with `POST marketplace/pharmacy-store`. It keeps its PROVIDER role, provider profile and
facility workspace. The store is a `MedicalCompany` row linked to that facility
(`MedicalCompany.facility`, business type PHARMACY; a database constraint ties the two
together). Staff, permissions, orders and the ledger then work as for any seller.
`seller_account_q()` is the one rule: a MEDICAL_COMPANY account, or a PROVIDER whose store is
linked to its own VERIFIED pharmacy profile. If the pharmacy loses verification, its store stops
selling at once.

**Steps.**
1. Register: `POST marketplace/company`, or `…/pharmacy-store` for a pharmacy. New stores start
   INACTIVE.
2. Upload documents: `POST marketplace/company/documents`. The required kinds are listed per
   business type in `REQUIRED_DOCUMENTS` (a fictional, conservative local rule set, not a
   statement of Iraqi licensing law).
3. Request verification. A Racheeta administrator reviews each document (approve, or reject with
   a reason) and verifies the business (`admin/marketplace/documents…`,
   `admin/marketplace/companies/<id>/verification`).
4. Activate: `POST marketplace/company/store/status {active: true}`. This is refused unless the
   business is verified and every required document is APPROVED. Pausing is always allowed.

`selling_q()` = verified, active seller account, store ACTIVE. It gates the public store, the
targeted B2B catalogue, checkout, quote orders and advertising.

Stores that existed before activation was introduced keep selling: the migration default is
ACTIVE, and the demo seeds their documents as approved. Only onboarding creates INACTIVE stores.
A (re)verification of an ACTIVE store whose required documents are not all approved puts it back
to INACTIVE, so a legacy store can never start selling again without approved licences.
`MedicalCompany.documents_complete` (every required document APPROVED) is part of `selling_q`.
- It is kept current by every upload, withdrawal and review.
- `marketplace 0007` computes it for existing rows. A store from before documents existed has
  none, so it stops selling until its licences are approved.
- Rejecting a previously approved licence stops the sale at once.
- An expired document no longer counts. Run `manage.py refresh_seller_documents` daily, because
  expiry happens with time, not with an event.
- A category's `required_documents` are also re-checked at checkout, not only at publication.

## Uploads (`marketplace/uploads.py`)

- **Seller documents:** PDF, JPEG or PNG, up to 5 MB.
- **Product photos:** JPEG, PNG or WebP, up to 3 MB, 64 to 6000 px per side.
- The type is sniffed from the bytes, never taken from the name or the client's header.
- SVG, HTML and Office files are refused, as are PDFs with JavaScript, launch actions, embedded
  files, rich media or XFA.
- Files are stored under `PRIVATE_MEDIA_ROOT`, never under the public `MEDIA_ROOT`, with a random
  `<uuid>.<ext>` name. The original name is kept for display only, stripped of paths and control
  characters. A SHA-256 is stored.
- Files are streamed only by permission-checked views, with `X-Content-Type-Options: nosniff`,
  `Content-Security-Policy: default-src 'none'; sandbox`, and `attachment` for documents.
- Documents can be opened by the business's OWNER/MANAGER (`company.documents.manage`) and
  Racheeta administrators.
- Photos are public only for a product on sale; otherwise they are visible to the business's team
  and staff. An unknown or hidden photo is a 404 either way.
- An approved document cannot be withdrawn (the history is kept).
- Photos are stored without identifying metadata: JPEG EXIF (including GPS), XMP, APP3–APP13,
  APP15 and comments; PNG text, time and EXIF chunks; WebP EXIF/XMP chunks and their VP8X flags.
  This is done byte-for-byte, with no re-encoding and no new dependency; colour profiles are kept.
  PDF documents keep their own metadata (author, producer). They are only ever shown to the
  business's owner/managers and Racheeta reviewers.
- A photo has the same audience as its product:
  - a public-store product: anyone;
  - a professional product: only the verified providers it is targeted at;
  - otherwise: the business's team and Racheeta staff.

**Production requirements for uploads (not built; no paid service needed to start):**
1. Private object storage (an S3-compatible bucket with no public ACL). Files are streamed through
   these permission-checked views or short-lived signed URLs, never a public bucket URL.
   Encryption at rest and versioned backups.
2. Malware scanning before a document becomes reviewable. For example, an open-source ClamAV
   worker; quarantine on detection and never serve unscanned files.
3. Keep: the type sniffing, the active-PDF refusal, size limits, random names, sanitized display
   names, nosniff and a sandboxed CSP. Optionally render documents to images for reviewers
   instead of opening the seller's PDF.
4. Per-seller quotas (count and bytes), rate limits on uploads, and audit retention of who
   uploaded and who reviewed.
5. A retention policy for rejected or superseded licences (legal advice needed). Delete files
   when their rows are deleted (the demo cleaner already does).
6. Re-encode photos server-side (an image library) if the stripping above is not enough for the
   formats accepted in production.

## Products: SKUs, variants, category rules

- **SKUs.** `Product.sku` and `ProductVariant.sku` are unique within a business, across products
  and variants (database constraints plus a service check).
- **Variants.** A variant has its own label, SKU, price (empty = the product price), stock and
  alert level. Once a product has active variants, the buyer must pick one (`variant_required`)
  and stock lives on the variants.
- **Inventory.** Reserve, release, consume and restock work on the variant row, and the movement
  ledger records the variant. Stock changes go through a stock adjustment with a reason.
- **Category rules** (administrator data on `ProductCategory`), enforced at publication, in the
  store query and at checkout:
  - `allowed_business_types`;
  - `required_documents` (approved seller documents needed to publish);
  - `max_order_quantity` (`quantity_limit`);
  - a bilingual buyer notice.
- **Direct B2B purchase.** `can_buy_directly` (a UI hint) is true for a priced, non-restricted
  product in an explicit B2B_VERIFIED_ONLY category. Checkout re-decides.

## Delivery fees and seller-declared tax (pass-through charges)

**Delivery fees.**
- A seller sets a fee per governorate (`ShippingRate`, with an estimate in days), a default fee
  and a free-over threshold.
- A seller with no delivery settings delivers free, as before. A seller with governorate rates
  and no default refuses other governorates (`no_delivery`).
- The fee becomes one SHIPPING order line.

**Tax.** Racheeta decides no tax obligation. The default is NONE.
- A seller may declare INCLUSIVE (the included part is shown only) or EXCLUSIVE (0–30%, added on
  top as a TAX line per merchandise line, with the same quantity) and a registration number.

**How the charge lines are treated.**
- Charge lines carry no product, no discount and **no commission**: merchandise_net =
  seller_payable = buyer_paid = the amount.
- The 20% commission base stays merchandise after seller discounts.
- The ledger and reconciliation need no change: charges are ordinary item snapshots accrued to the
  seller and refunded with the same cumulative rounding.

**Refunds.**
- A cancellation or dispute refund returns everything that remains, delivery included.
- A return refunds the returned units and their tax, not the delivery fee.

## Tracking, invoices, reports

- **Tracking.** At shipment the seller records a courier and a reference.
  `POST merchant/orders/<id>/tracking` adds progress events (picked up, in transit, out for
  delivery, attempted, delayed, note) to a SHIPPED order. Tracking never changes the order or
  payment status: delivery is still confirmed by the buyer or Racheeta finance.
- **Documents.** An INVOICE and a RECEIPT are issued when finance verifies the (simulated)
  payment, and a CREDIT_NOTE for each refund.
  - Each is a frozen JSON snapshot: seller of record, buyer, lines with variant and SKU, discounts,
    delivery, tax and totals. Later edits never change it.
  - Buyers see them at `orders/<id>/invoices`, and the seller's team at
    `merchant/orders/<id>/invoices`. Anyone else gets a 404.
  - Buyers never see the commission.
  - Orders paid before documents existed get theirs on first request (idempotent).
  - The web page is printable.
- **Reports.**
  - `merchant/reports/sales` (`company.reports.view` = OWNER, MANAGER, FINANCE): orders in a
    period, commission, delivery, tax, refunds, earnings, monthly totals and payouts.
  - `admin/commerce/reports/marketplace` (finance only): per-seller GMV, commission,
    Racheeta-funded discounts, charges, refunds, payouts, payable and receivable, with the
    reconciliation verdict.
  - `?export=csv` downloads either report as a spreadsheet; cells that start like a formula are
    neutralized.

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
| store activation, delivery and tax settings | OWNER, MANAGER |
| verification documents | OWNER, MANAGER |
| accounting report (CSV) | OWNER, MANAGER, FINANCE |

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

**Seller onboarding and catalogue** (`?company=` for staff)
- `POST marketplace/pharmacy-store`
- `marketplace/company/store` (GET, PATCH) and `…/store/status`
- `marketplace/company/documents`, `…/<id>` (DELETE), `…/<id>/file`
- `marketplace/company/shipping-rates` and `…/<id>`
- `marketplace/company/products/<id>/variants`, `marketplace/company/variants/<id>`
- `marketplace/company/products/<id>/images`, `marketplace/company/images/<id>`
- `GET marketplace/images/<id>` (public only for a product on sale)
- `merchant/orders/<id>/tracking`
- `merchant/orders/<id>/invoices[/<invoice>]`
- `merchant/reports/sales[?export=csv]`
- Administrators: `admin/marketplace/documents`, `…/<id>/decision`, `…/<id>/file`

**Buyer documents**
- `orders/<id>/invoices[/<invoice>]`

**Finance**
- `admin/commerce/reports/marketplace[?export=csv]`
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
| `marketplace 0006` | Pharmacy store link, store status (existing rows ACTIVE), seller-declared tax, delivery defaults, category rules, product SKU, `ProductVariant`, `ProductImage`, `SellerDocument`, `ShippingRate` |
| `marketplace 0007` | `documents_complete` (fail closed: existing stores without approved documents stop selling) |
| `commerce 0006` | A TAX line cascades with its merchandise line (needed by the demo cleanup) |
| `commerce 0005` | Order item kind (MERCHANDISE / SHIPPING / TAX), variant and SKU snapshots, order delivery and tax snapshots, variant-aware stock movements and quotes, `TrackingEvent`, `Invoice` |

To roll back the seller and product slice: run `migrate commerce 0004`, then
`migrate marketplace 0005`. This was verified on 2026-11-06 on a throwaway database (migrate →
roll back → re-migrate).

With data, first delete the SHIPPING/TAX lines and the variant orders (the old schema needs a
product on every line), the invoices and tracking events. On the demo database that means
`scripts/local_demo.sh clear`, which also deletes the uploaded demo files.

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
