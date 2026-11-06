"""Server-side pricing of a cart (docs/MARKETPLACE_COMMERCE.md §Pricing). Never trusts the client.

Per line (whole Iraqi dinars, Decimal, ROUND_HALF_UP):
    line_total        = unit_price x quantity
    seller_discount   = product offer (seller-funded %) + share of a SELLER coupon
    merchandise_net   = line_total - seller_discount            <- commission base
    platform_discount = share of a PLATFORM coupon (paid by Racheeta, not by the seller)
    buyer_paid        = merchandise_net - platform_discount
    commission        = round(merchandise_net x policy rate)     <- 20%
    seller_payable    = merchandise_net - commission
Coupon discounts are allocated to lines in proportion to their value with the largest-remainder
method (deterministic: ties go to the earlier line), so line amounts always add up exactly.
Stacking: at most one seller coupon per seller order and one platform coupon per checkout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from apps.ledger.posting import commission_of, dinars

from .models import Coupon, CouponRedemption, ProductOffer
from .types import CouponFunding, DiscountKind

ZERO = Decimal("0")


class PricingError(Exception):
    code = "invalid_coupon"

    def __init__(self, message: str, code: str = "invalid_coupon"):
        super().__init__(message)
        self.code = code


@dataclass
class PricedLine:
    product: object
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    offer_discount: Decimal = ZERO
    seller_coupon_discount: Decimal = ZERO
    platform_discount: Decimal = ZERO
    commission_rate: Decimal = ZERO
    channel: str = "B2C"

    @property
    def seller_discount(self) -> Decimal:
        return self.offer_discount + self.seller_coupon_discount

    @property
    def merchandise_net(self) -> Decimal:
        return self.line_total - self.seller_discount

    @property
    def buyer_paid(self) -> Decimal:
        return self.merchandise_net - self.platform_discount

    @property
    def commission(self) -> Decimal:
        return commission_of(self.merchandise_net, self.commission_rate)

    @property
    def seller_payable(self) -> Decimal:
        return self.merchandise_net - self.commission


@dataclass
class PricedOrder:
    company: object
    lines: list[PricedLine] = field(default_factory=list)
    seller_coupon: Coupon | None = None

    def total(self, attr: str) -> Decimal:
        return sum((getattr(line, attr) for line in self.lines), ZERO)

    @property
    def channel(self) -> str:
        return "B2B" if any(line.channel == "B2B" for line in self.lines) else "B2C"


@dataclass
class PricedCheckout:
    orders: list[PricedOrder]
    platform_coupon: Coupon | None = None

    def total(self, attr: str) -> Decimal:
        return sum((o.total(attr) for o in self.orders), ZERO)


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split whole-dinar `total` across `weights` proportionally; parts sum exactly to `total`."""
    total = dinars(total)
    weight_sum = sum(weights, ZERO)
    if total <= 0 or weight_sum <= 0:
        return [ZERO for _ in weights]
    raw = [total * w / weight_sum for w in weights]
    floors = [Decimal(int(r)) for r in raw]
    remainder = int(total - sum(floors, ZERO))
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def best_offer_percent(product, now) -> Decimal:
    offer = (
        ProductOffer.objects.filter(
            product=product, is_active=True, starts_at__lte=now, ends_at__gt=now
        )
        .order_by("-percent")
        .first()
    )
    return offer.percent if offer else ZERO


def _coupon_discount(coupon: Coupon, base: Decimal) -> Decimal:
    if base < coupon.min_subtotal:
        raise PricingError(
            f"Coupon {coupon.code} needs a subtotal of at least {coupon.min_subtotal}."
        )
    if coupon.kind == DiscountKind.PERCENT:
        amount = dinars(base * coupon.value / Decimal("100"))
        if coupon.max_discount is not None:
            amount = min(amount, dinars(coupon.max_discount))
    else:
        amount = dinars(coupon.value)
    return min(amount, base)


def _check_usable(coupon: Coupon, buyer, now) -> None:
    if not coupon.is_active or not (coupon.starts_at <= now < coupon.ends_at):
        raise PricingError(f"Coupon {coupon.code} is not valid now.")
    if coupon.max_redemptions is not None and coupon.redemptions >= coupon.max_redemptions:
        raise PricingError(f"Coupon {coupon.code} has been fully used.")
    if CouponRedemption.objects.filter(coupon=coupon, buyer=buyer, released=False).exists():
        raise PricingError(f"You have already used coupon {coupon.code}.")


def price(lines: list[PricedLine], coupons: list[Coupon], *, buyer, now=None) -> PricedCheckout:
    """`lines` carry locked products, quantities, unit prices, channel and the policy rate."""
    now = now or timezone.now()
    by_company: dict = {}
    for line in lines:
        line.line_total = dinars(line.unit_price * line.quantity)
        pct = best_offer_percent(line.product, now)
        line.offer_discount = dinars(line.line_total * pct / Decimal("100")) if pct else ZERO
        by_company.setdefault(line.product.company_id, PricedOrder(company=line.product.company))
        by_company[line.product.company_id].lines.append(line)
    orders = list(by_company.values())

    platform = [c for c in coupons if c.funded_by == CouponFunding.PLATFORM]
    seller = [c for c in coupons if c.funded_by == CouponFunding.SELLER]
    if len(platform) > 1:
        raise PricingError("Only one Racheeta coupon can be used per order.", "coupon_stacking")
    for coupon in coupons:
        _check_usable(coupon, buyer, now)

    for coupon in seller:
        order = by_company.get(coupon.company_id)
        if order is None:
            raise PricingError(f"Coupon {coupon.code} does not apply to the items in your cart.")
        if order.seller_coupon is not None:
            raise PricingError("Only one store coupon per store order.", "coupon_stacking")
        order.seller_coupon = coupon
        weights = [line.line_total - line.offer_discount for line in order.lines]
        amount = _coupon_discount(coupon, sum(weights, ZERO))
        for line, part in zip(order.lines, allocate(amount, weights), strict=True):
            line.seller_coupon_discount = part

    checkout = PricedCheckout(orders=orders, platform_coupon=platform[0] if platform else None)
    if checkout.platform_coupon is not None:
        every = [line for order in orders for line in order.lines]
        weights = [line.merchandise_net for line in every]
        amount = _coupon_discount(checkout.platform_coupon, sum(weights, ZERO))
        for line, part in zip(every, allocate(amount, weights), strict=True):
            line.platform_discount = part
    return checkout
