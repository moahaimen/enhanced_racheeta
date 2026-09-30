from decimal import Decimal

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer

from .models import PropertyListing, RealEstateSeller
from .types import (
    EMAIL_METHODS,
    PHONE_METHODS,
    ContactMethod,
    PropertyType,
    SuitableUse,
    TransactionType,
)

# Keys a client must never be able to send: ownership, lifecycle, derived state,
# targeting/payment/advertising (Phase 8) and image fields (deferred until
# production media storage exists).
CLIENT_FORBIDDEN_SELLER_FIELDS = frozenset(
    {
        "id",
        "account",
        "account_id",
        "user",
        "email",
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
        "verification_status",
        "verified",
        "created_at",
        "updated_at",
    }
)
CLIENT_FORBIDDEN_LISTING_FIELDS = frozenset(
    {
        "id",
        "seller",
        "seller_id",
        "owner",
        "owner_id",
        "account",
        "account_id",
        "publication_status",
        "published_at",
        "is_public",
        "is_expired",
        "created_at",
        "updated_at",
        "audience",
        "audiences",
        "target",
        "targets",
        "targeting",
        "provider_type",
        "provider_types",
        "specialty",
        "specialties",
        "campaign",
        "campaign_id",
        "featured",
        "is_featured",
        "boosted",
        "sponsored",
        "payment",
        "payment_id",
        "images",
        "image",
        "image_url",
        "gallery",
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


# ---- seller ------------------------------------------------------------------------


class SellerSummarySerializer(serializers.ModelSerializer):
    """The public face of a seller: never contact data or account identity."""

    class Meta:
        model = RealEstateSeller
        fields = ("id", "display_name", "seller_type")
        read_only_fields = fields


class SellerOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealEstateSeller
        fields = (
            "id",
            "seller_type",
            "display_name",
            "about",
            "phone",
            "public_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SellerWriteSerializer(_ForbidFieldsMixin, serializers.ModelSerializer):
    forbidden = CLIENT_FORBIDDEN_SELLER_FIELDS

    class Meta:
        model = RealEstateSeller
        fields = ("seller_type", "display_name", "about", "phone", "public_email")
        extra_kwargs = {"seller_type": {"required": True}, "display_name": {"required": True}}


# ---- listings ----------------------------------------------------------------------


class _ListingBase(serializers.ModelSerializer):
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True, allow_null=True)
    suitable_uses = serializers.ListField(
        child=serializers.ChoiceField(choices=SuitableUse.choices),
        source="suitable_use_codes",
        read_only=True,
    )


class PropertyListingPublicSerializer(_ListingBase):
    """What anyone sees of a publicly visible listing. Only the contact values
    the listing's contact method makes public are returned; the seller is a
    summary (profile id, display name, type) — never account identity."""

    seller = SellerSummarySerializer(read_only=True)
    contact_phone = serializers.SerializerMethodField()
    contact_email = serializers.SerializerMethodField()

    class Meta:
        model = PropertyListing
        fields = (
            "id",
            "title",
            "description",
            "property_type",
            "transaction_type",
            "governorate",
            "city",
            "district",
            "latitude",
            "longitude",
            "area_sqm",
            "price",
            "currency",
            "suitable_uses",
            "facilities",
            "contact_method",
            "contact_phone",
            "contact_email",
            "seller",
            "published_at",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_contact_phone(self, obj):
        return obj.contact_phone if obj.contact_method in PHONE_METHODS else None

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_contact_email(self, obj):
        return obj.contact_email if obj.contact_method in EMAIL_METHODS else None


class PropertyListingOwnerSerializer(_ListingBase):
    """The owner's view: stored contact values, lifecycle and derived state."""

    is_public = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = PropertyListing
        fields = (
            "id",
            "title",
            "description",
            "property_type",
            "transaction_type",
            "governorate",
            "city",
            "district",
            "latitude",
            "longitude",
            "area_sqm",
            "price",
            "currency",
            "suitable_uses",
            "facilities",
            "contact_method",
            "contact_phone",
            "contact_email",
            "publication_status",
            "published_at",
            "expires_at",
            "is_public",
            "is_expired",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PropertyListingWriteSerializer(_ForbidFieldsMixin, serializers.ModelSerializer):
    """Create (POST) and partial update (PATCH) by the owning seller. Drafts may
    be incomplete: only the identity of the ad (title, types, governorate) is
    required; completeness is the publication gate's job."""

    forbidden = CLIENT_FORBIDDEN_LISTING_FIELDS
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    property_type = serializers.ChoiceField(choices=PropertyType.choices)
    transaction_type = serializers.ChoiceField(choices=TransactionType.choices)
    contact_method = serializers.ChoiceField(choices=ContactMethod.choices, required=False)
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal(-90),
        max_value=Decimal(90),
        allow_null=True,
        required=False,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal(-180),
        max_value=Decimal(180),
        allow_null=True,
        required=False,
    )
    area_sqm = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        allow_null=True,
        required=False,
    )
    price = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, allow_null=True, required=False
    )
    expires_at = serializers.DateTimeField(allow_null=True, required=False)
    suitable_uses = serializers.ListField(
        child=serializers.ChoiceField(choices=SuitableUse.choices), required=False
    )

    class Meta:
        model = PropertyListing
        fields = (
            "title",
            "description",
            "property_type",
            "transaction_type",
            "governorate",
            "city",
            "district",
            "latitude",
            "longitude",
            "area_sqm",
            "price",
            "currency",
            "facilities",
            "contact_method",
            "contact_phone",
            "contact_email",
            "expires_at",
            "suitable_uses",
        )
        extra_kwargs = {"title": {"required": True}, "currency": {"required": False}}

    def validate_currency(self, value: str) -> str:
        if value not in settings.RACHEETA["CURRENCIES"]:
            raise serializers.ValidationError("Unsupported currency.", code="currency_unsupported")
        return value

    def validate_suitable_uses(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError(
                "Each suitable use can be given once.", code="duplicate_suitable_use"
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        governorate = attrs.get("governorate", getattr(instance, "governorate", None))
        city = attrs["city"] if "city" in attrs else getattr(instance, "city", None)
        if city is not None and governorate is not None and city.governorate_id != governorate.pk:
            raise serializers.ValidationError(
                {"city": ["This city does not belong to the selected governorate."]},
                code="city_mismatch",
            )
        lat = attrs["latitude"] if "latitude" in attrs else getattr(instance, "latitude", None)
        lng = attrs["longitude"] if "longitude" in attrs else getattr(instance, "longitude", None)
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": ["Latitude and longitude must be given together."]},
                code="coordinates_invalid",
            )
        return attrs


class OwnerDashboardSerializer(serializers.Serializer):
    listings_total = serializers.IntegerField()
    listings_draft = serializers.IntegerField()
    listings_published = serializers.IntegerField()
    listings_visible = serializers.IntegerField()
    listings_expired = serializers.IntegerField()
    listings_sale = serializers.IntegerField()
    listings_rent = serializers.IntegerField()


class PaginatedPropertyListingOwnerSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PropertyListingOwnerSerializer(many=True)
