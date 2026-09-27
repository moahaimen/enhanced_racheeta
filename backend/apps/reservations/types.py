from django.db import models


class ReservationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    COMPLETED = "COMPLETED", "Completed"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"
    NO_SHOW = "NO_SHOW", "No show"


PROVIDER_TRANSITIONS = {
    ReservationStatus.PENDING: frozenset(
        {
            ReservationStatus.CONFIRMED,
            ReservationStatus.REJECTED,
            ReservationStatus.CANCELLED,
        }
    ),
    ReservationStatus.CONFIRMED: frozenset(
        {
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        }
    ),
}
