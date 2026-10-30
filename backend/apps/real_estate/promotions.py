"""Listing promotions: seller request/end, administrator approve/reject, and the
bounded opt-in notification fan-out on approval. The only writer of
`ListingPromotion` rows."""

from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.notifications.types import NotificationEventType, NotificationResourceType
from apps.preferences import outreach
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus

from .models import PROVIDER_TYPE_VALUES, ListingPromotion, PropertyListing, RealEstateSeller
from .services import (
    AlreadyExists,
    InvalidTransition,
    ListingNotFound,
    ListingProblems,
    _lock_seller,
    _require_eligible,
)
from .types import MAX_PROMOTION_DAYS, PromotionStatus


def _validated_types(types) -> list[str]:
    values = sorted(set(types or []))
    if any(value not in PROVIDER_TYPE_VALUES for value in values):
        raise ListingProblems({"target_provider_types": "invalid_choice"})
    return values


@transaction.atomic
def request_promotion(
    seller: RealEstateSeller, listing_id, *, target_provider_types, days: int
) -> ListingPromotion:
    locked_seller = _lock_seller(seller)
    _require_eligible(locked_seller)
    listing = (
        PropertyListing.objects.publicly_visible()
        .select_for_update(of=("self",))
        .filter(pk=listing_id, seller=locked_seller)
        .first()
    )
    if listing is None:
        raise ListingNotFound("Only your own published, visible listings can be promoted.")
    if not isinstance(days, int) or not 1 <= days <= MAX_PROMOTION_DAYS:
        raise ListingProblems({"days": "out_of_range"})
    types = _validated_types(target_provider_types)
    try:
        with transaction.atomic():
            promotion = ListingPromotion.objects.create(
                listing=listing, target_provider_types=types, days=days
            )
    except IntegrityError as exc:
        raise AlreadyExists("This listing already has an open promotion.") from exc
    audit.record(
        actor=locked_seller.account,
        action="real_estate.promotion.requested",
        target=promotion,
        summary=listing.title,
        data={"days": days, "target_provider_types": types},
    )
    return promotion


def _lock_promotion(promotion_id, **filters) -> ListingPromotion:
    promotion = (
        ListingPromotion.objects.select_for_update()
        .select_related("listing")
        .filter(pk=promotion_id, **filters)
        .first()
    )
    if promotion is None:
        raise ListingNotFound("Promotion not found.")
    return promotion


@transaction.atomic
def end_promotion(seller: RealEstateSeller, promotion_id) -> ListingPromotion:
    """The seller can always withdraw a request or stop an active promotion."""
    locked_seller = _lock_seller(seller)
    promotion = _lock_promotion(promotion_id, listing__seller=locked_seller)
    if promotion.status not in (PromotionStatus.REQUESTED, PromotionStatus.ACTIVE):
        raise InvalidTransition("This promotion is already closed.")
    promotion.status = PromotionStatus.ENDED
    if promotion.ends_at is None or promotion.ends_at > timezone.now():
        promotion.ends_at = timezone.now() if promotion.starts_at else None
    promotion.save(update_fields=["status", "ends_at", "updated_at"])
    audit.record(
        actor=locked_seller.account,
        action="real_estate.promotion.ended",
        target=promotion,
        summary=promotion.listing.title,
    )
    return promotion


@transaction.atomic
def approve_promotion(promotion_id, *, decided_by) -> ListingPromotion:
    promotion = _lock_promotion(promotion_id)
    if promotion.status != PromotionStatus.REQUESTED:
        raise InvalidTransition("Only a requested promotion can be approved.")
    if not PropertyListing.objects.publicly_visible().filter(pk=promotion.listing_id).exists():
        raise InvalidTransition("The listing is no longer publicly visible.")
    now = timezone.now()
    promotion.status = PromotionStatus.ACTIVE
    promotion.starts_at = now
    promotion.ends_at = now + timedelta(days=promotion.days)
    promotion.decided_by = decided_by
    promotion.decided_at = now
    promotion.save()
    audit.record(
        actor=decided_by,
        action="real_estate.promotion.approved",
        target=promotion,
        summary=promotion.listing.title,
    )
    promotion_pk = promotion.pk
    transaction.on_commit(lambda: notify_promotion_audience(promotion_pk), robust=True)
    return promotion


@transaction.atomic
def reject_promotion(promotion_id, *, decided_by, reason: str) -> ListingPromotion:
    promotion = _lock_promotion(promotion_id)
    if promotion.status != PromotionStatus.REQUESTED:
        raise InvalidTransition("Only a requested promotion can be rejected.")
    reason = (reason or "").strip()
    if not reason:
        raise ListingProblems({"reason": "required"})
    promotion.status = PromotionStatus.REJECTED
    promotion.decided_by = decided_by
    promotion.decided_at = timezone.now()
    promotion.reject_reason = reason[:300]
    promotion.save()
    audit.record(
        actor=decided_by,
        action="real_estate.promotion.rejected",
        target=promotion,
        summary=promotion.listing.title,
        data={"reason": promotion.reject_reason},
    )
    return promotion


def _audience(promotion: ListingPromotion):
    candidates = ProviderProfile.objects.filter(
        verification_status=VerificationStatus.VERIFIED,
        account__is_active=True,
        account__role=AccountRole.PROVIDER,
        account__marketing_preference__real_estate_promotions=True,
    )
    if promotion.target_provider_types:
        candidates = candidates.filter(provider_type__in=promotion.target_provider_types)
    for provider in candidates.order_by("pk").iterator(chunk_size=200):
        if ListingPromotion.objects.visible_to(provider).filter(pk=promotion.pk).exists():
            yield provider.account_id


def notify_promotion_audience(promotion_id) -> int:
    promotion = ListingPromotion.objects.select_related("listing").filter(pk=promotion_id).first()
    if promotion is None:
        return 0
    return outreach.deliver(
        account_ids=_audience(promotion),
        topic="real_estate",
        event_type=NotificationEventType.PROPERTY_PROMOTION,
        dedupe_prefix=f"promotion:{promotion.pk}",
        resource_type=NotificationResourceType.LISTING,
        resource_id=promotion.listing_id,
        payload={"listing_title": promotion.listing.title},
    )
