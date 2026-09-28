from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel
from apps.providers.models import ProviderProfile, ServiceOffering


class Offer(BaseModel):
    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.CASCADE,
        related_name="offers",
    )
    service = models.ForeignKey(
        ServiceOffering,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offers",
    )
    service_title_snapshot = models.CharField(max_length=150)
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=1000, blank=True, default="")
    original_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    offer_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency_snapshot = models.CharField(max_length=3)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "offers_offer"
        ordering = ["-starts_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="offers_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(offer_price__gte=0),
                name="offers_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(offer_price__lt=F("original_price_snapshot")),
                name="offers_price_below_original",
            ),
        ]
        indexes = [
            models.Index(
                fields=["provider", "is_active", "starts_at", "ends_at"],
                name="offers_public_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.title
