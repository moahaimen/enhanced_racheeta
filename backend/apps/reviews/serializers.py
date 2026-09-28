from rest_framework import serializers

from .models import Review


class ReviewCreateSerializer(serializers.Serializer):
    reservation = serializers.UUIDField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(
        max_length=1000,
        allow_blank=True,
        required=False,
        default="",
    )


class PublicReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            "id",
            "provider_name_snapshot",
            "service_title_snapshot",
            "rating",
            "comment",
            "created_at",
        )
        read_only_fields = fields


class MyReviewSerializer(PublicReviewSerializer):
    reservation_id = serializers.UUIDField(read_only=True)
    provider_id = serializers.UUIDField(allow_null=True, read_only=True)

    class Meta(PublicReviewSerializer.Meta):
        fields = PublicReviewSerializer.Meta.fields + ("reservation_id", "provider_id")
        read_only_fields = fields
