"""Provider-side aggregates: reviews, offers and (facility only) practitioner memberships.

All three are computed for the caller's own `ProviderProfile` and nothing else. Practitioner
and facility reservations are deliberately never combined: a reservation belongs to the profile
that was booked, and no authoritative practitioner-to-facility reservation relation exists.
"""

from __future__ import annotations

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.offers.models import Offer
from apps.providers.models import ProviderMembership
from apps.providers.types import MembershipSide, MembershipStatus
from apps.reviews.models import Review


def review_summary(profile) -> dict:
    """1 query. `average_rating` is null (not 0) when there are no reviews."""
    row = (
        Review.objects.filter(provider=profile)
        .order_by()
        .aggregate(
            average=Avg("rating"),
            count=Count("pk"),
            **{f"r{star}": Count("pk", filter=Q(rating=star)) for star in range(1, 6)},
        )
    )
    average = row["average"]
    return {
        "average_rating": round(float(average), 2) if average is not None else None,
        "review_count": row["count"],
        "distribution": {str(star): row[f"r{star}"] for star in range(1, 6)},
    }


def offer_summary(profile, *, now=None) -> dict:
    """1 query. `running_now` is the public visibility rule for an offer (active flag, window
    containing `now`, active service); `scheduled` is active offers that have not started."""
    now = now or timezone.now()
    row = (
        Offer.objects.filter(provider=profile)
        .order_by()
        .aggregate(
            total=Count("pk"),
            running_now=Count(
                "pk",
                filter=Q(
                    is_active=True,
                    starts_at__lte=now,
                    ends_at__gt=now,
                    service__is_active=True,
                ),
            ),
            scheduled=Count("pk", filter=Q(is_active=True, starts_at__gt=now)),
        )
    )
    return row


def facility_membership_summary(profile) -> dict:
    """1 query over memberships where the caller is the facility.

    `incoming_requests` need the facility's answer (initiated by the practitioner);
    `outgoing_invitations` wait for the practitioner (initiated by the facility)."""
    pending = Q(status=MembershipStatus.PENDING)
    return (
        ProviderMembership.objects.filter(facility=profile)
        .order_by()
        .aggregate(
            active=Count("pk", filter=Q(status=MembershipStatus.ACTIVE)),
            incoming_requests=Count(
                "pk", filter=pending & Q(initiated_by=MembershipSide.PRACTITIONER)
            ),
            outgoing_invitations=Count(
                "pk", filter=pending & Q(initiated_by=MembershipSide.FACILITY)
            ),
        )
    )
