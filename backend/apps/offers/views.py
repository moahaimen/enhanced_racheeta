from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.models import ProviderProfile
from apps.providers.permissions import HasProviderProfile

from . import services
from .models import Offer
from .serializers import (
    OfferCreateSerializer,
    OfferOwnerSerializer,
    OfferUpdateSerializer,
    PaginatedOfferOwnerSerializer,
    PublicOfferSerializer,
)


class OfferAPIError(APIException):
    status_code = status.HTTP_409_CONFLICT


STATUS_FOR_CODE = {
    "service_unavailable": status.HTTP_409_CONFLICT,
    "invalid_offer": status.HTTP_400_BAD_REQUEST,
    "not_found": status.HTTP_404_NOT_FOUND,
}


def raise_api(exc: services.OfferError):
    err = OfferAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


@extend_schema(tags=["offers"], summary="Public active offers for a provider")
class PublicProviderOfferListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicOfferSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Offer.objects.none()
        provider = get_object_or_404(
            ProviderProfile.objects.discoverable(),
            pk=self.kwargs["provider_id"],
        )
        now = timezone.now()
        return Offer.objects.filter(
            provider=provider,
            service__is_active=True,
            is_active=True,
            starts_at__lte=now,
            ends_at__gt=now,
        ).order_by("ends_at")


@extend_schema(tags=["provider-offers"])
class ProviderOfferListView(generics.GenericAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = OfferOwnerSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Offer.objects.none()
        return Offer.objects.filter(provider=self.request.user.provider_profile).order_by(
            "-starts_at", "-created_at"
        )

    @extend_schema(summary="My offers", responses={200: PaginatedOfferOwnerSerializer})
    def get(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(OfferOwnerSerializer(page, many=True).data)
        return Response(OfferOwnerSerializer(qs, many=True).data)

    @extend_schema(
        summary="Create an offer",
        request=OfferCreateSerializer,
        responses={201: OfferOwnerSerializer},
    )
    def post(self, request):
        serializer = OfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            offer = services.create_offer(
                request.user.provider_profile,
                **serializer.validated_data,
            )
        except services.OfferError as exc:
            raise_api(exc)
        return Response(OfferOwnerSerializer(offer).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["provider-offers"])
class ProviderOfferDetailView(APIView):
    permission_classes = [HasProviderProfile]
    serializer_class = OfferUpdateSerializer

    @extend_schema(
        summary="Update or deactivate one of my offers",
        request=OfferUpdateSerializer,
        responses={200: OfferOwnerSerializer},
    )
    def patch(self, request, pk):
        serializer = OfferUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            offer = services.update_offer(
                request.user.provider_profile,
                offer_id=pk,
                changes=serializer.validated_data,
            )
        except services.OfferError as exc:
            raise_api(exc)
        return Response(OfferOwnerSerializer(offer).data)
