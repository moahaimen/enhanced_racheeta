"""Advertising (Phase 8): sponsored medical-product campaigns.

A MEDICAL_COMPANY promotes one of its marketplace products to eligible
providers. Everything commercial is server-owned: the price comes from the
active `AdvertisingRate`, is snapshotted on the campaign at submission, and a
campaign only becomes ACTIVE when an administrator verifies its
`CampaignPayment` (no gateway exists yet). Visibility is one queryset,
`AdvertisingCampaignQuerySet.visible_to`, evaluated from current database
state and server date on every read; it can only NARROW Phase 6 product
targeting (`ProductQuerySet.targeted_for`), never widen it.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, Exists, F, OuterRef, Q, Subquery, Value, When
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.core.models import BaseModel
from apps.geography.models import Governorate
from apps.marketplace.models import MedicalCompany, Product
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus
from apps.specialties.models import Specialty

from .types import CampaignStatus, PaymentMethod, PaymentStatus


class _GuardedFieldsMixin(models.Model):
    """History and ownership never move, whatever code path saves the row:
    `immutable_fields` can never change once a row is loaded; `frozen_after_submit`
    can not change once the loaded row has left DRAFT (`status` is the guard)."""

    immutable_fields: tuple[str, ...] = ()
    frozen_after_submit: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        loaded = getattr(self, "_loaded_guarded", None)
        if loaded is not None and not self._state.adding:
            frozen = set(self.immutable_fields)
            if loaded.get("status") not in (None, CampaignStatus.DRAFT):
                frozen |= set(self.frozen_after_submit)
            for name in frozen:
                if name in loaded and getattr(self, name) != loaded[name]:
                    raise ValueError(f"{name} cannot change here.")
        return super().save(*args, **kwargs)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        names = {*cls.immutable_fields, *cls.frozen_after_submit, "status"}
        instance._loaded_guarded = {
            name: getattr(instance, name) for name in names if name in instance.__dict__
        }
        return instance


class AdvertisingRate(BaseModel):
    """The administrator-configured price of one advertising day. There is NO
    seeded price: the owner sets the business rate. At most one rate is active."""

    code = models.SlugField(max_length=40, unique=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    price_per_day = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="IQD")
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "advertising_rate"
        ordering = ["-is_active", "code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_per_day__gt=0), name="advertising_rate_price_positive"
            ),
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="advertising_rate_one_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.price_per_day} {self.currency}/day"

    def clean(self):
        if self.currency not in settings.RACHEETA["CURRENCIES"]:
            raise ValidationError({"currency": "Unsupported currency."})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class AdvertisingCampaignQuerySet(models.QuerySet):
    def with_live_state(self, today=None):
        """`is_live` (ACTIVE and inside its date window today) and `is_ended`
        (ACTIVE past its end date), computed once per statement."""
        today = today or timezone.localdate()
        return self.annotate(
            is_live=Case(
                When(
                    status=CampaignStatus.ACTIVE,
                    starts_on__lte=today,
                    ends_on__gte=today,
                    then=Value(True),
                ),
                default=Value(False),
                output_field=models.BooleanField(),
            ),
            is_ended=Case(
                When(status=CampaignStatus.ACTIVE, ends_on__lt=today, then=Value(True)),
                default=Value(False),
                output_field=models.BooleanField(),
            ),
        )

    def visible_to(self, provider, today=None):
        """THE advertisement visibility rule. A sponsored campaign reaches a
        provider only when, from CURRENT database state and the server date:

        1. the campaign is ACTIVE, its payment VERIFIED and today is inside
           [starts_on, ends_on];
        2. its company is VERIFIED, on an active MEDICAL_COMPANY account, and
           owns the product;
        3. the product is targeted at this provider by the Phase 6 rule
           (`ProductQuerySet.targeted_for`) — the campaign can only NARROW that
           set, never make an otherwise invisible product visible;
        4. the provider is a verified, active PROVIDER (re-read here, never trusted
           from the request);
        5. each configured narrowing (provider types, specialties, governorates)
           matches the provider's current profile; a targeted governorate or
           specialty that has been deactivated stops producing exposure (the
           campaign and its payment are untouched — only exposure changes).
        """
        today = today or timezone.localdate()
        verified = ProviderProfile.objects.filter(
            pk=provider.pk,
            verification_status=VerificationStatus.VERIFIED,
            account__is_active=True,
            account__role=AccountRole.PROVIDER,
        )
        provider_specialties = ProviderProfile.specialties.through.objects.filter(
            providerprofile_id__in=verified.values("pk")
        ).values("specialty_id")
        wants_types = CampaignProviderType.objects.filter(campaign=OuterRef("pk"))
        wants_specialties = CampaignSpecialty.objects.filter(campaign=OuterRef("pk"))
        wants_governorates = CampaignGovernorate.objects.filter(campaign=OuterRef("pk"))
        product_reaches_provider = Product.objects.targeted_for(provider).filter(
            pk=OuterRef("product_id"), company_id=OuterRef("company_id")
        )
        return (
            self.filter(
                status=CampaignStatus.ACTIVE,
                payment__status=PaymentStatus.VERIFIED,
                starts_on__lte=today,
                ends_on__gte=today,
                company__verification_status=CompanyVerificationStatus.VERIFIED,
                company__account__is_active=True,
                company__account__role=AccountRole.MEDICAL_COMPANY,
            )
            .filter(Exists(product_reaches_provider))
            .filter(Exists(verified))
            .filter(
                ~Exists(wants_types)
                | Exists(
                    wants_types.filter(provider_type=Subquery(verified.values("provider_type")[:1]))
                )
            )
            .filter(
                ~Exists(wants_specialties)
                | Exists(
                    wants_specialties.filter(
                        specialty_id__in=provider_specialties, specialty__is_active=True
                    )
                )
            )
            .filter(
                ~Exists(wants_governorates)
                | Exists(
                    wants_governorates.filter(
                        governorate_id=Subquery(verified.values("governorate_id")[:1]),
                        governorate__is_active=True,
                    )
                )
            )
        )


class AdvertisingCampaign(_GuardedFieldsMixin, BaseModel):
    immutable_fields = ("company_id",)
    frozen_after_submit = (
        "product_id",
        "name",
        "starts_on",
        "ends_on",
        "quoted_days",
        "quoted_daily_rate",
        "quoted_amount",
        "quoted_currency",
        "quoted_at",
        "rate_id",
    )

    company = models.ForeignKey(
        MedicalCompany, on_delete=models.PROTECT, related_name="advertising_campaigns"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="advertising_campaigns"
    )
    # Internal label for the company/admin; NOT advertisement copy (the ad shows the product).
    name = models.CharField(max_length=150)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT
    )
    # --- the price snapshot, written once at submission -------------------------
    quoted_days = models.PositiveIntegerField(null=True, blank=True)
    quoted_daily_rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    quoted_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    quoted_currency = models.CharField(max_length=3, blank=True, default="")
    quoted_at = models.DateTimeField(null=True, blank=True)
    rate = models.ForeignKey(
        AdvertisingRate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="campaigns",
    )

    objects = AdvertisingCampaignQuerySet.as_manager()

    class Meta:
        db_table = "advertising_campaign"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_on__isnull=True)
                | Q(ends_on__isnull=True)
                | Q(ends_on__gte=F("starts_on")),
                name="advertising_campaign_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(quoted_amount__isnull=True) | Q(quoted_amount__gte=0),
                name="advertising_campaign_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(quoted_days__isnull=True) | Q(quoted_days__gt=0),
                name="advertising_campaign_days_positive",
            ),
            models.CheckConstraint(
                condition=Q(status=CampaignStatus.DRAFT)
                | (
                    Q(starts_on__isnull=False)
                    & Q(ends_on__isnull=False)
                    & Q(quoted_days__isnull=False)
                    & Q(quoted_daily_rate__isnull=False)
                    & Q(quoted_amount__isnull=False)
                    & Q(quoted_at__isnull=False)
                    & ~Q(quoted_currency="")
                ),
                name="advertising_campaign_submitted_has_quote",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status"], name="advertising_campaign_co_status"),
            models.Index(
                fields=["status", "starts_on", "ends_on"], name="advertising_campaign_window"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class CampaignProviderType(BaseModel):
    campaign = models.ForeignKey(
        AdvertisingCampaign, on_delete=models.CASCADE, related_name="target_provider_types"
    )
    provider_type = models.CharField(max_length=32, choices=ProviderType.choices)

    class Meta:
        db_table = "advertising_campaign_provider_type"
        ordering = ["campaign_id", "provider_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "provider_type"], name="advertising_campaign_ptype_unique"
            )
        ]


class CampaignSpecialty(BaseModel):
    campaign = models.ForeignKey(
        AdvertisingCampaign, on_delete=models.CASCADE, related_name="target_specialties"
    )
    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, related_name="advertising_targets"
    )

    class Meta:
        db_table = "advertising_campaign_specialty"
        ordering = ["campaign_id", "specialty_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "specialty"], name="advertising_campaign_specialty_unique"
            )
        ]


class CampaignGovernorate(BaseModel):
    campaign = models.ForeignKey(
        AdvertisingCampaign, on_delete=models.CASCADE, related_name="target_governorates"
    )
    governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, related_name="advertising_targets"
    )

    class Meta:
        db_table = "advertising_campaign_governorate"
        ordering = ["campaign_id", "governorate_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "governorate"], name="advertising_campaign_governorate_unique"
            )
        ]


class CampaignPayment(_GuardedFieldsMixin, BaseModel):
    """The manual payment record of ONE campaign: created by the submission
    service (never by the company), verified or rejected by an administrator."""

    immutable_fields = ("campaign_id", "amount", "currency")

    campaign = models.OneToOneField(
        AdvertisingCampaign, on_delete=models.PROTECT, related_name="payment"
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True, default="")
    reference = models.CharField(max_length=120, blank=True, default="")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "advertising_payment"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="advertising_payment_amount_non_negative"
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=PaymentStatus.VERIFIED, verified_at__isnull=False) & ~Q(method="")
                )
                | (~Q(status=PaymentStatus.VERIFIED) & Q(verified_at__isnull=True)),
                name="advertising_payment_verified_coherent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.campaign_id}: {self.amount} {self.currency} {self.status}"


def decimal_field_max(field) -> Decimal:
    """The largest positive value a DecimalField can store (e.g. 16 digits, 2 places ->
    99999999999999.99), derived from the field's own metadata so it cannot drift."""
    whole = "9" * (field.max_digits - field.decimal_places)
    fraction = "9" * field.decimal_places
    return Decimal(f"{whole}.{fraction}")


# What a campaign total must fit: the quote snapshot AND the payment record (both are
# stored). Computed once from the authoritative fields; the quote preview serializer
# mirrors the same precision (see QuoteResponseSerializer).
QUOTE_AMOUNT_FIELD = AdvertisingCampaign._meta.get_field("quoted_amount")
MAX_CAMPAIGN_AMOUNT = min(
    decimal_field_max(QUOTE_AMOUNT_FIELD),
    decimal_field_max(CampaignPayment._meta.get_field("amount")),
)
