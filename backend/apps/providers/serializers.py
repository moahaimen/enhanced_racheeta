"""Public (read) serializers are separate from owner (write) serializers.
Admin-controlled fields are read-only everywhere except the admin endpoint."""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer
from apps.specialties.models import Specialty
from apps.specialties.serializers import SpecialtySerializer

from .models import ProviderMembership, ProviderProfile, ServiceOffering
from .types import MembershipStatus, ProviderType, VerificationStatus

ADMIN_ONLY_FIELDS = frozenset(
    {
        "verification_status",
        "verification_note",
        "verification_requested_at",
        "verification_changed_at",
        "verified_at",
        "account",
        "id",
    }
)


class ForbidAdminFieldsMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        sent = set(getattr(self, "initial_data", {}) or {})
        forbidden = sorted(sent & ADMIN_ONLY_FIELDS)
        if forbidden:
            raise serializers.ValidationError(
                {f: ["This field cannot be set by a provider."] for f in forbidden},
                code="field_not_allowed",
            )
        return attrs


# ---- services --------------------------------------------------------------


class ServiceOfferingSerializer(serializers.ModelSerializer):
    """Owner view of a service (read + write)."""

    specialty = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True), allow_null=True, required=False
    )

    class Meta:
        model = ServiceOffering
        fields = (
            "id",
            "title",
            "description",
            "specialty",
            "price",
            "currency",
            "duration_minutes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"currency": {"required": False}}

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_duration_minutes(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Duration must be a positive number of minutes.")
        return value

    def validate_currency(self, value: str) -> str:
        value = value.upper()
        if value not in settings.RACHEETA["CURRENCIES"]:
            raise serializers.ValidationError("Unsupported currency.")
        return value

    def validate_title(self, value: str) -> str:
        value = value.strip()
        provider = self.context["provider"]
        qs = ServiceOffering.objects.filter(provider=provider, title=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("You already offer a service with this title.")
        return value


class PublicServiceSerializer(serializers.ModelSerializer):
    specialty = SpecialtySerializer(read_only=True)

    class Meta:
        model = ServiceOffering
        fields = (
            "id",
            "title",
            "description",
            "specialty",
            "price",
            "currency",
            "duration_minutes",
        )
        read_only_fields = fields


# ---- profile: public -------------------------------------------------------


class ProviderCardSerializer(serializers.ModelSerializer):
    """List item for discovery. No ratings: reviews arrive in Phase 4."""

    kind = serializers.CharField(read_only=True)
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    specialties = SpecialtySerializer(many=True, read_only=True)

    class Meta:
        model = ProviderProfile
        fields = (
            "id",
            "provider_type",
            "kind",
            "display_name",
            "governorate",
            "city",
            "specialties",
            "image_url",
        )
        read_only_fields = fields


class RelatedProviderSerializer(serializers.ModelSerializer):
    kind = serializers.CharField(read_only=True)

    class Meta:
        model = ProviderProfile
        fields = ("id", "provider_type", "kind", "display_name", "image_url")
        read_only_fields = fields


class ProviderPublicSerializer(ProviderCardSerializer):
    """Full public detail. `related_providers` are active memberships whose
    counterpart is itself discoverable."""

    services = serializers.SerializerMethodField()
    related_providers = serializers.SerializerMethodField()

    class Meta(ProviderCardSerializer.Meta):
        fields = ProviderCardSerializer.Meta.fields + (
            "about",
            "phone",
            "public_email",
            "website",
            "address",
            "latitude",
            "longitude",
            "services",
            "related_providers",
            "verified_at",
        )
        read_only_fields = fields

    @extend_schema_field(PublicServiceSerializer(many=True))
    def get_services(self, obj):
        # Prefetched as `active_services` by the view.
        items = getattr(obj, "active_services", None)
        if items is None:
            items = obj.services.filter(is_active=True).select_related("specialty")
        return PublicServiceSerializer(items, many=True).data

    @extend_schema_field(RelatedProviderSerializer(many=True))
    def get_related_providers(self, obj):
        items = getattr(obj, "related_profiles", None)
        if items is None:
            items = []
        return RelatedProviderSerializer(items, many=True).data


# ---- profile: owner --------------------------------------------------------


class ProviderOwnerSerializer(serializers.ModelSerializer):
    """What the owner sees: everything, admin fields read-only."""

    kind = serializers.CharField(read_only=True)
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    specialties = SpecialtySerializer(many=True, read_only=True)
    can_change_type = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = (
            "id",
            "provider_type",
            "kind",
            "can_change_type",
            "display_name",
            "about",
            "phone",
            "public_email",
            "website",
            "governorate",
            "city",
            "address",
            "latitude",
            "longitude",
            "image_url",
            "specialties",
            "is_visible",
            "verification_status",
            "verification_note",
            "verification_requested_at",
            "verification_changed_at",
            "verified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_can_change_type(self, obj) -> bool:
        return obj.verification_status != VerificationStatus.VERIFIED


class ProviderWriteSerializer(ForbidAdminFieldsMixin, serializers.ModelSerializer):
    """Create (POST) and partial update (PATCH) by the owner."""

    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    specialty_ids = serializers.PrimaryKeyRelatedField(
        source="specialties",
        queryset=Specialty.objects.filter(is_active=True),
        many=True,
        required=False,
    )

    class Meta:
        model = ProviderProfile
        fields = (
            "provider_type",
            "display_name",
            "about",
            "phone",
            "public_email",
            "website",
            "governorate",
            "city",
            "address",
            "latitude",
            "longitude",
            "image_url",
            "specialty_ids",
            "is_visible",
        )
        extra_kwargs = {
            "provider_type": {"required": True},
            "display_name": {"required": True},
        }

    def validate_provider_type(self, value: str) -> str:
        if value not in ProviderType.values:
            raise serializers.ValidationError("Unknown provider type.")
        instance = self.instance
        if (
            instance is not None
            and value != instance.provider_type
            and instance.verification_status == VerificationStatus.VERIFIED
        ):
            raise serializers.ValidationError(
                "A verified provider cannot change its type. Contact support.",
                code="type_locked",
            )
        return value

    def validate_image_url(self, value: str) -> str:
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("Image URL must use https.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        governorate = attrs.get("governorate", getattr(self.instance, "governorate", None))
        city = (
            attrs.get("city", getattr(self.instance, "city", None))
            if "city" in attrs or self.instance
            else None
        )
        if "city" in attrs:
            city = attrs["city"]
        if city is not None and governorate is not None and city.governorate_id != governorate.pk:
            raise serializers.ValidationError(
                {"city": ["This city does not belong to the selected governorate."]}
            )
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lng = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": ["Latitude and longitude must be given together."]}
            )
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise serializers.ValidationError({"latitude": ["Coordinates are out of range."]})
        return attrs


# ---- memberships -----------------------------------------------------------


class MembershipSerializer(serializers.ModelSerializer):
    practitioner = RelatedProviderSerializer(read_only=True)
    facility = RelatedProviderSerializer(read_only=True)
    my_side = serializers.SerializerMethodField()
    can_accept = serializers.SerializerMethodField()

    class Meta:
        model = ProviderMembership
        fields = (
            "id",
            "practitioner",
            "facility",
            "status",
            "initiated_by",
            "role_title",
            "my_side",
            "can_accept",
            "responded_at",
            "joined_at",
            "ended_at",
            "created_at",
        )
        read_only_fields = fields

    def get_my_side(self, obj) -> str | None:
        me = self.context.get("provider")
        return obj.side_of(me) if me else None

    def get_can_accept(self, obj) -> bool:
        side = self.get_my_side(obj)
        return bool(side and obj.status == MembershipStatus.PENDING and side != obj.initiated_by)


class MembershipCreateSerializer(serializers.Serializer):
    """`counterpart` is the other provider's public id: a facility when the
    caller is a practitioner, a practitioner when the caller is a facility."""

    counterpart = serializers.PrimaryKeyRelatedField(
        queryset=ProviderProfile.objects.discoverable()
    )
    role_title = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


# ---- admin -----------------------------------------------------------------


class VerificationDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            (s, VerificationStatus(s).label)
            for s in (
                VerificationStatus.VERIFIED,
                VerificationStatus.REJECTED,
                VerificationStatus.SUSPENDED,
                VerificationStatus.UNVERIFIED,
            )
        ]
    )
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
