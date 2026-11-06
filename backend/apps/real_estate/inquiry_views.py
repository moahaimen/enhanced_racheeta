"""Property inquiry API (Phase E). Scoping comes from `request.user` only: a seeker sees their own
inquiries; an owner sees inquiries on their own listings. Everything else answers 404."""

from django.db.models import Exists, OuterRef
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import inquiries
from .models import ListingInquiry, PropertyListing
from .permissions import HasRealEstateSeller
from .types import INQUIRY_MESSAGE_MAX, InquiryStatus
from .views import _own_seller, raise_api

# ---- serializers ----------------------------------------------------------------------------


class InquiryCreateSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=10, max_length=INQUIRY_MESSAGE_MAX)
    share_contact = serializers.BooleanField(required=False, default=False)


class InquiryRespondSerializer(serializers.Serializer):
    response = serializers.CharField(min_length=2, max_length=INQUIRY_MESSAGE_MAX)


class InquirySeekerSerializer(serializers.ModelSerializer):
    """The seeker's own view. `listing_is_public` lets the client link to the listing only while
    it is still public; the listing itself is never re-exposed here."""

    listing_id = serializers.UUIDField(read_only=True)
    listing_is_public = serializers.BooleanField(read_only=True)

    class Meta:
        model = ListingInquiry
        fields = [
            "id",
            "listing_id",
            "listing_title_snapshot",
            "listing_is_public",
            "message",
            "share_contact",
            "status",
            "owner_response",
            "responded_at",
            "status_changed_at",
            "created_at",
        ]
        read_only_fields = fields


class InquirerSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    # Empty unless the seeker chose to share contact details with the owner.
    email = serializers.CharField(allow_blank=True)
    phone_number = serializers.CharField(allow_blank=True)


class InquiryOwnerSerializer(serializers.ModelSerializer):
    listing_id = serializers.UUIDField(read_only=True)
    listing_is_public = serializers.BooleanField(read_only=True)
    inquirer = serializers.SerializerMethodField()

    class Meta:
        model = ListingInquiry
        fields = [
            "id",
            "listing_id",
            "listing_title_snapshot",
            "listing_is_public",
            "inquirer",
            "message",
            "share_contact",
            "status",
            "owner_response",
            "responded_at",
            "status_changed_at",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(InquirerSerializer)
    def get_inquirer(self, obj) -> dict:
        account = obj.inquirer
        shared = obj.share_contact
        return {
            "full_name": account.full_name,
            "email": account.email if shared else "",
            "phone_number": (account.phone_number or "") if shared else "",
        }


# ---- helpers --------------------------------------------------------------------------------


def _with_public_flag(qs):
    visible = PropertyListing.objects.publicly_visible().filter(pk=OuterRef("listing_id"))
    return qs.annotate(listing_is_public=Exists(visible))


def _mine(request):
    return _with_public_flag(ListingInquiry.objects.filter(inquirer=request.user))


def _owners(request, seller):
    return _with_public_flag(
        ListingInquiry.objects.filter(listing__seller=seller).select_related("inquirer")
    )


class _ThrottledPost:
    """Only sending an inquiry spends the inquiry quota; reads use the project defaults."""

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return super().get_throttles()


# ---- seeker ---------------------------------------------------------------------------------


@extend_schema(tags=["real-estate-inquiries"])
class ListingInquiryCreateView(_ThrottledPost, APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "real_estate_inquiries"
    serializer_class = InquiryCreateSerializer

    @extend_schema(
        summary="Send an inquiry about a public listing (signed-in accounts; throttled)",
        request=InquiryCreateSerializer,
        responses={201: InquirySeekerSerializer},
    )
    def post(self, request, pk):
        body = InquiryCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            inquiry = inquiries.create_inquiry(
                request.user,
                pk,
                message=body.validated_data["message"],
                share_contact=body.validated_data["share_contact"],
            )
        except inquiries.RealEstateError as exc:
            raise_api(exc)
        return Response(
            InquirySeekerSerializer(_mine(request).get(pk=inquiry.pk)).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["real-estate-inquiries"],
    summary="My property inquiries (newest first)",
    parameters=[OpenApiParameter("status", str, enum=InquiryStatus.values)],
)
class MyInquiryListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InquirySeekerSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingInquiry.objects.none()
        qs = _mine(self.request)
        wanted = self.request.query_params.get("status")
        if wanted in InquiryStatus.values:
            qs = qs.filter(status=wanted)
        return qs.order_by("-created_at", "id")


@extend_schema(tags=["real-estate-inquiries"])
class MyInquiryWithdrawView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InquirySeekerSerializer

    @extend_schema(summary="Withdraw my inquiry", request=None, responses=InquirySeekerSerializer)
    def post(self, request, pk):
        try:
            inquiries.withdraw(request.user, pk)
        except inquiries.RealEstateError as exc:
            raise_api(exc)
        return Response(InquirySeekerSerializer(_mine(request).get(pk=pk)).data)


# ---- owner ----------------------------------------------------------------------------------


@extend_schema(
    tags=["real-estate-inquiries"],
    summary="Inquiries about my listings (newest first)",
    parameters=[
        OpenApiParameter("status", str, enum=InquiryStatus.values),
        OpenApiParameter("listing", str, description="Listing UUID"),
    ],
)
class OwnerInquiryListView(generics.ListAPIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = InquiryOwnerSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingInquiry.objects.none()
        qs = _owners(self.request, _own_seller(self.request))
        params = self.request.query_params
        if params.get("status") in InquiryStatus.values:
            qs = qs.filter(status=params["status"])
        if params.get("listing"):
            try:
                qs = qs.filter(
                    listing_id=serializers.UUIDField().to_internal_value(params["listing"])
                )
            except serializers.ValidationError:
                return qs.none()
        return qs.order_by("-created_at", "id")


@extend_schema(tags=["real-estate-inquiries"])
class OwnerInquiryRespondView(APIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = InquiryRespondSerializer

    @extend_schema(
        summary="Answer an inquiry (may be answered again while it is live)",
        request=InquiryRespondSerializer,
        responses=InquiryOwnerSerializer,
    )
    def post(self, request, pk):
        seller = _own_seller(request)
        body = InquiryRespondSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            inquiries.respond(seller, pk, response=body.validated_data["response"])
        except inquiries.RealEstateError as exc:
            raise_api(exc)
        return Response(InquiryOwnerSerializer(_owners(request, seller).get(pk=pk)).data)


@extend_schema(tags=["real-estate-inquiries"])
class OwnerInquiryCloseView(APIView):
    permission_classes = [HasRealEstateSeller]
    serializer_class = InquiryOwnerSerializer

    @extend_schema(summary="Close an inquiry", request=None, responses=InquiryOwnerSerializer)
    def post(self, request, pk):
        seller = _own_seller(request)
        try:
            inquiries.close(seller, pk)
        except inquiries.RealEstateError as exc:
            raise_api(exc)
        return Response(InquiryOwnerSerializer(_owners(request, seller).get(pk=pk)).data)
