"""Coupons and product offers (docs/MARKETPLACE_COMMERCE.md §Discounts).

* SELLER coupons and product offers are created by the seller (capability company.offers.manage)
  and reduce that seller's merchandise value — and therefore Racheeta's 20% commission base;
* PLATFORM coupons are created only by Racheeta finance and are paid by Racheeta: the seller's
  merchandise value, commission and payable are unchanged.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.marketplace.models import Product

from .errors import CommerceError
from .models import Coupon, ProductOffer
from .types import CouponFunding, DiscountKind

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")
MAX_PERCENT = Decimal("90")


class PromotionError(CommerceError):
    code = "invalid_promotion"


def _window(starts_at, ends_at):
    starts_at = starts_at or timezone.now()
    if ends_at is None or ends_at <= starts_at:
        raise PromotionError("The end date must be after the start date.")
    if ends_at <= timezone.now():
        raise PromotionError("The end date must be in the future.")
    return starts_at, ends_at


def _whole(value) -> Decimal:
    value = Decimal(value)
    if value != value.to_integral_value():
        raise PromotionError("Amounts are whole Iraqi dinars.")
    return value


@transaction.atomic
def create_coupon(
    *,
    actor,
    funded_by: str,
    company=None,
    code: str,
    kind: str,
    value,
    max_discount=None,
    min_subtotal=0,
    starts_at=None,
    ends_at=None,
    max_redemptions=None,
) -> Coupon:
    code = (code or "").strip().upper()
    if not CODE_RE.match(code):
        raise PromotionError("Codes use 3–32 letters, digits or dashes.")
    if funded_by == CouponFunding.SELLER and company is None:
        raise PromotionError("A store coupon belongs to a store.")
    if funded_by == CouponFunding.PLATFORM and company is not None:
        raise PromotionError("A Racheeta coupon does not belong to a store.")
    value = Decimal(value)
    if kind == DiscountKind.PERCENT:
        if not Decimal("0") < value <= MAX_PERCENT:
            raise PromotionError("A percentage is between 1 and 90.")
    elif kind == DiscountKind.FIXED:
        value = _whole(value)
        if value <= 0:
            raise PromotionError("The discount must be more than zero.")
    else:
        raise PromotionError("Choose a percentage or a fixed amount.")
    if max_discount is not None:
        max_discount = _whole(max_discount)
        if max_discount <= 0:
            raise PromotionError("The maximum discount must be more than zero.")
    min_subtotal = _whole(min_subtotal or 0)
    if min_subtotal < 0:
        raise PromotionError("The minimum order cannot be negative.")
    if max_redemptions is not None and int(max_redemptions) < 1:
        raise PromotionError("Allow at least one use.")
    starts_at, ends_at = _window(starts_at, ends_at)
    try:
        with transaction.atomic():
            coupon = Coupon.objects.create(
                code=code,
                funded_by=funded_by,
                company=company,
                kind=kind,
                value=value,
                max_discount=max_discount,
                min_subtotal=min_subtotal,
                starts_at=starts_at,
                ends_at=ends_at,
                max_redemptions=max_redemptions,
                created_by=actor,
            )
    except IntegrityError as exc:
        raise PromotionError("This code is already used.", "already_exists") from exc
    audit.record(actor=actor, action="commerce.coupon.created", target=coupon, summary=code)
    return coupon


@transaction.atomic
def deactivate_coupon(coupon_id, *, actor, company_id=None) -> Coupon:
    scope = {"company_id": company_id} if company_id else {"funded_by": CouponFunding.PLATFORM}
    coupon = Coupon.objects.select_for_update().filter(pk=coupon_id, **scope).first()
    if coupon is None:
        raise PromotionError("Coupon not found.", "not_found")
    if coupon.is_active:
        coupon.is_active = False
        coupon.save(update_fields=["is_active", "updated_at"])
        audit.record(
            actor=actor, action="commerce.coupon.deactivated", target=coupon, summary=coupon.code
        )
    return coupon


@transaction.atomic
def create_offer(*, actor, company, product_id, percent, starts_at=None, ends_at=None):
    product = Product.objects.filter(pk=product_id, company=company).first()
    if product is None:
        raise PromotionError("Product not found.", "not_found")
    percent = Decimal(percent)
    if not Decimal("0") < percent <= MAX_PERCENT:
        raise PromotionError("A sale is between 1% and 90% off.")
    starts_at, ends_at = _window(starts_at, ends_at)
    offer = ProductOffer.objects.create(
        company=company,
        product=product,
        percent=percent,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=actor,
    )
    audit.record(
        actor=actor,
        action="commerce.offer.created",
        target=offer,
        summary=f"{product.title}: {percent}%",
    )
    return offer


@transaction.atomic
def deactivate_offer(offer_id, *, actor, company_id) -> ProductOffer:
    offer = ProductOffer.objects.select_for_update().filter(pk=offer_id, company_id=company_id)
    offer = offer.first()
    if offer is None:
        raise PromotionError("Offer not found.", "not_found")
    if offer.is_active:
        offer.is_active = False
        offer.save(update_fields=["is_active", "updated_at"])
        audit.record(actor=actor, action="commerce.offer.deactivated", target=offer)
    return offer
