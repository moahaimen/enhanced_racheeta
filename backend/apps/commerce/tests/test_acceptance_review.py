"""Final local acceptance review (2026-11-06): regression tests for every finding reproduced
against 40a6e0b, plus the acceptance checks on commission, restocking, uploads and privacy.

Findings (each first reproduced by a probe, then fixed):
  A1 a grandfathered ACTIVE store with NO approved licence documents could sell;
  A2 revoking (rejecting) a previously approved licence did not stop the store selling;
  A3 photos of professional-only (B2B) products were public to anonymous visitors;
  A4 checkout errors named a professional-only product to a buyer who may not see it;
  A5 JPEG EXIF (incl. GPS) and other photo metadata were published as uploaded.
"""

import struct
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.commerce.models import Coupon, Order, OrderItem, ProductOffer, StockMovement
from apps.ledger import settlement
from apps.ledger.settlement import reconciliation, statement
from apps.marketplace import sellers
from apps.marketplace.models import MedicalCompany, Product, ProductImage, SellerDocument
from apps.marketplace.types import BusinessType, SaleChannel
from apps.notifications.models import Notification
from apps.providers.types import ProviderType

from .conftest import client_for
from .test_sellers_products_orders import (
    ADMIN,
    COMPANY,
    MERCHANT,
    ORDERS,
    _buy,
    _fulfil_and_pay,
    _post,
    _verified,
    png,
)

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture(autouse=True)
def private_media(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path


def _approved(company, kind="COMMERCIAL_REGISTRATION"):
    return SellerDocument.objects.create(
        company=company,
        kind=kind,
        file=ContentFile(b"%PDF-1.4\n%%EOF\n", name="licence.pdf"),
        original_name="licence.pdf",
        content_type="application/pdf",
        size=16,
        sha256="0" * 64,
        status="APPROVED",
    )


# ---- A1 / A2: legacy and revoked licences -------------------------------------------------------


def test_a_grandfathered_store_without_approved_documents_cannot_sell(
    company_factory, category_factory, product_factory, provider_factory, account_factory, baghdad
):
    """marketplace 0007 computes documents_complete from real rows: a store from before
    documents existed has none, so it stops selling in the store, the B2B catalogue and checkout
    (consumer AND professional products) until its licences are approved."""
    legacy = company_factory(
        business_type=BusinessType.EQUIPMENT_SUPPLIER, documents_complete=False
    )
    assert legacy.store_status == "ACTIVE" and not legacy.can_sell
    consumer = product_factory(
        legacy, category_factory(consumer_allowed=True), price=D("1000"),
        sale_channel=SaleChannel.B2C, stock_quantity=5,
    )  # fmt: skip
    pro_cat = category_factory(rules=[(ProviderType.DOCTOR, None)])
    professional = product_factory(legacy, pro_cat, price=D("1000"), sale_channel=SaleChannel.B2B)
    doctor = provider_factory(ProviderType.DOCTOR)
    doctor.account = _verified(doctor.account)
    assert not Product.objects.consumer_store().filter(pk=consumer.pk).exists()
    assert not Product.objects.targeted_for(doctor).filter(pk=professional.pk).exists()
    patient = _verified(account_factory(role=AccountRole.PATIENT))
    assert _buy(patient, baghdad, [(consumer.pk, None, 1)], expect=403)["error"]["code"] == (
        "not_allowed"
    )
    assert (
        _buy(doctor.account, baghdad, [(professional.pk, None, 1)], expect=403)["error"]["code"]
        == "not_allowed"
    )
    # The seller uploads its licences; Racheeta approves them: it sells again.
    for kind in ("COMMERCIAL_REGISTRATION", "DEVICE_REGISTRATION"):
        doc = sellers.upload_document(
            legacy.pk, actor=legacy.account, kind=kind,
            upload=SimpleUploadedFile(f"{kind}.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"),
        )  # fmt: skip
        sellers.review_document(doc.pk, admin=None, approve=True)
    legacy.refresh_from_db()
    assert legacy.documents_complete and legacy.can_sell
    _buy(patient, baghdad, [(consumer.pk, None, 1)])


def test_the_migration_marks_existing_stores_without_documents_as_incomplete():
    """The 0007 data step, run on a store with and one without its documents."""
    import importlib

    from django.apps import apps as global_apps

    migration = importlib.import_module("apps.marketplace.migrations.0007_documents_complete")
    MedicalCompany.objects.all().delete()
    from apps.accounts.models import Account
    from apps.geography.models import Governorate

    def company(email, business):
        account = Account.objects.create_user(
            email=email, password="Str0ng-Passw0rd!", full_name="X", role="MEDICAL_COMPANY"
        )
        return MedicalCompany.objects.create(
            account=account, name=email, business_type=business, documents_complete=True,
            governorate=Governorate.objects.get(slug="baghdad"), verification_status="VERIFIED",
        )  # fmt: skip

    with_docs = company("with@example.com", "ASSISTIVE_DEVICE_STORE")
    _approved(with_docs)
    without = company("without@example.com", "ASSISTIVE_DEVICE_STORE")
    migration.compute(global_apps, None)
    with_docs.refresh_from_db()
    without.refresh_from_db()
    assert with_docs.documents_complete is True
    assert without.documents_complete is False


def test_revoking_an_approved_licence_stops_the_sale_at_once(
    company_factory, category_factory, product_factory, account_factory, baghdad
):
    store = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    doc = _approved(store)
    sellers.refresh_documents_complete(store.pk)
    product = product_factory(
        store, category_factory(consumer_allowed=True), price=D("1000"),
        sale_channel=SaleChannel.B2C, stock_quantity=5,
    )  # fmt: skip
    sellers.review_document(doc.pk, admin=None, approve=False, note="Licence revoked (demo)")
    store.refresh_from_db()
    assert not store.can_sell
    assert not Product.objects.consumer_store().filter(pk=product.pk).exists()
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    _buy(buyer, baghdad, [(product.pk, None, 1)], expect=403)


def test_a_category_licence_is_rechecked_at_sale_time(
    company_factory, category_factory, product_factory, account_factory, baghdad
):
    store = company_factory(business_type=BusinessType.EQUIPMENT_SUPPLIER)
    category = category_factory(consumer_allowed=True, required_documents=["DEVICE_REGISTRATION"])
    device = _approved(store, "DEVICE_REGISTRATION")
    product = product_factory(
        store, category, price=D("1000"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    _buy(buyer, baghdad, [(product.pk, None, 1)])
    SellerDocument.objects.filter(pk=device.pk).update(expires_on=timezone.localdate())
    _buy(buyer, baghdad, [(product.pk, None, 1)], expect=403)  # expired today
    SellerDocument.objects.filter(pk=device.pk).update(expires_on=None, status="REJECTED")
    _buy(buyer, baghdad, [(product.pk, None, 1)], expect=403)


# ---- A3 / A4: professional-only products ------------------------------------------------------


@pytest.fixture
def b2b(company_factory, category_factory, product_factory):
    seller = company_factory(business_type=BusinessType.SCIENTIFIC_OFFICE)
    category = category_factory(rules=[(ProviderType.DOCTOR, None)])
    product = product_factory(
        seller, category, price=D("5000"), sale_channel=SaleChannel.B2B, title="Lab kit (B2B)"
    )
    image = sellers.add_image(
        seller.pk, product.pk, actor=seller.account, upload=SimpleUploadedFile("k.png", png())
    )
    return seller, product, image


def test_professional_product_photos_follow_the_catalogue_targeting(
    b2b, provider_factory, account_factory, company_factory
):
    seller, product, image = b2b
    url = f"/api/v1/marketplace/images/{image.pk}"
    assert APIClient().get(url).status_code == 404  # anonymous
    patient = account_factory(role=AccountRole.PATIENT)
    assert client_for(patient).get(url).status_code == 404
    nurse = provider_factory(ProviderType.NURSE)  # verified, but not targeted
    assert client_for(nurse.account).get(url).status_code == 404
    rival = company_factory()
    assert client_for(rival.account).get(url).status_code == 404
    doctor = provider_factory(ProviderType.DOCTOR)
    assert client_for(doctor.account).get(url).status_code == 200
    assert client_for(seller.account).get(url).status_code == 200


def test_b2b_details_prices_and_ads_stay_with_targeted_professionals(
    b2b, provider_factory, account_factory, baghdad
):
    seller, product, _ = b2b
    patient = _verified(account_factory(role=AccountRole.PATIENT))
    for url in (
        f"/api/v1/marketplace/products/{product.pk}",
        f"/api/v1/store/products/{product.pk}",
    ):
        assert client_for(patient).get(url).status_code in (403, 404)
    assert APIClient().get(f"/api/v1/store/products/{product.pk}").status_code == 404
    refused = _buy(patient, baghdad, [(product.pk, None, 1)], expect=403)
    assert "Lab kit" not in str(refused) and "5000" not in str(refused)  # A4
    preview = client_for(patient).post(
        "/api/v1/checkouts/preview", {"items": [{"product": str(product.pk), "quantity": 1}]},
        format="json",
    )  # fmt: skip
    assert preview.status_code == 403 and "Lab kit" not in str(preview.json())
    nurse = provider_factory(ProviderType.NURSE)
    assert (
        client_for(nurse.account).get(f"/api/v1/marketplace/products/{product.pk}").status_code
        == 404
    )
    sponsored = client_for(nurse.account).get("/api/v1/advertising/marketplace").json()
    assert all(r["product"]["id"] != str(product.pk) for r in sponsored.get("results", []))


# ---- A5 and the upload review -------------------------------------------------------------------


def _jpeg_with_exif() -> bytes:
    exif = b"Exif\x00\x00GPS-LAT-33.31-LON-44.36 Camera-Serial-123"
    xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>owner@example.com</x:xmpmeta>"
    comment = b"taken at home"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, 120, 160, 1) + b"\x01\x11\x00"

    def seg(marker, payload):
        return marker + struct.pack(">H", len(payload) + 2) + payload

    return (
        b"\xff\xd8"
        + seg(b"\xff\xe0", b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
        + seg(b"\xff\xe1", exif)
        + seg(b"\xff\xe1", xmp)
        + seg(b"\xff\xfe", comment)
        + sof
        + b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
        + b"\x11" * 32
        + b"\xff\xd9"
    )


def _png_with_text() -> bytes:
    def chunk(kind, data):
        import zlib

        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    base = png(120, 90)
    head, rest = base[:33], base[33:]  # signature + IHDR, then IDAT/IEND
    return (
        head
        + chunk(b"tEXt", b"Author\x00Dr. Real Name")
        + chunk(b"tIME", b"\x07\xea\x0b\x06\x0c\x00\x00")
        + rest
    )


def _webp_with_exif() -> bytes:
    vp8x = (
        b"VP8X"
        + struct.pack("<I", 10)
        + bytes([0x0C, 0, 0, 0])
        + (119).to_bytes(3, "little")
        + (89).to_bytes(3, "little")
    )
    vp8l = b"VP8L" + struct.pack("<I", 5) + b"\x2f\x77\x40\x59\x00" + b"\x00"
    exif = b"EXIF" + struct.pack("<I", 12) + b"GPS-LAT-33.3"
    xmp = b"XMP " + struct.pack("<I", 8) + b"<x:meta>"
    body = b"WEBP" + vp8x + vp8l + exif + xmp
    return b"RIFF" + struct.pack("<I", len(body)) + body


@pytest.mark.parametrize(
    "name,data,secret",
    [
        ("photo.jpg", _jpeg_with_exif(), (b"GPS-LAT", b"owner@example.com", b"taken at home")),
        ("photo.png", _png_with_text(), (b"Dr. Real Name", b"tIME")),
        ("photo.webp", _webp_with_exif(), (b"GPS-LAT", b"<x:meta>")),
    ],
)
def test_photo_metadata_is_removed_before_storage(
    name, data, secret, company_factory, category_factory, product_factory
):
    from apps.marketplace import uploads

    seller = company_factory(business_type=BusinessType.EQUIPMENT_SUPPLIER)
    product = product_factory(
        seller, category_factory(consumer_allowed=True), price=D("1"),
        sale_channel=SaleChannel.B2C, stock_quantity=1,
    )  # fmt: skip
    image = sellers.add_image(
        seller.pk, product.pk, actor=seller.account, upload=SimpleUploadedFile(name, data)
    )
    stored = ProductImage.objects.get(pk=image.pk).file.read()
    for value in secret:
        assert value not in stored
    assert uploads.sniff(stored[:16]) == image.content_type  # still a valid file of its type
    if name.endswith(".webp"):
        assert stored[20] & 0x0C == 0  # VP8X no longer announces EXIF/XMP
        assert struct.unpack("<I", stored[4:8])[0] == len(stored) - 8


def test_upload_names_and_download_headers_cannot_be_abused(company_factory, baghdad):
    from apps.marketplace import uploads

    assert uploads.clean_name('..\\..\\windows\\system32\\evil".pdf') == "evil.pdf"
    assert uploads.clean_name("a\r\nSet-Cookie: x=1.pdf") == "aSet-Cookie x=1.pdf"
    assert uploads.clean_name("") == "document"
    company = company_factory()
    doc = sellers.upload_document(
        company.pk, actor=company.account, kind="OTHER",
        upload=SimpleUploadedFile('x"\r\nX-Injected: 1.pdf', b"%PDF-1.4\n%%EOF\n"),
    )  # fmt: skip
    response = client_for(company.account).get(f"{COMPANY}/documents/{doc.pk}/file")
    assert "\n" not in response["Content-Disposition"] and "X-Injected:" not in str(
        response.headers.get("X-Injected")
    )
    assert response["Content-Disposition"].startswith('attachment; filename="')


# ---- item 5: the 20% commission with every price component --------------------------------------


def test_commission_with_delivery_exclusive_tax_discounts_partial_return_and_refund_after_payout(
    company_factory, product_factory, category_factory, account_factory, baghdad, finance
):
    """2 × 50,000; seller sale 10%; seller coupon 5,000; Racheeta coupon 10,000; delivery 5,000;
    seller-declared 10% tax on top. The commission base is merchandise after SELLER discounts:
    100,000 − 10,000 − 5,000 = 85,000 → commission 17,000. Racheeta's coupon is paid by Racheeta
    and does not lower it. Tax (8,500 = 10% of 85,000) and delivery go to the seller in full."""
    shop = company_factory(business_type=BusinessType.EQUIPMENT_SUPPLIER)
    MedicalCompany.objects.filter(pk=shop.pk).update(tax_mode="EXCLUSIVE", tax_rate=D("10"))
    product = product_factory(
        shop, category_factory(consumer_allowed=True), price=D("50000"),
        sale_channel=SaleChannel.B2C, stock_quantity=10,
    )  # fmt: skip
    client = client_for(shop.account)
    _post(client, f"{COMPANY}/shipping-rates", {"governorate": baghdad.pk, "fee": "5000"})
    now = timezone.now()
    ProductOffer.objects.create(
        company=shop, product=product, percent=D("10"), starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )  # fmt: skip
    for code, funded, company in (("SHOP5K", "SELLER", shop), ("RCH10K", "PLATFORM", None)):
        Coupon.objects.create(
            code=code, funded_by=funded, company=company, kind="FIXED",
            value=D("5000") if funded == "SELLER" else D("10000"),
            starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1),
        )  # fmt: skip
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order_id = _buy(buyer, baghdad, [(product.pk, None, 2)], coupons=["SHOP5K", "RCH10K"])[
        "orders"
    ][0]["id"]
    order = Order.objects.get(pk=order_id)
    assert order.merchandise_net == D("85000") and order.commission_total == D("17000")
    assert order.platform_discount_total == D("10000")
    assert (order.tax_total, order.shipping_total) == (D("8500"), D("5000"))
    assert order.total == D("88500")  # 85,000 − 10,000 + 8,500 + 5,000
    assert order.seller_payable_total == D("81500")  # 85,000 − 17,000 + 8,500 + 5,000
    _fulfil_and_pay(client, buyer, finance, order_id)
    assert settlement.payable(shop.pk) == D("81500") and reconciliation()["ok"]
    # Partial return of one unit (its tax comes back; delivery stays with the seller).
    item = OrderItem.objects.get(order=order, kind="MERCHANDISE")
    ret = _post(
        client_for(buyer), f"{ORDERS}/{order_id}/returns",
        {"reason": "One too many (demo)", "lines": [{"item": str(item.pk), "quantity": 1}]},
    )["returns"][0]  # fmt: skip
    _post(client, f"{MERCHANT}/returns/{ret['id']}/decide", {"approve": True})
    _post(client, f"{MERCHANT}/returns/{ret['id']}/received")
    _post(client_for(finance), f"{ADMIN}/returns/{ret['id']}/refund")
    order.refresh_from_db()
    assert order.refunded_total == D("41750")  # 37,500 goods paid + 4,250 tax
    assert statement(shop.pk)["commission"] - statement(shop.pk)["refunded_commission"] == D("8500")
    assert settlement.payable(shop.pk) == D("43250") and reconciliation()["ok"]
    # Payout, then a dispute refund of everything left: the seller owes it back (receivable),
    # never a negative payable; the commission is fully reversed.
    batch = settlement.prepare(shop.pk, actor=finance)
    settlement.confirm(batch.pk, actor=finance, reference_note="SIM-PAYOUT-1")
    assert settlement.payable(shop.pk) == 0
    _post(client_for(buyer), f"{ORDERS}/{order_id}/disputes", {"reason": "Broken (demo)"})
    dispute = client_for(finance).get(f"{ADMIN}/disputes").json()["results"][0]
    _post(
        client_for(finance), f"{ADMIN}/disputes/{dispute['id']}/resolve",
        {"refund": True, "note": "Refunded after payout (demo)"},
    )  # fmt: skip
    order.refresh_from_db()
    assert order.refunded_total == order.total == D("88500")
    assert settlement.payable(shop.pk) == 0
    assert settlement.receivable(shop.pk) == D("43250")
    s = statement(shop.pk)
    assert s["commission"] - s["refunded_commission"] == 0
    assert reconciliation()["ok"]


def test_inclusive_tax_changes_nothing_but_the_invoice(
    company_factory, product_factory, category_factory, account_factory, baghdad, finance
):
    shop = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    MedicalCompany.objects.filter(pk=shop.pk).update(tax_mode="INCLUSIVE", tax_rate=D("5"))
    product = product_factory(
        shop, category_factory(consumer_allowed=True), price=D("30000"),
        sale_channel=SaleChannel.B2C, stock_quantity=3,
    )  # fmt: skip
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    order = Order.objects.get(pk=_buy(buyer, baghdad, [(product.pk, None, 1)])["orders"][0]["id"])
    assert (order.total, order.tax_total, order.tax_included_total) == (D("30000"), 0, D("1429"))
    assert (order.commission_total, order.seller_payable_total) == (D("6000"), D("24000"))
    _fulfil_and_pay(client_for(shop.account), buyer, finance, order.pk)
    invoice = client_for(buyer).get(f"{ORDERS}/{order.pk}/invoices").json()[0]
    doc = client_for(buyer).get(f"{ORDERS}/{order.pk}/invoices/{invoice['id']}").json()
    assert doc["snapshot"]["tax"]["included"] == "1429.00"
    assert reconciliation()["ok"]


# ---- item 6: restocking happens only when the goods come back ------------------------------------


def _on_hand(product):
    product.refresh_from_db()
    return product.stock_quantity, product.stock_reserved


def test_a_dispute_refund_never_restocks_but_a_received_return_does_once(
    company_factory, product_factory, category_factory, account_factory, baghdad, finance
):
    shop = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    product = product_factory(
        shop, category_factory(consumer_allowed=True), price=D("10000"),
        sale_channel=SaleChannel.B2C, stock_quantity=10,
    )  # fmt: skip
    client, fin = client_for(shop.account), client_for(finance)
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    # Dispute refund: money back, goods NOT back -> stock unchanged, no RESTOCK movement.
    first = _buy(buyer, baghdad, [(product.pk, None, 3)])["orders"][0]["id"]
    _fulfil_and_pay(client, buyer, finance, first)
    assert _on_hand(product) == (7, 0)
    _post(client_for(buyer), f"{ORDERS}/{first}/disputes", {"reason": "Never arrived (demo)"})
    dispute = fin.get(f"{ADMIN}/disputes").json()["results"][0]
    _post(fin, f"{ADMIN}/disputes/{dispute['id']}/resolve", {"refund": True, "note": "ok"})
    assert Order.objects.get(pk=first).payment_status == "REFUNDED"
    assert _on_hand(product) == (7, 0)
    assert not StockMovement.objects.filter(product=product, kind="RESTOCK").exists()
    # Return: approval does not restock; "items received" restocks; the refund does not again.
    second = _buy(buyer, baghdad, [(product.pk, None, 2)])["orders"][0]["id"]
    _fulfil_and_pay(client, buyer, finance, second)
    assert _on_hand(product) == (5, 0)
    item = OrderItem.objects.get(order_id=second, kind="MERCHANDISE")
    ret = _post(
        client_for(buyer), f"{ORDERS}/{second}/returns",
        {"reason": "Wrong model (demo)", "lines": [{"item": str(item.pk), "quantity": 2}]},
    )["returns"][0]  # fmt: skip
    _post(client, f"{MERCHANT}/returns/{ret['id']}/decide", {"approve": True})
    assert _on_hand(product) == (5, 0)
    _post(client, f"{MERCHANT}/returns/{ret['id']}/received")
    assert _on_hand(product) == (7, 0)
    _post(fin, f"{ADMIN}/returns/{ret['id']}/refund")
    assert _on_hand(product) == (7, 0)
    assert StockMovement.objects.filter(product=product, kind="RESTOCK").count() == 1
    # A paid order cancelled before shipping releases its reservation (never "restocks").
    third = _buy(buyer, baghdad, [(product.pk, None, 1)])["orders"][0]["id"]
    assert _on_hand(product) == (7, 1)
    _post(fin, f"{ADMIN}/orders/{third}/verify-payment", {"reference": "SIM-3"})
    _post(client_for(buyer), f"{ORDERS}/{third}/cancel")
    _post(fin, f"{ADMIN}/orders/{third}/refund-cancelled")
    assert _on_hand(product) == (7, 0)
    assert StockMovement.objects.filter(product=product, kind="RESTOCK").count() == 1
    assert reconciliation()["ok"]


# ---- item 8: advertising, preferences and channels are separate -------------------------------


def test_order_notifications_carry_no_buyer_contact_and_ads_respect_opt_out(
    company_factory,
    product_factory,
    category_factory,
    account_factory,
    baghdad,
    finance,
    django_capture_on_commit_callbacks,
):
    from apps.preferences import services as preferences

    shop = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    product = product_factory(
        shop, category_factory(consumer_allowed=True), price=D("10000"),
        sale_channel=SaleChannel.B2C, stock_quantity=5,
    )  # fmt: skip
    buyer = _verified(account_factory(role=AccountRole.PATIENT))
    preferences.update(buyer, {"offers_and_news": False, "channel_in_app": False})
    with django_capture_on_commit_callbacks(execute=True):
        order_id = _buy(buyer, baghdad, [(product.pk, None, 1)], phone="+964 770 111 2222")[
            "orders"
        ][0]["id"]
        _fulfil_and_pay(client_for(shop.account), buyer, finance, order_id)
    to_seller = Notification.objects.filter(recipient=shop.account)
    assert to_seller.exists()
    assert Notification.objects.filter(recipient=buyer, category="ORDER").exists()
    for n in to_seller:
        text = str(n.payload)
        assert "770" not in text and "Street" not in text and buyer.email not in text
    # Transactional order notifications reach the buyer even with marketing switched off.
    assert preferences.wants_in_app(buyer.pk, "sponsored_products") is False
    assert not Notification.objects.filter(recipient=buyer, category="MARKETING").exists()


def test_an_expired_licence_stops_the_store_after_the_daily_refresh(
    company_factory, category_factory, product_factory
):
    from django.core.management import call_command

    store = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    doc = _approved(store)
    sellers.refresh_documents_complete(store.pk)
    store.refresh_from_db()
    assert store.can_sell
    SellerDocument.objects.filter(pk=doc.pk).update(
        expires_on=timezone.localdate() - timedelta(days=1)
    )
    assert store.missing_documents() == ["COMMERCIAL_REGISTRATION"]
    call_command("refresh_seller_documents")
    store.refresh_from_db()
    assert not store.documents_complete and not store.can_sell
