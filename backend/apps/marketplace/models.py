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
from django.db.models import Q

from apps.core.models import BaseModel
from apps.geography.models import City, Governorate
from apps.providers.types import ProviderType
from apps.specialties.models import Specialty

from .types import CompanyVerificationStatus


class MedicalCompanyQuerySet(models.QuerySet):
    def publishing(self):
        """Companies whose active products may be exposed."""
        return self.filter(
            verification_status=CompanyVerificationStatus.VERIFIED, account__is_active=True
        )


class MedicalCompany(BaseModel):
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="medical_company"
    )
    name = models.CharField(max_length=150)
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
        return (
            self.verification_status == CompanyVerificationStatus.VERIFIED
            and self.account.is_active
        )


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

    class Meta:
        db_table = "marketplace_category"
        ordering = ["sort_order", "name_en"]
        verbose_name_plural = "product categories"

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
    def exposable(self):
        """Products that may be shown to SOME provider: published by a verified
        company with an active account, in an active category that has at
        least one active audience rule."""
        return self.filter(
            is_active=True,
            company__verification_status=CompanyVerificationStatus.VERIFIED,
            company__account__is_active=True,
            category__is_active=True,
            category__audiences__is_active=True,
        ).distinct()

    def targeted_for(self, provider):
        """THE targeting decision (list and detail share it): the exposable
        products whose category carries at least one active rule matching this
        provider — provider type equal (or unconstrained) AND specialty among
        the provider's (or unconstrained). All rule conditions sit in one
        filter() call so they apply to the same rule row."""
        specialty_ids = list(provider.specialties.values_list("pk", flat=True))
        return (
            self.filter(
                is_active=True,
                company__verification_status=CompanyVerificationStatus.VERIFIED,
                company__account__is_active=True,
                category__is_active=True,
            )
            .filter(
                Q(category__audiences__is_active=True)
                & (
                    Q(category__audiences__provider_type=provider.provider_type)
                    | Q(category__audiences__provider_type="")
                )
                & (
                    Q(category__audiences__specialty__in=specialty_ids)
                    | Q(category__audiences__specialty__isnull=True)
                )
            )
            .distinct()
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

    objects = ProductQuerySet.as_manager()

    class Meta:
        db_table = "marketplace_product"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="marketplace_product_price_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"], name="marketplace_product_owner_idx"),
            models.Index(fields=["category", "is_active"], name="marketplace_product_cat_idx"),
        ]

    def __str__(self) -> str:
        return self.title
