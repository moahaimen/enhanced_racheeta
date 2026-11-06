"""Multi-vendor checkout: one buyer action -> one Checkout -> one Order per seller.

Fail closed (docs/MARKETPLACE_COMMERCE.md §Eligibility): a line is purchasable only when the
product, its category's compliance class, its seller and the buyer all qualify RIGHT NOW.
Nothing the client sends (seller, price, discount, fee, status) is trusted.
"""

from __future__ import annotations

import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.ledger.posting import current_policy, dinars
from apps.marketplace.models import Product, ProductVariant
from apps.marketplace.permissions import current_verified_provider
from apps.marketplace.types import (
    NOT_PURCHASABLE_CLASSES,
    PROFESSIONAL_CHANNELS,
    ComplianceClass,
    TaxMode,
)
from apps.notifications.types import NotificationEventType, NotificationResourceType

from . import inventory
from .errors import CommerceError
from .models import Checkout, Coupon, CouponRedemption, Order, OrderItem, OrderTransition
from .pricing import PricedLine, PricingError, price
from .types import MAX_LINES, MAX_QUANTITY_PER_LINE, ItemKind, OrderStatus, PaymentMethod

BUYER_ROLES = frozenset({AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.REAL_ESTATE_SELLER})
CURRENCY = "IQD"


class CheckoutError(CommerceError):
    code = "invalid_cart"


def request_fingerprint(*, items, coupons, delivery: dict, payment_method: str, quote=None) -> str:
    """Canonical SHA-256 of what the buyer asked for (order of lines/coupons does not matter)."""
    import hashlib
    import json

    def ref(value):
        return str(getattr(value, "pk", value)) if value not in (None, "") else ""

    def line_key(key) -> str:  # products without a variant hash exactly as before variants
        product, variant = key
        return f"{product}:{variant}" if variant else str(product)

    canonical = {
        "items": sorted([line_key(k), int(v)] for k, v in _wanted(items).items()) if items else [],
        "coupons": sorted({(c or "").strip().upper() for c in coupons or [] if (c or "").strip()}),
        "payment_method": payment_method,
        "delivery": {
            "governorate": ref(delivery.get("governorate")),
            "city": ref(delivery.get("city")),
            "address": (delivery.get("address") or "").strip(),
            "phone": (delivery.get("phone") or "").strip(),
            "note": (delivery.get("note") or "").strip(),
            "latitude": ref(delivery.get("latitude")),
            "longitude": ref(delivery.get("longitude")),
        },
        "quote": ref(quote),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def replay(existing: Checkout, fingerprint: str) -> tuple[Checkout, bool]:
    """Same key again: the same request returns the first checkout; another request is refused."""
    if existing.request_hash and existing.request_hash != fingerprint:
        raise CheckoutError(
            "This request key was already used for a different order. Start a new checkout.",
            "idempotency_conflict",
        )
    return existing, False


def _number(prefix: str) -> str:
    return f"{prefix}-{timezone.localdate():%y%m%d}-{secrets.token_hex(3).upper()}"


def check_buyer(buyer) -> None:
    if not buyer.is_active or buyer.role not in BUYER_ROLES:
        raise CheckoutError("This account cannot buy in the marketplace.", "not_allowed")
    if not buyer.email_verified_at:
        raise CheckoutError("Verify your e-mail address before ordering.", "not_allowed")


def purchase_channel(product: Product, buyer) -> str:
    """'B2C' or 'B2B' when this buyer may buy this product now; raises otherwise (fail closed)."""
    company = product.company
    category = product.category
    if not product.is_active or not category.is_active:
        raise CheckoutError(f"“{product.title}” is not available.")
    if not company.can_sell:  # verified, active seller account, store ACTIVE (selling_q)
        raise CheckoutError(
            f"The seller of “{product.title}” cannot sell right now.", "not_allowed"
        )
    if category.allowed_business_types and company.business_type not in (
        category.allowed_business_types
    ):
        raise CheckoutError(f"“{product.title}” is not available.", "not_allowed")
    if product.is_restricted or category.compliance_class in NOT_PURCHASABLE_CLASSES:
        raise CheckoutError(
            f"“{product.title}” is a regulated item and cannot be bought online.", "not_purchasable"
        )
    if company.account_id == buyer.pk:
        raise CheckoutError("A business cannot buy from itself.", "not_allowed")
    if Product.objects.consumer_store().filter(pk=product.pk).exists():
        return "B2C"
    if category.compliance_class == ComplianceClass.QUOTE_ONLY:
        raise CheckoutError(f"“{product.title}” is sold by quotation only.", "quote_only")
    # Direct professional purchase needs an EXPLICIT B2B classification. B2C_ALLOWED is not
    # enough: legacy consumer categories (marketplace 0004) were only ever quote-able for B2B.
    if (
        product.sale_channel in PROFESSIONAL_CHANNELS
        and category.compliance_class == ComplianceClass.B2B_VERIFIED_ONLY
    ):
        provider = current_verified_provider(buyer)
        if (
            provider is not None
            and Product.objects.targeted_for(provider).filter(pk=product.pk).exists()
        ):
            return "B2B"
        raise CheckoutError(
            f"“{product.title}” is for verified healthcare professionals only.", "professional_only"
        )
    if product.sale_channel in PROFESSIONAL_CHANNELS:
        raise CheckoutError(f"“{product.title}” is sold by quotation only.", "quote_only")
    raise CheckoutError(f"“{product.title}” is not available.")


def _wanted(items: list[dict]) -> dict:
    """{(product id, variant id or None): quantity}; the same line twice is added up."""
    if not items or len(items) > MAX_LINES:
        raise CheckoutError(f"An order has between 1 and {MAX_LINES} lines.")
    wanted: dict = {}
    for line in items:
        qty = int(line["quantity"])
        if not 1 <= qty <= MAX_QUANTITY_PER_LINE:
            raise CheckoutError(f"Quantity must be between 1 and {MAX_QUANTITY_PER_LINE}.")
        key = (line["product"], line.get("variant") or None)
        wanted[key] = wanted.get(key, 0) + qty
        if wanted[key] > MAX_QUANTITY_PER_LINE:
            raise CheckoutError(f"Quantity must be between 1 and {MAX_QUANTITY_PER_LINE}.")
    return wanted


def _coupons(codes: list[str], *, lock: bool) -> list[Coupon]:
    codes = sorted({(c or "").strip().upper() for c in codes if (c or "").strip()})
    if len(codes) > 4:
        raise CheckoutError("Too many coupon codes.", "coupon_stacking")
    qs = Coupon.objects.filter(code__in=codes).order_by("pk")
    if lock:
        qs = qs.select_for_update()
    found = list(qs)
    missing = set(codes) - {c.code for c in found}
    if missing:
        raise CheckoutError(f"Unknown coupon {sorted(missing)[0]}.", "invalid_coupon")
    return found


def _variants(wanted: dict, *, lock: bool) -> dict:
    ids = sorted({str(v) for (_, v) in wanted if v})
    if not ids:
        return {}
    qs = ProductVariant.objects.filter(pk__in=ids)
    if lock:
        qs = qs.select_for_update(of=("self",))
    try:
        return {str(v.pk): v for v in qs.order_by("pk")}
    except ValidationError as exc:  # a malformed id is simply not available
        raise CheckoutError("Some products are not available.") from exc


def _priced(buyer, items, codes, *, lock: bool):
    check_buyer(buyer)
    wanted = _wanted(items)
    product_ids = sorted({str(p) for (p, _) in wanted})
    qs = Product.objects.filter(pk__in=product_ids).select_related(
        "company", "company__account", "company__facility", "category"
    )
    if lock:
        qs = qs.select_for_update(of=("self",))
    try:
        products = {str(p.pk): p for p in qs.order_by("pk")}
    except ValidationError as exc:
        raise CheckoutError("Some products are not available.") from exc
    if len(products) != len(product_ids):
        raise CheckoutError("Some products are not available.")
    variants = _variants(wanted, lock=lock)  # lock order: products, then variants (by id)
    variant_rows = ProductVariant.objects.filter(product_id__in=product_ids).values_list(
        "product_id", "is_active"
    )
    any_variants = {str(pk) for pk, _ in variant_rows}
    with_variants = {str(pk) for pk, active in variant_rows if active}
    policy = current_policy()
    lines, per_product = [], {}
    for (product_id, variant_id), qty in sorted(
        wanted.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))
    ):
        product = products[str(product_id)]
        channel = purchase_channel(product, buyer)
        variant = None
        if variant_id:
            variant = variants.get(str(variant_id))
            if variant is None or variant.product_id != product.pk or not variant.is_active:
                raise CheckoutError(f"This option of “{product.title}” is not available.")
            variant.product = product
        elif str(product.pk) in with_variants:
            raise CheckoutError(f"Choose an option of “{product.title}”.", "variant_required")
        elif str(product.pk) in any_variants:
            # Every option is hidden: the product's own stock is no longer kept, so it cannot be
            # sold as a single item (that would be untracked, i.e. unlimited, stock).
            raise CheckoutError(f"“{product.title}” is not available.")
        unit_price = variant.effective_price if variant is not None else product.price
        if unit_price is None:
            raise CheckoutError(
                f"“{product.title}” has no price; request a quotation.", "quote_only"
            )
        if product.currency != CURRENCY:
            raise CheckoutError("Only Iraqi dinar prices can be ordered.", "currency_not_supported")
        unit = variant if variant is not None else product
        left = inventory.available(unit)
        if left is not None and left < qty:
            raise CheckoutError(f"Not enough stock for “{unit.title}”.", "out_of_stock")
        per_product[product.pk] = per_product.get(product.pk, 0) + qty
        limit = product.category.max_order_quantity
        if limit is not None and per_product[product.pk] > limit:
            raise CheckoutError(
                f"At most {limit} of “{product.title}” per order.", "quantity_limit"
            )
        lines.append(
            PricedLine(
                product=product,
                quantity=qty,
                unit_price=unit_price,
                line_total=Decimal("0"),
                commission_rate=policy.rate_percent,
                channel=channel,
                variant=variant,
            )
        )
    try:
        priced = price(lines, _coupons(codes, lock=lock), buyer=buyer)
    except PricingError as exc:
        raise CheckoutError(str(exc), exc.code) from exc
    return priced, policy


def add_charges(priced, governorate_id) -> None:
    """Seller-declared pass-through charges, computed by the server: the delivery fee to the
    buyer's governorate and any tax the seller adds on top (EXCLUSIVE) or includes (INCLUSIVE,
    shown only). Charges are never part of the commission base. Without a governorate (a cart
    preview before the address is known) the delivery fee is left unknown."""
    from apps.marketplace.sellers import SellerError, shipping_quote

    for order in priced.orders:
        company = order.company
        if company.tax_mode == TaxMode.EXCLUSIVE and company.tax_rate > 0:
            for line in order.lines:
                line.tax = dinars(line.merchandise_net * company.tax_rate / Decimal("100"))
        elif company.tax_mode == TaxMode.INCLUSIVE and company.tax_rate > 0:
            for line in order.lines:
                net = line.merchandise_net
                line.tax_included = net - dinars(
                    net * Decimal("100") / (Decimal("100") + company.tax_rate)
                )
        if governorate_id is None:
            continue
        try:
            quote = shipping_quote(company, governorate_id, order.total("merchandise_net"))
        except SellerError as exc:
            raise CheckoutError(str(exc), exc.code) from exc
        order.shipping_fee = dinars(quote["fee"])
        order.shipping_days = (quote["min_days"], quote["max_days"])
        order.shipping_known = True


def preview(buyer, *, items: list[dict], coupons: list[str], governorate=None):
    priced, policy = _priced(buyer, items, coupons, lock=False)
    add_charges(priced, getattr(governorate, "pk", governorate))
    return priced, policy


@transaction.atomic
def place(
    buyer,
    *,
    items: list[dict],
    coupons: list[str],
    delivery: dict,
    payment_method: str,
    idempotency_key: str,
) -> tuple[Checkout, bool]:
    """Returns (checkout, created). A repeated key with the SAME request returns the first checkout
    unchanged; a repeated key with a different request is refused (idempotency_conflict)."""
    if payment_method not in PaymentMethod.values:
        raise CheckoutError("Choose cash on delivery or manual transfer.")
    key = (idempotency_key or "").strip()[:64]
    if not key:
        raise CheckoutError("Missing idempotency key.")
    fingerprint = request_fingerprint(
        items=items, coupons=coupons, delivery=delivery, payment_method=payment_method
    )
    existing = Checkout.objects.filter(buyer=buyer, idempotency_key=key).first()
    if existing is not None:
        return replay(existing, fingerprint)
    priced, policy = _priced(buyer, items, coupons, lock=True)
    add_charges(priced, getattr(delivery["governorate"], "pk", delivery["governorate"]))
    return persist(
        buyer,
        priced,
        policy,
        delivery=delivery,
        payment_method=payment_method,
        key=key,
        fingerprint=fingerprint,
    )


def persist(buyer, priced, policy, *, delivery, payment_method, key, fingerprint, quote=None):
    """Write the checkout, its per-seller orders, line snapshots, reservations and coupon uses.
    Callers hold row locks on every product and coupon involved."""
    try:
        with transaction.atomic():
            checkout = Checkout.objects.create(
                number=_number("CHK"),
                buyer=buyer,
                idempotency_key=key,
                request_hash=fingerprint,
                currency=CURRENCY,
                list_total=priced.total("line_total"),
                seller_discount_total=priced.total("seller_discount"),
                platform_discount_total=priced.total("platform_discount"),
                shipping_total=priced.sum_of("shipping_fee"),
                tax_total=priced.sum_of("tax_total"),
                total=priced.sum_of("grand_total"),
            )
    except IntegrityError:  # the same key raced in on another connection
        return replay(Checkout.objects.get(buyer=buyer, idempotency_key=key), fingerprint)
    now = timezone.now()
    for priced_order in priced.orders:
        company = priced_order.company
        charges = priced_order.shipping_fee + priced_order.tax_total
        order = Order.objects.create(
            number=_number("RCH"),
            checkout=checkout,
            channel=priced_order.channel,
            buyer=buyer,
            merchant=company,
            payment_method=payment_method,
            total=priced_order.grand_total,
            currency=CURRENCY,
            list_total=priced_order.total("line_total"),
            seller_discount_total=priced_order.total("seller_discount"),
            platform_discount_total=priced_order.total("platform_discount"),
            merchandise_net=priced_order.total("merchandise_net"),
            commission_total=priced_order.total("commission"),
            seller_payable_total=priced_order.total("seller_payable") + charges,
            commission_rate=policy.rate_percent,
            commission_policy_version=policy.version,
            shipping_total=priced_order.shipping_fee,
            shipping_min_days=priced_order.shipping_days[0],
            shipping_max_days=priced_order.shipping_days[1],
            tax_mode=company.tax_mode,
            tax_rate=company.tax_rate,
            tax_label=company.tax_label,
            tax_registration_number=company.tax_registration_number,
            tax_total=priced_order.tax_total,
            tax_included_total=priced_order.total("tax_included"),
            delivery_governorate=delivery["governorate"],
            delivery_city=delivery.get("city"),
            delivery_address=delivery["address"].strip(),
            delivery_latitude=delivery.get("latitude"),
            delivery_longitude=delivery.get("longitude"),
            contact_phone=delivery["phone"].strip(),
            note=delivery.get("note", "").strip(),
            status_changed_at=now,
            quote=quote,
        )
        for line in priced_order.lines:
            unit = line.stock_unit
            item = OrderItem.objects.create(
                order=order,
                product=line.product,
                variant=line.variant,
                sku_snapshot=(line.variant.sku if line.variant is not None else line.product.sku),
                variant_label_snapshot=line.variant.label if line.variant is not None else "",
                title_snapshot=line.product.title,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
                seller_discount=line.seller_discount,
                platform_discount=line.platform_discount,
                merchandise_net=line.merchandise_net,
                buyer_paid=line.buyer_paid,
                commission_rate=line.commission_rate,
                commission=line.commission,
                seller_payable=line.seller_payable,
                stock_tracked=unit.stock_quantity is not None,
            )
            if line.tax:
                _charge(
                    order,
                    ItemKind.TAX,
                    line.tax,
                    title=order.tax_label or "Tax",
                    parent=item,
                    quantity=line.quantity,
                )
            try:
                inventory.reserve(unit, line.quantity, order=order, actor=buyer)
            except inventory.NotEnoughStock as exc:
                raise CheckoutError(str(exc), "out_of_stock") from exc
        if priced_order.shipping_fee:
            _charge(order, ItemKind.SHIPPING, priced_order.shipping_fee, title="Delivery")
        if priced_order.seller_coupon is not None:
            _redeem(priced_order.seller_coupon, order, buyer, priced_order.total("seller_discount"))
        OrderTransition.objects.create(order=order, actor=buyer, to_status=OrderStatus.PLACED)
        audit.record(
            actor=buyer,
            action="commerce.order.placed",
            target=order,
            summary=order.number,
            data={
                "checkout": checkout.number,
                "lines": len(priced_order.lines),
                "total": str(order.total),
                "commission": str(order.commission_total),
            },
        )
        notify(
            order.merchant.account_id,
            NotificationEventType.ORDER_PLACED,
            order,
            "placed",
            {"order_number": order.number, "status": OrderStatus.PLACED},
        )
    if priced.platform_coupon is not None:
        first = checkout.orders.order_by("created_at").first()
        _redeem(priced.platform_coupon, first, buyer, priced.total("platform_discount"))
    return checkout, True


def _charge(order: Order, kind: str, amount: Decimal, *, title: str, parent=None, quantity=1):
    """A pass-through line: the buyer pays it, the seller receives all of it, no commission.
    A TAX line has the merchandise line's quantity, so it is refunded unit by unit with it."""
    return OrderItem.objects.create(
        order=order,
        kind=kind,
        parent_item=parent,
        title_snapshot=title[:150],
        unit_price=(amount / quantity).quantize(Decimal("0.01")),
        quantity=quantity,
        line_total=amount,
        seller_discount=Decimal("0"),
        platform_discount=Decimal("0"),
        merchandise_net=amount,
        buyer_paid=amount,
        commission_rate=Decimal("0"),
        commission=Decimal("0"),
        seller_payable=amount,
        stock_tracked=False,
    )


def _redeem(coupon: Coupon, order: Order, buyer, amount: Decimal) -> None:
    """Coupon row is locked (checkout locks coupons); the redemption cap is re-checked here."""
    if coupon.max_redemptions is not None and coupon.redemptions >= coupon.max_redemptions:
        raise CheckoutError(f"Coupon {coupon.code} has been fully used.", "invalid_coupon")
    try:
        with transaction.atomic():
            CouponRedemption.objects.create(coupon=coupon, order=order, buyer=buyer, amount=amount)
    except IntegrityError as exc:
        raise CheckoutError(
            f"You have already used coupon {coupon.code}.", "invalid_coupon"
        ) from exc
    Coupon.objects.filter(pk=coupon.pk).update(redemptions=coupon.redemptions + 1)
    coupon.redemptions += 1


def release_coupons(order: Order) -> None:
    """A cancelled order gives its coupon uses back (each once)."""
    for use in CouponRedemption.objects.select_for_update().filter(order=order, released=False):
        use.released = True
        use.save(update_fields=["released", "updated_at"])
        coupon = Coupon.objects.select_for_update().get(pk=use.coupon_id)
        if coupon.redemptions > 0:
            coupon.redemptions -= 1
            coupon.save(update_fields=["redemptions", "updated_at"])


def notify(recipient_id, event, order: Order, suffix: str, payload: dict) -> None:
    from apps.notifications import services as notifications
    from apps.notifications.types import NotificationCategory

    order_id = order.pk
    transaction.on_commit(
        lambda: notifications.create_notification(
            recipient_id=recipient_id,
            category=NotificationCategory.ORDER,
            event_type=event,
            dedupe_key=f"order:{order_id}:{suffix}:{recipient_id}",
            payload=payload,
            resource_type=NotificationResourceType.ORDER,
            resource_id=order_id,
        ),
        robust=True,
    )
