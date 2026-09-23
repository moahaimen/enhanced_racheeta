from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount

from . import services
from .filters import ProviderFilter
from .models import ProviderMembership, ProviderProfile, ServiceOffering
from .permissions import HasProviderProfile, IsProviderAccount
from .serializers import (
    MembershipCreateSerializer,
    MembershipSerializer,
    ProviderCardSerializer,
    ProviderOwnerSerializer,
    ProviderPublicSerializer,
    ProviderWriteSerializer,
    ServiceOfferingSerializer,
    VerificationDecisionSerializer,
)
from .types import MembershipStatus

# ---- public discovery ------------------------------------------------------


@extend_schema(
    tags=["providers"],
    summary="Discover providers (verified and visible only)",
    parameters=[
        OpenApiParameter("type", str, description="Provider type code, e.g. DOCTOR"),
        OpenApiParameter("kind", str, description="PRACTITIONER or FACILITY"),
        OpenApiParameter("specialty", str, description="Specialty slug"),
        OpenApiParameter("governorate", str, description="Governorate id"),
        OpenApiParameter("city", str, description="City id"),
        OpenApiParameter("search", str, description="Matches display name"),
        OpenApiParameter(
            "ordering", str, description="display_name | -display_name | created_at | -created_at"
        ),
    ],
)
class ProviderListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ProviderCardSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProviderFilter
    search_fields = ["display_name"]
    ordering_fields = ["display_name", "created_at"]
    ordering = ["display_name"]

    def get_queryset(self):
        return ProviderProfile.objects.discoverable().with_public_relations()


@extend_schema(tags=["providers"], summary="Public provider profile")
class ProviderDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ProviderPublicSerializer

    def get_queryset(self):
        return (
            ProviderProfile.objects.discoverable()
            .with_public_relations()
            .prefetch_related(
                Prefetch(
                    "services",
                    queryset=ServiceOffering.objects.filter(is_active=True).select_related(
                        "specialty"
                    ),
                    to_attr="active_services",
                )
            )
        )

    def get_object(self):
        obj = super().get_object()
        # Active memberships whose counterpart is itself public.
        if obj.is_practitioner:
            links = ProviderMembership.objects.filter(
                practitioner=obj, status=MembershipStatus.ACTIVE
            ).select_related("facility__account")
            obj.related_profiles = [m.facility for m in links if m.facility.is_discoverable]
        else:
            links = ProviderMembership.objects.filter(
                facility=obj, status=MembershipStatus.ACTIVE
            ).select_related("practitioner__account")
            obj.related_profiles = [m.practitioner for m in links if m.practitioner.is_discoverable]
        return obj


# ---- owner self-management -------------------------------------------------


def _own_profile(request) -> ProviderProfile:
    try:
        return (
            ProviderProfile.objects.select_related("governorate", "city", "account")
            .prefetch_related("specialties")
            .get(account=request.user)
        )
    except ProviderProfile.DoesNotExist as exc:
        raise NotFound("You have not created a provider profile yet.") from exc


@extend_schema(tags=["provider-self"])
class MyProviderView(APIView):
    """Create, read and update the caller's own provider profile."""

    permission_classes = [IsProviderAccount]
    serializer_class = ProviderOwnerSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(responses={200: ProviderOwnerSerializer}, summary="My provider profile")
    def get(self, request):
        return Response(ProviderOwnerSerializer(_own_profile(request)).data)

    @extend_schema(
        request=ProviderWriteSerializer,
        responses={201: ProviderOwnerSerializer},
        summary="Create my provider profile (onboarding)",
    )
    def post(self, request):
        if ProviderProfile.objects.filter(account=request.user).exists():
            raise ValidationError(
                {"non_field_errors": ["You already have a provider profile."]},
                code="already_exists",
            )
        serializer = ProviderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save(account=request.user)
        return Response(
            ProviderOwnerSerializer(_own_profile(request)).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=ProviderWriteSerializer,
        responses={200: ProviderOwnerSerializer},
        summary="Update my provider profile",
    )
    def patch(self, request):
        profile = _own_profile(request)
        serializer = ProviderWriteSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
        return Response(ProviderOwnerSerializer(_own_profile(request)).data)


@extend_schema(tags=["provider-self"], summary="Request verification of my profile")
class MyVerificationRequestView(APIView):
    permission_classes = [HasProviderProfile]
    serializer_class = None

    @extend_schema(request=None, responses={200: ProviderOwnerSerializer})
    def post(self, request):
        profile = _own_profile(request)
        try:
            services.request_verification(profile)
        except services.InvalidTransition as exc:
            raise ValidationError(
                {"non_field_errors": [str(exc)]}, code="invalid_transition"
            ) from exc
        return Response(ProviderOwnerSerializer(_own_profile(request)).data)


@extend_schema(tags=["provider-self"])
class MyServiceListView(generics.ListCreateAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = ServiceOfferingSerializer
    pagination_class = None
    queryset = ServiceOffering.objects.none()  # real queryset below; keeps schema generation quiet

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ServiceOffering.objects.none()
        return ServiceOffering.objects.filter(provider__account=self.request.user).select_related(
            "specialty"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            ctx["provider"] = self.request.user.provider_profile
        return ctx

    def perform_create(self, serializer):
        serializer.save(provider=self.request.user.provider_profile)

    @extend_schema(summary="My service offerings")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Add a service offering")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["provider-self"])
class MyServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = ServiceOfferingSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ServiceOffering.objects.none()
        # Scoped to the owner: a foreign id is simply a 404, never someone else's row.
        return ServiceOffering.objects.filter(provider__account=self.request.user).select_related(
            "specialty"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            ctx["provider"] = self.request.user.provider_profile
        return ctx


@extend_schema(tags=["provider-self"])
class MyMembershipListView(generics.ListCreateAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = MembershipSerializer
    pagination_class = None
    queryset = ProviderMembership.objects.none()

    def _me(self) -> ProviderProfile:
        return self.request.user.provider_profile

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProviderMembership.objects.none()
        me = self._me()
        qs = ProviderMembership.objects.filter(practitioner=me) | ProviderMembership.objects.filter(
            facility=me
        )
        return qs.select_related("practitioner", "facility").order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            ctx["provider"] = self._me()
        return ctx

    @extend_schema(summary="My memberships (both sides)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=MembershipCreateSerializer,
        responses={201: MembershipSerializer},
        summary="Request to join a facility / invite a practitioner",
    )
    def post(self, request, *args, **kwargs):
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        me = self._me()
        try:
            membership = services.create_membership(
                initiator=me,
                counterpart=serializer.validated_data["counterpart"],
                role_title=serializer.validated_data.get("role_title", ""),
            )
        except services.DuplicateMembership as exc:
            raise ValidationError(
                {
                    "counterpart": [
                        "A pending or active membership with this provider already exists."
                    ]
                },
                code="duplicate_membership",
            ) from exc
        except services.InvalidTransition as exc:
            raise ValidationError({"counterpart": [str(exc)]}, code="invalid_membership") from exc
        membership = ProviderMembership.objects.select_related("practitioner", "facility").get(
            pk=membership.pk
        )
        return Response(
            MembershipSerializer(membership, context={"provider": me}).data,
            status=status.HTTP_201_CREATED,
        )


class _MembershipActionView(APIView):
    permission_classes = [HasProviderProfile]
    serializer_class = None
    action = None  # set per subclass

    @extend_schema(request=None, responses={200: MembershipSerializer})
    def post(self, request, pk):
        me = request.user.provider_profile
        membership = get_object_or_404(
            ProviderMembership.objects.select_related("practitioner", "facility"),
            pk=pk,
        )
        if membership.side_of(me) is None:
            raise NotFound  # not a party: behave as if it does not exist
        handler = getattr(services, f"{self.action}_membership")
        try:
            handler(membership, me)
        except services.InvalidTransition as exc:
            raise ValidationError(
                {"non_field_errors": [str(exc)]}, code="invalid_transition"
            ) from exc
        except services.NotAParty as exc:  # pragma: no cover - guarded above
            raise PermissionDenied from exc
        return Response(MembershipSerializer(membership, context={"provider": me}).data)


@extend_schema(tags=["provider-self"], summary="Accept a pending membership (counterpart only)")
class MembershipAcceptView(_MembershipActionView):
    action = "accept"


@extend_schema(tags=["provider-self"], summary="Reject or withdraw a pending membership")
class MembershipRejectView(_MembershipActionView):
    action = "reject"


@extend_schema(tags=["provider-self"], summary="End an active membership")
class MembershipEndView(_MembershipActionView):
    action = "end"


# ---- admin -----------------------------------------------------------------


@extend_schema(tags=["admin"], summary="Set a provider's verification status (administrators)")
class AdminVerificationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = VerificationDecisionSerializer

    @extend_schema(request=VerificationDecisionSerializer, responses={200: ProviderOwnerSerializer})
    def post(self, request, pk):
        profile = get_object_or_404(ProviderProfile, pk=pk)
        serializer = VerificationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_verification(
            profile,
            serializer.validated_data["status"],
            serializer.validated_data.get("note", ""),
            by=request.user,
        )
        profile = (
            ProviderProfile.objects.select_related("governorate", "city")
            .prefetch_related("specialties")
            .get(pk=pk)
        )
        return Response(ProviderOwnerSerializer(profile).data)
