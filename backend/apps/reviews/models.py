from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.providers.models import ProviderProfile
from apps.reservations.models import Reservation


class Review(BaseModel):
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.PROTECT,
        related_name="review",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="provider_reviews",
    )
    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    provider_name_snapshot = models.CharField(max_length=150)
    service_title_snapshot = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.CharField(max_length=1000, blank=True, default="")

    class Meta:
        db_table = "reviews_review"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="reviews_rating_1_to_5",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "-created_at"], name="reviews_provider_idx"),
            models.Index(fields=["patient", "-created_at"], name="reviews_patient_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provider_name_snapshot}: {self.rating}/5"
