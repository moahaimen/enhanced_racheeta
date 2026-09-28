from django.conf import settings
from rest_framework import serializers

from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer

from .models import MedicalCompany, Product, ProductCategory
from .types import IDENTITY_LOCKED_STATUSES, VERIFICATION_DECISION_CHOICES

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

    class Meta:
        model = ProductCategory
        fields = ("id", "slug", "name_ar", "name_en", "parent_id", "sort_order")
        read_only_fields = fields


# ---- company -----------------------------------------------------------------------


class CompanySummarySerializer(serializers.ModelSerializer):
    """What a provider sees about the publisher of a product."""

    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True, allow_null=True)

    class Meta:
        model = MedicalCompany
        fields = ("id", "name", "governorate", "city", "website", "public_email", "phone")
        read_only_fields = fields


class CompanyOwnerSerializer(serializers.ModelSerializer):
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True, allow_null=True)
    can_publish = serializers.BooleanField(read_only=True)
    identity_locked = serializers.SerializerMethodField()

    def get_identity_locked(self, obj) -> bool:
        """Name, location and website are frozen while review is pending or granted."""
        return obj.verification_status in IDENTITY_LOCKED_STATUSES

    class Meta:
        model = MedicalCompany
        fields = (
            "id",
            "name",
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
            "identity_locked",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CompanyWriteSerializer(_ForbidFieldsMixin, serializers.ModelSerializer):
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
    products_total = serializers.IntegerField()
    products_active = serializers.IntegerField()
    products_inactive = serializers.IntegerField()
    products_exposable = serializers.IntegerField()


# ---- products ----------------------------------------------------------------------


class ProductPublicSerializer(serializers.ModelSerializer):
    """A targeted provider's view of a product."""

    category = ProductCategorySerializer(read_only=True)
    company = CompanySummarySerializer(read_only=True)

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
            "category",
            "company",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProductOwnerSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)

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
        fields = ("category", "title", "description", "brand", "model_name", "price", "currency")
        extra_kwargs = {"title": {"required": True}, "currency": {"required": False}}

    def validate_currency(self, value: str) -> str:
        if value not in settings.RACHEETA["CURRENCIES"]:
            raise serializers.ValidationError("Unsupported currency.")
        return value


class PaginatedProductOwnerSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ProductOwnerSerializer(many=True)
