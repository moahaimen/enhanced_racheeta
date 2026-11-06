"""Property inquiries (Phase E): a signed-in seeker asks the owner about one public listing and
the owner answers inside Racheeta.

Rules (all re-checked on locked rows; views never decide them):
* only a PUBLICLY VISIBLE listing accepts a new inquiry (an unpublished, expired or ineligible
  listing answers 404, exactly like the public detail page);
* the owner cannot inquire about their own listing; one live (OPEN/ANSWERED) inquiry per seeker
  and listing; at most MAX_INQUIRIES_PER_DAY new inquiries per seeker in 24 hours (the view is
  also throttled);
* the owner answers (OPEN/ANSWERED → ANSWERED) or closes (→ CLOSED); the seeker withdraws
  (→ WITHDRAWN). CLOSED and WITHDRAWN are final;
* the owner may wind down inquiries on a listing that is no longer public, but nothing here ever
  re-exposes that listing;
* every change is audited; notifications carry only the listing title (no message, no contact).
"""

from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.notifications import services as notifications
from apps.notifications.types import (
    NotificationCategory,
    NotificationEventType,
    NotificationResourceType,
)

from .models import ListingInquiry, PropertyListing, RealEstateSeller
from .services import ListingNotFound, RealEstateError
from .types import LIVE_INQUIRY_STATUSES, MAX_INQUIRIES_PER_DAY, InquiryStatus


class InquiryError(RealEstateError):
    code = "inquiry_error"


class DuplicateInquiry(InquiryError):
    code = "duplicate_inquiry"


class InquiryLimitReached(InquiryError):
    code = "inquiry_limit_reached"


class OwnListing(InquiryError):
    code = "own_listing"


class InquiryNotFound(InquiryError):
    code = "not_found"


class InvalidInquiryTransition(InquiryError):
    code = "invalid_transition"


def _notify(inquiry: ListingInquiry, *, recipient_id, event: str, key: str) -> None:
    def send():
        notifications.create_notification(
            recipient_id=recipient_id,
            category=NotificationCategory.INQUIRY,
            event_type=event,
            dedupe_key=f"inquiry:{inquiry.pk}:{key}:{recipient_id}",
            resource_type=NotificationResourceType.INQUIRY,
            resource_id=inquiry.pk,
            payload={"listing_title": inquiry.listing_title_snapshot, "status": inquiry.status},
        )

    transaction.on_commit(send)


@transaction.atomic
def create_inquiry(account, listing_id, *, message: str, share_contact: bool) -> ListingInquiry:
    listing = (
        PropertyListing.objects.publicly_visible()
        .select_for_update(of=("self",))
        .select_related("seller__account")
        .filter(pk=listing_id)
        .first()
    )
    if listing is None:
        raise ListingNotFound("Listing not found.")
    if listing.seller.account_id == account.pk:
        raise OwnListing("You cannot send an inquiry about your own listing.")
    since = timezone.now() - timedelta(hours=24)
    if (
        ListingInquiry.objects.filter(inquirer=account, created_at__gte=since).count()
        >= MAX_INQUIRIES_PER_DAY
    ):
        raise InquiryLimitReached("You have reached today's inquiry limit. Try again tomorrow.")
    if ListingInquiry.objects.filter(
        listing=listing, inquirer=account, status__in=LIVE_INQUIRY_STATUSES
    ).exists():
        raise DuplicateInquiry("You already have an open inquiry about this listing.")
    try:
        with transaction.atomic():
            inquiry = ListingInquiry.objects.create(
                listing=listing,
                inquirer=account,
                listing_title_snapshot=listing.title,
                message=message.strip(),
                share_contact=bool(share_contact),
            )
    except IntegrityError as exc:  # a concurrent duplicate lost the race on the constraint
        raise DuplicateInquiry("You already have an open inquiry about this listing.") from exc
    audit.record(
        actor=account,
        action="real_estate.inquiry.created",
        target=inquiry,
        summary=listing.title,
        data={"listing_id": str(listing.pk)},
    )
    _notify(
        inquiry,
        recipient_id=listing.seller.account_id,
        event=NotificationEventType.INQUIRY_RECEIVED,
        key="received",
    )
    return inquiry


def _lock_owner_inquiry(seller: RealEstateSeller, inquiry_id) -> ListingInquiry:
    inquiry = (
        ListingInquiry.objects.select_for_update(of=("self",))
        .select_related("listing")
        .filter(pk=inquiry_id, listing__seller=seller)
        .first()
    )
    if inquiry is None:
        raise InquiryNotFound("Inquiry not found.")
    return inquiry


def _move(inquiry: ListingInquiry, status: str, *, actor, action: str, fields=()) -> None:
    previous = inquiry.status
    inquiry.status = status
    inquiry.status_changed_at = timezone.now()
    inquiry.save(update_fields=["status", "status_changed_at", "updated_at", *fields])
    audit.record(
        actor=actor,
        action=action,
        target=inquiry,
        summary=inquiry.listing_title_snapshot,
        data={"from": previous, "to": status},
    )


@transaction.atomic
def respond(seller: RealEstateSeller, inquiry_id, *, response: str) -> ListingInquiry:
    inquiry = _lock_owner_inquiry(seller, inquiry_id)
    if inquiry.status not in LIVE_INQUIRY_STATUSES:
        raise InvalidInquiryTransition("This inquiry is closed.")
    inquiry.owner_response = response.strip()
    inquiry.responded_at = timezone.now()
    _move(
        inquiry,
        InquiryStatus.ANSWERED,
        actor=seller.account,
        action="real_estate.inquiry.answered",
        fields=("owner_response", "responded_at"),
    )
    _notify(
        inquiry,
        recipient_id=inquiry.inquirer_id,
        event=NotificationEventType.INQUIRY_ANSWERED,
        key=f"answered:{inquiry.responded_at.isoformat()}",
    )
    return inquiry


@transaction.atomic
def close(seller: RealEstateSeller, inquiry_id) -> ListingInquiry:
    inquiry = _lock_owner_inquiry(seller, inquiry_id)
    if inquiry.status not in LIVE_INQUIRY_STATUSES:
        raise InvalidInquiryTransition("This inquiry is already closed.")
    _move(inquiry, InquiryStatus.CLOSED, actor=seller.account, action="real_estate.inquiry.closed")
    return inquiry


@transaction.atomic
def withdraw(account, inquiry_id) -> ListingInquiry:
    inquiry = (
        ListingInquiry.objects.select_for_update().filter(pk=inquiry_id, inquirer=account).first()
    )
    if inquiry is None:
        raise InquiryNotFound("Inquiry not found.")
    if inquiry.status not in LIVE_INQUIRY_STATUSES:
        raise InvalidInquiryTransition("This inquiry is already closed.")
    _move(inquiry, InquiryStatus.WITHDRAWN, actor=account, action="real_estate.inquiry.withdrawn")
    return inquiry


def owner_counts(seller: RealEstateSeller) -> dict:
    rows = ListingInquiry.objects.filter(listing__seller=seller)
    return {
        "inquiries_open": rows.filter(status=InquiryStatus.OPEN).count(),
        "inquiries_answered": rows.filter(status=InquiryStatus.ANSWERED).count(),
        "inquiries_total": rows.count(),
    }
