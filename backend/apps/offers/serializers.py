from django.utils import timezone
from rest_framework import serializers

from .models import Offer


class PublicOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = (
            "id",
            "service_title_snapshot",
            "title",
            "description",
            "original_price_snapshot",
            "offer_price",
            "currency_snapshot",
            "starts_at",
            "ends_at",
        )
        read_only_fields = fields


class OfferOwnerSerializer(PublicOfferSerializer):
    service_id = serializers.UUIDField(read_only=True)

    class Meta(PublicOfferSerializer.Meta):
        fields = PublicOfferSerializer.Meta.fields + (
            "service_id",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OfferCreateSerializer(serializers.Serializer):
    service = serializers.UUIDField()
    title = serializers.CharField(max_length=150)
    description = serializers.CharField(
        max_length=1000,
        allow_blank=True,
        required=False,
        default="",
    )
    offer_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError(
                {"ends_at": ["End time must be after start time."]}
            )
        if attrs["ends_at"] <= timezone.now():
            raise serializers.ValidationError({"ends_at": ["Offer must end in the future."]})
        return attrs


class OfferUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(
        max_length=1000,
        allow_blank=True,
        required=False,
    )
    offer_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    is_active = serializers.BooleanField(required=False)
