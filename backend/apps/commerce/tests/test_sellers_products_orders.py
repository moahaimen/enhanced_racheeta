"""Seller onboarding for every seller category (a pharmacy keeps its provider identity), safe
uploads, store activation, category rules, variants, delivery fees, seller-declared tax,
tracking, invoices, accounting reports and cross-organization isolation.

Everything is fictional and every payment is simulated. The 20% commission, the seller
receivable and the reconciliation rules are asserted on every money path.
"""

import struct
import threading
import uuid
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.commerce.models import Invoice, Order, OrderItem, StockMovement
from apps.ledger.settlement import reconciliation, statement
from apps.marketplace.models import (
    MedicalCompany,
    Product,
    ProductAudience,
    ProductCategory,
    ProductVariant,
)
from apps.marketplace.types import BusinessType, SaleChannel
from apps.providers.types import ProviderType, VerificationStatus
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

D = Decimal
API = "/api/v1"
MP = f"{API}/marketplace"
COMPANY = f"{MP}/company"
STORE = f"{COMPANY}/store"
DOCS = f"{COMPANY}/documents"
CHECKOUTS = f"{API}/checkouts"
ORDERS = f"{API}/orders"
MERCHANT = f"{API}/merchant"
ADMIN = f"{API}/admin/commerce"

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def png(width=120, height=90) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + ihdr
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture(autouse=True)
def private_media(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"
    return settings.PRIVATE_MEDIA_ROOT


def _post(client, url, body=None, expect=200, fmt="json"):
    response = client.post(url, body or {}, format=fmt)
    assert response.status_code == expect, (url, response.status_code, response.content[:400])
    return response.json() if response.content else None


def _verified(account):
    type(account).objects.filter(pk=account.pk).update(email_verified_at=timezone.now())
    return type(account).objects.get(pk=account.pk)


def _upload(client, kind, data=PDF, name="licence.pdf", expect=201, company=None):
    url = DOCS + (f"?company={company}" if company else "")
    return _post(
        client,
        url,
        {"kind": kind, "file": SimpleUploadedFile(name, data, content_type="application/pdf")},
        expect=expect,
        fmt="multipart",
    )


def _approve_all(admin_client, company_id):
    for doc in admin_client.get(f"{API}/admin/marketplace/documents?company={company_id}").json()[
        "results"
    ]:
        _post(
            admin_client,
            f"{API}/admin/marketplace/documents/{doc['id']}/decision",
            {"approve": True},
        )


def _onboard(client, admin_client, *, business_type, baghdad, pharmacy=False):
    """Register -> documents -> verification -> approval -> activation, all through the API."""
    if pharmacy:
        company = _post(client, f"{MP}/pharmacy-store", {}, expect=201)
    else:
        company = _post(
            client,
            COMPANY,
            {
                "name": f"Demo {business_type}",
                "business_type": business_type,
                "governorate": baghdad.pk,
            },
            expect=201,
        )
    assert company["store_status"] == "INACTIVE" and company["can_sell"] is False
    for kind in company["required_documents"]:
        _upload(client, kind)
    _post(client, f"{COMPANY}/verification/request")
    _post(
        admin_client,
        f"{API}/admin/marketplace/companies/{company['id']}/verification",
        {"status": "VERIFIED"},
    )
    refused = client.post(f"{STORE}/status", {"active": True}, format="json")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "documents_missing"
    _approve_all(admin_client, company["id"])
    body = _post(client, f"{STORE}/status", {"active": True})
    assert body["store_status"] == "ACTIVE" and body["can_sell"] is True
    return body


@pytest.fixture
def consumer_category(category_factory):
    return category_factory(slug="home-care", consumer_allowed=True)


@pytest.fixture
def pro_category(category_factory):
    return category_factory(slug="clinic-supplies", rules=[(ProviderType.DOCTOR, None)])


@pytest.fixture
def doctor(provider_factory):
    profile = provider_factory(ProviderType.DOCTOR)
    profile.account = _verified(profile.account)
    return profile


@pytest.fixture
def pharmacy(provider_factory):
    profile = provider_factory(ProviderType.PHARMACY)
    profile.account = _verified(profile.account)
    return profile


def _company(account) -> MedicalCompany:
    return MedicalCompany.objects.get(account=account)


def _product(client, category, **fields):
    body = {
        "category": str(category.pk),
        "title": fields.pop("title", "Demo product"),
        "price": fields.pop("price", "100000"),
        **fields,
    }
    product = _post(client, f"{COMPANY}/products", body, expect=201)
    return product


def _publish(client, product_id):
    return _post(client, f"{COMPANY}/products/{product_id}/activate")


def _checkout_body(baghdad, lines, **extra):
    body = {
        "items": [
            {"product": str(p), "quantity": q, **({"variant": str(v)} if v else {})}
            for p, v, q in lines
        ],
        "payment_method": "CASH_ON_DELIVERY",
        "governorate": baghdad.pk,
        "address": "Street 1 (demo)",
        "phone": "+964 770 000 0000",
        "idempotency_key": uuid.uuid4().hex,
    }
    body.update(extra)
    return body


def _buy(buyer, baghdad, lines, expect=201, **extra):
    response = client_for(buyer).post(
        CHECKOUTS, _checkout_body(baghdad, lines, **extra), format="json"
    )
    assert response.status_code == expect, response.json()
    return response.json()


def _fulfil_and_pay(seller_client, buyer, finance, order_id, *, complete=True):
    _post(seller_client, f"{MERCHANT}/orders/{order_id}/transition", {"status": "CONFIRMED"})
    _post(
        seller_client,
        f"{MERCHANT}/orders/{order_id}/transition",
        {"status": "SHIPPED", "shipping_reference": "TRK-1 (demo)", "courier_name": "Demo courier"},
    )
    _post(client_for(buyer), f"{ORDERS}/{order_id}/confirm-delivery")
    fin = client_for(finance)
    _post(fin, f"{ADMIN}/orders/{order_id}/verify-payment", {"reference": "SIM-PAY-1"})
    if complete:
        _post(fin, f"{ADMIN}/orders/{order_id}/complete")


# ---- Priority 1: every seller category, end to end ---------------------------------------------

RETAIL = [
    BusinessType.ASSISTIVE_DEVICE_STORE,
    BusinessType.EQUIPMENT_SUPPLIER,
    BusinessType.MEDICAL_SUPPLIES_OFFICE,
]
PROFESSIONAL = [
    BusinessType.MEDICAL_COMPANY,
    BusinessType.PHARMACEUTICAL_COMPANY,
    BusinessType.SCIENTIFIC_OFFICE,
    BusinessType.PHARMA_DISTRIBUTOR,
]


@pytest.mark.parametrize("business_type", RETAIL + PROFESSIONAL + [BusinessType.PHARMACY])
def test_every_seller_category_onboards_sells_and_refunds_with_20_percent(
    business_type,
    account_factory,
    admin_client,
    baghdad,
    consumer_category,
    pro_category,
    doctor,
    pharmacy,
    finance,
):
    if business_type == BusinessType.PHARMACY:
        owner = pharmacy.account
    else:
        owner = account_factory(role=AccountRole.MEDICAL_COMPANY)
    client = client_for(owner)
    company = _onboard(
        client,
        admin_client,
        business_type=business_type,
        baghdad=baghdad,
        pharmacy=business_type == BusinessType.PHARMACY,
    )
    retail = business_type in RETAIL or business_type == BusinessType.PHARMACY
    if retail:
        product = _product(
            client,
            consumer_category,
            sale_channel="B2C",
            stock_quantity=5,
            sku=f"SKU-{business_type}",
        )
        buyer = _verified(account_factory(role=AccountRole.PATIENT))
    else:
        product = _product(client, pro_category, sale_channel="B2B", stock_quantity=5)
        buyer = doctor.account
    _publish(client, product["id"])
    checkout = _buy(buyer, baghdad, [(product["id"], None, 1)])
    order = checkout["orders"][0]
    assert order["channel"] == ("B2C" if retail else "B2B")
    _fulfil_and_pay(client, buyer, finance, order["id"])
    row = Order.objects.get(pk=order["id"])
    assert (row.total, row.commission_total, row.seller_payable_total) == (
        D("100000"),
        D("20000"),
        D("80000"),
    )
    # A refund after completion (dispute) reverses the commission; the books still reconcile.
    _post(client_for(buyer), f"{ORDERS}/{order['id']}/disputes", {"reason": "Damaged (demo)"})
    dispute = client_for(finance).get(f"{ADMIN}/disputes").json()["results"][0]
    _post(
        client_for(finance),
        f"{ADMIN}/disputes/{dispute['id']}/resolve",
        {"refund": True, "note": "Refunded (demo)"},
    )
    row.refresh_from_db()
    assert row.payment_status == "REFUNDED" and row.refunded_total == D("100000")
    assert statement(company["id"])["seller_earnings"] == 0
    assert reconciliation()["ok"]
    kinds = sorted(Invoice.objects.filter(order=row).values_list("kind", flat=True))
    assert kinds == ["CREDIT_NOTE", "INVOICE", "RECEIPT"]


def test_a_pharmacy_opens_its_store_and_keeps_its_provider_identity(pharmacy, baghdad):
    client = client_for(pharmacy.account)
    store = _post(client, f"{MP}/pharmacy-store", {"name": "Demo Pharmacy Store"}, expect=201)
    assert store["business_type"] == "PHARMACY" and store["facility_id"] == str(pharmacy.pk)
    pharmacy.account.refresh_from_db()
    assert pharmacy.account.role == AccountRole.PROVIDER  # never forced to become a company
    kinds = {w["kind"] for w in client.get(f"{API}/workspaces").json()}
    assert {"facility", "company"} <= kinds
    facility = next(w for w in client.get(f"{API}/workspaces").json() if w["kind"] == "facility")
    assert "store" in facility["modules"]
    again = client.post(f"{MP}/pharmacy-store", {}, format="json")
    assert again.status_code == 409


def test_only_a_pharmacy_can_open_a_pharmacy_store(provider_factory, account_factory, baghdad):
    doctor = provider_factory(ProviderType.DOCTOR)
    assert (
        client_for(doctor.account).post(f"{MP}/pharmacy-store", {}, format="json").status_code
        == 403
    )
    company_account = account_factory(role=AccountRole.MEDICAL_COMPANY)
    response = client_for(company_account).post(
        COMPANY,
        {"name": "Fake pharmacy", "business_type": "PHARMACY", "governorate": baghdad.pk},
        format="json",
    )
    assert response.status_code == 400
    lab = provider_factory(ProviderType.LABORATORY)
    assert (
        client_for(lab.account).post(f"{MP}/pharmacy-store", {}, format="json").status_code == 403
    )


def test_a_pharmacy_store_stops_selling_when_the_pharmacy_loses_verification(
    pharmacy, admin_client, account_factory, baghdad, consumer_category
):
    client = client_for(pharmacy.account)
    _onboard(client, admin_client, business_type="PHARMACY", baghdad=baghdad, pharmacy=True)
    product = _product(client, consumer_category, sale_channel="B2C", stock_quantity=3)
    _publish(client, product["id"])
    assert any(
        p["id"] == product["id"] for p in client.get(f"{API}/store/products").json()["results"]
    )
    pharmacy.verification_status = VerificationStatus.SUSPENDED
    pharmacy.save(update_fields=["verification_status"])
    assert all(
        p["id"] != product["id"] for p in client.get(f"{API}/store/products").json()["results"]
    )
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    refused = _buy(buyer, baghdad, [(product["id"], None, 1)], expect=403)
    assert refused["error"]["code"] == "not_allowed"


def test_store_activation_needs_verification_and_approved_documents_and_pausing_hides_products(
    account_factory, admin_client, baghdad, consumer_category
):
    owner = account_factory(role=AccountRole.MEDICAL_COMPANY)
    client = client_for(owner)
    company = _post(
        client,
        COMPANY,
        {
            "name": "Demo store",
            "business_type": "ASSISTIVE_DEVICE_STORE",
            "governorate": baghdad.pk,
        },
        expect=201,
    )
    early = client.post(f"{STORE}/status", {"active": True}, format="json")
    assert early.status_code == 403 and early.json()["error"]["code"] == "company_not_verified"
    _upload(client, "COMMERCIAL_REGISTRATION")
    _post(client, f"{COMPANY}/verification/request")
    _post(
        admin_client,
        f"{API}/admin/marketplace/companies/{company['id']}/verification",
        {"status": "VERIFIED"},
    )
    doc = admin_client.get(f"{API}/admin/marketplace/documents?status=PENDING").json()["results"][0]
    no_note = admin_client.post(
        f"{API}/admin/marketplace/documents/{doc['id']}/decision", {"approve": False}, format="json"
    )
    assert no_note.status_code == 400  # a rejection must say why
    _post(
        admin_client,
        f"{API}/admin/marketplace/documents/{doc['id']}/decision",
        {"approve": False, "note": "Unreadable scan"},
    )
    assert client.post(f"{STORE}/status", {"active": True}, format="json").status_code == 409
    _upload(client, "COMMERCIAL_REGISTRATION")
    _approve_all(admin_client, company["id"])
    _post(client, f"{STORE}/status", {"active": True})
    product = _product(client, consumer_category, sale_channel="B2C", stock_quantity=2)
    _publish(client, product["id"])
    assert client.get(f"{API}/store/products/{product['id']}").status_code == 200
    paused = _post(client, f"{STORE}/status", {"active": False})
    assert paused["store_status"] == "PAUSED" and paused["can_sell"] is False
    assert client.get(f"{API}/store/products/{product['id']}").status_code == 404
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    refused = _buy(buyer, baghdad, [(product["id"], None, 1)], expect=403)
    assert refused["error"]["code"] == "not_allowed"


# ---- uploads -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,data,why",
    [
        ("licence.pdf", b"<html><script>alert(1)</script></html>", "html disguised as pdf"),
        ("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>", "svg"),
        ("form.pdf", b"%PDF-1.7\n/OpenAction << /JS (app.alert(1)) >>\n%%EOF\n", "pdf with js"),
        ("attach.pdf", b"%PDF-1.7\n/EmbeddedFile 1 0 R\n%%EOF\n", "pdf with attachment"),
        ("cut.pdf", b"%PDF-1.7\n1 0 obj", "truncated pdf"),
        ("empty.pdf", b"", "empty"),
        ("big.pdf", b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024) + b"\n%%EOF\n", "over 5 MB"),
    ],
)
def test_dangerous_or_broken_documents_are_refused(name, data, why, account_factory, baghdad):
    owner = account_factory(role=AccountRole.MEDICAL_COMPANY)
    client = client_for(owner)
    _post(
        client,
        COMPANY,
        {"name": "Demo", "business_type": "MEDICAL_COMPANY", "governorate": baghdad.pk},
        expect=201,
    )
    response = client.post(
        DOCS,
        {"kind": "OTHER", "file": SimpleUploadedFile(name, data)},
        format="multipart",
    )
    assert response.status_code == 400, why
    assert not _company(owner).documents.exists()


def test_documents_are_private_random_named_and_served_safely(
    account_factory, admin_client, baghdad, private_media
):
    owner = account_factory(role=AccountRole.MEDICAL_COMPANY)
    client = client_for(owner)
    _post(
        client,
        COMPANY,
        {"name": "Demo", "business_type": "MEDICAL_COMPANY", "governorate": baghdad.pk},
        expect=201,
    )
    doc = _upload(client, "COMMERCIAL_REGISTRATION", name="../../etc/passwd<>.pdf")
    assert doc["original_name"] == "passwd.pdf" and doc["content_type"] == "application/pdf"
    stored = _company(owner).documents.get().file.name
    assert stored.startswith("seller-documents/") and "passwd" not in stored
    assert (private_media / stored).exists()
    response = client.get(doc["file_url"])
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response["Content-Security-Policy"]
    assert response["Content-Disposition"].startswith("attachment")
    # Another business, an anonymous visitor and a random account never get it.
    rival = account_factory(role=AccountRole.MEDICAL_COMPANY)
    _post(
        client_for(rival),
        COMPANY,
        {"name": "Rival", "business_type": "MEDICAL_COMPANY", "governorate": baghdad.pk},
        expect=201,
    )
    assert client_for(rival).get(doc["file_url"]).status_code == 404
    from rest_framework.test import APIClient

    assert APIClient().get(doc["file_url"]).status_code in (401, 403)
    patient = account_factory(role=AccountRole.PATIENT)
    assert client_for(patient).get(doc["file_url"]).status_code == 403
    # Racheeta administrators review it through their own endpoint.
    admin_doc = admin_client.get(f"{API}/admin/marketplace/documents").json()["results"][0]
    assert admin_client.get(admin_doc["file_url"]).status_code == 200
    # An approved document cannot be withdrawn (history kept); a pending one can.
    _approve_all(admin_client, _company(owner).pk)
    assert client.delete(f"{DOCS}/{doc['id']}").status_code == 400
    other = _upload(client, "OTHER", data=png(), name="scan.png")
    assert client.delete(f"{DOCS}/{other['id']}").status_code == 204


def test_product_photos_are_validated_and_hidden_until_the_product_is_on_sale(
    account_factory, baghdad, consumer_category, company_factory, product_factory
):
    store = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    product = product_factory(
        store, consumer_category, is_active=False, price=D("5000"), sale_channel="B2C",
        stock_quantity=4,
    )  # fmt: skip
    client = client_for(store.account)
    url = f"{COMPANY}/products/{product.pk}/images"
    for name, data in (("x.png", b"GIF89a....."), ("tiny.png", png(10, 10)), ("doc.pdf", PDF)):
        bad = client.post(url, {"file": SimpleUploadedFile(name, data)}, format="multipart")
        assert bad.status_code == 400, name
    image = _post(client, url, {"file": SimpleUploadedFile("chair.png", png())}, 201, "multipart")
    assert (image["width"], image["height"]) == (120, 90)
    from rest_framework.test import APIClient

    assert APIClient().get(image["url"]).status_code == 404  # product not published yet
    assert client.get(image["url"]).status_code == 200  # the business's own team
    _publish(client, product.pk)
    shown = APIClient().get(image["url"])
    assert shown.status_code == 200 and shown["Content-Type"] == "image/png"
    assert shown["X-Content-Type-Options"] == "nosniff"
    card = APIClient().get(f"{API}/store/products/{product.pk}").json()
    assert card["images"][0]["url"] == image["url"]
    rival = company_factory()
    gone = client_for(rival.account).delete(f"{COMPANY}/images/{image['id']}")
    assert gone.status_code == 404


# ---- category rules ----------------------------------------------------------------------------


def test_category_rules_limit_who_publishes_what_and_how_many(
    company_factory, product_factory, account_factory, baghdad, category_factory
):
    category = category_factory(
        slug="otc-care",
        consumer_allowed=True,
        allowed_business_types=["PHARMACY"],
        required_documents=["DEVICE_REGISTRATION"],
        max_order_quantity=2,
    )
    shop = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    product = product_factory(
        shop, category, is_active=False, price=D("1000"), sale_channel="B2C", stock_quantity=9
    )
    refused = client_for(shop.account).post(f"{COMPANY}/products/{product.pk}/activate")
    assert refused.status_code == 409  # not a pharmacy
    # Even if the row were forced active, the store and checkout keep it out.
    Product.objects.filter(pk=product.pk).update(is_active=True)
    assert client_for(shop.account).get(f"{API}/store/products/{product.pk}").status_code == 404
    category.allowed_business_types = []
    category.save()
    refused = client_for(shop.account).post(f"{COMPANY}/products/{product.pk}/activate")
    assert refused.status_code == 409 and "DEVICE_REGISTRATION" in str(refused.json())
    category.required_documents = []
    category.save()
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    over = _buy(buyer, baghdad, [(product.pk, None, 3)], expect=400)
    assert over["error"]["code"] == "quantity_limit"
    _buy(buyer, baghdad, [(product.pk, None, 2)])


# ---- Priority 2: variants and SKUs -------------------------------------------------------------


@pytest.fixture
def scrubs(company_factory, product_factory, consumer_category):
    shop = company_factory(business_type=BusinessType.MEDICAL_SUPPLIES_OFFICE)
    product = product_factory(
        shop, consumer_category, price=D("20000"), sale_channel="B2C", stock_quantity=5,
        title="Scrubs (demo)", sku="SCRUB",
    )  # fmt: skip
    client = client_for(shop.account)
    small = _post(
        client,
        f"{COMPANY}/products/{product.pk}/variants",
        {"sku": "SCRUB-S", "label": "Size S", "stock_quantity": 1},
        expect=201,
    )
    large = _post(
        client,
        f"{COMPANY}/products/{product.pk}/variants",
        {"sku": "SCRUB-L", "label": "Size L", "price": "25000", "stock_quantity": 4},
        expect=201,
    )
    return shop, product, small, large


def test_variants_have_their_own_sku_price_and_stock(scrubs, account_factory, baghdad, finance):
    shop, product, small, large = scrubs
    product.refresh_from_db()
    assert product.stock_quantity is None  # stock moved to the variants
    client = client_for(shop.account)
    dupe = client.post(
        f"{COMPANY}/products/{product.pk}/variants",
        {"sku": "SCRUB", "label": "Size M"},
        format="json",
    )
    assert dupe.status_code == 400  # the product's own SKU is taken too
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    missing = _buy(buyer, baghdad, [(product.pk, None, 1)], expect=400)
    assert missing["error"]["code"] == "variant_required"
    order = _buy(buyer, baghdad, [(product.pk, large["id"], 2), (product.pk, small["id"], 1)])
    items = {i["variant_label_snapshot"]: i for i in order["orders"][0]["items"]}
    assert (
        items["Size L"]["unit_price"] == "25000.00" and items["Size L"]["sku_snapshot"] == "SCRUB-L"
    )
    assert items["Size S"]["unit_price"] == "20000.00"
    row = Order.objects.get(pk=order["orders"][0]["id"])
    assert row.commission_total == D("14000")  # 20% of 70,000
    small_row = ProductVariant.objects.get(pk=small["id"])
    assert (small_row.stock_quantity, small_row.stock_reserved) == (1, 1)
    sold_out = _buy(buyer, baghdad, [(product.pk, small["id"], 1)], expect=409)
    assert sold_out["error"]["code"] == "out_of_stock"
    # Cancelling releases exactly the variants' reservations.
    _post(client_for(buyer), f"{ORDERS}/{row.pk}/cancel")
    assert ProductVariant.objects.get(pk=small["id"]).stock_reserved == 0
    assert ProductVariant.objects.get(pk=large["id"]).stock_reserved == 0
    moves = StockMovement.objects.filter(order=row).values_list("variant_id", "kind")
    assert {(str(v), k) for v, k in moves} == {
        (small["id"], "RESERVE"),
        (large["id"], "RESERVE"),
        (small["id"], "RELEASE"),
        (large["id"], "RELEASE"),
    }
    # Stock changes go through an adjustment with a reason.
    assert (
        client.patch(
            f"{COMPANY}/variants/{small['id']}", {"stock_quantity": 50}, format="json"
        ).status_code
        == 400
    )
    adjusted = _post(
        client,
        f"{MERCHANT}/inventory/{product.pk}/adjust",
        {"delta": 3, "reason": "Delivery received", "variant_id": small["id"]},
    )
    assert adjusted["variant_id"] == small["id"] and adjusted["on_hand"] == 4
    rows = client.get(f"{MERCHANT}/inventory").json()
    assert {r["sku"] for r in rows if r["id"] == str(product.pk)} == {"SCRUB-S", "SCRUB-L"}
    assert reconciliation()["ok"]


def test_a_variant_of_another_product_or_store_cannot_be_bought_or_edited(
    scrubs, company_factory, product_factory, consumer_category, account_factory, baghdad
):
    shop, product, small, _ = scrubs
    rival = company_factory(business_type=BusinessType.MEDICAL_SUPPLIES_OFFICE)
    other = product_factory(
        rival, consumer_category, price=D("1000"), sale_channel="B2C", stock_quantity=5
    )
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    _buy(buyer, baghdad, [(other.pk, small["id"], 1)], expect=400)
    edit = client_for(rival.account).patch(
        f"{COMPANY}/variants/{small['id']}", {"label": "hijacked"}, format="json"
    )
    assert edit.status_code == 404
    listing = client_for(rival.account).get(f"{COMPANY}/products/{product.pk}/variants")
    assert listing.status_code == 200 and listing.json() == []


def test_a_product_whose_options_are_all_hidden_cannot_be_bought(scrubs, account_factory, baghdad):
    shop, product, small, large = scrubs
    client = client_for(shop.account)
    for v in (small, large):
        hide = client.patch(f"{COMPANY}/variants/{v['id']}", {"is_active": False}, format="json")
        assert hide.status_code == 200
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    refused = _buy(buyer, baghdad, [(product.pk, None, 1)], expect=400)
    assert refused["error"]["code"] == "invalid_cart"
    hidden = _buy(buyer, baghdad, [(product.pk, small["id"], 1)], expect=400)
    assert "not available" in hidden["error"]["message"]


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_the_last_unit_of_a_variant_is_sold_once(scrubs, account_factory, baghdad):
    _, product, small, _ = scrubs
    buyers = [_verified(account_factory(role=AccountRole.PATIENT)) for _ in range(4)]
    results = []

    def attempt(buyer):
        try:
            response = client_for(buyer).post(
                CHECKOUTS, _checkout_body(baghdad, [(product.pk, small["id"], 1)]), format="json"
            )
            results.append(response.status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(b,)) for b in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [201, 409, 409, 409]
    variant = ProductVariant.objects.get(pk=small["id"])
    assert (variant.stock_quantity, variant.stock_reserved) == (1, 1)


# ---- Priority 3: delivery fees, tax, tracking, invoices, reports --------------------------------


@pytest.fixture
def bed_store(company_factory, product_factory, consumer_category, baghdad):
    shop = company_factory(business_type=BusinessType.EQUIPMENT_SUPPLIER)
    bed = product_factory(
        shop, consumer_category, price=D("100000"), sale_channel="B2C", stock_quantity=10,
        title="Home-care bed (demo)",
    )  # fmt: skip
    client = client_for(shop.account)
    _post(client, f"{COMPANY}/shipping-rates", {"governorate": baghdad.pk, "fee": "5000"})
    return shop, bed, client


def test_delivery_fee_goes_to_the_seller_without_commission(
    bed_store, account_factory, baghdad, finance
):
    shop, bed, client = bed_store
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    preview = _post(
        client_for(buyer),
        f"{CHECKOUTS}/preview",
        {"items": [{"product": str(bed.pk), "quantity": 1}], "governorate": baghdad.pk},
    )
    assert preview["shipping_known"] and preview["orders"][0]["shipping_fee"] == "5000.00"
    assert preview["total"] == "105000.00" and preview["merchandise_total"] == "100000.00"
    order_id = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    row = Order.objects.get(pk=order_id)
    assert (row.total, row.shipping_total, row.commission_total) == (
        D("105000"),
        D("5000"),
        D("20000"),
    )
    shipping = OrderItem.objects.get(order=row, kind="SHIPPING")
    assert (shipping.commission, shipping.seller_payable) == (0, D("5000"))
    _fulfil_and_pay(client, buyer, finance, order_id)
    report = statement(shop.pk)
    assert report["commission"] == D("20000") and report["shipping_collected"] == D("5000")
    assert report["seller_earnings"] == D("85000") and report["payable"] == D("85000")
    assert reconciliation()["ok"]


def test_delivery_rules_free_over_threshold_and_unserved_governorates(
    bed_store, account_factory, baghdad
):
    from apps.geography.models import Governorate

    shop, bed, client = bed_store
    client.patch(STORE, {"free_shipping_over": "150000"}, format="json")
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    two = _buy(buyer, baghdad, [(bed.pk, None, 2)])
    assert two["orders"][0]["shipping_total"] == "0.00"  # 200,000 >= 150,000
    elsewhere = Governorate.objects.exclude(pk=baghdad.pk).filter(is_active=True).first()
    refused = _buy(buyer, baghdad, [(bed.pk, None, 1)], expect=400, governorate=elsewhere.pk)
    assert refused["error"]["code"] == "no_delivery"
    client.patch(STORE, {"default_shipping_fee": "8000"}, format="json")
    ok = _buy(buyer, baghdad, [(bed.pk, None, 1)], governorate=elsewhere.pk)
    assert ok["orders"][0]["shipping_total"] == "8000.00"


def test_cancelled_paid_order_refunds_delivery_but_a_return_does_not(
    bed_store, account_factory, baghdad, finance
):
    shop, bed, client = bed_store
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    fin = client_for(finance)
    first = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    _post(fin, f"{ADMIN}/orders/{first}/verify-payment", {"reference": "SIM-TRANSFER-1"})
    _post(client_for(buyer), f"{ORDERS}/{first}/cancel")
    _post(fin, f"{ADMIN}/orders/{first}/refund-cancelled")
    assert Order.objects.get(pk=first).refunded_total == D("105000")
    second = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    _fulfil_and_pay(client, buyer, finance, second)
    item = OrderItem.objects.get(order_id=second, kind="MERCHANDISE")
    ret = _post(
        client_for(buyer),
        f"{ORDERS}/{second}/returns",
        {"reason": "Wrong size (demo)", "lines": [{"item": str(item.pk), "quantity": 1}]},
    )["returns"][0]
    shipping = OrderItem.objects.get(order_id=second, kind="SHIPPING")
    refused = client_for(buyer).post(
        f"{ORDERS}/{second}/returns",
        {"reason": "x", "lines": [{"item": str(shipping.pk), "quantity": 1}]},
        format="json",
    )
    assert refused.status_code in (400, 409)
    _post(client, f"{MERCHANT}/returns/{ret['id']}/decide", {"approve": True})
    _post(client, f"{MERCHANT}/returns/{ret['id']}/received")
    _post(fin, f"{ADMIN}/returns/{ret['id']}/refund")
    row = Order.objects.get(pk=second)
    assert row.refunded_total == D("100000") and row.payment_status == "PARTIALLY_REFUNDED"
    assert statement(shop.pk)["seller_earnings"] == D("5000")  # the delivery fee it earned
    assert reconciliation()["ok"]


def test_seller_declared_tax_is_passed_through_and_refunded_with_the_goods(
    company_factory, product_factory, consumer_category, account_factory, baghdad, finance
):
    shop = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    walker = product_factory(
        shop, consumer_category, price=D("30000"), sale_channel="B2C", stock_quantity=10
    )
    client = client_for(shop.account)
    too_high = client.patch(STORE, {"tax_mode": "EXCLUSIVE", "tax_rate": "31"}, format="json")
    assert too_high.status_code == 400
    _ = client.patch(
        STORE,
        {"tax_mode": "EXCLUSIVE", "tax_rate": "10", "tax_label": "Sales tax (demo)"},
        format="json",
    )
    assert _.status_code == 200, _.json()
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order_id = _buy(buyer, baghdad, [(walker.pk, None, 3)])["orders"][0]["id"]
    row = Order.objects.get(pk=order_id)
    assert (row.total, row.tax_total, row.commission_total) == (D("99000"), D("9000"), D("18000"))
    tax = OrderItem.objects.get(order=row, kind="TAX")
    assert tax.quantity == 3 and tax.parent_item.kind == "MERCHANDISE"
    _fulfil_and_pay(client, buyer, finance, order_id)
    item = OrderItem.objects.get(order=row, kind="MERCHANDISE")
    ret = _post(
        client_for(buyer),
        f"{ORDERS}/{order_id}/returns",
        {"reason": "Not needed (demo)", "lines": [{"item": str(item.pk), "quantity": 1}]},
    )["returns"][0]
    _post(client, f"{MERCHANT}/returns/{ret['id']}/decide", {"approve": True})
    _post(client, f"{MERCHANT}/returns/{ret['id']}/received")
    _post(client_for(finance), f"{ADMIN}/returns/{ret['id']}/refund")
    row.refresh_from_db()
    assert row.refunded_total == D("33000")  # one unit + its tax
    assert statement(shop.pk)["tax_collected"] == D("6000")
    assert reconciliation()["ok"]
    # INCLUSIVE only shows the included part; NONE (the default) shows nothing.
    client.patch(STORE, {"tax_mode": "INCLUSIVE", "tax_rate": "10"}, format="json")
    inclusive = Order.objects.get(
        pk=_buy(buyer, baghdad, [(walker.pk, None, 1)])["orders"][0]["id"]
    )
    assert (inclusive.total, inclusive.tax_total, inclusive.tax_included_total) == (
        D("30000"),
        0,
        D("2727"),
    )


def test_tracking_events_are_the_sellers_and_never_change_the_status(
    bed_store, account_factory, baghdad, company_factory
):
    shop, bed, client = bed_store
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order_id = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    early = client.post(
        f"{MERCHANT}/orders/{order_id}/tracking", {"status": "IN_TRANSIT"}, format="json"
    )
    assert early.status_code == 409
    _post(client, f"{MERCHANT}/orders/{order_id}/transition", {"status": "CONFIRMED"})
    _post(
        client,
        f"{MERCHANT}/orders/{order_id}/transition",
        {"status": "SHIPPED", "shipping_reference": "TRK-9", "courier_name": "Demo courier"},
    )
    _post(
        client,
        f"{MERCHANT}/orders/{order_id}/tracking",
        {"status": "OUT_FOR_DELIVERY", "location": "Karrada (demo)"},
        201,
    )
    seen = client_for(buyer).get(f"{ORDERS}/{order_id}").json()
    assert seen["status"] == "SHIPPED" and seen["courier_name"] == "Demo courier"
    assert [e["status"] for e in seen["tracking_events"]] == ["OUT_FOR_DELIVERY"]
    rival = company_factory()
    forged = client_for(rival.account).post(
        f"{MERCHANT}/orders/{order_id}/tracking", {"status": "DELAYED"}, format="json"
    )
    assert forged.status_code == 404
    bogus = client.post(
        f"{MERCHANT}/orders/{order_id}/tracking", {"status": "DELIVERED"}, format="json"
    )
    assert bogus.status_code == 400


def test_invoices_are_frozen_snapshots_visible_only_to_the_buyer_and_the_seller(
    bed_store, account_factory, baghdad, finance, company_factory
):
    shop, bed, client = bed_store
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order_id = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    assert client_for(buyer).get(f"{ORDERS}/{order_id}/invoices").json() == []  # not paid yet
    _fulfil_and_pay(client, buyer, finance, order_id)
    docs = client_for(buyer).get(f"{ORDERS}/{order_id}/invoices").json()
    assert [d["kind"] for d in docs] == ["INVOICE", "RECEIPT"]
    invoice = client_for(buyer).get(f"{ORDERS}/{order_id}/invoices/{docs[0]['id']}").json()
    snap = invoice["snapshot"]
    assert snap["totals"]["total"] == "105000.00" and snap["totals"]["shipping"] == "5000.00"
    assert snap["lines"][0]["title"] == "Home-care bed (demo)"
    assert "commission" not in str(snap).lower()  # buyers never see the commission
    assert "no real payment" in snap["notice"]
    Product.objects.filter(pk=bed.pk).update(title="Renamed later")
    again = client_for(buyer).get(f"{ORDERS}/{order_id}/invoices/{docs[0]['id']}").json()
    assert again["snapshot"]["lines"][0]["title"] == "Home-care bed (demo)"
    seller_docs = client.get(f"{MERCHANT}/orders/{order_id}/invoices").json()
    assert {d["number"] for d in seller_docs} == {d["number"] for d in docs}
    stranger = _verified(account_factory(role=AccountRole.PATIENT))
    assert client_for(stranger).get(f"{ORDERS}/{order_id}/invoices").status_code == 404
    rival = company_factory()
    assert (
        client_for(rival.account).get(f"{MERCHANT}/orders/{order_id}/invoices").status_code == 404
    )


def test_orders_paid_before_documents_existed_get_them_on_first_request(
    bed_store, account_factory, baghdad, finance
):
    shop, bed, client = bed_store
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order_id = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    _fulfil_and_pay(client, buyer, finance, order_id)
    Invoice.objects.filter(order_id=order_id).delete()  # as if paid before this feature
    docs = client_for(buyer).get(f"{ORDERS}/{order_id}/invoices").json()
    assert [d["kind"] for d in docs] == ["INVOICE", "RECEIPT"]
    assert client_for(buyer).get(f"{ORDERS}/{order_id}/invoices").json() == docs  # idempotent


def test_accounting_reports_match_the_ledger_and_are_scoped(
    bed_store, account_factory, baghdad, finance, support_staff, company_factory
):
    shop, bed, client = bed_store
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order_id = _buy(buyer, baghdad, [(bed.pk, None, 1)])["orders"][0]["id"]
    _fulfil_and_pay(client, buyer, finance, order_id)
    report = client.get(f"{MERCHANT}/reports/sales").json()
    assert D(str(report["totals"]["settled_commission"])) == D("20000")
    assert D(str(report["totals"]["settled_earnings"])) == statement(shop.pk)["seller_earnings"]
    csv = client.get(f"{MERCHANT}/reports/sales?export=csv")
    assert csv.status_code == 200 and csv["Content-Type"].startswith("text/csv")
    assert csv.content.decode().splitlines()[0].startswith("order,placed,completed")
    rival = company_factory()
    assert (
        client_for(rival.account).get(f"{MERCHANT}/reports/sales?company={shop.pk}").status_code
        == 403
    )
    finance_member = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(account=finance_member, company=shop, role="FINANCE")
    assert (
        client_for(finance_member).get(f"{MERCHANT}/reports/sales?company={shop.pk}").status_code
        == 200
    )
    viewer = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(account=viewer, company=shop, role="VIEWER")
    assert client_for(viewer).get(f"{MERCHANT}/reports/sales?company={shop.pk}").status_code == 403
    platform = client_for(finance).get(f"{ADMIN}/reports/marketplace").json()
    assert platform["reconciliation_ok"] is True
    mine = next(r for r in platform["sellers"] if r["seller"] == shop.name)
    assert D(str(mine["commission"])) == D("20000") and D(str(mine["gmv"])) == D("105000")
    assert client_for(support_staff).get(f"{ADMIN}/reports/marketplace").status_code == 403
    bad = client.get(f"{MERCHANT}/reports/sales?from=2026-12-01&to=2026-01-01")
    assert bad.status_code == 400


def test_report_csv_cannot_inject_spreadsheet_formulas():
    from apps.commerce.reports import to_csv

    text = to_csv([{"seller": '=HYPERLINK("http://x")', "gmv": D("-5")}], ("seller", "gmv"))
    assert "'=HYPERLINK" in text and ",-5" in text


# ---- isolation and staff roles ------------------------------------------------------------------


def test_store_tools_never_cross_organizations_and_follow_staff_roles(
    scrubs, company_factory, account_factory, baghdad
):
    shop, product, small, _ = scrubs
    rival = company_factory()
    rc = client_for(rival.account)
    q = f"?company={shop.pk}"
    for method, url, body in (
        ("get", f"{STORE}{q}", None),
        ("patch", f"{STORE}{q}", {"tax_mode": "NONE"}),
        ("post", f"{STORE}/status{q}", {"active": False}),
        ("get", f"{DOCS}{q}", None),
        ("get", f"{COMPANY}/shipping-rates{q}", None),
        ("post", f"{COMPANY}/shipping-rates{q}", {"governorate": baghdad.pk, "fee": "1"}),
        ("get", f"{COMPANY}/products/{product.pk}/variants{q}", None),
        ("post", f"{COMPANY}/products/{product.pk}/variants{q}", {"sku": "X", "label": "X"}),
        ("patch", f"{COMPANY}/variants/{small['id']}{q}", {"label": "X"}),
        ("get", f"{MERCHANT}/reports/sales{q}", None),
    ):
        response = getattr(rc, method)(url, body, format="json")
        assert response.status_code == 403, (method, url, response.status_code)
    # Staff roles inside the shop: each does only its job.
    editor = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(account=editor, company=shop, role="PRODUCT_EDITOR")
    ec = client_for(editor)
    assert ec.post(
        f"{COMPANY}/products/{product.pk}/variants{q}", {"sku": "SCRUB-M", "label": "Size M"},
        format="json",
    ).status_code == 201  # fmt: skip
    assert ec.get(f"{DOCS}{q}").status_code == 403
    assert ec.post(f"{STORE}/status{q}", {"active": False}, format="json").status_code == 403
    manager = account_factory(role=AccountRole.PATIENT)
    member = OrganizationMember.objects.create(account=manager, company=shop, role="MANAGER")
    mc = client_for(manager)
    assert mc.get(f"{DOCS}{q}").status_code == 200
    assert (
        mc.patch(f"{STORE}{q}", {"default_shipping_fee": "2000"}, format="json").status_code == 200
    )
    member.status = "ENDED"
    member.ended_at = timezone.now()
    member.save()
    assert mc.get(f"{DOCS}{q}").status_code == 403


def test_pharmacy_store_staff_and_rival_pharmacy_are_isolated(
    pharmacy, provider_factory, admin_client, account_factory, baghdad
):
    client = client_for(pharmacy.account)
    store = _onboard(client, admin_client, business_type="PHARMACY", baghdad=baghdad, pharmacy=True)
    other = provider_factory(ProviderType.PHARMACY)
    oc = client_for(other.account)
    _post(oc, f"{MP}/pharmacy-store", {}, expect=201)
    q = f"?company={store['id']}"
    assert oc.get(f"{DOCS}{q}").status_code == 403
    assert oc.get(f"{MERCHANT}/orders{q}").status_code == 403
    own_docs = oc.get(DOCS).json()
    assert own_docs == []  # its own (empty) documents, never the first pharmacy's


# ---- Priority 4: advertising stays compliant for the new sellers --------------------------------


def test_a_pharmacy_can_advertise_only_while_selling_and_never_regulated_items(
    pharmacy, admin_client, baghdad, category_factory
):
    client = client_for(pharmacy.account)
    _onboard(client, admin_client, business_type="PHARMACY", baghdad=baghdad, pharmacy=True)
    pro = category_factory(slug="clinic-otc", rules=[(ProviderType.DOCTOR, None)])
    product = _product(client, pro, sale_channel="B2B", stock_quantity=5)
    _publish(client, product["id"])
    today = timezone.localdate()
    body = {
        "name": "Pharmacy campaign (demo)",
        "product": product["id"],
        "starts_on": str(today),
        "ends_on": str(today + timezone.timedelta(days=7)),
    }
    created = client.post(f"{API}/advertising/company/campaigns", body, format="json")
    assert created.status_code == 201, created.json()
    restricted = category_factory(
        slug="rx-only", rules=[(ProviderType.DOCTOR, None)],
        compliance_class="RESTRICTED_PENDING_REVIEW",
    )  # fmt: skip
    rx = _product(client, restricted, sale_channel="B2B", stock_quantity=5, is_restricted=True)
    refused = client.post(
        f"{API}/advertising/company/campaigns", {**body, "product": rx["id"]}, format="json"
    )
    assert refused.status_code == 400
    _post(client, f"{STORE}/status", {"active": False})
    company = _company(pharmacy.account)
    assert not company.can_sell


def test_reverifying_a_legacy_store_without_documents_does_not_reopen_it(company_factory):
    from apps.marketplace import services as mp

    legacy = company_factory(status="PENDING")
    assert legacy.store_status == "ACTIVE"  # a store from before activation existed
    mp.set_verification(legacy, "VERIFIED", admin=None)
    legacy.refresh_from_db()
    assert legacy.store_status == "INACTIVE" and not legacy.can_sell


def test_existing_stores_keep_selling_and_new_ones_start_inactive(company_factory, baghdad):
    legacy = company_factory()
    assert legacy.store_status == "ACTIVE" and legacy.can_sell  # migrated rows keep selling
    from apps.marketplace.services import create_company

    fresh = create_company(
        legacy.account.__class__.objects.create_user(
            email="new-seller@example.com", password="Str0ng-Passw0rd!", full_name="New",
            role=AccountRole.MEDICAL_COMPANY,
        ),
        {"name": "New store", "business_type": "MEDICAL_COMPANY", "governorate": baghdad},
    )  # fmt: skip
    assert fresh.store_status == "INACTIVE"


def test_audience_rules_still_target_professional_products(
    company_factory, product_factory, provider_factory
):
    category = ProductCategory.objects.create(
        slug="lab-kits", name_ar="عدة", name_en="Lab kits", compliance_class="B2B_VERIFIED_ONLY"
    )
    ProductAudience.objects.create(category=category, provider_type=ProviderType.LABORATORY)
    seller = company_factory(business_type=BusinessType.SCIENTIFIC_OFFICE)
    product = product_factory(seller, category, price=D("1"), sale_channel=SaleChannel.B2B)
    lab = provider_factory(ProviderType.LABORATORY)
    doctor = provider_factory(ProviderType.DOCTOR)
    assert Product.objects.targeted_for(lab).filter(pk=product.pk).exists()
    assert not Product.objects.targeted_for(doctor).filter(pk=product.pk).exists()
    MedicalCompany.objects.filter(pk=seller.pk).update(store_status="PAUSED")
    assert not Product.objects.targeted_for(lab).filter(pk=product.pk).exists()
