"""Medical marketplace (Phase 6): companies publish products; categories and
their audience rules are system-controlled; targeting is decided here.

- `MedicalCompany`: one per MEDICAL_COMPANY account, admin-verified.
- `ProductCategory`: administrator reference data (bilingual, slug, tree).
- `ProductAudience`: administrator rule "this category is for providers of
  type X and/or specialty Y". Companies never write these rows.
- `Product`: a company's listing in one category; `is_active` is the
  company's publication switch, but exposure additionally requires a
  verified company, an active category with at least one active rule, and a
  matching provider — see `ProductQuerySet.targeted_for`.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef, Q

from apps.accounts.roles import AccountRole
from apps.core.models import BaseModel
from apps.geography.models import City, Governorate
from apps.providers.types import ProviderType
from apps.specialties.models import Specialty

from .types import (
    CONSUMER_CHANNELS,
    PROFESSIONAL_CHANNELS,
    RETAIL_BUSINESS_TYPES,
    BusinessType,
    CompanyVerificationStatus,
    ComplianceClass,
    SaleChannel,
)


class MedicalCompanyQuerySet(models.QuerySet):
    def publishing(self):
        """Companies whose active products may be exposed: VERIFIED, on an
        active account whose role is still MEDICAL_COMPANY (a role moved
        elsewhere by staff withdraws publication at once, like suspension)."""
        return self.filter(
            verification_status=CompanyVerificationStatus.VERIFIED,
            account__is_active=True,
            account__role=AccountRole.MEDICAL_COMPANY,
        )


class MedicalCompany(BaseModel):
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="medical_company"
    )
    name = models.CharField(max_length=150)
    # Normalized classification (verified identity: locked while PENDING/VERIFIED).
    business_type = models.CharField(
        max_length=32, choices=BusinessType.choices, default=BusinessType.MEDICAL_COMPANY
    )
    description = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    public_email = models.EmailField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, related_name="medical_companies"
    )
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="medical_companies", null=True, blank=True
    )
    address = models.CharField(max_length=255, blank=True, default="")
    # --- administrator-controlled -------------------------------------------
    verification_status = models.CharField(
        max_length=16,
        choices=CompanyVerificationStatus.choices,
        default=CompanyVerificationStatus.UNVERIFIED,
    )
    verification_note = models.TextField(blank=True, default="")
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    verification_changed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    objects = MedicalCompanyQuerySet.as_manager()

    class Meta:
        db_table = "marketplace_company"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["verification_status"], name="marketplace_company_status_idx")
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def can_publish(self) -> bool:
        """Same eligibility as MedicalCompanyQuerySet.publishing(), for one
        loaded company (callers on the write path load it fresh under lock)."""
        return (
            self.verification_status == CompanyVerificationStatus.VERIFIED
            and self.account.is_active
            and self.account.role == AccountRole.MEDICAL_COMPANY
        )


class ProductCategoryQuerySet(models.QuerySet):
    def with_publishability(self):
        """Annotates `can_publish`: an active category with at least one active
        audience rule — the state the publication gate checks
        (services._locked_publishable_category), computed once per statement
        as an EXISTS subquery, never per row. Read-only reference state for
        clients; the gate on locked rows stays authoritative."""
        active_rule = ProductAudience.objects.filter(
            category=OuterRef("pk"), category__is_active=True, is_active=True
        )
        return self.annotate(can_publish=Exists(active_rule))


class ProductCategory(BaseModel):
    """Administrator reference data. The Master Plan's examples (dental,
    laboratory, ...) are examples; the taxonomy is managed, not seeded."""

    slug = models.SlugField(max_length=60, unique=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # Administrator governance: products in this category MAY be offered in the public store
    # (assistive devices, general supplies). Medicines and restricted equipment never are.
    consumer_allowed = models.BooleanField(default=False)
    # Purchase eligibility (fail closed). The public store needs B2C_ALLOWED AND consumer_allowed.
    compliance_class = models.CharField(
        max_length=28,
        choices=ComplianceClass.choices,
        default=ComplianceClass.RESTRICTED_PENDING_REVIEW,
    )

    class Meta:
        db_table = "marketplace_category"
        ordering = ["sort_order", "name_en"]
        verbose_name_plural = "product categories"

    objects = ProductCategoryQuerySet.as_manager()

    def __str__(self) -> str:
        return self.name_en

    def has_active_audience(self) -> bool:
        return self.audiences.filter(is_active=True).exists()


class ProductAudience(BaseModel):
    """One targeting rule of a category: matches a provider when the configured
    provider type equals the provider's type AND the configured specialty is one
    of the provider's specialties; a constraint left empty is not enforced, but
    at least one must be set (a rule can never match everyone)."""

    category = models.ForeignKey(
        ProductCategory, on_delete=models.CASCADE, related_name="audiences"
    )
    provider_type = models.CharField(
        max_length=32, choices=ProviderType.choices, blank=True, default=""
    )
    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, related_name="product_audiences", null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "marketplace_audience"
        ordering = ["category", "provider_type", "specialty_id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(provider_type="") | Q(specialty__isnull=False),
                name="marketplace_audience_meaningful",
            ),
            models.UniqueConstraint(
                fields=["category", "provider_type", "specialty"],
                name="marketplace_audience_unique",
                nulls_distinct=False,
            ),
        ]

    def __str__(self) -> str:
        parts = [p for p in (self.provider_type, getattr(self.specialty, "slug", None)) if p]
        return f"{self.category_id}: {' + '.join(parts) or '?'}"

    def validate_rule(self) -> None:
        if not self.provider_type and self.specialty_id is None:
            raise ValidationError(
                {"provider_type": ["Set a provider type, a specialty, or both."]},
                code="empty_rule",
            )

    def clean(self):
        super().clean()
        self.validate_rule()

    def save(self, *args, **kwargs):
        self.validate_rule()
        return super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def consumer_store(self):
        """Products offered in the public store (see consumer_store_filter)."""
        return self.filter(consumer_store_filter())

    def exposable(self):
        """Products that may be shown to SOME provider: published by a verified
        company on an active MEDICAL_COMPANY account, in an active category
        that has at least one active audience rule."""
        return self.filter(
            is_active=True,
            sale_channel__in=PROFESSIONAL_CHANNELS,
            company__verification_status=CompanyVerificationStatus.VERIFIED,
            company__account__is_active=True,
            company__account__role=AccountRole.MEDICAL_COMPANY,
            category__is_active=True,
            category__audiences__is_active=True,
        ).distinct()

    def targeted_for(self, provider):
        """THE targeting decision (list and detail share it): the exposable
        products whose category carries at least one active rule matching this
        provider. The provider's verification, type and specialties are read by
        the SAME SQL statement that returns the products (subqueries on the
        provider row), never from the Python object the caller holds, so a
        provider suspended or unverified after the request started gets no rows,
        and specialties it could edit once unlocked are never matched. All rule
        conditions sit in one filter() call so they apply to the same rule row."""
        from apps.providers.models import ProviderProfile
        from apps.providers.types import VerificationStatus

        verified = ProviderProfile.objects.filter(
            pk=provider.pk,
            verification_status=VerificationStatus.VERIFIED,
            account__is_active=True,
            account__role="PROVIDER",
        )
        verified_type = verified.values("provider_type")[:1]
        verified_specialties = ProviderProfile.specialties.through.objects.filter(
            providerprofile_id__in=verified.values("pk")
        ).values("specialty_id")
        return (
            self.filter(
                is_active=True,
                sale_channel__in=PROFESSIONAL_CHANNELS,
                company__verification_status=CompanyVerificationStatus.VERIFIED,
                company__account__is_active=True,
                company__account__role=AccountRole.MEDICAL_COMPANY,
                category__is_active=True,
            )
            .filter(models.Exists(verified))
            .filter(
                Q(category__audiences__is_active=True)
                & (
                    Q(category__audiences__provider_type=models.Subquery(verified_type))
                    | Q(category__audiences__provider_type="")
                )
                & (
                    Q(category__audiences__specialty__in=verified_specialties)
                    | Q(category__audiences__specialty__isnull=True)
                )
            )
            .distinct()
        )


def consumer_store_filter() -> Q:
    """THE public-store rule (one place; list, detail and checkout share it): a published,
    non-restricted product offered to consumers, in an active consumer-allowed category, by a
    verified retail business on an active MEDICAL_COMPANY account."""
    return Q(
        is_active=True,
        sale_channel__in=CONSUMER_CHANNELS,
        is_restricted=False,
        category__is_active=True,
        category__consumer_allowed=True,
        category__compliance_class=ComplianceClass.B2C_ALLOWED,
        company__verification_status=CompanyVerificationStatus.VERIFIED,
        company__business_type__in=RETAIL_BUSINESS_TYPES,
        company__account__is_active=True,
        company__account__role=AccountRole.MEDICAL_COMPANY,
    )


class Product(BaseModel):
    company = models.ForeignKey(MedicalCompany, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(ProductCategory, on_delete=models.PROTECT, related_name="products")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    brand = models.CharField(max_length=100, blank=True, default="")
    model_name = models.CharField(max_length=100, blank=True, default="")
    # Null = price on request.
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # Validated against settings.RACHEETA["CURRENCIES"] in the serializer (as services are).
    currency = models.CharField(max_length=3, default="IQD")
    # The company's publication switch; exposure needs more (see targeted_for).
    is_active = models.BooleanField(default=False)
    # Where the product may be offered. Existing products are B2B (targeted professional catalogue).
    sale_channel = models.CharField(
        max_length=4, choices=SaleChannel.choices, default=SaleChannel.B2B
    )
    # Prescription medicines / restricted equipment: professional (B2B) only, never in the store.
    is_restricted = models.BooleanField(default=False)
    # Merchant-owned inventory for store orders; null = not stocked (quote/price on request only).
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    # Units held for placed orders that have not shipped yet (available = on hand - reserved).
    stock_reserved = models.PositiveIntegerField(default=0)
    # Low-stock alert threshold on AVAILABLE units (null = no alert).
    reorder_threshold = models.PositiveIntegerField(null=True, blank=True)
    # Product photo (an https link the business provides; no file uploads exist yet).
    image_url = models.URLField(max_length=500, blank=True, default="")

    objects = ProductQuerySet.as_manager()

    class Meta:
        db_table = "marketplace_product"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(stock_quantity__isnull=True) & Q(stock_reserved=0))
                | Q(stock_reserved__lte=models.F("stock_quantity")),
                name="marketplace_product_reserved_le_on_hand",
            ),
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="marketplace_product_price_non_negative",
            ),
            # Defence in depth for the service rule: restricted items are professional-only.
            models.CheckConstraint(
                condition=Q(is_restricted=False) | Q(sale_channel="B2B"),
                name="marketplace_product_restricted_is_b2b",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"], name="marketplace_product_owner_idx"),
            models.Index(fields=["category", "is_active"], name="marketplace_product_cat_idx"),
        ]

    def __str__(self) -> str:
        return self.title
