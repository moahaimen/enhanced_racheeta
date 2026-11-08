"""Promotion endpoints: seller self-service, administrator review, provider feed."""

from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount
from apps.marketplace.permissions import current_verified_provider

from . import promotions, services
from .models import ListingPromotion, ListingSuitableUse
from .permissions import HasRealEstateSeller
from .serializers import (
    ListingPromotionSerializer,
    PromotedListingSerializer,
    PromotionRejectSerializer,
    PromotionRequestSerializer,
)
from .types import PromotionStatus
from .views import _own_seller, raise_api


def _promotion_relations(qs):
    return qs.select_related("listing")


@extend_schema(tags=["real-estate"], summary="My listing promotions (paginated)")
class MyPromotionListView(generics.ListCreateAPIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = ListingPromotionSerializer
    queryset = ListingPromotion.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingPromotion.objects.none()
        return _promotion_relations(
            ListingPromotion.objects.filter(listing__seller__account=self.request.user)
        )

    @extend_schema(request=PromotionRequestSerializer, responses={201: ListingPromotionSerializer})
    def post(self, request):
        seller = _own_seller(request)
        body = PromotionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            promotion = promotions.request_promotion(
                seller,
                body.validated_data["listing"],
                target_provider_types=body.validated_data["target_provider_types"],
                days=body.validated_data["days"],
            )
        except services.RealEstateError as exc:
            raise_api(exc)
        return Response(ListingPromotionSerializer(promotion).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["real-estate"],
    summary="Withdraw or stop one of my promotions",
    request=None,
    responses=ListingPromotionSerializer,
)
class MyPromotionEndView(APIView):
    permission_classes = [HasRealEstateSeller]

    def post(self, request, pk):
        seller = _own_seller(request)
        try:
            promotion = promotions.end_promotion(seller, pk)
        except services.RealEstateError as exc:
            raise_api(exc)
        return Response(ListingPromotionSerializer(promotion).data)


@extend_schema(
    tags=["real-estate"],
    summary="Administrator: listing promotions (paginated)",
    parameters=[OpenApiParameter("status", str, enum=PromotionStatus.values)],
)
class AdminPromotionListView(generics.ListAPIView):
    permission_classes = [IsAdminAccount]
    serializer_class = ListingPromotionSerializer
    queryset = ListingPromotion.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingPromotion.objects.none()
        qs = _promotion_relations(ListingPromotion.objects.all())
        wanted = self.request.query_params.get("status")
        if wanted in PromotionStatus.values:
            qs = qs.filter(status=wanted)
        return qs


@extend_schema(
    tags=["real-estate"],
    summary="Administrator: approve a promotion",
    request=None,
    responses=ListingPromotionSerializer,
)
class AdminPromotionApproveView(APIView):
    permission_classes = [IsAdminAccount]

    def post(self, request, pk):
        try:
            promotion = promotions.approve_promotion(pk, decided_by=request.user)
        except services.RealEstateError as exc:
            raise_api(exc)
        return Response(ListingPromotionSerializer(promotion).data)


@extend_schema(
    tags=["real-estate"],
    summary="Administrator: reject a promotion",
    request=PromotionRejectSerializer,
    responses=ListingPromotionSerializer,
)
class AdminPromotionRejectView(APIView):
    permission_classes = [IsAdminAccount]

    def post(self, request, pk):
        body = PromotionRejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            promotion = promotions.reject_promotion(
                pk, decided_by=request.user, reason=body.validated_data["reason"]
            )
        except services.RealEstateError as exc:
            raise_api(exc)
        return Response(ListingPromotionSerializer(promotion).data)


@extend_schema(
    tags=["real-estate"],
    summary="Promoted medical properties for me (opt-in, verified providers; paginated)",
)
class PromotedListingFeedView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PromotedListingSerializer
    filter_backends: list = []
    queryset = ListingPromotion.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingPromotion.objects.none()
        provider = current_verified_provider(self.request.user)
        if provider is None:
            raise PermissionDenied("Only verified providers see promoted properties.")
        return (
            ListingPromotion.objects.visible_to(provider)
            .select_related("listing__seller", "listing__governorate", "listing__city")
            .prefetch_related(
                Prefetch("listing__suitable_uses", queryset=ListingSuitableUse.objects.all())
            )
            .order_by("ends_at", "id")
        )
