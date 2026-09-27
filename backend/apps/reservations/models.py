from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import BaseModel
from apps.providers.models import ProviderProfile, ServiceOffering

from .types import ReservationStatus


class Reservation(BaseModel):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    service = models.ForeignKey(
        ServiceOffering,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )

    provider_name_snapshot = models.CharField(max_length=150)
    service_title_snapshot = models.CharField(max_length=150)
    price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    currency_snapshot = models.CharField(max_length=3)
    duration_minutes_snapshot = models.PositiveSmallIntegerField()

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=12,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
    )
    status_changed_at = models.DateTimeField(default=timezone.now)
    patient_note = models.CharField(max_length=1000, blank=True, default="")

    class Meta:
        db_table = "reservations_reservation"
        ordering = ["-starts_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="reservations_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes_snapshot__gt=0),
                name="reservations_duration_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["patient", "status", "starts_at"],
                name="reservations_patient_idx",
            ),
            models.Index(
                fields=["provider", "status", "starts_at"],
                name="reservations_provider_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.patient_id} -> {self.provider_name_snapshot} [{self.status}]"


class ReservationTransition(BaseModel):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="transitions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    from_status = models.CharField(
        max_length=12,
        choices=ReservationStatus.choices,
        blank=True,
        default="",
    )
    to_status = models.CharField(max_length=12, choices=ReservationStatus.choices)
    reason = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "reservations_transition"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.reservation_id}: {self.from_status} -> {self.to_status}"
