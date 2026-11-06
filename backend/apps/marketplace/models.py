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

import os

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Exists, F, OuterRef, Q

from apps.accounts.roles import AccountRole
from apps.core.models import BaseModel
from apps.geography.models import City, Governorate
from apps.providers.types import ProviderType
from apps.providers.types import VerificationStatus as ProviderVerification
from apps.specialties.models import Specialty

from .types import (
    CONSUMER_CHANNELS,
    PROFESSIONAL_CHANNELS,
    RETAIL_BUSINESS_TYPES,
    BusinessType,
    CompanyVerificationStatus,
    ComplianceClass,
    DocumentStatus,
    SaleChannel,
    SellerDocumentKind,
    StoreStatus,
    TaxMode,
)


def seller_account_q(prefix: str = "") -> Q:
    """THE seller-account rule (one place): a MEDICAL_COMPANY account, or a PROVIDER account
    whose store is linked to its OWN, VERIFIED pharmacy profile. A pharmacy keeps its healthcare
    provider identity; moving the account to another role, or losing pharmacy verification,
    withdraws the store at once."""
    p = prefix
    return Q(**{f"{p}account__role": AccountRole.MEDICAL_COMPANY}) | Q(
        **{
            f"{p}account__role": AccountRole.PROVIDER,
            f"{p}business_type": BusinessType.PHARMACY,
            f"{p}facility__provider_type": ProviderType.PHARMACY,
            f"{p}facility__verification_status": ProviderVerification.VERIFIED,
            f"{p}facility__account_id": F(f"{p}account_id"),
        }
    )


def seller_workspace_q(prefix: str = "") -> Q:
    """Who may RUN a store's workspace (set it up, upload documents, prepare products): its
    MEDICAL_COMPANY account, or the pharmacy account whose own facility the store is linked to.
    Selling additionally needs selling_q()."""
    p = prefix
    return Q(**{f"{p}account__role": AccountRole.MEDICAL_COMPANY}) | Q(
        **{
            f"{p}account__role": AccountRole.PROVIDER,
            f"{p}business_type": BusinessType.PHARMACY,
            f"{p}facility__account_id": F(f"{p}account_id"),
        }
    )


def is_store_owner_account(account) -> bool:
    """The account may own a store workspace: a MEDICAL_COMPANY account, or a PROVIDER account
    whose own provider profile is a pharmacy (it keeps its provider role)."""
    if not (account and account.is_authenticated):
        return False
    if account.role == AccountRole.MEDICAL_COMPANY:
        return True
    if account.role != AccountRole.PROVIDER:
        return False
    from apps.providers.models import ProviderProfile

    return ProviderProfile.objects.filter(
        account_id=account.pk, provider_type=ProviderType.PHARMACY
    ).exists()


def publishing_q(prefix: str = "") -> Q:
    """Verified business on an active seller account (may publish products)."""
    return Q(
        **{
            f"{prefix}verification_status": CompanyVerificationStatus.VERIFIED,
            f"{prefix}account__is_active": True,
        }
    ) & seller_account_q(prefix)


def selling_q(prefix: str = "") -> Q:
    """Publishing AND the seller's store is ACTIVE AND every required licence document is
    approved: its products are offered and can be bought. A grandfathered ACTIVE store without
    approved documents does not sell (fail closed)."""
    return publishing_q(prefix) & Q(
        **{f"{prefix}store_status": StoreStatus.ACTIVE, f"{prefix}documents_complete": True}
    )


class MedicalCompanyQuerySet(models.QuerySet):
    def publishing(self):
        """Companies whose active products may be exposed: VERIFIED, on an
        active seller account (see seller_account_q; a role moved elsewhere by
        staff withdraws publication at once, like suspension), store ACTIVE."""
        return self.filter(selling_q())


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
    # --- pharmacy store: the PROVIDER facility this store belongs to (same account) ------------
    facility = models.OneToOneField(
        "providers.ProviderProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="store",
    )
    # --- the seller's store switch (selling needs ACTIVE and VERIFIED) --------------------------
    # Rows that existed before activation was introduced keep selling (migration default ACTIVE);
    # onboarding creates new stores INACTIVE (services.create_company).
    store_status = models.CharField(
        max_length=10, choices=StoreStatus.choices, default=StoreStatus.ACTIVE
    )
    store_status_changed_at = models.DateTimeField(null=True, blank=True)
    # Every document REQUIRED_DOCUMENTS lists for this business type is APPROVED. Kept current by
    # sellers.refresh_documents_complete() on every upload, withdrawal and review; computed for
    # existing rows by marketplace 0007 (no documents -> False: legacy stores stop selling).
    documents_complete = models.BooleanField(default=False)
    # --- seller-declared tax treatment (Racheeta does not decide tax obligations) --------------
    tax_mode = models.CharField(max_length=10, choices=TaxMode.choices, default=TaxMode.NONE)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_label = models.CharField(max_length=40, blank=True, default="")
    tax_registration_number = models.CharField(max_length=40, blank=True, default="")
    # --- delivery: fee when no governorate rate matches (null = free / included) ---------------
    default_shipping_fee = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    free_shipping_over = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    objects = MedicalCompanyQuerySet.as_manager()

    class Meta:
        db_table = "marketplace_company"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["verification_status"], name="marketplace_company_status_idx")
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0) & Q(tax_rate__lte=30),
                name="marketplace_company_tax_rate_bounds",
            ),
            models.CheckConstraint(
                condition=Q(tax_mode="NONE", tax_rate=0) | ~Q(tax_mode="NONE"),
                name="marketplace_company_no_rate_without_tax",
            ),
            # A pharmacy store is always linked to a facility, and only a pharmacy store is.
            models.CheckConstraint(
                condition=(Q(business_type="PHARMACY") & Q(facility__isnull=False))
                | (~Q(business_type="PHARMACY") & Q(facility__isnull=True)),
                name="marketplace_company_pharmacy_has_facility",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def seller_account_ok(self) -> bool:
        """seller_account_q for one loaded company (re-read on write paths)."""
        role = self.account.role
        if role == AccountRole.MEDICAL_COMPANY:
            return True
        if role != AccountRole.PROVIDER or self.business_type != BusinessType.PHARMACY:
            return False
        facility = self.facility
        return bool(
            facility is not None
            and facility.account_id == self.account_id
            and facility.provider_type == ProviderType.PHARMACY
            and facility.verification_status == ProviderVerification.VERIFIED
        )

    @property
    def can_publish(self) -> bool:
        """Same eligibility as publishing_q(), for one loaded company (callers on the write path
        load it fresh under lock): may prepare and publish products."""
        return (
            self.verification_status == CompanyVerificationStatus.VERIFIED
            and self.account.is_active
            and self.seller_account_ok
        )

    @property
    def can_sell(self) -> bool:
        """selling_q() for one loaded company: publishing, store ACTIVE, documents complete."""
        return (
            self.can_publish and self.store_status == StoreStatus.ACTIVE and self.documents_complete
        )

    def missing_documents(self) -> list[str]:
        """Required document kinds with no APPROVED document (store activation needs none)."""
        from django.utils import timezone

        from .types import REQUIRED_DOCUMENTS

        approved = set(
            self.documents.filter(status=DocumentStatus.APPROVED)
            .filter(Q(expires_on__isnull=True) | Q(expires_on__gt=timezone.localdate()))
            .values_list("kind", flat=True)
        )  # an expired licence no longer counts
        return [k for k in REQUIRED_DOCUMENTS.get(self.business_type, ()) if k not in approved]


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
    # --- category-specific compliance rules (administrator; empty = no extra rule) -------------
    # Only these business types may publish here (e.g. medicines: pharmacies and pharma firms).
    allowed_business_types = ArrayField(
        models.CharField(max_length=32, choices=BusinessType.choices), blank=True, default=list
    )
    # Approved seller documents needed to publish here (e.g. DEVICE_REGISTRATION for devices).
    required_documents = ArrayField(
        models.CharField(max_length=32, choices=SellerDocumentKind.choices),
        blank=True,
        default=list,
    )
    # Most units of one product a buyer may order at once (null = the general limit).
    max_order_quantity = models.PositiveIntegerField(null=True, blank=True)
    # Shown to buyers on the product page and on the invoice (e.g. "Use under supervision").
    buyer_notice_ar = models.CharField(max_length=300, blank=True, default="")
    buyer_notice_en = models.CharField(max_length=300, blank=True, default="")

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
        """Products that may be shown to SOME provider: published by a selling
        business (selling_q: verified, active seller account, store ACTIVE), in an
        active category that has at least one active audience rule."""
        return self.filter(
            selling_q("company__"),
            is_active=True,
            sale_channel__in=PROFESSIONAL_CHANNELS,
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
                selling_q("company__"),
                is_active=True,
                sale_channel__in=PROFESSIONAL_CHANNELS,
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


class _one_item_array(models.Func):  # noqa: N801 - reads like a function in filters
    """ARRAY[<expr>] — lets an ArrayField `contains` lookup compare with another column."""

    template = "ARRAY[%(expressions)s]::varchar(32)[]"
    output_field = ArrayField(models.CharField(max_length=32))


def consumer_store_filter() -> Q:
    """THE public-store rule (one place; list, detail and checkout share it): a published,
    non-restricted product offered to consumers, in an active consumer-allowed category, by a
    selling retail business (selling_q), whose business type the category allows."""
    return (
        Q(
            is_active=True,
            sale_channel__in=CONSUMER_CHANNELS,
            is_restricted=False,
            category__is_active=True,
            category__consumer_allowed=True,
            category__compliance_class=ComplianceClass.B2C_ALLOWED,
            company__business_type__in=RETAIL_BUSINESS_TYPES,
        )
        & selling_q("company__")
        & (
            Q(category__allowed_business_types=[])
            | Q(
                category__allowed_business_types__contains=_one_item_array(
                    F("company__business_type")
                )
            )
        )
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
    # Product photo link (legacy / external). Uploaded photos are ProductImage rows.
    image_url = models.URLField(max_length=500, blank=True, default="")
    # Seller's stock-keeping code (unique within the business when set). Variants have their own.
    sku = models.CharField(max_length=64, blank=True, default="")

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
            models.UniqueConstraint(
                fields=["company", "sku"],
                condition=~Q(sku=""),
                name="marketplace_product_sku_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"], name="marketplace_product_owner_idx"),
            models.Index(fields=["category", "is_active"], name="marketplace_product_cat_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class PrivateStorage(FileSystemStorage):
    """Uploaded files live OUTSIDE the public media folder (PRIVATE_MEDIA_ROOT, read at use time)
    and are only ever streamed by views that check who is asking (apps.marketplace.uploads)."""

    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


def private_storage():
    return PrivateStorage()


class ProductVariant(BaseModel):
    """A sellable version of a product (size, colour, pack). When a product has active variants
    the buyer picks one, and price and stock are the VARIANT's (price null = the product price)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    # Denormalized from the product so a SKU is unique within the business (database-enforced).
    company = models.ForeignKey(
        MedicalCompany, on_delete=models.CASCADE, related_name="product_variants"
    )
    sku = models.CharField(max_length=64)
    label = models.CharField(max_length=80)  # "Size L", "Pack of 50", "Blue / 120 cm"
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    stock_reserved = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "marketplace_variant"
        ordering = ["sort_order", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "sku"], name="marketplace_variant_sku"),
            models.UniqueConstraint(fields=["product", "label"], name="marketplace_variant_label"),
            models.CheckConstraint(
                condition=(Q(stock_quantity__isnull=True) & Q(stock_reserved=0))
                | Q(stock_reserved__lte=models.F("stock_quantity")),
                name="marketplace_variant_reserved_le_on_hand",
            ),
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="marketplace_variant_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} {self.label}"

    @property
    def title(self) -> str:  # inventory messages and alerts read `title`
        return f"{self.product.title} — {self.label}"

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.product.price


class ProductImage(BaseModel):
    """A validated product photo (JPEG, PNG or WebP; type sniffed from the bytes, never from the
    name). Stored privately under a random name and served by `product-image` with nosniff."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    file = models.FileField(storage=private_storage, upload_to="product-images/", max_length=200)
    content_type = models.CharField(max_length=32)
    size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    alt_text = models.CharField(max_length=150, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "marketplace_product_image"
        ordering = ["sort_order", "created_at", "id"]


class SellerDocument(BaseModel):
    """A verification document a seller submits (licence, registration). Private: only the
    business's owner/managers and Racheeta administrators can open it."""

    company = models.ForeignKey(MedicalCompany, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=32, choices=SellerDocumentKind.choices)
    file = models.FileField(storage=private_storage, upload_to="seller-documents/", max_length=200)
    original_name = models.CharField(max_length=150)  # display only, sanitized
    content_type = models.CharField(max_length=32)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    reference_number = models.CharField(max_length=60, blank=True, default="")
    expires_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=DocumentStatus.choices, default=DocumentStatus.PENDING
    )
    review_note = models.CharField(max_length=300, blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "marketplace_seller_document"
        ordering = ["-created_at", "id"]
        indexes = [models.Index(fields=["company", "status"], name="marketplace_doc_status_idx")]


class ShippingRate(BaseModel):
    """The seller's delivery fee to one governorate (overrides the default fee)."""

    company = models.ForeignKey(
        MedicalCompany, on_delete=models.CASCADE, related_name="shipping_rates"
    )
    governorate = models.ForeignKey(Governorate, on_delete=models.PROTECT, related_name="+")
    fee = models.DecimalField(max_digits=12, decimal_places=2)
    min_days = models.PositiveSmallIntegerField(default=1)
    max_days = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "marketplace_shipping_rate"
        ordering = ["governorate__name_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "governorate"], name="marketplace_shipping_one_per_region"
            ),
            models.CheckConstraint(condition=Q(fee__gte=0), name="marketplace_shipping_fee_ge0"),
            models.CheckConstraint(
                condition=Q(max_days__gte=models.F("min_days")),
                name="marketplace_shipping_days_order",
            ),
        ]
