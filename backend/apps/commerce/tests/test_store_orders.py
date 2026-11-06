from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit.models import AuditEvent
from apps.commerce.models import Order
from apps.marketplace.types import BusinessType, CompanyVerificationStatus, SaleChannel
from apps.notifications.models import Notification
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

STORE = "/api/v1/store/products"
ORDERS = "/api/v1/orders"
CHECKOUTS = "/api/v1/checkouts"
MERCHANT = "/api/v1/merchant/orders"


def _ids(response):
    return {row["id"] for row in response.json()["results"]}


# ---- public store visibility --------------------------------------------------------------------


def test_store_lists_only_allowed_consumer_products(
    api_client, store, store_category, store_product, product_factory, company_factory
):
    restricted = product_factory(
        store,
        store_category,
        price=Decimal("1"),
        sale_channel=SaleChannel.B2B,
        is_restricted=True,
        stock_quantity=3,
    )
    b2b_only = product_factory(
        store, store_category, price=Decimal("1"), sale_channel=SaleChannel.B2B, stock_quantity=3
    )
    pharma = company_factory(business_type=BusinessType.PHARMACEUTICAL_COMPANY)
    wrong_business = product_factory(
        pharma, store_category, price=Decimal("1"), sale_channel=SaleChannel.B2C, stock_quantity=3
    )
    unverified_store = company_factory(
        status=CompanyVerificationStatus.PENDING, business_type=BusinessType.ASSISTIVE_DEVICE_STORE
    )
    unverified = product_factory(
        unverified_store,
        store_category,
        price=Decimal("1"),
        sale_channel=SaleChannel.B2C,
        stock_quantity=3,
    )
    ids = _ids(api_client.get(STORE))
    assert str(store_product.pk) in ids
    for hidden in (restricted, b2b_only, wrong_business, unverified):
        assert str(hidden.pk) not in ids
        assert api_client.get(f"{STORE}/{hidden.pk}").status_code == 404


def test_restricted_product_cannot_be_consumer_channel(store, store_category, product_factory):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        product_factory(
            store,
            store_category,
            price=Decimal("1"),
            sale_channel=SaleChannel.B2C,
            is_restricted=True,
        )


def test_suspended_store_disappears(api_client, store, store_product):
    store.account.is_active = False
    store.account.save(update_fields=["is_active"])
    assert str(store_product.pk) not in _ids(api_client.get(STORE))


# ---- checkout -----------------------------------------------------------------------------------


def test_checkout_uses_server_prices_and_reserves_stock(buyer, store_product, checkout):
    body = checkout([(store_product, 2)])
    body["items"][0]["unit_price"] = "1.00"  # tampering: ignored
    body["total"] = "1.00"
    response = client_for(buyer).post(CHECKOUTS, body, format="json")
    assert response.status_code == 201, response.json()
    data = response.json()["orders"][0]
    assert Decimal(data["total"]) == Decimal("300000.00")
    assert data["status"] == "PLACED" and data["payment_status"] == "UNPAID"
    assert "commission_total" not in data  # the buyer never sees Racheeta's fee
    store_product.refresh_from_db()
    # Units are reserved (not yet consumed): on hand stays 5, 2 reserved, 3 available.
    assert (store_product.stock_quantity, store_product.stock_reserved) == (5, 2)
    assert AuditEvent.objects.filter(action="commerce.order.placed").exists()


def test_merchant_is_notified_on_commit(
    buyer, store, store_product, checkout, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(buyer).post(CHECKOUTS, checkout([(store_product, 1)]), format="json")
    assert response.status_code == 201
    note = Notification.objects.get(recipient=store.account, event_type="ORDER_PLACED")
    assert set(note.payload) <= {"order_number", "status"}


def test_checkout_rejects_restricted_and_out_of_stock(
    buyer, store, store_category, store_product, product_factory, checkout
):
    restricted = product_factory(
        store,
        store_category,
        price=Decimal("5"),
        sale_channel=SaleChannel.B2B,
        is_restricted=True,
        stock_quantity=10,
    )
    client = client_for(buyer)
    refused = client.post(CHECKOUTS, checkout([(restricted, 1)]), format="json")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "not_purchasable"
    response = client.post(CHECKOUTS, checkout([(store_product, 6)]), format="json")
    assert response.status_code == 409
    store_product.refresh_from_db()
    assert (store_product.stock_quantity, store_product.stock_reserved) == (5, 0)


def test_one_checkout_splits_into_one_order_per_seller_and_rejects_bad_quantities(
    buyer, store_product, store_category, company_factory, product_factory, checkout
):
    other = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    other_product = product_factory(
        other,
        store_category,
        price=Decimal("10000"),
        sale_channel=SaleChannel.B2C,
        stock_quantity=4,
    )
    client = client_for(buyer)
    mixed = client.post(
        CHECKOUTS, checkout([(store_product, 1), (other_product, 2)]), format="json"
    )
    assert mixed.status_code == 201, mixed.json()
    data = mixed.json()
    assert len(data["orders"]) == 2
    assert {o["merchant"]["id"] for o in data["orders"]} == {
        str(store_product.company_id),
        str(other.pk),
    }
    assert Decimal(data["total"]) == Decimal("170000.00")
    for qty in (0, -1, 21):
        assert (
            client.post(CHECKOUTS, checkout([(store_product, qty)]), format="json").status_code
            == 400
        )


def test_unverified_email_and_company_accounts_cannot_order(
    account_factory, store, store_product, checkout
):
    unverified = account_factory(role=AccountRole.PATIENT)
    assert (
        client_for(unverified)
        .post(CHECKOUTS, checkout([(store_product, 1)]), format="json")
        .status_code
        == 403
    )
    assert (
        client_for(store.account)
        .post(CHECKOUTS, checkout([(store_product, 1)]), format="json")
        .status_code
        == 403
    )


def test_checkout_never_accepts_card_data(buyer, store_product, checkout):
    body = checkout([(store_product, 1)], payment_method="CARD", card_number="4111111111111111")
    assert client_for(buyer).post(CHECKOUTS, body, format="json").status_code == 400
    assert not Order.objects.exists()


# ---- lifecycle, cancellation and object access --------------------------------------------------


def _place(buyer, product, checkout, qty=1):
    response = client_for(buyer).post(CHECKOUTS, checkout([(product, qty)]), format="json")
    assert response.status_code == 201, response.json()
    return response.json()["orders"][0]["id"]


def test_buyer_cancel_restores_stock_and_only_before_shipping(
    buyer, store, store_product, checkout
):
    order_id = _place(buyer, store_product, checkout, qty=2)
    response = client_for(buyer).post(
        f"{ORDERS}/{order_id}/cancel", {"reason": "changed mind"}, format="json"
    )
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
    store_product.refresh_from_db()
    assert (store_product.stock_quantity, store_product.stock_reserved) == (5, 0)

    second = _place(buyer, store_product, checkout)
    merchant = client_for(store.account)
    for step in ("CONFIRMED", "SHIPPED"):
        assert (
            merchant.post(
                f"{MERCHANT}/{second}/transition", {"status": step}, format="json"
            ).status_code
            == 200
        )
    assert client_for(buyer).post(f"{ORDERS}/{second}/cancel", {}, format="json").status_code == 409
    store_product.refresh_from_db()
    assert (store_product.stock_quantity, store_product.stock_reserved) == (4, 0)  # shipped


def test_seller_cannot_mark_delivered_or_paid_and_payment_stays_unverified(
    buyer, store, store_product, checkout
):
    order_id = _place(buyer, store_product, checkout)
    merchant = client_for(store.account)
    for forbidden in ("DELIVERED", "COMPLETED"):
        assert (
            merchant.post(
                f"{MERCHANT}/{order_id}/transition", {"status": forbidden}, format="json"
            ).status_code
            == 400
        )
    assert (
        merchant.post(
            f"{MERCHANT}/{order_id}/transition", {"status": "SHIPPED"}, format="json"
        ).status_code
        == 409
    )  # must be accepted first
    gone = merchant.post(f"{MERCHANT}/{order_id}/payment-received", {}, format="json")
    assert gone.status_code == 404  # sellers never confirm payments: Racheeta finance does
    for step in ("CONFIRMED", "SHIPPED"):
        response = merchant.post(
            f"{MERCHANT}/{order_id}/transition", {"status": step}, format="json"
        )
        assert response.status_code == 200
    delivered = client_for(buyer).post(f"{ORDERS}/{order_id}/confirm-delivery", {}, format="json")
    assert delivered.status_code == 200 and delivered.json()["status"] == "DELIVERED"
    assert delivered.json()["payment_status"] == "UNPAID"  # cash is verified by finance, not here


def test_other_buyers_and_other_stores_cannot_see_an_order(
    buyer, account_factory, store, store_product, company_factory, checkout
):
    order_id = _place(buyer, store_product, checkout)
    stranger = account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())
    assert client_for(stranger).get(f"{ORDERS}/{order_id}").status_code == 404
    assert (
        client_for(stranger).post(f"{ORDERS}/{order_id}/cancel", {}, format="json").status_code
        == 404
    )
    rival = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    rival_client = client_for(rival.account)
    assert rival_client.get(f"{MERCHANT}/{order_id}").status_code == 404
    assert rival_client.get(f"{MERCHANT}?company={store.pk}").status_code == 403
    assert rival_client.get(f"{MERCHANT}?company=not-a-uuid").status_code == 403


def test_staff_roles_viewer_reads_staff_manages_ended_loses_access(
    buyer, account_factory, store, store_product, checkout
):
    order_id = _place(buyer, store_product, checkout)
    viewer = account_factory(role=AccountRole.PATIENT)
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=viewer, company=store, role="VIEWER", added_by=store.account
    )
    membership = OrganizationMember.objects.create(
        account=staff, company=store, role="STAFF", added_by=store.account
    )
    query = f"?company={store.pk}"
    assert client_for(viewer).get(f"{MERCHANT}{query}").status_code == 200
    assert (
        client_for(viewer)
        .post(f"{MERCHANT}/{order_id}/transition{query}", {"status": "CONFIRMED"}, format="json")
        .status_code
        == 403
    )
    assert (
        client_for(staff)
        .post(f"{MERCHANT}/{order_id}/transition{query}", {"status": "CONFIRMED"}, format="json")
        .status_code
        == 200
    )
    membership.status = "ENDED"
    membership.ended_at = timezone.now()
    membership.save()
    assert client_for(staff).get(f"{MERCHANT}{query}").status_code == 403


def test_store_shows_photo_and_only_a_few_left_hint(
    api_client, store, store_category, product_factory
):
    few = product_factory(
        store,
        store_category,
        price=Decimal("10"),
        sale_channel=SaleChannel.B2C,
        stock_quantity=3,
        image_url="https://example.com/walker.png",
    )
    plenty = product_factory(
        store, store_category, price=Decimal("10"), sale_channel=SaleChannel.B2C, stock_quantity=40
    )
    rows = {r["id"]: r for r in api_client.get(STORE).json()["results"]}
    assert rows[str(few.pk)]["image_url"] == "https://example.com/walker.png"
    assert rows[str(few.pk)]["low_stock"] is True and rows[str(plenty.pk)]["low_stock"] is False
    assert "stock_quantity" not in rows[str(few.pk)]  # the exact figure stays private


def test_business_can_set_a_product_photo_but_not_a_non_url(store, store_category):
    from .conftest import client_for

    client = client_for(store.account)
    base = {"category": str(store_category.pk), "title": "Photo walker", "price": "10"}
    bad = client.post(
        "/api/v1/marketplace/company/products", {**base, "image_url": "not a link"}, format="json"
    )
    assert bad.status_code == 400 and "image_url" in bad.json()["error"]["details"]
    ok = client.post(
        "/api/v1/marketplace/company/products",
        {**base, "image_url": "https://example.com/p.png"},
        format="json",
    )
    assert ok.status_code == 201 and ok.json()["image_url"] == "https://example.com/p.png"


def test_delivery_defaults_come_from_my_last_order_only(
    buyer, account_factory, store_product, checkout, baghdad
):
    buyer.phone_number = "07801112233"
    buyer.save(update_fields=["phone_number"])
    first = client_for(buyer).get(f"{ORDERS}/delivery-defaults").json()
    assert first == {"governorate": None, "city": None, "address": "", "phone": "07801112233"}
    body = checkout([(store_product, 1)], address="Karrada, street 5", phone="0770 999 8877")
    assert client_for(buyer).post(CHECKOUTS, body, format="json").status_code == 201
    after = client_for(buyer).get(f"{ORDERS}/delivery-defaults").json()
    assert after["governorate"] == str(baghdad.pk)
    assert after["address"] == "Karrada, street 5" and after["phone"] == "07709998877"
    stranger = account_factory(role=AccountRole.PATIENT)
    assert client_for(stranger).get(f"{ORDERS}/delivery-defaults").json()["address"] == ""


def test_delivery_pin_is_optional_but_must_be_a_pair(buyer, store_product, checkout):
    client = client_for(buyer)
    half = checkout([(store_product, 1)], latitude="33.312805")
    assert client.post(CHECKOUTS, half, format="json").status_code == 400
    pinned = checkout([(store_product, 1)], latitude="33.312805", longitude="44.361488")
    response = client.post(CHECKOUTS, pinned, format="json")
    assert response.status_code == 201
    assert response.json()["orders"][0]["delivery_latitude"] == "33.312805"
