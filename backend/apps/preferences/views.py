from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import FIELDS


class PreferenceSerializer(serializers.Serializer):
    show_sponsored_products = serializers.BooleanField(required=False)
    real_estate_promotions = serializers.BooleanField(required=False)
    job_alerts = serializers.BooleanField(required=False)
    offers_and_news = serializers.BooleanField(required=False)
    channel_in_app = serializers.BooleanField(required=False)
    channel_email = serializers.BooleanField(required=False)
    channel_push = serializers.BooleanField(required=False)

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(FIELDS)
        if unknown:
            raise serializers.ValidationError({k: "Unknown field." for k in sorted(unknown)})
        return attrs


class MyPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["preferences"],
        summary="My marketing preferences (display + outreach consent)",
        responses=PreferenceSerializer,
    )
    def get(self, request):
        return Response(services.get(request.user))

    @extend_schema(
        tags=["preferences"],
        summary="Change my marketing preferences",
        request=PreferenceSerializer,
        responses=PreferenceSerializer,
    )
    def patch(self, request):
        serializer = PreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(services.update(request.user, serializer.validated_data))
