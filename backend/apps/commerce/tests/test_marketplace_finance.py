"""The 20% marketplace: exact commission examples, simulated payment, accrual, refunds, payouts,
reconciliation, idempotency, and the security rules around them (all fictional money)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.commerce.models import Checkout, Coupon, Order, ProductOffer, StockMovement
from apps.commerce.pricing import allocate
from apps.ledger import posting
from apps.ledger.models import LedgerEntry, LedgerLine, MarketplaceCommissionPolicy
from apps.ledger.posting import LedgerError, Line, commission_of, dinars
from apps.ledger.settlement import reconciliation
from apps.ledger.types import Account
from apps.marketplace.types import BusinessType, SaleChannel
from apps.providers.types import ProviderType
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

CHECKOUTS = "/api/v1/checkouts"
ORDERS = "/api/v1/orders"
MERCHANT = "/api/v1/merchant"
ADMIN = "/api/v1/admin/commerce"
LEDGER = "/api/v1/admin/ledger"
D = Decimal


@pytest.fixture
def hundred_k(store, store_category, product_factory):
    return product_factory(
        store,
        store_category,
        title="Hospital bed (demo)",
        price=D("100000"),
        sale_channel=SaleChannel.B2C,
        stock_quantity=10,
    )


def _buy(buyer, checkout, lines, **extra):
    response = client_for(buyer).post(CHECKOUTS, checkout(lines, **extra), format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def _order(buyer, checkout, lines, **extra):
    return _buy(buyer, checkout, lines, **extra)["orders"][0]["id"]


def _post(client, url, body=None, expect=200):
    response = client.post(url, body or {}, format="json")
    assert response.status_code == expect, (url, response.json())
    return response.json()


def _ship(store, order_id):
    merchant = client_for(store.account)
    _post(merchant, f"{MERCHANT}/orders/{order_id}/transition", {"status": "CONFIRMED"})
    return _post(
        merchant,
        f"{MERCHANT}/orders/{order_id}/transition",
        {"status": "SHIPPED", "shipping_reference": "COURIER-1 (demo)"},
    )


def _deliver_pay_complete(buyer, finance, store, order_id):
    _ship(store, order_id)
    _post(client_for(buyer), f"{ORDERS}/{order_id}/confirm-delivery")
    fin = client_for(finance)
    _post(fin, f"{ADMIN}/orders/{order_id}/verify-payment", {"reference": "CASH-REMIT-1 (sim)"})
    return _post(fin, f"{ADMIN}/orders/{order_id}/complete")


def _reconciled():
    report = reconciliation()
    assert report["ok"], [c for c in report["checks"] if not c["ok"]]
    return report


# ---- the exact examples of the business decision


def test_100000_sale_gives_20000_commission_and_80000_payable(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    done = _deliver_pay_complete(buyer, finance, store, order_id)
    assert done["status"] == "COMPLETED" and done["settlement_state"] == "ACCRUED"
    assert D(done["merchandise_net"]) == D("100000")
    assert D(done["commission_total"]) == D("20000")
    assert D(done["seller_payable_total"]) == D("80000")
    assert D(done["commission_rate"]) == D("20.00") and done["commission_policy_version"] == 1
    assert posting.balance(Account.COMMISSION_REVENUE) == D("20000")
    assert posting.balance(Account.SELLER_PAYABLE, company_id=store.pk) == D("80000")
    assert posting.balance(Account.CUSTOMER_FUNDS_HELD) == 0
    _reconciled()


def test_seller_discount_to_90000_gives_18000_fee_and_72000_payable(
    buyer, finance, store, hundred_k, checkout
):
    now = timezone.now()
    ProductOffer.objects.create(
        company=store,
        product=hundred_k,
        percent=D("10"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=3),
    )
    placed = _buy(buyer, checkout, [(hundred_k, 1)])
    assert D(placed["total"]) == D("90000") and D(placed["seller_discount_total"]) == D("10000")
    done = _deliver_pay_complete(buyer, finance, store, placed["orders"][0]["id"])
    assert D(done["merchandise_net"]) == D("90000")
    assert D(done["commission_total"]) == D("18000")
    assert D(done["seller_payable_total"]) == D("72000")
    _reconciled()


def test_seller_coupon_lowers_the_commission_base(buyer, finance, store, hundred_k, checkout):
    now = timezone.now()
    Coupon.objects.create(
        code="STORE10K",
        funded_by="SELLER",
        company=store,
        kind="FIXED",
        value=D("10000"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
    placed = _buy(buyer, checkout, [(hundred_k, 1)], coupons=["store10k"])
    done = _deliver_pay_complete(buyer, finance, store, placed["orders"][0]["id"])
    assert (D(done["total"]), D(done["commission_total"]), D(done["seller_payable_total"])) == (
        D("90000"),
        D("18000"),
        D("72000"),
    )


def test_platform_coupon_is_paid_by_racheeta_not_the_seller(
    buyer, finance, store, hundred_k, checkout
):
    now = timezone.now()
    Coupon.objects.create(
        code="RACHEETA10",
        funded_by="PLATFORM",
        kind="PERCENT",
        value=D("10"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
    placed = _buy(buyer, checkout, [(hundred_k, 1)], coupons=["RACHEETA10"])
    assert D(placed["total"]) == D("90000") and D(placed["platform_discount_total"]) == D("10000")
    done = _deliver_pay_complete(buyer, finance, store, placed["orders"][0]["id"])
    assert D(done["merchandise_net"]) == D("100000")
    assert D(done["commission_total"]) == D("20000")
    assert D(done["seller_payable_total"]) == D("80000")
    assert -posting.balance(Account.PLATFORM_PROMO_EXPENSE) == D("10000")
    _reconciled()


def test_rounding_is_whole_dinars_half_up_and_allocation_is_exact():
    assert dinars(D("2.5")) == D("3") and dinars(D("2.49")) == D("2")
    assert commission_of(D("12347"), D("20.00")) == D("2469")  # 2469.4
    assert commission_of(D("12348"), D("20.00")) == D("2470")  # 2469.6
    assert allocate(D("10000"), [D("1"), D("1"), D("1")]) == [D("3334"), D("3333"), D("3333")]


def test_multi_seller_checkout_snapshots_each_order(
    buyer, store, store_category, hundred_k, company_factory, product_factory, checkout
):
    other = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    cane = product_factory(
        other, store_category, price=D("15000"), sale_channel=SaleChannel.B2C, stock_quantity=9
    )
    placed = _buy(buyer, checkout, [(hundred_k, 1), (cane, 2)])
    orders = {o["merchant"]["id"]: o for o in placed["orders"]}
    assert D(orders[str(store.pk)]["total"]) == D("100000")
    assert D(orders[str(other.pk)]["total"]) == D("30000")
    rows = {o.merchant_id: o for o in Order.objects.filter(checkout_id=placed["id"])}
    assert rows[store.pk].commission_total == D("20000")
    assert rows[other.pk].commission_total == D("6000")


# ---- idempotency and concurrency guards


def test_two_clicks_on_place_order_create_one_checkout(buyer, hundred_k, checkout):
    body = checkout([(hundred_k, 2)])
    client = client_for(buyer)
    first = client.post(CHECKOUTS, body, format="json")
    again = client.post(CHECKOUTS, body, format="json")
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    assert Checkout.objects.count() == 1 and Order.objects.count() == 1
    hundred_k.refresh_from_db()
    assert hundred_k.stock_reserved == 2


def test_payment_and_accrual_post_exactly_once(buyer, finance, store, hundred_k, checkout):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    fin = client_for(finance)
    _post(fin, f"{ADMIN}/orders/{order_id}/verify-payment", {"reference": "again"})
    _post(fin, f"{ADMIN}/orders/{order_id}/complete")
    assert LedgerEntry.objects.filter(order_id=order_id, kind="PAYMENT").count() == 1
    assert LedgerEntry.objects.filter(order_id=order_id, kind="ACCRUAL").count() == 1
    assert posting.balance(Account.COMMISSION_REVENUE) == D("20000")
    _reconciled()


def test_completion_needs_payment_delivery_and_no_open_return(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    fin = client_for(finance)
    _post(fin, f"{ADMIN}/orders/{order_id}/complete", expect=409)  # not delivered
    _ship(store, order_id)
    _post(client_for(buyer), f"{ORDERS}/{order_id}/confirm-delivery")
    _post(fin, f"{ADMIN}/orders/{order_id}/complete", expect=409)  # not paid
    _post(fin, f"{ADMIN}/orders/{order_id}/verify-payment", {"reference": "SIM-1"})
    item = Order.objects.get(pk=order_id).items.get()
    _post(
        client_for(buyer),
        f"{ORDERS}/{order_id}/returns",
        {"lines": [{"item": str(item.pk), "quantity": 1}], "reason": "Wrong size (demo)"},
    )
    _post(fin, f"{ADMIN}/orders/{order_id}/complete", expect=409)  # return open
    assert not LedgerEntry.objects.filter(kind="ACCRUAL").exists()


def test_cancelling_releases_stock_exactly_once(buyer, hundred_k, checkout):
    order_id = _order(buyer, checkout, [(hundred_k, 3)])
    client = client_for(buyer)
    _post(client, f"{ORDERS}/{order_id}/cancel")
    _post(client, f"{ORDERS}/{order_id}/cancel", expect=409)
    hundred_k.refresh_from_db()
    assert (hundred_k.stock_quantity, hundred_k.stock_reserved) == (10, 0)
    assert StockMovement.objects.filter(order_id=order_id, kind="RELEASE").count() == 1


# ---- refunds


def _return(buyer, store, finance, order_id, qty):
    item = Order.objects.get(pk=order_id).items.get()
    created = _post(
        client_for(buyer),
        f"{ORDERS}/{order_id}/returns",
        {"lines": [{"item": str(item.pk), "quantity": qty}], "reason": "Not needed (demo)"},
    )
    return_id = (
        created["returns"][0]["id"]
        if len(created["returns"]) == 1
        else next(r["id"] for r in created["returns"] if r["status"] == "REQUESTED")
    )
    merchant = client_for(store.account)
    _post(merchant, f"{MERCHANT}/returns/{return_id}/decide", {"approve": True})
    _post(merchant, f"{MERCHANT}/returns/{return_id}/received")
    return _post(client_for(finance), f"{ADMIN}/returns/{return_id}/refund")


def test_partial_then_full_return_reverses_commission_proportionally(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 3)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    assert posting.balance(Account.SELLER_PAYABLE, company_id=store.pk) == D("240000")

    partial = _return(buyer, store, finance, order_id, 1)
    assert partial["payment_status"] == "PARTIALLY_REFUNDED"
    assert D(partial["refunded_total"]) == D("100000")
    assert posting.balance(Account.COMMISSION_REVENUE) == D("40000")
    assert posting.balance(Account.SELLER_PAYABLE, company_id=store.pk) == D("160000")
    _reconciled()

    full = _return(buyer, store, finance, order_id, 2)
    assert full["payment_status"] == "REFUNDED" and D(full["refunded_total"]) == D("300000")
    assert posting.balance(Account.COMMISSION_REVENUE) == 0
    assert posting.balance(Account.SELLER_PAYABLE, company_id=store.pk) == 0
    hundred_k.refresh_from_db()
    assert hundred_k.stock_quantity == 10  # 3 shipped, 3 restocked
    _reconciled()


def test_refunding_unit_by_unit_adds_up_exactly_with_odd_amounts(
    buyer, finance, store, store_category, product_factory, checkout
):
    odd = product_factory(
        store, store_category, price=D("33333"), sale_channel=SaleChannel.B2C, stock_quantity=9
    )
    now = timezone.now()
    Coupon.objects.create(
        code="ODD-PLATFORM",
        funded_by="PLATFORM",
        kind="FIXED",
        value=D("1001"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
    order_id = _order(buyer, checkout, [(odd, 3)], coupons=["ODD-PLATFORM"])
    _deliver_pay_complete(buyer, finance, store, order_id)
    for _ in range(3):
        _return(buyer, store, finance, order_id, 1)
    item = Order.objects.get(pk=order_id).items.get()
    assert item.refunded_buyer_paid == item.buyer_paid
    assert item.refunded_platform_discount == item.platform_discount == D("1001")
    assert item.refunded_commission == item.commission
    assert item.refunded_seller_payable == item.seller_payable
    assert posting.balance(Account.SELLER_PAYABLE, company_id=store.pk) == 0
    assert posting.balance(Account.PLATFORM_PROMO_EXPENSE) == 0
    _reconciled()


def test_paid_order_cancelled_before_shipping_is_refunded_by_finance(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)], payment_method="MANUAL_TRANSFER")
    fin = client_for(finance)
    _post(fin, f"{ADMIN}/orders/{order_id}/verify-payment", {"reference": "TRF-77 (sim)"})
    cancelled = _post(client_for(buyer), f"{ORDERS}/{order_id}/cancel")
    assert cancelled["payment_status"] == "REFUND_PENDING"
    refunded = _post(fin, f"{ADMIN}/orders/{order_id}/refund-cancelled")
    assert refunded["payment_status"] == "REFUNDED"
    _post(fin, f"{ADMIN}/orders/{order_id}/refund-cancelled", expect=409)  # once
    assert posting.balance(Account.CUSTOMER_FUNDS_HELD) == 0
    assert posting.balance(Account.PLATFORM_CASH) == 0
    _reconciled()


def test_dispute_resolved_with_refund_after_completion(buyer, finance, store, hundred_k, checkout):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    opened = _post(
        client_for(buyer), f"{ORDERS}/{order_id}/disputes", {"reason": "Arrived damaged (demo)"}
    )
    dispute_id = opened["disputes"][0]["id"]
    _post(client_for(buyer), f"{ORDERS}/{order_id}/disputes", {"reason": "again"}, expect=409)
    fin = client_for(finance)
    resolved = _post(
        fin, f"{ADMIN}/disputes/{dispute_id}/resolve", {"refund": True, "note": "Photos checked"}
    )
    assert resolved["payment_status"] == "REFUNDED"
    assert posting.balance(Account.COMMISSION_REVENUE) == 0
    _reconciled()


# ---- payouts


def test_payout_is_prepared_then_confirmed_once_by_finance(
    buyer, finance, support_staff, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    fin = client_for(finance)
    assert (
        client_for(support_staff)
        .post(f"{LEDGER}/settlements/prepare", {"company": str(store.pk)}, format="json")
        .status_code
        == 403
    )
    draft = _post(fin, f"{LEDGER}/settlements/prepare", {"company": str(store.pk)}, expect=201)
    assert D(draft["amount"]) == D("80000") and draft["status"] == "DRAFT"
    _post(fin, f"{LEDGER}/settlements/{draft['id']}/confirm", {}, expect=400)  # needs a reference
    paid = _post(
        fin, f"{LEDGER}/settlements/{draft['id']}/confirm", {"reference_note": "SIM-PAYOUT-1"}
    )
    assert paid["status"] == "PAID"
    _post(fin, f"{LEDGER}/settlements/{draft['id']}/confirm", {"reference_note": "x"})
    assert LedgerEntry.objects.filter(kind="PAYOUT").count() == 1
    assert posting.balance(Account.SELLER_PAYABLE, company_id=store.pk) == 0
    _post(fin, f"{LEDGER}/settlements/prepare", {"company": str(store.pk)}, expect=400)
    statement = client_for(store.account).get(f"{MERCHANT}/finance").json()
    assert D(statement["paid_out"]) == D("80000") and D(statement["payable"]) == 0
    assert D(statement["commission"]) == D("20000")
    _reconciled()


def test_a_payout_cannot_exceed_what_is_owed_after_a_refund(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    fin = client_for(finance)
    draft = _post(fin, f"{LEDGER}/settlements/prepare", {"company": str(store.pk)}, expect=201)
    dispute = _post(client_for(buyer), f"{ORDERS}/{order_id}/disputes", {"reason": "Broken"})
    _post(
        fin,
        f"{ADMIN}/disputes/{dispute['disputes'][0]['id']}/resolve",
        {"refund": True, "note": "ok"},
    )
    _post(
        fin, f"{LEDGER}/settlements/{draft['id']}/confirm", {"reference_note": "late"}, expect=409
    )
    assert not LedgerEntry.objects.filter(kind="PAYOUT").exists()
    _reconciled()


# ---- the ledger itself


def test_ledger_rows_cannot_be_changed_or_deleted(buyer, finance, store, hundred_k, checkout):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    line = LedgerLine.objects.first()
    with pytest.raises(DatabaseError), transaction.atomic():
        LedgerLine.objects.filter(pk=line.pk).update(debit=D("1"))
    with pytest.raises(DatabaseError), transaction.atomic():
        LedgerEntry.objects.filter(order_id=order_id).delete()
    with pytest.raises(ValidationError):
        line.memo = "edited"
        line.save()


def test_posting_refuses_unbalanced_negative_fractional_and_foreign_currency():
    with pytest.raises(LedgerError):
        posting.post("t1", kind="PAYMENT", lines=[Line(Account.PLATFORM_CASH, debit=D("5"))])
    with pytest.raises(LedgerError):
        posting.post(
            "t2",
            kind="PAYMENT",
            lines=[Line(Account.PLATFORM_CASH, debit=D("-5")), Line(Account.COMMISSION_REVENUE)],
        )
    with pytest.raises(LedgerError):
        posting.post(
            "t3",
            kind="PAYMENT",
            lines=[
                Line(Account.PLATFORM_CASH, debit=D("1.5")),
                Line(Account.CUSTOMER_FUNDS_HELD, credit=D("1.5")),
            ],
        )
    with pytest.raises(LedgerError):
        posting.post(
            "t4",
            kind="PAYMENT",
            currency="USD",
            lines=[
                Line(Account.PLATFORM_CASH, debit=D("1")),
                Line(Account.CUSTOMER_FUNDS_HELD, credit=D("1")),
            ],
        )
    assert not LedgerEntry.objects.exists()


def test_policy_change_never_rewrites_an_existing_order(buyer, finance, store, hundred_k, checkout):
    first = _order(buyer, checkout, [(hundred_k, 1)])
    MarketplaceCommissionPolicy.objects.create(
        version=2, rate_percent=D("25.00"), effective_from=timezone.now(), note="test only"
    )
    second = _order(buyer, checkout, [(hundred_k, 1)])
    done = _deliver_pay_complete(buyer, finance, store, first)
    assert D(done["commission_total"]) == D("20000") and done["commission_policy_version"] == 1
    assert Order.objects.get(pk=second).commission_total == D("25000")


# ---- security


def test_forged_prices_fees_statuses_and_sellers_are_ignored(buyer, hundred_k, checkout, store):
    body = checkout([(hundred_k, 1)])
    body["items"][0].update({"unit_price": "1", "merchant": "x"})
    body.update(
        {"status": "COMPLETED", "payment_status": "PAID", "commission_rate": "0", "total": "1"}
    )
    data = client_for(buyer).post(CHECKOUTS, body, format="json").json()
    order = Order.objects.get(pk=data["orders"][0]["id"])
    assert (order.status, order.payment_status) == ("PLACED", "UNPAID")
    assert order.total == D("100000") and order.commission_total == D("20000")
    assert order.merchant_id == store.pk


def test_only_finance_can_verify_complete_refund_or_read_the_ledger(
    buyer, support_staff, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    for actor in (buyer, store.account, support_staff):
        client = client_for(actor)
        for url, body in (
            (f"{ADMIN}/orders/{order_id}/verify-payment", {"reference": "x"}),
            (f"{ADMIN}/orders/{order_id}/complete", {}),
            (f"{ADMIN}/orders/{order_id}/confirm-delivery", {}),
        ):
            assert client.post(url, body, format="json").status_code == 403
        assert client.get(f"{LEDGER}/reconciliation").status_code == 403
        assert client.get(f"{LEDGER}/entries").status_code == 403
    assert Order.objects.get(pk=order_id).payment_status == "UNPAID"


def test_another_seller_cannot_touch_my_orders_returns_or_stock(
    buyer, finance, store, hundred_k, checkout, company_factory
):
    order_id = _order(buyer, checkout, [(hundred_k, 2)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    item = Order.objects.get(pk=order_id).items.get()
    created = _post(
        client_for(buyer),
        f"{ORDERS}/{order_id}/returns",
        {"lines": [{"item": str(item.pk), "quantity": 1}], "reason": "demo"},
    )
    return_id = created["returns"][0]["id"]
    rival = client_for(company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE).account)
    url = f"{MERCHANT}/orders/{order_id}/transition"
    assert rival.post(url, {"status": "CANCELLED"}, format="json").status_code == 404
    assert (
        rival.post(
            f"{MERCHANT}/returns/{return_id}/decide", {"approve": True}, format="json"
        ).status_code
        == 404
    )
    assert (
        rival.post(
            f"{MERCHANT}/inventory/{hundred_k.pk}/adjust",
            {"delta": -5, "reason": "x"},
            format="json",
        ).status_code
        == 400
    )
    assert rival.get(f"{MERCHANT}/finance?company={store.pk}").status_code == 403
    hundred_k.refresh_from_db()
    assert hundred_k.stock_quantity == 8


def test_buyer_cannot_return_more_than_bought_or_outside_the_window(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    item = Order.objects.get(pk=order_id).items.get()
    url = f"{ORDERS}/{order_id}/returns"
    too_many = {"lines": [{"item": str(item.pk), "quantity": 2}], "reason": "x"}
    _post(client_for(buyer), url, too_many, expect=400)
    Order.objects.filter(pk=order_id).update(delivered_at=timezone.now() - timedelta(days=15))
    ok_qty = {"lines": [{"item": str(item.pk), "quantity": 1}], "reason": "x"}
    _post(client_for(buyer), url, ok_qty, expect=409)


def test_coupon_abuse_is_refused(
    buyer, account_factory, store, hundred_k, checkout, company_factory
):
    now = timezone.now()
    Coupon.objects.create(
        code="ONCE",
        funded_by="SELLER",
        company=store,
        kind="FIXED",
        value=D("1000"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        max_redemptions=5,
    )
    for code in ("P1", "P2"):
        Coupon.objects.create(
            code=code,
            funded_by="PLATFORM",
            kind="FIXED",
            value=D("500"),
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(days=1),
        )
    Coupon.objects.create(
        code="OLD",
        funded_by="PLATFORM",
        kind="FIXED",
        value=D("500"),
        starts_at=now - timedelta(days=9),
        ends_at=now - timedelta(days=1),
    )
    other = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    Coupon.objects.create(
        code="ELSEWHERE",
        funded_by="SELLER",
        company=other,
        kind="FIXED",
        value=D("500"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
    client = client_for(buyer)

    def code_of(coupons):
        response = client.post(
            CHECKOUTS, checkout([(hundred_k, 1)], coupons=coupons), format="json"
        )
        return response.status_code, response.json().get("error", {}).get("code")

    assert code_of(["P1", "P2"]) == (400, "coupon_stacking")
    assert code_of(["OLD"]) == (400, "invalid_coupon")
    assert code_of(["ELSEWHERE"]) == (400, "invalid_coupon")
    assert code_of(["NOPE"]) == (400, "invalid_coupon")
    first = _order(buyer, checkout, [(hundred_k, 1)], coupons=["ONCE"])
    assert code_of(["ONCE"]) == (400, "invalid_coupon")  # once per buyer
    _post(client, f"{ORDERS}/{first}/cancel")
    _order(buyer, checkout, [(hundred_k, 1)], coupons=["ONCE"])  # released by the cancellation
    assert Coupon.objects.get(code="ONCE").redemptions == 1


def test_unverified_seller_and_prohibited_category_cannot_sell(
    buyer, store, store_category, hundred_k, product_factory, category_factory, checkout
):
    banned_category = category_factory(
        slug="banned", consumer_allowed=True, compliance_class="PROHIBITED"
    )
    banned = product_factory(
        store, banned_category, price=D("10"), sale_channel=SaleChannel.B2C, stock_quantity=3
    )
    client = client_for(buyer)
    assert client.post(CHECKOUTS, checkout([(banned, 1)]), format="json").status_code == 403
    store.verification_status = "PENDING"
    store.save(update_fields=["verification_status"])
    response = client.post(CHECKOUTS, checkout([(hundred_k, 1)]), format="json")
    assert response.status_code == 403 and not Order.objects.exists()


def test_b2b_product_is_sold_only_to_a_targeted_verified_professional(
    buyer, store, product_factory, category_factory, provider_factory, checkout
):
    lab = category_factory(
        slug="lab-supplies",
        rules=[(ProviderType.DOCTOR, None)],
        compliance_class="B2B_VERIFIED_ONLY",
    )
    reagent = product_factory(
        store, lab, price=D("50000"), sale_channel=SaleChannel.B2B, stock_quantity=4
    )
    refused = client_for(buyer).post(CHECKOUTS, checkout([(reagent, 1)]), format="json")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "professional_only"
    doctor = provider_factory(provider_type=ProviderType.DOCTOR)
    doctor.account.email_verified_at = timezone.now()
    doctor.account.save(update_fields=["email_verified_at"])
    placed = _buy(doctor.account, checkout, [(reagent, 1)])
    assert placed["orders"][0]["channel"] == "B2B"


def test_accepted_quote_becomes_one_order_at_the_quoted_price(
    store, product_factory, category_factory, provider_factory, checkout, finance
):
    lab = category_factory(
        slug="quote-only", rules=[(ProviderType.DOCTOR, None)], compliance_class="QUOTE_ONLY"
    )
    analyser = product_factory(store, lab, sale_channel=SaleChannel.B2B, stock_quantity=None)
    doctor = provider_factory(provider_type=ProviderType.DOCTOR)
    doctor.account.email_verified_at = timezone.now()
    doctor.account.save(update_fields=["email_verified_at"])
    pro = client_for(doctor.account)
    quote = _post(pro, "/api/v1/quotes", {"product": str(analyser.pk), "quantity": 2}, expect=201)
    _post(
        client_for(store.account),
        f"/api/v1/merchant/quotes/{quote['id']}/respond",
        {"unit_price": "750000"},
    )
    body = checkout([])
    body.pop("items")
    _post(pro, f"/api/v1/quotes/{quote['id']}/order", body, expect=409)  # not accepted yet
    _post(pro, f"/api/v1/quotes/{quote['id']}/close", {"outcome": "ACCEPTED"})
    ordered = _post(pro, f"/api/v1/quotes/{quote['id']}/order", body, expect=201)
    order = Order.objects.get(pk=ordered["orders"][0]["id"])
    assert (order.total, order.commission_total, order.seller_payable_total) == (
        D("1500000"),
        D("300000"),
        D("1200000"),
    )
    assert order.quote_id is not None and order.channel == "B2B"
    body["idempotency_key"] = "another-key-123"
    _post(pro, f"/api/v1/quotes/{quote['id']}/order", body, expect=409)  # ordered once


def test_expired_quote_cannot_be_accepted(
    store, product_factory, category_factory, provider_factory
):
    lab = category_factory(slug="q2", rules=[(ProviderType.DOCTOR, None)])
    item = product_factory(store, lab, sale_channel=SaleChannel.B2B)
    doctor = provider_factory(provider_type=ProviderType.DOCTOR)
    pro = client_for(doctor.account)
    quote = _post(pro, "/api/v1/quotes", {"product": str(item.pk), "quantity": 1}, expect=201)
    _post(
        client_for(store.account),
        f"/api/v1/merchant/quotes/{quote['id']}/respond",
        {"unit_price": "1000"},
    )
    from apps.commerce.models import QuoteRequest

    QuoteRequest.objects.filter(pk=quote["id"]).update(expires_at=timezone.now())
    _post(pro, f"/api/v1/quotes/{quote['id']}/close", {"outcome": "ACCEPTED"}, expect=409)


# ---- seller roles and inventory


def _member(store, account_factory, role):
    account = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=account, company=store, role=role, added_by=store.account
    )
    return client_for(account)


def test_specialist_staff_roles_do_only_their_job(
    buyer, account_factory, store, store_category, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    q = f"?company={store.pk}"
    fulfillment = _member(store, account_factory, "FULFILLMENT")
    stock = _member(store, account_factory, "STOCK_MANAGER")
    finance_staff = _member(store, account_factory, "FINANCE")
    editor = _member(store, account_factory, "PRODUCT_EDITOR")
    viewer = _member(store, account_factory, "VIEWER")
    adjust = (f"{MERCHANT}/inventory/{hundred_k.pk}/adjust{q}", {"delta": 5, "reason": "Delivery"})
    confirm = (f"{MERCHANT}/orders/{order_id}/transition{q}", {"status": "CONFIRMED"})

    assert fulfillment.post(*adjust, format="json").status_code == 403
    assert stock.post(*confirm, format="json").status_code == 403
    assert stock.post(*adjust, format="json").status_code == 200
    assert fulfillment.post(*confirm, format="json").status_code == 200
    assert finance_staff.get(f"{MERCHANT}/finance{q}").status_code == 200
    for client in (fulfillment, stock, editor, viewer):
        assert client.get(f"{MERCHANT}/finance{q}").status_code == 403
    assert finance_staff.post(*confirm, format="json").status_code == 403
    patch = editor.patch(
        f"/api/v1/marketplace/company/products/{hundred_k.pk}{q}",
        {"title": "Bed v2"},
        format="json",
    )
    assert patch.status_code == 200 and patch.json()["title"] == "Bed v2"
    assert (
        viewer.patch(
            f"/api/v1/marketplace/company/products/{hundred_k.pk}{q}",
            {"title": "x"},
            format="json",
        ).status_code
        == 403
    )
    assert editor.post(*adjust, format="json").status_code == 403


def test_stock_never_drops_below_reserved_and_low_stock_alerts(
    buyer, store, hundred_k, checkout, django_capture_on_commit_callbacks
):
    from apps.notifications.models import Notification

    owner = client_for(store.account)
    _post(owner, f"{MERCHANT}/inventory/{hundred_k.pk}/threshold", {"threshold": 3})
    _order(buyer, checkout, [(hundred_k, 6)])
    refused = owner.post(
        f"{MERCHANT}/inventory/{hundred_k.pk}/adjust",
        {"delta": -5, "reason": "Count"},
        format="json",
    )
    assert refused.status_code == 400
    with django_capture_on_commit_callbacks(execute=True):
        row = _post(
            owner, f"{MERCHANT}/inventory/{hundred_k.pk}/adjust", {"delta": -2, "reason": "Damaged"}
        )
    assert (row["on_hand"], row["reserved"], row["available"], row["low"]) == (8, 6, 2, True)
    assert Notification.objects.filter(recipient=store.account, event_type="STOCK_LOW").exists()
    kinds = [
        m["kind"]
        for m in owner.get(f"{MERCHANT}/inventory/{hundred_k.pk}/movements").json()["results"]
    ]
    assert kinds == ["ADJUST", "RESERVE"]


def test_facility_cannot_be_given_a_seller_only_role(provider_factory, account_factory):
    from apps.workspaces import services as ws
    from apps.workspaces.services import MembershipError

    facility = provider_factory(provider_type=ProviderType.HOSPITAL)
    target = account_factory(role=AccountRole.PATIENT)
    with pytest.raises(MembershipError):
        ws.add_member(
            actor=facility.account,
            org_kind="facility",
            org_id=facility.pk,
            email=target.email,
            role="FINANCE",
        )
