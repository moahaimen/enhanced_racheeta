"""Two buyers race for the last unit: exactly one order wins (row lock on the product)."""

import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.commerce import checkout
from apps.commerce.models import Order
from apps.geography.models import Governorate
from apps.marketplace.models import Product

pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


@pytest.mark.parametrize("round_", range(3))
def test_last_unit_is_sold_once(account_factory, store_product, round_):
    Product.objects.filter(pk=store_product.pk).update(stock_quantity=1)
    buyers = [
        account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())
        for _ in range(2)
    ]
    governorate = Governorate.objects.get(slug="baghdad")
    barrier = threading.Barrier(2)
    outcomes: list = []

    def attempt(buyer):
        try:
            barrier.wait(timeout=5)
            checkout.place(
                buyer,
                items=[{"product": store_product.pk, "quantity": 1}],
                coupons=[],
                delivery={
                    "governorate": governorate,
                    "address": "Demo street",
                    "phone": "07700000000",
                },
                payment_method="CASH_ON_DELIVERY",
                idempotency_key=f"race-{buyer.pk}",
            )
            outcomes.append("ok")
        except checkout.CheckoutError as exc:
            outcomes.append(exc.code)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(b,)) for b in buyers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert sorted(outcomes) == ["ok", "out_of_stock"]
    assert Order.objects.count() == 1
    product = Product.objects.get(pk=store_product.pk)
    assert (product.stock_quantity, product.stock_reserved) == (1, 1)  # reserved, not shipped
    assert Order.objects.get().total == Decimal("150000.00")


def _race(fn, n=2):
    barrier = threading.Barrier(n)
    outcomes: list = []

    def run(i):
        try:
            barrier.wait(timeout=5)
            outcomes.append(fn(i))
        except Exception as exc:  # noqa: BLE001 — the outcome is what we assert on
            outcomes.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    return outcomes


def test_same_checkout_key_sent_twice_at_once_creates_one_checkout(account_factory, store_product):
    from apps.commerce.models import Checkout

    buyer = account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())
    governorate = Governorate.objects.get(slug="baghdad")

    def place(_):
        result, created = checkout.place(
            buyer,
            items=[{"product": store_product.pk, "quantity": 2}],
            coupons=[],
            delivery={"governorate": governorate, "address": "Demo", "phone": "07700000000"},
            payment_method="CASH_ON_DELIVERY",
            idempotency_key="double-click-key",
        )
        return created

    outcomes = _race(place)
    assert Checkout.objects.count() == 1 and Order.objects.count() == 1
    assert sorted(map(str, outcomes)) == ["False", "True"]
    assert Product.objects.get(pk=store_product.pk).stock_reserved == 2


def test_two_finance_operators_completing_at_once_accrue_once(
    account_factory, store, store_product
):
    from django.contrib.auth.models import Permission

    from apps.commerce import lifecycle
    from apps.ledger.models import LedgerEntry

    buyer = account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())
    governorate = Governorate.objects.get(slug="baghdad")
    result, _ = checkout.place(
        buyer,
        items=[{"product": store_product.pk, "quantity": 1}],
        coupons=[],
        delivery={"governorate": governorate, "address": "Demo", "phone": "07700000000"},
        payment_method="CASH_ON_DELIVERY",
        idempotency_key="finance-race",
    )
    order = result.orders.get()
    operators = []
    for _ in range(2):
        user = account_factory(role=AccountRole.PATIENT)
        type(user).objects.filter(pk=user.pk).update(role=AccountRole.ADMIN, is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename="change_settlementbatch"))
        operators.append(type(user).objects.get(pk=user.pk))
    lifecycle.seller_transition(
        order.pk, company_id=store.pk, actor=store.account, to_status="CONFIRMED"
    )
    lifecycle.seller_transition(
        order.pk, company_id=store.pk, actor=store.account, to_status="SHIPPED"
    )
    lifecycle.confirm_delivery(order.pk, actor=buyer)
    lifecycle.verify_payment(order.pk, actor=operators[0], reference="SIM")

    outcomes = _race(lambda i: lifecycle.complete(order.pk, actor=operators[i]).status)
    assert outcomes == ["COMPLETED", "COMPLETED"]
    assert LedgerEntry.objects.filter(order_id=order.pk, kind="ACCRUAL").count() == 1
