"""Medical real estate (Phase 7): owners and agents advertise properties that
suit medical use; the public browses them.

- `RealEstateSeller`: one per REAL_ESTATE_SELLER account. No verification
  lifecycle in this phase — the account's role is the authority for access.
- `PropertyListing`: the advertisement. `publication_status` is server-owned
  (DRAFT/PUBLISHED) and public exposure additionally needs a future
  `expires_at`, an eligible seller account and active geography — see
  `PropertyListingQuerySet.publicly_visible`, the single visibility rule.
- `ListingSuitableUse`: normalized, searchable medical uses of a listing.

Coordinates are plain decimals (no PostGIS); images are deferred until
production media storage exists.
"""

from django.conf import settings
from django.db import models
from django.db.models import Case, Exists, OuterRef, Q, Value, When
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.core.models import BaseModel
from apps.geography.models import City, Governorate

from .types import (
    SUITABLE_USE_ORDER,
    ContactMethod,
    PropertyType,
    PublicationStatus,
    SellerType,
    SuitableUse,
    TransactionType,
)


class _ImmutableFieldsMixin(models.Model):
    """Ownership never moves: saving a loaded row whose immutable field has
    changed is refused, whatever code path (admin, shell, service) tries it."""

    immutable_fields: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        loaded = getattr(self, "_loaded_immutable", None)
        if loaded and not self._state.adding:
            for name, original in loaded.items():
                if getattr(self, name) != original:
                    raise ValueError(f"{name} cannot change after creation.")
        return super().save(*args, **kwargs)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_immutable = {
            name: getattr(instance, name)
            for name in cls.immutable_fields
            if name in instance.__dict__
        }
        return instance


class RealEstateSeller(_ImmutableFieldsMixin, BaseModel):
    immutable_fields = ("account_id",)

    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="real_estate_seller"
    )
    seller_type = models.CharField(max_length=8, choices=SellerType.choices)
    display_name = models.CharField(max_length=150)
    about = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    public_email = models.EmailField(blank=True, default="")

    class Meta:
        db_table = "real_estate_seller"
        ordering = ["display_name"]

    def __str__(self) -> str:
        return self.display_name

    @property
    def is_eligible(self) -> bool:
        """Active account whose role is still REAL_ESTATE_SELLER (callers on the
        write path load the seller and account fresh under lock)."""
        return self.account.is_active and self.account.role == AccountRole.REAL_ESTATE_SELLER


class PropertyListingQuerySet(models.QuerySet):
    def publicly_visible(self, now=None):
        """THE public exposure rule; list and detail both start here and client
        filters only narrow it. Evaluated from live database state and server
        time on every read (no scheduler): PUBLISHED, not expired, seller on an
        active REAL_ESTATE_SELLER account, active governorate and — when set —
        active city."""
        now = now or timezone.now()
        return self.filter(
            publication_status=PublicationStatus.PUBLISHED,
            expires_at__gt=now,
            seller__account__is_active=True,
            seller__account__role=AccountRole.REAL_ESTATE_SELLER,
            governorate__is_active=True,
        ).filter(Q(city__isnull=True) | Q(city__is_active=True))

    def with_public_state(self, now=None):
        """Owner-side derived state, computed once per statement: `is_public`
        (passes publicly_visible) and `is_expired` (PUBLISHED past its expiry)."""
        now = now or timezone.now()
        visible = PropertyListing.objects.publicly_visible(now).filter(pk=OuterRef("pk"))
        return self.annotate(
            is_public=Exists(visible),
            is_expired=Case(
                When(
                    publication_status=PublicationStatus.PUBLISHED,
                    expires_at__lte=now,
                    then=Value(True),
                ),
                default=Value(False),
                output_field=models.BooleanField(),
            ),
        )


class PropertyListing(_ImmutableFieldsMixin, BaseModel):
    immutable_fields = ("seller_id",)

    seller = models.ForeignKey(RealEstateSeller, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    property_type = models.CharField(max_length=32, choices=PropertyType.choices)
    transaction_type = models.CharField(max_length=8, choices=TransactionType.choices)
    governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, related_name="property_listings"
    )
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="property_listings", null=True, blank=True
    )
    district = models.CharField(max_length=150, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # Null while a draft is incomplete; required (> 0) to publish.
    area_sqm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Null = price on request.
    price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # Validated against settings.RACHEETA["CURRENCIES"] (like every module).
    currency = models.CharField(max_length=3, default="IQD")
    facilities = models.TextField(blank=True, default="")
    contact_method = models.CharField(
        max_length=8, choices=ContactMethod.choices, default=ContactMethod.PHONE
    )
    contact_phone = models.CharField(max_length=32, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    # --- server-owned lifecycle ---------------------------------------------
    publication_status = models.CharField(
        max_length=10, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT
    )
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = PropertyListingQuerySet.as_manager()

    class Meta:
        db_table = "real_estate_listing"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="real_estate_listing_price_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(area_sqm__isnull=True) | Q(area_sqm__gt=0),
                name="real_estate_listing_area_positive",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True) | (Q(latitude__gte=-90) & Q(latitude__lte=90)),
                name="real_estate_listing_latitude_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True)
                | (Q(longitude__gte=-180) & Q(longitude__lte=180)),
                name="real_estate_listing_longitude_range",
            ),
            models.CheckConstraint(
                condition=(Q(latitude__isnull=True) & Q(longitude__isnull=True))
                | (Q(latitude__isnull=False) & Q(longitude__isnull=False)),
                name="real_estate_listing_coordinate_pair",
            ),
            models.CheckConstraint(
                condition=Q(publication_status=PublicationStatus.DRAFT)
                | (Q(area_sqm__isnull=False) & Q(expires_at__isnull=False)),
                name="real_estate_listing_published_complete",
            ),
        ]
        indexes = [
            models.Index(fields=["seller", "publication_status"], name="real_estate_seller_status"),
            models.Index(
                fields=["publication_status", "expires_at"], name="real_estate_status_expiry"
            ),
            models.Index(
                fields=["publication_status", "transaction_type"], name="real_estate_status_txn"
            ),
            models.Index(
                fields=["publication_status", "property_type"], name="real_estate_status_ptype"
            ),
            models.Index(fields=["governorate", "city"], name="real_estate_geo_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def suitable_use_codes(self) -> list[str]:
        """Suitable uses in fixed display order. Reads the prefetch cache when
        present (list/detail prefetch it), one query otherwise."""
        return sorted(
            (row.use for row in self.suitable_uses.all()), key=lambda use: SUITABLE_USE_ORDER[use]
        )


class ListingSuitableUse(BaseModel):
    """One medical use a listing suits (normalized so it is searchable). Rows are
    only ever replaced by the services while holding the parent listing's lock."""

    listing = models.ForeignKey(
        PropertyListing, on_delete=models.CASCADE, related_name="suitable_uses"
    )
    use = models.CharField(max_length=24, choices=SuitableUse.choices)

    class Meta:
        db_table = "real_estate_listing_use"
        ordering = ["listing_id", "use"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "use"], name="real_estate_listing_use_unique"
            )
        ]
        indexes = [models.Index(fields=["use"], name="real_estate_use_idx")]

    def __str__(self) -> str:
        return f"{self.listing_id}:{self.use}"
