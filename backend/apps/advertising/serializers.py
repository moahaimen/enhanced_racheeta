from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.geography.models import Governorate
from apps.marketplace.models import Product
from apps.marketplace.serializers import ProductPublicSerializer
from apps.providers.types import ProviderType
from apps.specialties.models import Specialty
from apps.specialties.serializers import SpecialtySerializer

from .models import AdvertisingCampaign, CampaignPayment
from .types import PaymentMethod

# Keys a company must never be able to send: lifecycle, money, ownership, payment
# proof and verification are all server-owned (field_not_allowed).
CLIENT_FORBIDDEN_CAMPAIGN_FIELDS = frozenset(
    {
        "id",
        "company",
        "company_id",
        "status",
        "payment",
        "payment_status",
        "is_paid",
        "paid",
        "verified",
        "verified_at",
        "verified_by",
        "amount",
        "quoted_amount",
        "daily_rate",
        "quoted_daily_rate",
        "quoted_days",
        "quoted_currency",
        "quoted_at",
        "currency",
        "price",
        "total",
        "quote",
        "rate",
        "reference",
        "payment_reference",
        "is_live",
        "is_ended",
        "created_at",
        "updated_at",
    }
)
ADMIN_FORBIDDEN_DECISION_FIELDS = frozenset(
    {
        "amount",
        "currency",
        "status",
        "payment_status",
        "quoted_amount",
        "quoted_daily_rate",
        "quoted_days",
        "company",
        "company_id",
        "product",
        "product_id",
        "verified_by",
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


# ---- shared nested pieces -----------------------------------------------------------------


class CampaignGovernorateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Governorate
        fields = ("id", "slug", "name_ar", "name_en", "is_active")
        read_only_fields = fields


class CampaignProductSerializer(serializers.ModelSerializer):
    """The company's own view of the product a campaign promotes."""

    category = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "title", "brand", "model_name", "is_active", "category")
        read_only_fields = fields

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "slug": {"type": "string"},
                "name_ar": {"type": "string"},
                "name_en": {"type": "string"},
            },
            "required": ["id", "slug", "name_ar", "name_en"],
        }
    )
    def get_category(self, obj):
        c = obj.category
        return {"id": c.pk, "slug": c.slug, "name_ar": c.name_ar, "name_en": c.name_en}


class QuoteSnapshotSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    daily_rate = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    currency = serializers.CharField()
    quoted_at = serializers.DateTimeField()


class OwnerPaymentSerializer(serializers.ModelSerializer):
    """What a company may know about its payment: never the admin note or the verifier."""

    class Meta:
        model = CampaignPayment
        fields = (
            "status",
            "amount",
            "currency",
            "method",
            "reference",
            "created_at",
            "verified_at",
        )
        read_only_fields = fields


class _CampaignTargeting(serializers.ModelSerializer):
    provider_types = serializers.SerializerMethodField()
    specialties = serializers.SerializerMethodField()
    governorates = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()
    is_live = serializers.BooleanField(read_only=True)
    is_ended = serializers.BooleanField(read_only=True)

    @extend_schema_field(
        serializers.ListField(child=serializers.ChoiceField(choices=ProviderType.choices))
    )
    def get_provider_types(self, obj):
        return sorted(row.provider_type for row in obj.target_provider_types.all())

    @extend_schema_field(SpecialtySerializer(many=True))
    def get_specialties(self, obj):
        rows = sorted((row.specialty for row in obj.target_specialties.all()), key=lambda s: s.slug)
        return SpecialtySerializer(rows, many=True).data

    @extend_schema_field(CampaignGovernorateSerializer(many=True))
    def get_governorates(self, obj):
        rows = sorted(
            (row.governorate for row in obj.target_governorates.all()), key=lambda g: g.slug
        )
        return CampaignGovernorateSerializer(rows, many=True).data

    @extend_schema_field(QuoteSnapshotSerializer(allow_null=True))
    def get_quote(self, obj):
        if obj.quoted_amount is None:
            return None
        return QuoteSnapshotSerializer(
            {
                "days": obj.quoted_days,
                "daily_rate": obj.quoted_daily_rate,
                "amount": obj.quoted_amount,
                "currency": obj.quoted_currency,
                "quoted_at": obj.quoted_at,
            }
        ).data


# ---- company -------------------------------------------------------------------------------


class CampaignOwnerSerializer(_CampaignTargeting):
    product = CampaignProductSerializer(read_only=True)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = AdvertisingCampaign
        fields = (
            "id",
            "name",
            "product",
            "starts_on",
            "ends_on",
            "status",
            "provider_types",
            "specialties",
            "governorates",
            "quote",
            "payment",
            "is_live",
            "is_ended",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(OwnerPaymentSerializer(allow_null=True))
    def get_payment(self, obj):
        payment = getattr(obj, "payment", None)
        return OwnerPaymentSerializer(payment).data if payment is not None else None


class CampaignWriteSerializer(_ForbidFieldsMixin, serializers.Serializer):
    """Create (POST) and partial update (PATCH) of a DRAFT. The company is the
    caller's own; the product must be one of its products; nothing commercial is accepted."""

    forbidden = CLIENT_FORBIDDEN_CAMPAIGN_FIELDS
    name = serializers.CharField(max_length=150)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.none())
    starts_on = serializers.DateField(allow_null=True, required=False)
    ends_on = serializers.DateField(allow_null=True, required=False)
    provider_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ProviderType.choices), required=False
    )
    specialties = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True), many=True, required=False
    )
    governorates = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True), many=True, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        if company is not None:  # only the caller's own products can be chosen
            self.fields["product"].queryset = Product.objects.filter(company=company)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        starts = (
            attrs["starts_on"] if "starts_on" in attrs else getattr(instance, "starts_on", None)
        )
        ends = attrs["ends_on"] if "ends_on" in attrs else getattr(instance, "ends_on", None)
        if starts is not None and ends is not None and ends < starts:
            raise serializers.ValidationError(
                {"ends_on": ["The end date cannot be before the start date."]}, code="dates_invalid"
            )
        for key in ("provider_types", "specialties", "governorates"):
            values = attrs.get(key)
            if values is not None and len(set(map(str, values))) != len(values):
                raise serializers.ValidationError(
                    {key: ["Each target can be chosen once."]}, code="duplicate_target"
                )
        return attrs


class QuoteDatesSerializer(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class QuoteResponseSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    daily_rate = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=16, decimal_places=2)
    currency = serializers.CharField()


class CampaignDashboardSerializer(serializers.Serializer):
    campaigns_total = serializers.IntegerField()
    campaigns_draft = serializers.IntegerField()
    campaigns_pending_payment = serializers.IntegerField()
    campaigns_active = serializers.IntegerField()
    campaigns_live = serializers.IntegerField()
    campaigns_ended = serializers.IntegerField()
    campaigns_rejected = serializers.IntegerField()
    campaigns_cancelled = serializers.IntegerField()


class PaginatedCampaignOwnerSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CampaignOwnerSerializer(many=True)


# ---- providers -----------------------------------------------------------------------------


class SponsoredCampaignSerializer(serializers.ModelSerializer):
    """What an eligible provider sees: the existing product (organic representation) and
    the window — never payment, price, notes or lifecycle internals."""

    sponsored = serializers.SerializerMethodField()
    product = ProductPublicSerializer(read_only=True)

    class Meta:
        model = AdvertisingCampaign
        fields = ("id", "sponsored", "starts_on", "ends_on", "product")
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_sponsored(self, obj) -> bool:
        return True


# ---- administrators ------------------------------------------------------------------------


class AdminPaymentSerializer(serializers.ModelSerializer):
    verified_by_email = serializers.EmailField(
        source="verified_by.email", read_only=True, default=None
    )

    class Meta:
        model = CampaignPayment
        fields = (
            "status",
            "amount",
            "currency",
            "method",
            "reference",
            "admin_note",
            "verified_by_email",
            "verified_at",
            "created_at",
        )
        read_only_fields = fields


class AdminCompanySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    account_email = serializers.EmailField(source="account.email")


class CampaignAdminSerializer(_CampaignTargeting):
    company = AdminCompanySerializer(read_only=True)
    product = CampaignProductSerializer(read_only=True)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = AdvertisingCampaign
        fields = (
            "id",
            "name",
            "company",
            "product",
            "starts_on",
            "ends_on",
            "status",
            "provider_types",
            "specialties",
            "governorates",
            "quote",
            "payment",
            "is_live",
            "is_ended",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(AdminPaymentSerializer(allow_null=True))
    def get_payment(self, obj):
        payment = getattr(obj, "payment", None)
        return AdminPaymentSerializer(payment).data if payment is not None else None


class PaymentVerificationSerializer(_ForbidFieldsMixin, serializers.Serializer):
    """The administrator's confirmation: how it was paid and the external reference.
    The amount is the campaign's own quote — it is never an input."""

    forbidden = ADMIN_FORBIDDEN_DECISION_FIELDS
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class PaymentRejectionSerializer(_ForbidFieldsMixin, serializers.Serializer):
    forbidden = ADMIN_FORBIDDEN_DECISION_FIELDS
    reason = serializers.CharField(max_length=2000)
