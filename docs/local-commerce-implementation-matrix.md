# Local commerce implementation matrix (multi-vendor marketplace, 20% commission)

LOCAL ONLY. Fictional data, simulated money. Nothing here is deployed, and no real payment is made.

Status legend:
- **PASS**: implemented, and verified by automated tests and/or the browser walkthrough (evidence column).
- **PARTIAL**: works, but part of the spec is missing (stated).
- **NOT IMPLEMENTED**: not built in this slice.

Evidence keys:
- `T:` a backend pytest in `backend/apps/**/tests`.
- `W:` a web vitest.
- `B:` the browser walkthrough of 2026-11-06 (local demo DB, 127.0.0.1:5180).
- `S:` a seeded demo scenario (`apps/demo/content/local_extras.py`).

## 1. Sellers, organizations, staff

| Feature | Status | Evidence / note |
|---|---|---|
| Seller roles OWNER, MANAGER, PRODUCT_EDITOR, STOCK_MANAGER, FULFILLMENT, FINANCE, VIEWER (plus legacy STAFF) | PASS | T: `test_specialist_staff_roles_do_only_their_job`, `test_facility_cannot_be_given_a_seller_only_role`; migration `workspaces/0002_seller_roles` |
| Per-organization capability checks on every seller endpoint (`?company=`) | PASS | T: `test_another_seller_cannot_touch_my_orders_returns_or_stock`, `test_other_buyers_and_other_stores_cannot_see_an_order`, `test_staff_roles_viewer_reads_staff_manages_ended_loses_access` |
| PRODUCT_EDITOR edits products of the business it works for | PASS | T: specialist-roles test (PATCH via `?company=`); VIEWER is refused |
| Seller cannot set verification, commission, payment, refund or payout | PASS | no such seller endpoint; T: `test_seller_cannot_mark_delivered_or_paid_…`, `test_only_finance_can_…` |
| Company onboarding and verification request (existing) | PASS (pre-existing) | `apps/marketplace` (unchanged) |
| Seller document upload / licence evidence | NOT IMPLEMENTED | there is no safe file storage yet; verification stays an admin decision |
| Store activation request as a separate step | NOT IMPLEMENTED | publication is gated by company verification plus category compliance |

## 2. Compliance (fail closed)

| Feature | Status | Evidence / note |
|---|---|---|
| Compliance classes B2C_ALLOWED / B2B_VERIFIED_ONLY / QUOTE_ONLY / RESTRICTED_PENDING_REVIEW / PROHIBITED on categories; default is pending review | PASS | migration `marketplace/0004`; the fixtures had to classify their categories explicitly |
| Public store shows only B2C_ALLOWED, non-restricted products from verified retail sellers | PASS | T: `test_store_lists_only_allowed_consumer_products` |
| Checkout refuses restricted, pending-review and prohibited items | PASS | T: `test_checkout_rejects_restricted_and_out_of_stock`, `test_unverified_seller_and_prohibited_category_cannot_sell` |
| B2B_VERIFIED_ONLY sold only to a verified, targeted professional | PASS | T: `test_b2b_product_is_sold_only_to_a_targeted_verified_professional` |
| QUOTE_ONLY cannot be bought directly; only through an accepted quote | PASS | T: `test_accepted_quote_becomes_one_order_at_the_quoted_price` |
| Unverified or suspended seller cannot sell | PASS | T: `test_unverified_seller_and_prohibited_category_cannot_sell`, `test_suspended_store_disappears` |
| Regulated products cannot be advertised (campaign creation and paid exposure refused) | PASS | T: `test_regulated_products_can_never_be_advertised` (restricted, PROHIBITED, pending review); `advertising.services._advertisable` |

## 3. Commission and ledger

| Feature | Status | Evidence / note |
|---|---|---|
| `MarketplaceCommissionPolicy` v1 = 20.00%, versioned, snapshotted per order and per line | PASS | T: `test_policy_change_never_rewrites_an_existing_order` |
| 100,000 IQD → 20,000 fee → 80,000 payable | PASS | T: `test_100000_sale_gives_20000_commission_and_80000_payable`; S: `hassan-100k`; B: order RCH-261106-4B74E0 |
| 100,000 with a 10% seller sale → 90,000 → 18,000 fee → 72,000 payable | PASS | T: `test_seller_discount_to_90000_…`, `test_seller_coupon_lowers_the_commission_base`; S: `zainab-90k-offer` |
| Racheeta-funded coupon does not reduce the commission base or the seller payable | PASS | T: `test_platform_coupon_is_paid_by_racheeta_not_the_seller`; B: RACHEETA10K, buyer paid 92,000, seller payable stayed 80,000 |
| Decimal amounts, whole-dinar ROUND_HALF_UP, exact largest-remainder allocation | PASS | T: `test_rounding_is_whole_dinars_half_up_and_allocation_is_exact` |
| No fee at order creation; accrual only when PAID + DELIVERED with no open return or dispute | PASS | T: `test_completion_needs_payment_delivery_and_no_open_return` |
| Immutable double-entry ledger (DB trigger refuses UPDATE/DELETE) | PASS | T: `test_ledger_rows_cannot_be_changed_or_deleted` |
| Posting refuses unbalanced, negative, fractional or non-IQD entries | PASS | T: `test_posting_refuses_unbalanced_negative_fractional_and_foreign_currency` |
| Idempotent payment and accrual (retries, double clicks, concurrent workers) | PASS | T: `test_payment_and_accrual_post_exactly_once`, `test_two_finance_operators_completing_at_once_accrue_once` (real threads) |
| Proportional compensating refunds (cumulative rounding, adds up exactly) | PASS | T: `test_partial_then_full_return_reverses_commission_proportionally`, `test_refunding_unit_by_unit_adds_up_exactly_with_odd_amounts`; B: return refund 92,000 |
| Reconciliation (5 balances re-derived from orders, plus 4 integrity checks) | PASS | T: every finance test asserts `reconciliation()["ok"]`; B: all 9 checks passed after the browser run |
| Separate accounting domain (not `billing` or `advertising` payments) | PASS | `apps/ledger` only posts marketplace orders and settlements |
| Shipping fees, taxes, processing costs | NOT IMPLEMENTED | no shipping or tax lines exist; the commission base is merchandise only, as specified |
| Multi-currency | NOT IMPLEMENTED (by design) | IQD only; any other currency is refused (no exchange-rate snapshot exists) |

## 4. Payments, payouts (simulated)

| Feature | Status | Evidence / note |
|---|---|---|
| Finance-only simulated payment verification (reference required), posted once | PASS | T: finance tests; B: SIM-COD-REMIT-E2E-1 |
| Support staff without the finance permission refused (403) everywhere | PASS | T: `test_only_finance_can_verify_complete_refund_or_read_the_ledger`; W: refusal message; B: `local-support` refused |
| Payout preview (prepare) → finance confirms PAID, one PAYOUT entry | PASS | T: `test_payout_is_prepared_then_confirmed_once_by_finance`; B: rehab payout 291,680 IQD |
| A payout can never exceed what is owed (refund after preparation leaves it stale) | PASS | T: `test_a_payout_cannot_exceed_what_is_owed_after_a_refund` |
| Merchant statement (sales, discounts, commission, refunds, earnings, paid out, owed) | PASS | T: payout test; W: seller statement test; B: seller statement tab |
| Real payment provider, bank transfers, automatic payouts | NOT IMPLEMENTED (forbidden) | local demo only; see `docs/MARKETPLACE_COMMERCE.md` §Legal and payment constraints |

## 5. Orders, inventory, offers, quotes

| Feature | Status | Evidence / note |
|---|---|---|
| One checkout → one order per seller; buyer sees them grouped; each seller sees only its own order | PASS | T: `test_one_checkout_splits_into_one_order_per_seller…`, `test_multi_seller_checkout_snapshots_each_order`; B: CHK-261106-808AAE (2 orders), the rehab seller saw only its own |
| Server-only prices; forged price, fee, status or seller ignored | PASS | T: `test_forged_prices_fees_statuses_and_sellers_are_ignored`, `test_checkout_uses_server_prices_and_reserves_stock`; W: payload contains no price, total, commission or merchant |
| Two-click / retried checkout creates one checkout (idempotency key) | PASS | T: `test_two_clicks_on_place_order_create_one_checkout`, `test_same_checkout_key_sent_twice_at_once_creates_one_checkout` (threads); W: key sent |
| Order state machine: seller accept/decline/ship; buyer cancel/confirm; finance confirm/complete | PASS | T: `test_seller_cannot_mark_delivered_or_paid_…`, `test_buyer_cancel_restores_stock_and_only_before_shipping`; B: full lifecycle |
| Inventory on hand / reserved / available / threshold, movement ledger | PASS | T: `test_stock_never_drops_below_reserved_and_low_stock_alerts`; B: seller inventory tab |
| Reserve at checkout, release exactly once, consume on ship, restock on received return | PASS | T: `test_cancelling_releases_stock_exactly_once`, `test_last_unit_is_sold_once` (threads, ×3); B: chair stock 12 → 10 after 3 shipped and 1 returned |
| Low-stock notification (deduplicated per product per day) | PASS | T: low-stock test |
| Seller-funded coupons and sales; Racheeta-funded coupons; expiry, max uses, one per buyer, stacking limits, release on cancel | PASS | T: `test_coupon_abuse_is_refused`; B: coupon preview |
| Returns (window 14 days, quantity limits) → approve → received → finance refund | PASS | T: `test_buyer_cannot_return_more_than_bought_or_outside_the_window`, return tests; B: return of RCH-…4B74E0 |
| Disputes (one open per order) → finance resolves with or without refund | PASS | T: `test_dispute_resolved_with_refund_after_completion`; S: `ali-open-dispute` |
| Paid order cancelled before shipping → REFUND_PENDING → finance refund | PASS | T: `test_paid_order_cancelled_before_shipping_is_refunded_by_finance`; S: `zainab-paid-cancelled-refunded` |
| Quote → accept → order at quoted price, 20%, once; expired quote refused | PASS | T: `test_accepted_quote_becomes_one_order_at_the_quoted_price`, `test_expired_quote_cannot_be_accepted`; S: `amal-fridge` |
| Product variants / SKUs, bundles | NOT IMPLEMENTED | one price per product |
| Buyer invoice / receipt document | PARTIAL | the order card shows the full server breakdown (items, discounts, paid, refunded); there is no printable invoice |

## 6. Dashboards, notifications, UI

| Feature | Status | Evidence / note |
|---|---|---|
| Cart: one checkout, coupon field, server-priced per-seller breakdown | PASS | W: `one checkout for two stores…`; B |
| My orders grouped by checkout; confirm receipt, return, dispute; no commission shown to buyers | PASS | W: buyer test; B |
| Seller center: orders (with 20% snapshot), returns, inventory, coupons and sales, statement | PASS | W: statement test; B |
| Seller workspace dashboard module `store_finance` (real ledger figures; owner and FINANCE only) | PASS | T: `test_seller_finance_module_shows_real_20_percent_figures_…` |
| Racheeta finance console: queues, returns, disputes, payouts, reconciliation, coupons, ledger, policy | PASS | B; W: refusal test |
| Notifications: order placed, status, paid, refunded, return requested, stock low, settlement paid | PASS | `notifications.presentation` (ar/en); T: low-stock and merchant-notified tests |
| Arabic RTL and English LTR at 1440 px and 390 px | PASS | screenshots in `local-demo/screenshots-marketplace/{ar,en}/{1440,390}/` (git-ignored) |
| Admin UI to create a new commission policy version | NOT IMPLEMENTED (by design) | read-only in the UI; a new version is a reviewed data migration, so a click can never change the rate |

## 7. Demo data and tooling

| Feature | Status | Evidence / note |
|---|---|---|
| Seeded scenarios: new, accepted, paid+shipped, delivered awaiting payment, 100k, 90k, Racheeta coupon, multi-vendor, cancelled, declined, paid→cancelled→refunded, partial return, open return, open dispute, quote→order, paid payout, draft payout | PASS | S: `MARKET_SCENARIOS`, `QUOTE_ORDERS`, `SETTLEMENTS` |
| seed → seed (no change) → clear → seed | PASS | 2,093 rows each seed; clear removed 2,139 rows, including 21 ledger entries, 51 lines and 2 settlements |
| Ledger purge only inside the guarded cleaner transaction (`set_config(..., true)`) | PASS | `apps/demo/cleaner._allow_ledger_purge` |
| Finance (`local-finance`) and support (`local-support`) staff, non-superuser | PASS | seeded with `--with-admin`; credentials only in `local-demo/.env.demo` (git-ignored) |
