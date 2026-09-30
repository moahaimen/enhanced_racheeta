from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, generics, status
from rest_framework.exceptions import APIException, ErrorDetail, NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .filters import OwnerListingFilter, PublicListingFilter
from .models import PropertyListing, RealEstateSeller
from .permissions import HasRealEstateSeller, IsRealEstateSellerAccount
from .serializers import (
    OwnerDashboardSerializer,
    PaginatedPropertyListingOwnerSerializer,
    PropertyListingOwnerSerializer,
    PropertyListingPublicSerializer,
    PropertyListingWriteSerializer,
    SellerOwnerSerializer,
    SellerWriteSerializer,
)
from .types import PublicationStatus


class RealEstateAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


STATUS_FOR_CODE = {
    "already_exists": status.HTTP_409_CONFLICT,
    "seller_not_eligible": status.HTTP_403_FORBIDDEN,
    "not_found": status.HTTP_404_NOT_FOUND,
    "invalid_transition": status.HTTP_400_BAD_REQUEST,
}


def raise_api(exc: services.RealEstateError):
    """Service errors -> the uniform envelope. Field problems (structure or the
    publication gate) become a validation error whose `codes` are typed per
    field; everything else carries its own machine code."""
    if isinstance(exc, services.ListingProblems):
        raise ValidationError(
            {
                field: [ErrorDetail(services.PROBLEM_MESSAGES.get(code, code), code=code)]
                for field, code in exc.problems.items()
            }
        ) from exc
    err = RealEstateAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


def _own_seller(request) -> RealEstateSeller:
    try:
        return RealEstateSeller.objects.select_related("account").get(account=request.user)
    except RealEstateSeller.DoesNotExist as exc:
        raise NotFound("You have not created a seller profile yet.") from exc


def _listing_relations(qs):
    return qs.select_related("seller", "governorate", "city").prefetch_related("suitable_uses")


# ---- public ---------------------------------------------------------------------------


def _public_listings():
    """List and detail share this: THE visibility rule, then relations. Filters
    are applied on top and can only narrow it."""
    return _listing_relations(PropertyListing.objects.publicly_visible())


@extend_schema(
    tags=["real-estate"],
    summary="Public medical real-estate listings (paginated, newest first by default)",
)
class PublicListingListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PropertyListingPublicSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PublicListingFilter
    search_fields = ["title", "description", "district"]
    queryset = PropertyListing.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PropertyListing.objects.none()
        return _public_listings().order_by("-created_at", "id")


@extend_schema(tags=["real-estate"], summary="One public listing (404 unless publicly visible)")
class PublicListingDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PropertyListingPublicSerializer
    queryset = PropertyListing.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PropertyListing.objects.none()
        return _public_listings()  # same rule as the list: a plain 404 otherwise


# ---- seller self-service --------------------------------------------------------------


@extend_schema(tags=["real-estate-owner"])
class MySellerView(APIView):
    permission_classes = [IsRealEstateSellerAccount]
    serializer_class = SellerOwnerSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(responses={200: SellerOwnerSerializer}, summary="My seller profile")
    def get(self, request):
        return Response(SellerOwnerSerializer(_own_seller(request)).data)

    @extend_schema(
        request=SellerWriteSerializer,
        responses={201: SellerOwnerSerializer},
        summary="Create my seller profile (onboarding)",
    )
    def post(self, request):
        serializer = SellerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.create_seller(request.user, dict(serializer.validated_data))
        except services.RealEstateError as exc:
            raise_api(exc)
        return Response(SellerOwnerSerializer(_own_seller(request)).data, status=201)

    @extend_schema(
        request=SellerWriteSerializer,
        responses={200: SellerOwnerSerializer},
        summary="Update my seller profile",
    )
    def patch(self, request):
        seller = _own_seller(request)
        serializer = SellerWriteSerializer(seller, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_seller(seller, dict(serializer.validated_data))
        except services.RealEstateError as exc:
            raise_api(exc)
        return Response(SellerOwnerSerializer(_own_seller(request)).data)


@extend_schema(tags=["real-estate-owner"])
class MyDashboardView(APIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = OwnerDashboardSerializer

    @extend_schema(responses={200: OwnerDashboardSerializer}, summary="My listing counts")
    def get(self, request):
        return Response(
            OwnerDashboardSerializer(services.dashboard_summary(_own_seller(request))).data
        )


def _own_listings(request):
    return _listing_relations(
        PropertyListing.objects.filter(seller__account=request.user).with_public_state()
    )


def _own_listing_response(request, pk, status_code=status.HTTP_200_OK):
    """After a write: answer with the listing as the owner list reads it."""
    return Response(
        PropertyListingOwnerSerializer(_own_listings(request).get(pk=pk)).data,
        status=status_code,
    )


@extend_schema(tags=["real-estate-owner"])
class MyListingListView(generics.GenericAPIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = PropertyListingOwnerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = OwnerListingFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PropertyListing.objects.none()
        return _own_listings(self.request).order_by("-created_at", "id")

    @extend_schema(
        summary="My listings (paginated, newest first)",
        parameters=[
            OpenApiParameter("page", int, description="Page number (20 per page)."),
            OpenApiParameter(
                "publication_status", str, enum=PublicationStatus.values, description="Filter."
            ),
        ],
        responses={200: PaginatedPropertyListingOwnerSerializer},
    )
    def get(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(PropertyListingOwnerSerializer(page, many=True).data)
        return Response(PropertyListingOwnerSerializer(qs, many=True).data)

    @extend_schema(
        summary="Create a listing (a draft until published)",
        request=PropertyListingWriteSerializer,
        responses={201: PropertyListingOwnerSerializer},
    )
    def post(self, request):
        serializer = PropertyListingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        uses = data.pop("suitable_uses", None)
        try:
            listing = services.create_listing(_own_seller(request), data, uses)
        except services.RealEstateError as exc:
            raise_api(exc)
        return _own_listing_response(request, listing.pk, status.HTTP_201_CREATED)


@extend_schema(tags=["real-estate-owner"])
class MyListingDetailView(APIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = PropertyListingOwnerSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def _get(self, request, pk):
        return get_object_or_404(_own_listings(request), pk=pk)  # foreign ids: 404

    @extend_schema(responses={200: PropertyListingOwnerSerializer}, summary="One of my listings")
    def get(self, request, pk):
        return Response(PropertyListingOwnerSerializer(self._get(request, pk)).data)

    @extend_schema(
        request=PropertyListingWriteSerializer,
        responses={200: PropertyListingOwnerSerializer},
        summary="Update one of my listings (a published listing is re-validated in full)",
    )
    def patch(self, request, pk):
        listing = self._get(request, pk)
        serializer = PropertyListingWriteSerializer(listing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        uses = data.pop("suitable_uses", None)
        try:
            services.update_listing(_own_seller(request), listing.pk, data, uses)
        except services.RealEstateError as exc:
            raise_api(exc)
        return _own_listing_response(request, listing.pk)


def _publication_view(publish: bool, summary: str):
    @extend_schema(tags=["real-estate-owner"], summary=summary)
    class View(APIView):
        permission_classes = [HasRealEstateSeller]
        serializer_class = None

        @extend_schema(request=None, responses={200: PropertyListingOwnerSerializer})
        def post(self, request, pk):
            action = services.publish_listing if publish else services.unpublish_listing
            try:
                listing = action(_own_seller(request), pk)
            except services.RealEstateError as exc:
                raise_api(exc)
            return _own_listing_response(request, listing.pk)

    View.__name__ = "MyListingPublishView" if publish else "MyListingUnpublishView"
    return View


MyListingPublishView = _publication_view(True, "Publish one of my listings (full publication gate)")
MyListingUnpublishView = _publication_view(False, "Unpublish one of my listings (back to draft)")
