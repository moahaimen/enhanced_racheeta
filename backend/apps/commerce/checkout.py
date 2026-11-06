"""Multi-vendor checkout: one buyer action -> one Checkout -> one Order per seller.

Fail closed (docs/MARKETPLACE_COMMERCE.md §Eligibility): a line is purchasable only when the
product, its category's compliance class, its seller and the buyer all qualify RIGHT NOW.
Nothing the client sends (seller, price, discount, fee, status) is trusted.
"""

from __future__ import annotations

import secrets
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.ledger.posting import current_policy
from apps.marketplace.models import Product
from apps.marketplace.permissions import current_verified_provider
from apps.marketplace.types import (
    NOT_PURCHASABLE_CLASSES,
    PROFESSIONAL_CHANNELS,
    CompanyVerificationStatus,
    ComplianceClass,
)
from apps.notifications.types import NotificationEventType, NotificationResourceType

from . import inventory
from .errors import CommerceError
from .models import Checkout, Coupon, CouponRedemption, Order, OrderItem, OrderTransition
from .pricing import PricedLine, PricingError, price
from .types import MAX_LINES, MAX_QUANTITY_PER_LINE, OrderStatus, PaymentMethod

BUYER_ROLES = frozenset({AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.REAL_ESTATE_SELLER})
CURRENCY = "IQD"


class CheckoutError(CommerceError):
    code = "invalid_cart"


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
    if (
        company.verification_status != CompanyVerificationStatus.VERIFIED
        or not company.account.is_active
        or company.account.role != AccountRole.MEDICAL_COMPANY
    ):
        raise CheckoutError(
            f"The seller of “{product.title}” cannot sell right now.", "not_allowed"
        )
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
    if product.sale_channel in PROFESSIONAL_CHANNELS and category.compliance_class in (
        ComplianceClass.B2B_VERIFIED_ONLY,
        ComplianceClass.B2C_ALLOWED,
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
    raise CheckoutError(f"“{product.title}” is not available.")


def _wanted(items: list[dict]) -> dict:
    if not items or len(items) > MAX_LINES:
        raise CheckoutError(f"An order has between 1 and {MAX_LINES} lines.")
    wanted: dict = {}
    for line in items:
        qty = int(line["quantity"])
        if not 1 <= qty <= MAX_QUANTITY_PER_LINE:
            raise CheckoutError(f"Quantity must be between 1 and {MAX_QUANTITY_PER_LINE}.")
        wanted[line["product"]] = wanted.get(line["product"], 0) + qty
        if wanted[line["product"]] > MAX_QUANTITY_PER_LINE:
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


def _priced(buyer, items, codes, *, lock: bool):
    check_buyer(buyer)
    wanted = _wanted(items)
    qs = Product.objects.filter(pk__in=list(wanted)).select_related(
        "company", "company__account", "category"
    )
    if lock:
        qs = qs.select_for_update(of=("self",))
    products = list(qs.order_by("pk"))
    if len(products) != len(wanted):
        raise CheckoutError("Some products are not available.")
    policy = current_policy()
    lines = []
    for product in products:
        channel = purchase_channel(product, buyer)
        if product.price is None:
            raise CheckoutError(
                f"“{product.title}” has no price; request a quotation.", "quote_only"
            )
        if product.currency != CURRENCY:
            raise CheckoutError("Only Iraqi dinar prices can be ordered.", "currency_not_supported")
        qty = wanted[product.pk]
        left = inventory.available(product)
        if left is not None and left < qty:
            raise CheckoutError(f"Not enough stock for “{product.title}”.", "out_of_stock")
        lines.append(
            PricedLine(
                product=product,
                quantity=qty,
                unit_price=product.price,
                line_total=Decimal("0"),
                commission_rate=policy.rate_percent,
                channel=channel,
            )
        )
    try:
        priced = price(lines, _coupons(codes, lock=lock), buyer=buyer)
    except PricingError as exc:
        raise CheckoutError(str(exc), exc.code) from exc
    return priced, policy


def preview(buyer, *, items: list[dict], coupons: list[str]):
    priced, policy = _priced(buyer, items, coupons, lock=False)
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
    """Returns (checkout, created). A repeated key returns the first checkout unchanged."""
    if payment_method not in PaymentMethod.values:
        raise CheckoutError("Choose cash on delivery or manual transfer.")
    key = (idempotency_key or "").strip()[:64]
    if not key:
        raise CheckoutError("Missing idempotency key.")
    existing = Checkout.objects.filter(buyer=buyer, idempotency_key=key).first()
    if existing is not None:
        return existing, False
    priced, policy = _priced(buyer, items, coupons, lock=True)
    return persist(buyer, priced, policy, delivery=delivery, payment_method=payment_method, key=key)


def persist(buyer, priced, policy, *, delivery, payment_method, key, quote=None):
    """Write the checkout, its per-seller orders, line snapshots, reservations and coupon uses.
    Callers hold row locks on every product and coupon involved."""
    try:
        with transaction.atomic():
            checkout = Checkout.objects.create(
                number=_number("CHK"),
                buyer=buyer,
                idempotency_key=key,
                currency=CURRENCY,
                list_total=priced.total("line_total"),
                seller_discount_total=priced.total("seller_discount"),
                platform_discount_total=priced.total("platform_discount"),
                total=priced.total("buyer_paid"),
            )
    except IntegrityError:  # the same key raced in on another connection
        return Checkout.objects.get(buyer=buyer, idempotency_key=key), False
    now = timezone.now()
    for priced_order in priced.orders:
        order = Order.objects.create(
            number=_number("RCH"),
            checkout=checkout,
            channel=priced_order.channel,
            buyer=buyer,
            merchant=priced_order.company,
            payment_method=payment_method,
            total=priced_order.total("buyer_paid"),
            currency=CURRENCY,
            list_total=priced_order.total("line_total"),
            seller_discount_total=priced_order.total("seller_discount"),
            platform_discount_total=priced_order.total("platform_discount"),
            merchandise_net=priced_order.total("merchandise_net"),
            commission_total=priced_order.total("commission"),
            seller_payable_total=priced_order.total("seller_payable"),
            commission_rate=policy.rate_percent,
            commission_policy_version=policy.version,
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
            OrderItem.objects.create(
                order=order,
                product=line.product,
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
                stock_tracked=line.product.stock_quantity is not None,
            )
            try:
                inventory.reserve(line.product, line.quantity, order=order, actor=buyer)
            except inventory.NotEnoughStock as exc:
                raise CheckoutError(str(exc), "out_of_stock") from exc
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
