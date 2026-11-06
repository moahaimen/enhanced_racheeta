from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from apps.core.phone import IraqiPhoneField
from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer

from .models import (
    MedicalCompany,
    Product,
    ProductCategory,
    ProductImage,
    ProductVariant,
    SellerDocument,
    ShippingRate,
)
from .types import (
    IDENTITY_LOCKED_STATUSES,
    REQUIRED_DOCUMENTS,
    VERIFICATION_DECISION_CHOICES,
    SellerDocumentKind,
    TaxMode,
)

# Keys a company must never be able to send: targeting is derived from the
# category by the backend, publication goes through the activate/deactivate
# endpoints, and verification is an administrator decision.
CLIENT_FORBIDDEN_PRODUCT_FIELDS = frozenset(
    {
        "company",
        "company_id",
        "is_active",
        "provider_type",
        "provider_types",
        "specialty",
        "specialties",
        "specialty_ids",
        "audience",
        "audiences",
        "target",
        "targets",
        "targeting",
    }
)
CLIENT_FORBIDDEN_COMPANY_FIELDS = frozenset(
    {
        "account",
        "verification_status",
        "verification_note",
        "verification_requested_at",
        "verification_changed_at",
        "verified_at",
        "store_status",
        "facility",
        "facility_id",
    }
)


class _ForbidFieldsMixin:
    forbidden: frozenset[str] = frozenset()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        sent = set(getattr(self, "initial_data", {}) or {})
        bad = sorted(sent & self.forbidden)
        if bad:
            raise serializers.ValidationError(
                {f: ["This field cannot be set by a client."] for f in bad},
                code="field_not_allowed",
            )
        return attrs


# ---- categories --------------------------------------------------------------------


class ProductCategorySerializer(serializers.ModelSerializer):
    parent_id = serializers.UUIDField(read_only=True, allow_null=True)
    can_publish = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "slug",
            "name_ar",
            "name_en",
            "parent_id",
            "sort_order",
            "can_publish",
            "consumer_allowed",
        )
        read_only_fields = fields

    def get_can_publish(self, obj) -> bool:
        """Whether a product in this category can currently be published: the
        category is active and has at least one active audience rule. Derived
        by the backend at read time; publication is still decided server-side."""
        # Read strictly from the SQL annotation (ProductCategoryQuerySet
        # .with_publishability): a queryset that forgot it fails loudly instead
        # of querying per category.
        return obj.can_publish


# ---- company -----------------------------------------------------------------------


class CompanySummarySerializer(serializers.ModelSerializer):
    """What a provider sees about the publisher of a product."""

    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True, allow_null=True)

    class Meta:
        model = MedicalCompany
        fields = (
            "id",
            "name",
            "business_type",
            "governorate",
            "city",
            "website",
            "public_email",
            "phone",
        )
        read_only_fields = fields


class CompanyOwnerSerializer(serializers.ModelSerializer):
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True, allow_null=True)
    can_publish = serializers.BooleanField(read_only=True)
    can_sell = serializers.BooleanField(read_only=True)
    identity_locked = serializers.SerializerMethodField()
    facility_id = serializers.UUIDField(read_only=True, allow_null=True)
    required_documents = serializers.SerializerMethodField()
    missing_documents = serializers.SerializerMethodField()

    def get_identity_locked(self, obj) -> bool:
        """Name, location and website are frozen while review is pending or granted."""
        return obj.verification_status in IDENTITY_LOCKED_STATUSES

    def get_required_documents(self, obj) -> list[str]:
        return list(REQUIRED_DOCUMENTS.get(obj.business_type, ()))

    def get_missing_documents(self, obj) -> list[str]:
        """Required kinds without an APPROVED document (the store cannot be activated yet)."""
        return obj.missing_documents()

    class Meta:
        model = MedicalCompany
        fields = (
            "id",
            "name",
            "business_type",
            "description",
            "phone",
            "public_email",
            "website",
            "governorate",
            "city",
            "address",
            "verification_status",
            "verification_note",
            "verification_requested_at",
            "verification_changed_at",
            "verified_at",
            "can_publish",
            "can_sell",
            "identity_locked",
            "facility_id",
            "store_status",
            "store_status_changed_at",
            "required_documents",
            "missing_documents",
            "tax_mode",
            "tax_rate",
            "tax_label",
            "tax_registration_number",
            "default_shipping_fee",
            "free_shipping_over",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CompanyWriteSerializer(_ForbidFieldsMixin, serializers.ModelSerializer):
    phone = IraqiPhoneField(required=False, allow_blank=True)

    forbidden = CLIENT_FORBIDDEN_COMPANY_FIELDS
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )

    class Meta:
        model = MedicalCompany
        fields = (
            "name",
            "business_type",
            "description",
            "phone",
            "public_email",
            "website",
            "governorate",
            "city",
            "address",
        )
        extra_kwargs = {"name": {"required": True}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        governorate = attrs.get("governorate", getattr(self.instance, "governorate", None))
        city = attrs.get(
            "city", getattr(self.instance, "city", None) if "city" not in attrs else None
        )
        if "city" in attrs:
            city = attrs["city"]
        if city is not None and governorate is not None and city.governorate_id != governorate.pk:
            raise serializers.ValidationError(
                {"city": ["This city does not belong to the selected governorate."]}
            )
        return attrs


class CompanyVerificationDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=VERIFICATION_DECISION_CHOICES)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class CompanyAdminSerializer(CompanyOwnerSerializer):
    account_email = serializers.EmailField(source="account.email", read_only=True)

    class Meta(CompanyOwnerSerializer.Meta):
        fields = CompanyOwnerSerializer.Meta.fields + ("account_email",)
        read_only_fields = fields


class CompanyDashboardSerializer(serializers.Serializer):
    verification_status = serializers.CharField()
    can_publish = serializers.BooleanField()
    can_sell = serializers.BooleanField()
    store_status = serializers.CharField()
    products_total = serializers.IntegerField()
    products_active = serializers.IntegerField()
    products_inactive = serializers.IntegerField()
    products_exposable = serializers.IntegerField()


# ---- store settings, documents, delivery -------------------------------------------


class StoreSettingsSerializer(serializers.Serializer):
    """Seller-declared tax treatment and delivery defaults (validated again in the service)."""

    tax_mode = serializers.ChoiceField(choices=TaxMode.choices, required=False)
    tax_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=30, required=False
    )
    tax_label = serializers.CharField(max_length=40, required=False, allow_blank=True)
    tax_registration_number = serializers.CharField(max_length=40, required=False, allow_blank=True)
    default_shipping_fee = serializers.DecimalField(
        max_digits=12, decimal_places=0, min_value=0, required=False, allow_null=True
    )
    free_shipping_over = serializers.DecimalField(
        max_digits=12, decimal_places=0, min_value=0, required=False, allow_null=True
    )


class PharmacyStoreSerializer(serializers.Serializer):
    """Opening a pharmacy's store: everything else comes from the pharmacy's own profile."""

    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    public_email = serializers.EmailField(required=False, allow_blank=True)


class SellerDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    def get_file_url(self, obj) -> str:
        return reverse("v1:marketplace-document-file", args=[obj.pk])

    class Meta:
        model = SellerDocument
        fields = (
            "id",
            "kind",
            "original_name",
            "content_type",
            "size",
            "sha256",
            "reference_number",
            "expires_on",
            "status",
            "review_note",
            "reviewed_at",
            "created_at",
            "file_url",
        )
        read_only_fields = fields


class SellerDocumentUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=SellerDocumentKind.choices)
    file = serializers.FileField()
    reference_number = serializers.CharField(max_length=60, required=False, allow_blank=True)
    expires_on = serializers.DateField(required=False, allow_null=True)


class AdminSellerDocumentSerializer(SellerDocumentSerializer):
    company_id = serializers.UUIDField(read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    business_type = serializers.CharField(source="company.business_type", read_only=True)

    def get_file_url(self, obj) -> str:
        return reverse("v1:admin-marketplace-document-file", args=[obj.pk])

    class Meta(SellerDocumentSerializer.Meta):
        fields = SellerDocumentSerializer.Meta.fields + (
            "company_id",
            "company_name",
            "business_type",
        )
        read_only_fields = fields


class DocumentDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ShippingRateSerializer(serializers.ModelSerializer):
    governorate = GovernorateSerializer(read_only=True)

    class Meta:
        model = ShippingRate
        fields = ("id", "governorate", "fee", "min_days", "max_days", "is_active")
        read_only_fields = fields


class ShippingRateWriteSerializer(serializers.Serializer):
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    fee = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0)
    min_days = serializers.IntegerField(min_value=0, max_value=60, default=1)
    max_days = serializers.IntegerField(min_value=0, max_value=60, default=3)
    is_active = serializers.BooleanField(default=True)


class StoreStatusSerializer(serializers.Serializer):
    active = serializers.BooleanField()


# ---- variants and photos -------------------------------------------------------------


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return reverse("v1:marketplace-product-image", args=[obj.pk])

    class Meta:
        model = ProductImage
        fields = ("id", "url", "width", "height", "alt_text", "sort_order")
        read_only_fields = fields


class VariantOwnerSerializer(serializers.ModelSerializer):
    available = serializers.SerializerMethodField()

    def get_available(self, obj) -> int | None:
        if obj.stock_quantity is None:
            return None
        return obj.stock_quantity - obj.stock_reserved

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "label",
            "price",
            "stock_quantity",
            "stock_reserved",
            "available",
            "reorder_threshold",
            "is_active",
            "sort_order",
        )
        read_only_fields = fields


class VariantWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64, required=False)
    label = serializers.CharField(max_length=80, required=False)
    price = serializers.DecimalField(
        max_digits=12, decimal_places=0, min_value=0, required=False, allow_null=True
    )
    stock_quantity = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    reorder_threshold = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(min_value=0, max_value=999, required=False)


class VariantPublicSerializer(serializers.ModelSerializer):
    """What a buyer sees of a variant: its price and whether it can be ordered (no counts)."""

    price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()

    def get_price(self, obj) -> str | None:
        price = obj.effective_price
        return None if price is None else f"{price:.2f}"

    def _left(self, obj):
        return None if obj.stock_quantity is None else obj.stock_quantity - obj.stock_reserved

    def get_in_stock(self, obj) -> bool:
        left = self._left(obj)
        return left is None or left > 0

    def get_low_stock(self, obj) -> bool:
        left = self._left(obj)
        return left is not None and 0 < left <= LOW_STOCK_HINT

    class Meta:
        model = ProductVariant
        fields = ("id", "sku", "label", "price", "in_stock", "low_stock")
        read_only_fields = fields


class ImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    alt_text = serializers.CharField(max_length=150, required=False, allow_blank=True)


def _active_variants(obj):
    return [v for v in obj.variants.all() if v.is_active]


# ---- products ----------------------------------------------------------------------


class ProductPublicSerializer(serializers.ModelSerializer):
    """A targeted provider's view of a product."""

    category = ProductCategorySerializer(read_only=True)
    company = CompanySummarySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()
    can_buy_directly = serializers.SerializerMethodField()

    def get_variants(self, obj) -> list[dict]:
        return VariantPublicSerializer(_active_variants(obj), many=True).data

    def get_can_buy_directly(self, obj) -> bool:
        """UI hint only (checkout re-decides): a priced product in an explicit
        B2B_VERIFIED_ONLY category; everything else is by quotation."""
        return bool(
            obj.price is not None
            and not obj.is_restricted
            and obj.category.compliance_class == "B2B_VERIFIED_ONLY"
        )

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "description",
            "brand",
            "model_name",
            "price",
            "currency",
            "image_url",
            "images",
            "variants",
            "can_buy_directly",
            "sku",
            "sale_channel",
            "category",
            "company",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProductOwnerSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = VariantOwnerSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "description",
            "brand",
            "model_name",
            "price",
            "currency",
            "image_url",
            "sale_channel",
            "is_restricted",
            "stock_quantity",
            "stock_reserved",
            "reorder_threshold",
            "sku",
            "images",
            "variants",
            "category",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProductWriteSerializer(_ForbidFieldsMixin, serializers.ModelSerializer):
    """Create (POST) and partial update (PATCH) by the owning company. The
    category is the ONLY targeting input; audiences derive from it server-side."""

    forbidden = CLIENT_FORBIDDEN_PRODUCT_FIELDS
    category = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.filter(is_active=True)
    )
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, allow_null=True, required=False
    )

    class Meta:
        model = Product
        fields = (
            "category",
            "title",
            "description",
            "brand",
            "model_name",
            "price",
            "currency",
            "image_url",
            "sale_channel",
            "is_restricted",
            "stock_quantity",
            "sku",
        )
        extra_kwargs = {
            "sku": {"required": False},
            "title": {"required": True},
            "currency": {"required": False},
            "sale_channel": {"required": False},
            "is_restricted": {"required": False},
            "stock_quantity": {"required": False},
            "image_url": {"required": False},
        }

    def validate_currency(self, value: str) -> str:
        if value not in settings.RACHEETA["CURRENCIES"]:
            raise serializers.ValidationError("Unsupported currency.")
        return value


LOW_STOCK_HINT = 5


class StoreCategorySerializer(serializers.ModelSerializer):
    """Public store category: names and the buyer notice (no catalogue-governance flags)."""

    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "slug",
            "name_ar",
            "name_en",
            "buyer_notice_ar",
            "buyer_notice_en",
            "max_order_quantity",
        )
        read_only_fields = fields


class StoreProductSerializer(serializers.ModelSerializer):
    """The public store's view of a consumer product (no professional catalogue data,
    no exact stock figure: only whether it can be ordered)."""

    category = StoreCategorySerializer(read_only=True)
    company = CompanySummarySerializer(read_only=True)
    in_stock = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()

    def get_variants(self, obj) -> list[dict]:
        return VariantPublicSerializer(_active_variants(obj), many=True).data

    def get_in_stock(self, obj) -> bool:
        variants = _active_variants(obj)
        if variants:
            return any(
                v.stock_quantity is None or v.stock_quantity > v.stock_reserved for v in variants
            )
        return bool(obj.stock_quantity)

    def get_low_stock(self, obj) -> bool:
        """Only a hint ("few left"); the exact quantity is the business's own data."""
        if _active_variants(obj):
            return False
        return obj.stock_quantity is not None and 0 < obj.stock_quantity <= LOW_STOCK_HINT

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "description",
            "brand",
            "model_name",
            "price",
            "currency",
            "image_url",
            "images",
            "variants",
            "in_stock",
            "low_stock",
            "category",
            "company",
        )
        read_only_fields = fields


class PaginatedProductOwnerSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ProductOwnerSerializer(many=True)
