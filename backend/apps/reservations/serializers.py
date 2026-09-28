from rest_framework import serializers

from apps.accounts.models import Account
from apps.providers.serializers import PublicServiceSerializer, RelatedProviderSerializer

from .models import AvailabilitySlot, Reservation, ReservationTransition
from .types import ReservationStatus


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    provider = RelatedProviderSerializer(read_only=True)
    service = PublicServiceSerializer(read_only=True)

    class Meta:
        model = AvailabilitySlot
        fields = (
            "id",
            "provider",
            "service",
            "starts_at",
            "ends_at",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class PaginatedAvailabilitySlotSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AvailabilitySlotSerializer(many=True)


class AvailabilitySlotCreateSerializer(serializers.Serializer):
    service = serializers.UUIDField()
    starts_at = serializers.DateTimeField()


class AvailabilityQuerySerializer(serializers.Serializer):
    service = serializers.UUIDField(required=False)
    from_at = serializers.DateTimeField(required=False)
    to_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("from_at")
        end = attrs.get("to_at")
        if start and end and start >= end:
            raise serializers.ValidationError({"to": ["Must be later than from."]})
        return attrs


class ReservationTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationTransition
        fields = ("from_status", "to_status", "reason", "created_at")
        read_only_fields = fields


class PatientSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ("id", "full_name")
        read_only_fields = fields


class ReservationPatientSerializer(serializers.ModelSerializer):
    provider_id = serializers.UUIDField(read_only=True)
    service_id = serializers.UUIDField(read_only=True)
    availability_slot_id = serializers.UUIDField(read_only=True)
    transitions = ReservationTransitionSerializer(many=True, read_only=True)

    class Meta:
        model = Reservation
        fields = (
            "id",
            "provider_id",
            "provider_name_snapshot",
            "service_id",
            "service_title_snapshot",
            "availability_slot_id",
            "price_snapshot",
            "currency_snapshot",
            "duration_minutes_snapshot",
            "starts_at",
            "ends_at",
            "status",
            "status_changed_at",
            "patient_note",
            "transitions",
            "created_at",
        )
        read_only_fields = fields


class ReservationProviderSerializer(ReservationPatientSerializer):
    patient = PatientSummarySerializer(read_only=True)

    class Meta(ReservationPatientSerializer.Meta):
        fields = ("patient",) + ReservationPatientSerializer.Meta.fields


class ReservationCreateSerializer(serializers.Serializer):
    availability_slot = serializers.UUIDField()
    patient_note = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
    )


class ReservationCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


PROVIDER_TARGETS = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.REJECTED,
    ReservationStatus.CANCELLED,
    ReservationStatus.COMPLETED,
    ReservationStatus.NO_SHOW,
)


class ProviderTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PROVIDER_TARGETS)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
