from django.db import IntegrityError, transaction

from apps.audit import services as audit_services
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus

from .models import Review


class ReviewError(Exception):
    code = "review_error"


class ReservationNotReviewable(ReviewError):
    code = "reservation_not_reviewable"


class AlreadyReviewed(ReviewError):
    code = "already_reviewed"


@transaction.atomic
def create_review(*, patient, reservation_id, rating: int, comment: str = "") -> Review:
    try:
        reservation = (
            Reservation.objects.select_for_update(of=("self",))
            .select_related("provider")
            .get(pk=reservation_id, patient=patient)
        )
    except Reservation.DoesNotExist as exc:
        raise ReservationNotReviewable("This reservation cannot be reviewed.") from exc

    if reservation.status != ReservationStatus.COMPLETED or reservation.provider_id is None:
        raise ReservationNotReviewable("Only completed reservations can be reviewed.")

    if Review.objects.filter(reservation=reservation).exists():
        raise AlreadyReviewed("This reservation already has a review.")

    try:
        review = Review.objects.create(
            reservation=reservation,
            patient=patient,
            provider=reservation.provider,
            provider_name_snapshot=reservation.provider_name_snapshot,
            service_title_snapshot=reservation.service_title_snapshot,
            rating=rating,
            comment=comment.strip(),
        )
    except IntegrityError as exc:
        raise AlreadyReviewed("This reservation already has a review.") from exc

    audit_services.record(
        actor=patient,
        action="review.created",
        target=review,
        summary=f"{rating}/5 for completed reservation",
        data={
            "reservation_id": str(reservation.pk),
            "provider_id": str(reservation.provider_id),
        },
    )
    return review
