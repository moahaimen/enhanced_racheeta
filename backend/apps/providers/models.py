"""Provider domain: one ProviderProfile per eligible Account, memberships
between practitioners and facilities, and service offerings.

Practitioners and facilities share one table classified by `provider_type`;
type-specific data (licences, beds, ...) will live in optional one-to-one
extension tables when a business rule needs them (ADR-023).
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel
from apps.geography.models import City, Governorate
from apps.specialties.models import Specialty

from .types import (
    MembershipSide,
    MembershipStatus,
    ProviderKind,
    ProviderType,
    VerificationStatus,
    kind_of,
)


class ProviderProfileQuerySet(models.QuerySet):
    def discoverable(self):
        """What the public may see: verified, visible, active account."""
        return self.filter(
            verification_status=VerificationStatus.VERIFIED,
            is_visible=True,
            account__is_active=True,
        )

    def with_public_relations(self):
        return self.select_related("governorate", "city").prefetch_related("specialties")


class ProviderProfile(BaseModel):
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_profile"
    )
    provider_type = models.CharField(max_length=32, choices=ProviderType.choices)
    display_name = models.CharField(max_length=150)
    about = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    public_email = models.EmailField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    governorate = models.ForeignKey(Governorate, on_delete=models.PROTECT, related_name="providers")
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="providers", null=True, blank=True
    )
    address = models.CharField(max_length=255, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # Reference to a logo/photo. Uploads arrive with the media module; until
    # then providers may point at an existing https image.
    image_url = models.URLField(blank=True, default="")
    specialties = models.ManyToManyField(Specialty, blank=True, related_name="providers")

    # --- admin-controlled -------------------------------------------------
    verification_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED
    )
    verification_note = models.TextField(blank=True, default="")
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    verification_changed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    # --- provider-controlled ----------------------------------------------
    is_visible = models.BooleanField(default=True)

    objects = ProviderProfileQuerySet.as_manager()

    class Meta:
        db_table = "providers_profile"
        ordering = ["display_name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                    )
                ),
                name="providers_profile_coordinates_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name="providers_profile_coordinates_both_or_none",
            ),
        ]
        indexes = [
            # Discovery: status + visibility first, then the common filters.
            models.Index(
                fields=["verification_status", "is_visible", "provider_type"],
                name="providers_profile_discover_idx",
            ),
            models.Index(fields=["governorate", "city"], name="providers_profile_geo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.provider_type})"

    @property
    def kind(self) -> str:
        return kind_of(self.provider_type)

    @property
    def is_practitioner(self) -> bool:
        return self.kind == ProviderKind.PRACTITIONER

    @property
    def is_facility(self) -> bool:
        return self.kind == ProviderKind.FACILITY

    @property
    def is_discoverable(self) -> bool:
        return (
            self.verification_status == VerificationStatus.VERIFIED
            and self.is_visible
            and self.account.is_active
        )


class ProviderMembership(BaseModel):
    """A practitioner working at a facility. Either side may initiate; the
    other side accepts or rejects; either side may end an active membership."""

    practitioner = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="facility_memberships"
    )
    facility = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="practitioner_memberships"
    )
    status = models.CharField(
        max_length=16, choices=MembershipStatus.choices, default=MembershipStatus.PENDING
    )
    initiated_by = models.CharField(max_length=16, choices=MembershipSide.choices)
    role_title = models.CharField(max_length=100, blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "providers_membership"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(practitioner=F("facility")), name="providers_membership_not_self"
            ),
            # One live relationship per pair; history rows (REJECTED/ENDED) may accumulate.
            models.UniqueConstraint(
                fields=["practitioner", "facility"],
                condition=Q(status__in=["PENDING", "ACTIVE"]),
                name="providers_membership_one_live_per_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["facility", "status"], name="providers_membership_fac_idx"),
            models.Index(fields=["practitioner", "status"], name="providers_membership_prac_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.practitioner_id} @ {self.facility_id} [{self.status}]"

    def side_of(self, profile: ProviderProfile) -> str | None:
        if profile.pk == self.practitioner_id:
            return MembershipSide.PRACTITIONER
        if profile.pk == self.facility_id:
            return MembershipSide.FACILITY
        return None


class ServiceOffering(BaseModel):
    """A service a provider offers. Availability/booking belongs to Phase 3."""

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="services")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, null=True, blank=True, related_name="services"
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    currency = models.CharField(max_length=3, default="IQD")
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "providers_service"
        ordering = ["title"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0), name="providers_service_price_nonneg"
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__isnull=True) | Q(duration_minutes__gt=0),
                name="providers_service_duration_positive",
            ),
            models.UniqueConstraint(
                fields=["provider", "title"], name="providers_service_title_unique_per_provider"
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "is_active"], name="providers_service_active_idx")
        ]

    def __str__(self) -> str:
        return self.title
