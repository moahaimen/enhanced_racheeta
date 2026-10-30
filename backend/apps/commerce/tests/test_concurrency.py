"""Two buyers race for the last unit: exactly one order wins (row lock on the product)."""

import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.commerce import services
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
            services.place_order(
                buyer,
                items=[{"product": store_product.pk, "quantity": 1}],
                delivery={
                    "governorate": governorate,
                    "address": "Demo street",
                    "phone": "0770000000",
                },
                payment_method="CASH_ON_DELIVERY",
            )
            outcomes.append("ok")
        except services.OutOfStock:
            outcomes.append("out_of_stock")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(b,)) for b in buyers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert sorted(outcomes) == ["ok", "out_of_stock"]
    assert Order.objects.count() == 1
    assert Product.objects.get(pk=store_product.pk).stock_quantity == 0
    assert Order.objects.get().total == Decimal("150000.00")
