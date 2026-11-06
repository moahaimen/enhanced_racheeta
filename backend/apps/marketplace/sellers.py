"""Seller onboarding and store management (docs/MARKETPLACE_COMMERCE.md §Sellers).

* A pharmacy opens its store FROM its pharmacy provider profile: the account keeps its PROVIDER
  role, its facility workspace and its healthcare identity. The store is a MedicalCompany row
  linked to that facility (business type PHARMACY), so staff, permissions, orders and the ledger
  work exactly as for any other seller.
* Verification documents are uploaded by the owner (or a MANAGER), reviewed by Racheeta.
* Store activation is the seller's own step, allowed only when Racheeta has verified the business
  and every required document is approved. Pausing is always allowed.
* Tax treatment and delivery fees are seller-declared settings, bounded and audited.
* Variants and photos belong to products of the acting business only.
Every change is decided on locked rows and audited.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType

from . import uploads
from .models import (
    MedicalCompany,
    Product,
    ProductImage,
    ProductVariant,
    SellerDocument,
    ShippingRate,
)
from .services import (
    AlreadyExists,
    InvalidTransition,
    MarketplaceError,
    ProductNotFound,
    _sku_taken,
    create_company,
)
from .types import (
    MAX_TAX_RATE,
    BusinessType,
    CompanyVerificationStatus,
    DocumentStatus,
    SellerDocumentKind,
    StoreStatus,
    TaxMode,
)

MAX_IMAGES_PER_PRODUCT = 8
MAX_VARIANTS_PER_PRODUCT = 30
MAX_DOCUMENTS_PER_COMPANY = 30


class SellerError(MarketplaceError):
    code = "invalid"

    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _lock_company(company_id) -> MedicalCompany:
    return (
        MedicalCompany.objects.select_for_update(of=("self",))
        .select_related("account", "facility")
        .get(pk=company_id)
    )


# ---- pharmacy store -------------------------------------------------------------------------


@transaction.atomic
def open_pharmacy_store(account, fields: dict) -> MedicalCompany:
    """A PROVIDER account whose own profile is a PHARMACY opens its store (it stays a provider)."""
    facility = (
        ProviderProfile.objects.select_for_update()
        .filter(account_id=account.pk, provider_type=ProviderType.PHARMACY)
        .first()
    )
    if facility is None:
        raise SellerError(
            "Only a pharmacy provider profile can open a pharmacy store.", "not_allowed"
        )
    if MedicalCompany.objects.filter(account_id=account.pk).exists():
        raise AlreadyExists("You already have a store.")
    values = {
        "name": (fields.get("name") or facility.display_name).strip()[:150],
        "business_type": BusinessType.PHARMACY,
        "description": fields.get("description", ""),
        "phone": fields.get("phone") or getattr(facility, "phone", "") or "",
        "public_email": fields.get("public_email", ""),
        "website": fields.get("website", ""),
        "governorate": fields.get("governorate") or facility.governorate,
        "city": fields.get("city") if "city" in fields else getattr(facility, "city", None),
        "address": fields.get("address") or getattr(facility, "address", "") or "",
    }
    company = create_company(account, values, facility=facility)
    audit.record(
        actor=account,
        action="marketplace.pharmacy_store.opened",
        target=company,
        summary=company.name,
        data={"facility": str(facility.pk)},
    )
    return company


# ---- store activation -----------------------------------------------------------------------


@transaction.atomic
def set_store_status(company_id, *, actor, active: bool) -> MedicalCompany:
    company = _lock_company(company_id)
    if active:
        if company.verification_status != CompanyVerificationStatus.VERIFIED:
            raise SellerError(
                "Racheeta must verify your business before the store can be activated.",
                "company_not_verified",
            )
        if not company.can_publish:
            raise SellerError(
                "This store cannot sell: the seller account (or the pharmacy's verification) "
                "is not in good standing.",
                "not_allowed",
            )
        missing = company.missing_documents()
        if missing:
            raise SellerError(
                "Some required documents are not approved yet: " + ", ".join(missing),
                "documents_missing",
            )
        target = StoreStatus.ACTIVE
    else:
        if company.store_status != StoreStatus.ACTIVE:
            raise InvalidTransition("The store is not active.")
        target = StoreStatus.PAUSED
    if company.store_status == target:
        return company
    previous = company.store_status
    company.store_status = target
    company.store_status_changed_at = timezone.now()
    company.save(update_fields=["store_status", "store_status_changed_at", "updated_at"])
    audit.record(
        actor=actor,
        action="marketplace.store.status_changed",
        target=company,
        summary=f"{previous} -> {target}",
        data={"from": previous, "to": target},
    )
    return company


# ---- documents ------------------------------------------------------------------------------


@transaction.atomic
def upload_document(company_id, *, actor, kind: str, upload, reference_number="", expires_on=None):
    if kind not in SellerDocumentKind.values:
        raise SellerError("Choose the type of document.")
    company = _lock_company(company_id)
    if company.documents.count() >= MAX_DOCUMENTS_PER_COMPANY:
        raise SellerError("Too many documents; remove an old one first.")
    if expires_on is not None and expires_on <= timezone.localdate():
        raise SellerError("This document has already expired.")
    checked = uploads.check_document(upload)
    doc = SellerDocument.objects.create(
        company=company,
        kind=kind,
        file=checked.content,
        original_name=checked.original_name,
        content_type=checked.content_type,
        size=checked.size,
        sha256=checked.sha256,
        reference_number=(reference_number or "").strip()[:60],
        expires_on=expires_on,
        uploaded_by=actor,
    )
    audit.record(
        actor=actor,
        action="marketplace.document.uploaded",
        target=doc,
        summary=f"{company.name}: {kind}",
        data={"sha256": checked.sha256, "size": checked.size},
    )
    return doc


@transaction.atomic
def withdraw_document(document_id, *, company_id, actor) -> None:
    doc = (
        SellerDocument.objects.select_for_update()
        .filter(pk=document_id, company_id=company_id)
        .first()
    )
    if doc is None:
        raise ProductNotFound("Document not found.")
    if doc.status == DocumentStatus.APPROVED:
        raise SellerError("An approved document cannot be removed; upload a newer one instead.")
    audit.record(actor=actor, action="marketplace.document.withdrawn", target=doc, summary=doc.kind)
    doc.file.delete(save=False)
    doc.delete()


@transaction.atomic
def review_document(document_id, *, admin, approve: bool, note: str = "") -> SellerDocument:
    """Racheeta administrator decision. Rejecting a document of an ACTIVE store whose type needs
    it pauses nothing automatically; the administrator suspends the business if needed."""
    doc = SellerDocument.objects.select_for_update().filter(pk=document_id).first()
    if doc is None:
        raise ProductNotFound("Document not found.")
    note = (note or "").strip()
    if not approve and not note:
        raise SellerError("Tell the seller why the document is rejected.")
    doc.status = DocumentStatus.APPROVED if approve else DocumentStatus.REJECTED
    doc.review_note = note[:300]
    doc.reviewed_by, doc.reviewed_at = admin, timezone.now()
    doc.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
    audit.record(
        actor=admin,
        action="marketplace.document.reviewed",
        target=doc,
        summary=f"{doc.kind}: {doc.status}",
        data={"company": str(doc.company_id)},
    )
    return doc


# ---- tax and delivery settings --------------------------------------------------------------


def _money(value, field: str, *, allow_none=True) -> Decimal | None:
    if value in (None, ""):
        if allow_none:
            return None
        raise SellerError(f"{field} is required.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SellerError(f"{field} must be a number.") from exc
    if amount < 0 or amount != amount.to_integral_value() or amount > Decimal("10000000"):
        raise SellerError(f"{field} must be a whole number of dinars, zero or more.")
    return amount


@transaction.atomic
def update_store_settings(company_id, *, actor, data: dict) -> MedicalCompany:
    company = _lock_company(company_id)
    changed = {}
    if "tax_mode" in data or "tax_rate" in data:
        mode = data.get("tax_mode", company.tax_mode)
        if mode not in TaxMode.values:
            raise SellerError("Choose how your prices treat tax.")
        try:
            rate = Decimal(str(data.get("tax_rate", company.tax_rate) or 0))
        except (InvalidOperation, ValueError) as exc:
            raise SellerError("The tax rate must be a number.") from exc
        if mode == TaxMode.NONE:
            rate = Decimal("0")
        elif not (Decimal("0") < rate <= MAX_TAX_RATE) or rate != rate.quantize(Decimal("0.01")):
            raise SellerError(f"Enter a tax rate above 0 and at most {MAX_TAX_RATE}%.")
        changed.update(tax_mode=mode, tax_rate=rate)
    for key, limit in (("tax_label", 40), ("tax_registration_number", 40)):
        if key in data:
            changed[key] = (data.get(key) or "").strip()[:limit]
    if "default_shipping_fee" in data:
        changed["default_shipping_fee"] = _money(data["default_shipping_fee"], "Delivery fee")
    if "free_shipping_over" in data:
        changed["free_shipping_over"] = _money(data["free_shipping_over"], "Free delivery over")
    for key, value in changed.items():
        setattr(company, key, value)
    if changed:
        company.save(update_fields=[*changed, "updated_at"])
        audit.record(
            actor=actor,
            action="marketplace.store.settings_changed",
            target=company,
            summary=company.name,
            data={k: str(v) for k, v in changed.items()},
        )
    return company


@transaction.atomic
def set_shipping_rate(company_id, *, actor, governorate, fee, min_days=1, max_days=3, active=True):
    company = _lock_company(company_id)
    fee = _money(fee, "Delivery fee", allow_none=False)
    try:
        min_days, max_days = int(min_days), int(max_days)
    except (TypeError, ValueError) as exc:
        raise SellerError("Delivery days must be whole numbers.") from exc
    if not (0 <= min_days <= max_days <= 60):
        raise SellerError("Delivery days must be between 0 and 60, earliest first.")
    rate, _ = ShippingRate.objects.update_or_create(
        company=company,
        governorate=governorate,
        defaults={
            "fee": fee,
            "min_days": min_days,
            "max_days": max_days,
            "is_active": bool(active),
        },
    )
    audit.record(
        actor=actor,
        action="marketplace.store.shipping_rate_set",
        target=company,
        summary=f"{governorate.slug}: {fee}",
    )
    return rate


@transaction.atomic
def delete_shipping_rate(rate_id, *, company_id, actor) -> None:
    deleted, _ = ShippingRate.objects.filter(pk=rate_id, company_id=company_id).delete()
    if not deleted:
        raise ProductNotFound("Delivery rate not found.")
    audit.record(
        actor=actor,
        action="marketplace.store.shipping_rate_deleted",
        target=_lock_company(company_id),
        summary=str(rate_id),
    )


def shipping_quote(company: MedicalCompany, governorate_id, merchandise_total: Decimal) -> dict:
    """The delivery fee this seller charges for an order to `governorate_id` (server-side).
    A seller with no delivery settings at all delivers free (the behaviour before fees existed).
    """
    rate = (
        ShippingRate.objects.filter(company=company, governorate_id=governorate_id, is_active=True)
        .only("fee", "min_days", "max_days")
        .first()
    )
    if rate is not None:
        fee, days = rate.fee, (rate.min_days, rate.max_days)
    elif company.default_shipping_fee is not None:
        fee, days = company.default_shipping_fee, (None, None)
    elif ShippingRate.objects.filter(company=company, is_active=True).exists():
        raise SellerError(f"{company.name} does not deliver to this governorate.", "no_delivery")
    else:
        fee, days = Decimal("0"), (None, None)
    if company.free_shipping_over is not None and merchandise_total >= company.free_shipping_over:
        fee = Decimal("0")
    return {"fee": fee, "min_days": days[0], "max_days": days[1]}


# ---- variants -------------------------------------------------------------------------------


def _locked_product(company_id, product_id) -> Product:
    product = (
        Product.objects.select_for_update(of=("self",))
        .filter(pk=product_id, company_id=company_id)
        .first()
    )
    if product is None:
        raise ProductNotFound("Product not found.")
    return product


def _variant_values(data: dict, *, partial: bool) -> dict:
    values = {}
    if "label" in data or not partial:
        label = (data.get("label") or "").strip()
        if not label:
            raise SellerError("Name the variant (for example: Size L).")
        values["label"] = label[:80]
    if "sku" in data or not partial:
        sku = (data.get("sku") or "").strip()
        if not sku:
            raise SellerError("Give the variant a SKU.")
        values["sku"] = sku[:64]
    if "price" in data:
        values["price"] = _money(data.get("price"), "Price")
    if "stock_quantity" in data:
        qty = data.get("stock_quantity")
        if qty not in (None, "") and (not isinstance(qty, int) or qty < 0 or qty > 1_000_000):
            raise SellerError("Stock is a whole number of units.")
        values["stock_quantity"] = None if qty in (None, "") else qty
    if "reorder_threshold" in data:
        th = data.get("reorder_threshold")
        if th not in (None, "") and (not isinstance(th, int) or th < 0):
            raise SellerError("The alert level is a whole number of units.")
        values["reorder_threshold"] = None if th in (None, "") else th
    if "is_active" in data:
        values["is_active"] = bool(data["is_active"])
    if "sort_order" in data:
        values["sort_order"] = max(0, min(int(data.get("sort_order") or 0), 999))
    return values


@transaction.atomic
def create_variant(company_id, product_id, *, actor, data: dict) -> ProductVariant:
    product = _locked_product(company_id, product_id)
    if product.variants.count() >= MAX_VARIANTS_PER_PRODUCT:
        raise SellerError(f"A product has at most {MAX_VARIANTS_PER_PRODUCT} variants.")
    values = _variant_values(data, partial=False)
    if _sku_taken(company_id, values["sku"]):
        raise SellerError(f"The SKU {values['sku']} is already used in your store.")
    if not product.variants.exists():
        # From now on stock lives on the variants. Units reserved for open orders stay on the
        # product until those orders ship or are cancelled.
        if product.stock_reserved:
            raise SellerError(
                "Finish or cancel the open orders of this product before adding variants."
            )
        if product.stock_quantity is not None:
            product.stock_quantity = None
            product.save(update_fields=["stock_quantity", "updated_at"])
    try:
        with transaction.atomic():
            variant = ProductVariant.objects.create(
                product=product, company_id=company_id, **values
            )
    except IntegrityError as exc:
        raise SellerError("A variant with this name or SKU already exists.") from exc
    if variant.stock_quantity:
        from apps.commerce.models import StockMovement
        from apps.commerce.types import StockMovementKind

        StockMovement.objects.create(
            product=product,
            variant=variant,
            kind=StockMovementKind.ADJUST,
            quantity=variant.stock_quantity,
            on_hand_after=variant.stock_quantity,
            reserved_after=0,
            actor=actor,
            reason="Opening stock of a new variant",
        )
    audit.record(
        actor=actor,
        action="marketplace.variant.created",
        target=variant,
        summary=f"{product.title}: {variant.label}",
        data={"sku": variant.sku},
    )
    return variant


@transaction.atomic
def update_variant(company_id, variant_id, *, actor, data: dict) -> ProductVariant:
    variant = (
        ProductVariant.objects.select_for_update(of=("self",))
        .select_related("product")
        .filter(pk=variant_id, company_id=company_id)
        .first()
    )
    if variant is None:
        raise ProductNotFound("Variant not found.")
    values = _variant_values(data, partial=True)
    if "stock_quantity" in values:
        # Stock changes go through the inventory adjustment (with a reason and a movement row).
        raise SellerError("Change stock with a stock adjustment (it records why).")
    if "sku" in values and _sku_taken(company_id, values["sku"], variant=variant):
        raise SellerError(f"The SKU {values['sku']} is already used in your store.")
    for key, value in values.items():
        setattr(variant, key, value)
    try:
        with transaction.atomic():
            variant.save()
    except IntegrityError as exc:
        raise SellerError("A variant with this name or SKU already exists.") from exc
    audit.record(
        actor=actor,
        action="marketplace.variant.updated",
        target=variant,
        summary=variant.label,
        data={"fields": sorted(values)},
    )
    return variant


# ---- photos ---------------------------------------------------------------------------------


@transaction.atomic
def add_image(company_id, product_id, *, actor, upload, alt_text: str = "") -> ProductImage:
    product = _locked_product(company_id, product_id)
    if product.images.count() >= MAX_IMAGES_PER_PRODUCT:
        raise SellerError(f"A product has at most {MAX_IMAGES_PER_PRODUCT} photos.")
    checked = uploads.check_image(upload)
    image = ProductImage.objects.create(
        product=product,
        file=checked.content,
        content_type=checked.content_type,
        size=checked.size,
        width=checked.width,
        height=checked.height,
        sha256=checked.sha256,
        alt_text=(alt_text or "").strip()[:150],
        sort_order=product.images.count(),
        uploaded_by=actor,
    )
    audit.record(
        actor=actor,
        action="marketplace.product_image.added",
        target=product,
        summary=product.title,
        data={"image": str(image.pk), "sha256": checked.sha256},
    )
    return image


@transaction.atomic
def remove_image(company_id, image_id, *, actor) -> None:
    image = (
        ProductImage.objects.select_for_update()
        .filter(pk=image_id, product__company_id=company_id)
        .first()
    )
    if image is None:
        raise ProductNotFound("Photo not found.")
    audit.record(
        actor=actor,
        action="marketplace.product_image.removed",
        target=image.product,
        summary=str(image.pk),
    )
    image.file.delete(save=False)
    image.delete()


def image_visible_to(image: ProductImage, account) -> bool:
    """Photos of a product someone may see: anyone for a product on sale (store or targeted
    catalogue, which already passed the publication gates), the business's own team otherwise."""
    from apps.workspaces import access

    product = image.product
    if (
        product.is_active
        and Product.objects.filter(pk=product.pk).filter(_public_product_q()).exists()
    ):
        return True
    if account is None or not account.is_authenticated:
        return False
    if account.is_staff:
        return True
    return access.can_company(account, product.company_id, "company.products.view")


def _public_product_q():
    from django.db.models import Q

    from .models import consumer_store_filter, selling_q

    return consumer_store_filter() | (Q(is_active=True) & selling_q("company__"))
