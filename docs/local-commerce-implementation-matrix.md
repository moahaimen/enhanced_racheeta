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
| Per-organization capability checks on every seller endpoint (`?company=`) | PASS | T: `test_seller_endpoints_never_cross_organizations` (9 reads + 8 writes × rival owner and rival MANAGER), `test_an_ended_membership_loses_every_seller_tool_at_once`, `test_a_seller_never_sees_the_other_sellers_order_of_the_same_checkout`, `test_another_seller_cannot_touch_my_orders_returns_or_stock` |
| PRODUCT_EDITOR edits products of the business it works for | PASS | T: specialist-roles test (PATCH via `?company=`); VIEWER is refused |
| Seller cannot set verification, commission, payment, refund or payout | PASS | no such seller endpoint; T: `test_seller_cannot_mark_delivered_or_paid_…`, `test_only_finance_can_…` |
| Company onboarding and verification request | PASS | T: `test_every_seller_category_onboards_sells_and_refunds_with_20_percent` (×8 business types, all through the API) |
| Pharmacy sells WITHOUT leaving its provider identity (store linked to its pharmacy profile; role stays PROVIDER; facility workspace kept) | PASS | T: `test_a_pharmacy_opens_its_store_and_keeps_its_provider_identity`, `test_only_a_pharmacy_can_open_a_pharmacy_store`, `test_a_pharmacy_store_stops_selling_when_the_pharmacy_loses_verification`; W: pharmacy start + doctor refused; B: Al-Amal store order RCH-261106-A850B0 |
| Seller document upload / licence evidence (private, type-sniffed, size-limited, active PDFs refused, random names, nosniff + sandbox CSP) | PASS (local storage) | T: `test_dangerous_or_broken_documents_are_refused` (×7), `test_documents_are_private_random_named_and_served_safely`; production needs private object storage and malware scanning (NOT IMPLEMENTED) |
| Racheeta document review (approve, reject with reason) and verification decision in the web console | PASS | T: activation test; W: admin sellers tab; S: Tigris (pending doc), Noor (rejected doc) |
| Store activation as a separate step (needs verification AND every required document approved; pause any time) | PASS | T: `test_store_activation_needs_verification_and_approved_documents_and_pausing_hides_products`; W: setup tab refuses activation while a document is missing. Stores that existed before keep selling (migration default ACTIVE, documented). Re-verifying a store with missing documents puts it back to INACTIVE: T: `test_reverifying_a_legacy_store_without_documents_does_not_reopen_it`; the existing visibility test now also proves the store stays hidden until its documents are approved and it is re-activated |
| Required documents per business type | PASS (fictional rule set) | `marketplace.types.REQUIRED_DOCUMENTS`; not a statement of Iraqi licensing law |

## 2. Compliance (fail closed)

| Feature | Status | Evidence / note |
|---|---|---|
| Compliance classes B2C_ALLOWED / B2B_VERIFIED_ONLY / QUOTE_ONLY / RESTRICTED_PENDING_REVIEW / PROHIBITED on categories; default is pending review | PASS | migration `marketplace/0004`; the fixtures had to classify their categories explicitly |
| Public store shows only B2C_ALLOWED, non-restricted products from verified retail sellers | PASS | T: `test_store_lists_only_allowed_consumer_products` |
| Checkout refuses restricted, pending-review and prohibited items | PASS | T: `test_checkout_rejects_restricted_and_out_of_stock`, `test_unverified_seller_and_prohibited_category_cannot_sell` |
| B2B_VERIFIED_ONLY sold only to a verified, targeted professional; direct B2B purchase needs that explicit class (B2C_ALLOWED no longer grants it) | PASS | T: `test_b2b_product_is_sold_only_to_a_targeted_verified_professional`, `test_previously_published_products_keep_only_their_old_purchase_paths` |
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
| Immutable double-entry ledger: triggers refuse UPDATE, DELETE and TRUNCATE; no session bypass; policy versions protected | PASS (database level) | T: `test_ledger_rows_cannot_be_changed_or_deleted`, `test_the_session_purge_flag_no_longer_bypasses_immutability`, `test_truncate_of_ledger_tables_is_refused` |
| Application credentials cannot alter history (production role setup) | PASS (verified locally) / **operator action required in production** | T: `test_a_restricted_runtime_role_cannot_change_history_even_with_tricks`, `test_ledger_db_audit_flags_an_owner_or_superuser_connection`; real login-role check on a throwaway DB (§Audit). Production must run with a non-owner runtime role (`ledger_db_audit --grant-sql/--strict`) |
| Posting refuses unbalanced, negative, fractional or non-IQD entries | PASS | T: `test_posting_refuses_unbalanced_negative_fractional_and_foreign_currency` |
| Idempotent payment and accrual (retries, double clicks, concurrent workers) | PASS | T: `test_payment_and_accrual_post_exactly_once`, `test_two_finance_operators_completing_at_once_accrue_once` (real threads) |
| Proportional compensating refunds (cumulative rounding, adds up exactly) | PASS | T: `test_partial_then_full_return_reverses_commission_proportionally`, `test_refunding_unit_by_unit_adds_up_exactly_with_odd_amounts`; B: return refund 92,000 |
| Reconciliation: 5 balances re-derived (cash, buyer funds held, commission, Racheeta coupons, seller net position) plus 6 integrity checks (entries balance, no negative payable, no negative receivable, payable/receivable netted, payment entry per paid order, one accrual per order) | PASS | T: every finance and audit test asserts `reconciliation()["ok"]`; demo DB reconciled after seed → seed → clear → seed |
| Separate accounting domain (not `billing` or `advertising` payments) | PASS | `apps/ledger` only posts marketplace orders and settlements |
| Delivery fees (per governorate, default, free-over, delivery estimate) as pass-through SHIPPING lines, no commission | PASS | T: `test_delivery_fee_goes_to_the_seller_without_commission`, `test_delivery_rules_free_over_threshold_and_unserved_governorates`, `test_cancelled_paid_order_refunds_delivery_but_a_return_does_not`; B: 8 walkthrough orders |
| Seller-declared tax (NONE default / INCLUSIVE shown only / EXCLUSIVE 0–30% TAX lines refunded with the goods), no commission on tax | PASS | T: `test_seller_declared_tax_is_passed_through_and_refunded_with_the_goods`; B: Sharq 5% EXCLUSIVE, Aman INCLUSIVE. Racheeta decides no tax obligation |
| Payment processing costs | NOT IMPLEMENTED (by design) | no payment provider exists |
| Multi-currency | NOT IMPLEMENTED (by design) | IQD only; any other currency is refused (no exchange-rate snapshot exists) |

## 4. Payments, payouts (simulated)

| Feature | Status | Evidence / note |
|---|---|---|
| Finance-only simulated payment verification (reference required), posted once | PASS | T: finance tests; B: SIM-COD-REMIT-E2E-1 |
| Support staff without the finance permission refused (403) everywhere | PASS | T: `test_only_finance_can_verify_complete_refund_or_read_the_ledger`; W: refusal message; B: `local-support` refused |
| Payout preview (prepare) → finance confirms PAID, one PAYOUT entry | PASS | T: `test_payout_is_prepared_then_confirmed_once_by_finance`; B: rehab payout 291,680 IQD |
| A payout can never exceed what is owed (refund after preparation leaves it stale) | PASS | T: `test_a_payout_cannot_exceed_what_is_owed_after_a_refund`, `test_refund_racing_a_payout_confirmation_stays_consistent` (threads ×3) |
| Refund AFTER a confirmed payout: payable never negative; SELLER_RECEIVABLE; offset against next sales; finance recovery (simulated) | PASS | T: `test_full_refund_after_payout_creates_a_receivable_not_a_negative_payable`, `test_partial_refund_after_payout_is_offset_by_the_next_sales`, `test_refund_takes_from_what_is_still_held_before_creating_a_receivable`, `test_finance_records_recovery_never_more_than_owed`, `test_two_refunds_after_payout_at_once_add_up` (threads); W: receivable test; S: `POST_PAYOUT_REFUNDS` (Al-Aman owes 20,000) |
| Merchant statement (sales, discounts, commission, refunds, earnings, paid out, owed) | PASS | T: payout test; W: seller statement test; B: seller statement tab |
| Real payment provider, bank transfers, automatic payouts | NOT IMPLEMENTED (forbidden) | local demo only; see `docs/MARKETPLACE_COMMERCE.md` §Legal and payment constraints |

## 5. Orders, inventory, offers, quotes

| Feature | Status | Evidence / note |
|---|---|---|
| One checkout → one order per seller; buyer sees them grouped; each seller sees only its own order | PASS | T: `test_one_checkout_splits_into_one_order_per_seller…`, `test_multi_seller_checkout_snapshots_each_order`; B: CHK-261106-808AAE (2 orders), the rehab seller saw only its own |
| Server-only prices; forged price, fee, status or seller ignored | PASS | T: `test_forged_prices_fees_statuses_and_sellers_are_ignored`, `test_checkout_uses_server_prices_and_reserves_stock`; W: payload contains no price, total, commission or merchant |
| Two-click / retried checkout creates one checkout (idempotency key) | PASS | T: `test_two_clicks_on_place_order_create_one_checkout`, `test_same_checkout_key_sent_twice_at_once_creates_one_checkout` (threads), `test_the_same_request_again_is_a_replay_whatever_the_line_order`; W: key sent |
| Key reused with a DIFFERENT request (items, coupons, address, phone, payment) → 409, nothing created | PASS | T: `test_reusing_a_key_for_a_different_request_is_refused` (×5) |
| Order state machine: seller accept/decline/ship; buyer cancel/confirm; finance confirm/complete | PASS | T: `test_seller_cannot_mark_delivered_or_paid_…`, `test_buyer_cancel_restores_stock_and_only_before_shipping`; B: full lifecycle |
| Inventory on hand / reserved / available / threshold, movement ledger | PASS | T: `test_stock_never_drops_below_reserved_and_low_stock_alerts`; B: seller inventory tab |
| Reserve at checkout, release exactly once, consume on ship, restock on received return | PASS | T: `test_cancelling_releases_stock_exactly_once`, `test_last_unit_is_sold_once` (threads, ×3); B: chair stock 12 → 10 after 3 shipped and 1 returned |
| Low-stock notification (deduplicated per product per day) | PASS | T: low-stock test |
| Seller-funded coupons and sales; Racheeta-funded coupons; expiry, max uses, one per buyer, stacking limits, release on cancel | PASS | T: `test_coupon_abuse_is_refused`; B: coupon preview |
| Returns (window 14 days, quantity limits) → approve → received → finance refund | PASS | T: `test_buyer_cannot_return_more_than_bought_or_outside_the_window`, return tests; B: return of RCH-…4B74E0 |
| Disputes (one open per order) → finance resolves with or without refund | PASS | T: `test_dispute_resolved_with_refund_after_completion`; S: `ali-open-dispute` |
| Paid order cancelled before shipping → REFUND_PENDING → finance refund | PASS | T: `test_paid_order_cancelled_before_shipping_is_refunded_by_finance`; S: `zainab-paid-cancelled-refunded` |
| Quote → accept → order at quoted price, 20%, once; expired quote refused | PASS | T: `test_accepted_quote_becomes_one_order_at_the_quoted_price`, `test_expired_quote_cannot_be_accepted`; S: `amal-fridge` |
| SKUs (unique per business across products and variants) and product variants with their own price and stock | PASS | T: `test_variants_have_their_own_sku_price_and_stock`, `test_a_variant_of_another_product_or_store_cannot_be_bought_or_edited`, `test_the_last_unit_of_a_variant_is_sold_once` (threads), `test_a_product_whose_options_are_all_hidden_cannot_be_bought`; W: option picker, one cart line per option; B: sleeve M, bandage 10 cm, gloves M, swabs box of 50 |
| Bundles | NOT IMPLEMENTED | — |
| Product photos (validated JPEG/PNG/WebP, private until the product is on sale) | PASS | T: `test_product_photos_are_validated_and_hidden_until_the_product_is_on_sale`. Not re-encoded (no image library installed): EXIF metadata is not stripped (PARTIAL for privacy) |
| Category-specific compliance rules (allowed business types, required documents, max per order, buyer notice) | PASS | T: `test_category_rules_limit_who_publishes_what_and_how_many`; S: `demo-pharmacy-care` (pharmacies only, 3 per order) |
| Buyer invoice, payment receipt, credit note per refund (frozen snapshots, buyer + seller only, printable) | PASS (HTML print) | T: `test_invoices_are_frozen_snapshots_visible_only_to_the_buyer_and_the_seller`, `test_orders_paid_before_documents_existed_get_them_on_first_request`; W: printable document; B: all 8 orders have INVOICE + RECEIPT + CREDIT_NOTE. No server PDF or legal e-invoice numbering |
| Delivery tracking (courier, reference, progress events; never changes the order status) | PASS (manual) | T: `test_tracking_events_are_the_sellers_and_never_change_the_status`; B: 8 sellers posted "In transit". No courier integration |
| Seller and platform accounting reports, CSV (formula-safe) | PASS | T: `test_accounting_reports_match_the_ledger_and_are_scoped`, `test_report_csv_cannot_inject_spreadsheet_formulas`; W: seller report; finance report tab |
| Direct B2B purchase from the professional catalogue (B2B_VERIFIED_ONLY, with options) | PASS | T: every-category test (4 B2B types); B: CHK-261106-07943C |

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
| seed → seed (no change) → clear → seed | PASS | after the audit: 2,106 rows each seed; clear removed 2,152 rows, including 22 ledger entries, 54 lines and 2 settlements (the first clear also removed the browser walkthrough's 8 entries and 24 lines) |
| Demo ledger cleanup only on the guarded local demo DB (owner-only `DISABLE TRIGGER` inside the cleaner's transaction; restored before commit) | PASS | T: `test_demo_cleaner_unlocks_the_ledger_only_on_the_guarded_local_demo_db`, `test_demo_cleaner_triggers_come_back_after_its_transaction`; demo DB: all 8 ledger triggers enabled after clear and seed |
| Cleaner proves walkthrough-created rows demo-owned transitively (never infers an account) | PASS | T: `test_cleaner_proves_walkthrough_rows_demo_owned_but_never_real_users`; the existing refusal tests in `apps/demo/tests/test_clear.py` all pass |
| Finance (`local-finance`) and support (`local-support`) staff, non-superuser | PASS | seeded with `--with-admin`; credentials only in `local-demo/.env.demo` (git-ignored) |

## Audit of 2026-11-06 (independent financial and security review)

Each finding was first reproduced with a probe test against the code as it stood (commit `a487f6a`).
Then it was fixed and pinned by a regression test in `backend/apps/commerce/tests/test_audit_regressions.py` (23 test functions, 30 cases).

Verification after the audit:
- backend: 2,186 passed, 1 skipped (firebase SDK not installed locally);
- web: 550 passed, typecheck clean, lint at the 6 pre-existing warnings, build OK;
- OpenAPI: 0 errors, 0 warnings;
- demo: seed → seed → clear → seed, reconciled with all 11 checks passing;
- browser: a finance recovery of 20,000 IQD cleared Al-Aman's receivable, and all 11 checks passed.

| # | Finding (reproduced) | Fix | Regression evidence |
|---|---|---|---|
| 1 | **Refund after a confirmed payout made the seller payable negative (−80,000)**; reconciliation failed `no_negative_seller_payable`. There was no receivable, offset or recovery. | New SELLER_RECEIVABLE account (`ledger 0003`). Refunds take from what is still held for the seller, and the rest becomes a receivable. Completed sales settle the receivable first. Finance can record a recovery (`admin/ledger/recoveries`). All seller-balance decisions take the seller row lock. Reconciliation checks the net seller position, plus no negative receivable and payable/receivable netting. | full, partial, held-first, recovery and over-recovery tests; refund-vs-payout race (threads ×3); two concurrent refunds |
| 2a | **Any session could bypass immutability** with `set_config('racheeta.ledger_purge','on')`, including the application's own credentials. | The bypass was removed from `ledger_refuse_change()` (`ledger 0004`). | `test_the_session_purge_flag_no_longer_bypasses_immutability` |
| 2b | **TRUNCATE wiped the ledger** (5 → 0 lines); row triggers do not fire on TRUNCATE. | BEFORE TRUNCATE triggers on all append-only ledger tables, refusing any non-empty table. | `test_truncate_of_ledger_tables_is_refused` |
| 2c | **The table owner can disable triggers**, and the app connected as owner and superuser. This cannot be solved inside the database. | `ledger_db_audit` command (`--strict`, `--grant-sql`); the documented runtime-role requirement; recovery and policy tables protected; demo cleanup uses owner-only DISABLE TRIGGER inside its guarded transaction. | restricted-role test; command test; real login-role check (`--strict` OK; DELETE/TRUNCATE "permission denied"; DISABLE TRIGGER "must be owner") |
| 3 | `marketplace 0004` auto-approved **inactive legacy consumer categories** and **consumer categories containing regulated items**. Legacy consumer categories also silently gained **direct B2B purchase** (before: quotation only). | `marketplace 0005` demotes those to RESTRICTED_PENDING_REVIEW (only demotes, idempotent). Direct B2B checkout now requires an explicit B2B_VERIFIED_ONLY class; other professional items get `quote_only`. 0004 itself is unchanged (already applied). | `test_legacy_migration_never_authorizes_more_than_before`, `test_previously_published_products_keep_only_their_old_purchase_paths`, `test_regulated_and_unreviewed_products_never_reach_the_store` |
| 4 | **OpenAPI generation error**: two override names for one choice set, so provider/employer verification fields were published as `CompanyVerificationStatusEnum`. Plus 3 operationId collisions. | One shared `VerificationStatusEnum` / `VerificationDecisionEnum`; explicit operation IDs on the 3 list views. | `scripts/export_openapi.sh`: **0 errors, 0 warnings** (before: 1 error, 3 warnings) |
| 5 | **Idempotency-key reuse with a different request returned the first checkout** (quantity 5 silently ignored, 200). | `Checkout.request_hash` (`commerce 0004`): the same request replays; a different one returns 409 `idempotency_conflict`. Quote orders are covered too. | 5 parametrized conflict cases; replay with reordered lines; another buyer's key is independent |
| 6 | A rival seller adjusting another store's stock got **400 instead of 404**. Scoping held, but the error disclosed nothing useful. | Inventory "not found" now uses the `not_found` code (404). The existing test expectation was made stricter (400 → 404). | the organization sweep over every seller endpoint |
| 7 | Found during the fixes: the demo cleaner **could not remove rows created in browser walkthroughs** (multi-level references). Its dry-run report also **double-counted** adopted rows, and a ledger entry that references no order (a recovery) would have been **left behind** with its lines removed. | Ownership proof made transitive and anchored (accounts never inferred); blockers not yet proven are retried rather than refused; each row is counted once; entries posted by registered demo operators are included. | `test_cleaner_proves_walkthrough_rows_demo_owned_but_never_real_users`, `test_cleaner_removes_a_demo_operators_entry_that_has_no_order`; the 64 existing demo-cleaner tests (including the real-user refusals) pass; after a real clear the demo DB holds 0 ledger rows and 0 disabled triggers |

**Not changed by the audit.** No existing financial record was edited. The demo data was cleared
and re-seeded through the guarded tooling only. No test expectation was weakened; the only edited
expectation (finding 6) is stricter.


## Seller workspaces, products, orders and advertising (2026-11-06, second slice)

Verification: backend 2,227 passed, 1 skipped (firebase SDK not installed locally); web 559
passed, typecheck clean, lint at the 6 pre-existing warnings, build OK; OpenAPI 0 errors, 0
warnings; migrations `marketplace 0006` and `commerce 0005` roll back and re-apply on a throwaway
database; demo seed → seed (2,333 rows each) → clear (all uploaded demo files deleted, 0 disabled
ledger triggers) → seed.

New tests: `apps/commerce/tests/test_sellers_products_orders.py` (28 functions, 41 cases) and
`web/src/pages/market/SellerFeatures.test.tsx` (9). Existing tests were not weakened. Three exact
expectations were extended with new fields: the dashboard counts dict, the reviewed public-API list
(product photos), and the writable product fields (`sku`). One existing test
(`test_visibility_follows_current_server_state`) gained steps: a re-verified store without approved
documents must now stay hidden, so the test approves the documents and re-activates the store
before asserting that the product is visible again. Two query-count budgets were kept by
restructuring the code, not by raising them.

### Browser purchase-and-refund walkthrough, one per seller type (local demo DB)

Buyers: `patient-sara` (public store, cash on delivery) and `dr-ahmed-jabouri` (verified doctor,
direct B2B, simulated manual transfer). Each seller accepted, shipped with a courier and posted a
tracking update. Each buyer confirmed receipt. `local-finance` verified the simulated payment and
completed the order (20% accrued), then refunded it: Rehab through a return (the seller approved it
and marked it received), the other seven through disputes.

| Seller type | Account | Order | Paid (incl. delivery/tax) | Commission (20% of goods) | Refund | Ledger | Documents |
|---|---|---|---|---|---|---|---|
| Assistive device store | `company-rehab-mobility` | RCH-261106-767AEA | 70,000 (5,000 delivery) | 13,000 | 65,000 via return (delivery kept) | PAYMENT, ACCRUAL, REFUND | invoice, receipt, credit note |
| Medical equipment supplier | `company-sharq-devices` | RCH-261106-B570B2 | 46,500 (15,000 delivery + 1,500 tax 5%) | 6,000 | 46,500 via dispute | same | same |
| Medical supplies office | `company-aman-consumables` | RCH-261106-0D5C32 | 27,000 (3,000 delivery; 1,143 tax included) | 4,800 | 27,000 | same | same |
| Pharmacy (provider account) | `amal-pharmacy` | RCH-261106-A850B0 | 8,000 (2,000 delivery) | 1,200 | 8,000 | same | same |
| Pharmaceutical company | `company-dijla-pharma` | RCH-261106-1E6D2E | 25,000 (7,000 delivery) | 3,600 | 25,000 | same | same |
| Scientific office | `company-ibn-sina-scientific` | RCH-261106-FB0D4F | 22,000 | 4,400 | 22,000 | same | same |
| Pharmaceutical distributor | `company-kurdistan-medicines` | RCH-261106-DCDC90 | 9,000 | 1,800 | 9,000 | same | same |
| Medical company (new seller) | `company-hayat-medical` | RCH-261106-AFE4B5 | 22,000 (10,000 delivery) | 2,400 | 22,000 | same | same |

After the walkthrough, reconciliation passed all 11 checks.

### Advertising (Priority 4)

| Feature | Status | Evidence / note |
|---|---|---|
| Targeted professional product advertisements | PASS (pre-existing, re-run) | `apps/advertising/tests` (264 pass); sponsored products now carry the first uploaded photo with no extra query |
| Clearly labelled sponsored dashboard placements | PASS (pre-existing) | W: `sponsored section appears only when the server includes it, labelled as sponsored`; `sponsored: true` on every ad payload |
| User-controlled optional notification preferences (display off; outreach opt-in, all off by default) | PASS (pre-existing) | `apps/preferences/tests` |
| No advertising of regulated medicines or devices; only selling stores (verified + store ACTIVE) can advertise | PASS | T: `test_regulated_products_can_never_be_advertised`, `test_a_pharmacy_can_advertise_only_while_selling_and_never_regulated_items`; `selling_q` in `visible_to` |

### Known gaps (honest)

- Uploads use the local filesystem: there is no object storage, malware scanning or EXIF stripping.
- Invoices are browser-printable HTML: there is no server-side PDF or legal e-invoice numbering.
- Tracking is entered manually: there is no courier integration.
- Required documents and tax treatment are fictional, seller-declared local rules, not legal or
  tax advice.
- Delivery fees are not refunded on a return (a stated policy). A cancellation or dispute refund
  returns them.
