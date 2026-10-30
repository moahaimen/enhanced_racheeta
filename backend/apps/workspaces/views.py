"""Workspace API. Every endpoint re-resolves the caller's role in the organization from the
database (apps.workspaces.access) and checks the capability matrix (types.CAPABILITIES)."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commerce.models import Order, QuoteRequest
from apps.commerce.types import OPEN_QUOTE_STATUSES, OrderStatus
from apps.marketplace.models import MedicalCompany, Product
from apps.providers.models import ProviderMembership, ProviderProfile
from apps.providers.types import MembershipStatus
from apps.reservations import services as reservation_services
from apps.reservations.models import Reservation
from apps.reservations.serializers import (
    ProviderTransitionSerializer,
    ReservationProviderSerializer,
)
from apps.reservations.types import ReservationStatus
from apps.reservations.views import reservation_queryset

from . import access, services
from .models import OrganizationMember
from .types import GRANTABLE_ROLES, MemberStatus, role_has

WorkspaceSerializer = inline_serializer(
    name="Workspace",
    many=True,
    fields={
        "id": serializers.CharField(),
        "kind": serializers.CharField(),
        "subtype": serializers.CharField(),
        "title": serializers.CharField(),
        "role": serializers.CharField(),
        "path": serializers.CharField(),
        "verification_status": serializers.CharField(),
        "modules": serializers.ListField(child=serializers.CharField()),
        "capabilities": serializers.ListField(child=serializers.CharField()),
    },
)


class WorkspaceListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["workspaces"],
        summary="Workspaces I may open now (server-computed)",
        responses=WorkspaceSerializer,
    )
    def get(self, request):
        return Response(services.build_workspaces(request.user))


class WorkspaceAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


def _role_or_404(request, kind: str, org_id):
    role = (
        access.facility_role(request.user, org_id)
        if kind == "facility"
        else access.company_role(request.user, org_id)
    )
    if role is None:
        # Same answer for "does not exist" and "not yours": no organization enumeration.
        raise NotFound("Workspace not found.")
    return role


def _require(role: str, capability: str) -> None:
    if not role_has(role, capability):
        raise PermissionDenied("Your role in this organization does not allow this.")


FacilitySummarySerializer = inline_serializer(
    name="FacilityWorkspaceSummary",
    fields={
        "id": serializers.UUIDField(),
        "name": serializers.CharField(),
        "provider_type": serializers.CharField(),
        "role": serializers.CharField(),
        "capabilities": serializers.ListField(child=serializers.CharField()),
        "counts": serializers.DictField(child=serializers.IntegerField()),
    },
)


class FacilityWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["workspaces"],
        summary="Facility workspace summary",
        responses=FacilitySummarySerializer,
    )
    def get(self, request, pk):
        role = _role_or_404(request, "facility", pk)
        _require(role, "facility.view")
        facility = ProviderProfile.objects.get(pk=pk)
        now = timezone.now()
        reservations = facility.reservations.all()
        counts = {
            "pending": reservations.filter(status=ReservationStatus.PENDING).count(),
            "upcoming": reservations.filter(
                status__in=[ReservationStatus.PENDING, ReservationStatus.CONFIRMED],
                starts_at__gte=now,
            ).count(),
            "today": reservations.filter(starts_at__date=timezone.localdate()).count(),
            "practitioners": ProviderMembership.objects.filter(
                facility=facility, status=MembershipStatus.ACTIVE
            ).count(),
            "staff": OrganizationMember.objects.filter(
                facility=facility, status=MemberStatus.ACTIVE
            ).count(),
        }
        return Response(
            {
                "id": facility.pk,
                "name": facility.display_name,
                "provider_type": facility.provider_type,
                "role": role,
                "capabilities": services.capabilities_of(role),
                "counts": counts,
            }
        )


@extend_schema(tags=["workspaces"], summary="Reservations of a facility I work for")
class FacilityReservationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReservationProviderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Reservation.objects.none()
        role = _role_or_404(self.request, "facility", self.kwargs["pk"])
        _require(role, "facility.reservations.view")
        qs = reservation_queryset().filter(provider_id=self.kwargs["pk"])
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs


class FacilityReservationTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["workspaces"],
        summary="Confirm, reject, complete or mark no-show (facility staff)",
        request=ProviderTransitionSerializer,
        responses=ReservationProviderSerializer,
    )
    def post(self, request, pk, reservation_id):
        role = _role_or_404(request, "facility", pk)
        _require(role, "facility.reservations.manage")
        serializer = ProviderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        facility = ProviderProfile.objects.get(pk=pk)
        try:
            reservation_services.transition_as_provider(
                reservation_id,
                provider=facility,
                actor=request.user,
                target_status=serializer.validated_data["status"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except reservation_services.NotAParty as exc:
            raise NotFound("Reservation not found.") from exc
        except reservation_services.ReservationError as exc:
            err = WorkspaceAPIError(str(exc) or "invalid_transition", code="invalid_transition")
            err.status_code = status.HTTP_409_CONFLICT
            raise err from exc
        return Response(
            ReservationProviderSerializer(reservation_queryset().get(pk=reservation_id)).data
        )


CompanySummarySerializer = inline_serializer(
    name="CompanyWorkspaceSummary",
    fields={
        "id": serializers.UUIDField(),
        "name": serializers.CharField(),
        "business_type": serializers.CharField(),
        "role": serializers.CharField(),
        "capabilities": serializers.ListField(child=serializers.CharField()),
        "counts": serializers.DictField(child=serializers.IntegerField()),
    },
)


class CompanyWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["workspaces"],
        summary="Business workspace summary",
        responses=CompanySummarySerializer,
    )
    def get(self, request, pk):
        role = _role_or_404(request, "company", pk)
        _require(role, "company.view")
        company = MedicalCompany.objects.get(pk=pk)
        open_orders = [OrderStatus.PLACED, OrderStatus.CONFIRMED, OrderStatus.SHIPPED]
        counts = {
            "products_active": Product.objects.filter(company=company, is_active=True).count(),
            "orders_open": Order.objects.filter(merchant=company, status__in=open_orders).count(),
            "quotes_open": QuoteRequest.objects.filter(
                company=company, status__in=OPEN_QUOTE_STATUSES
            ).count(),
            "staff": OrganizationMember.objects.filter(
                company=company, status=MemberStatus.ACTIVE
            ).count(),
        }
        return Response(
            {
                "id": company.pk,
                "name": company.name,
                "business_type": company.business_type,
                "role": role,
                "capabilities": services.capabilities_of(role),
                "counts": counts,
            }
        )


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="account.email", read_only=True)
    full_name = serializers.CharField(source="account.full_name", read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ("id", "email", "full_name", "role", "status", "created_at", "ended_at")
        read_only_fields = fields


class MemberCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[(r.value, r.label) for r in GRANTABLE_ROLES])


class MemberListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MemberSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return OrganizationMember.objects.none()
        kind, pk = self.kwargs["kind"], self.kwargs["pk"]
        _require(_role_or_404(self.request, kind, pk), "members.view")
        scope = {"facility_id": pk} if kind == "facility" else {"company_id": pk}
        return OrganizationMember.objects.filter(
            status=MemberStatus.ACTIVE, **scope
        ).select_related("account")

    @extend_schema(tags=["workspaces"], summary="Staff of an organization (owner, manager)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["workspaces"],
        summary="Add an existing account as manager, staff or viewer (owner only)",
        request=MemberCreateSerializer,
        responses={201: MemberSerializer},
    )
    def post(self, request, kind, pk):
        _require(_role_or_404(request, kind, pk), "members.manage")
        serializer = MemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            member = services.add_member(
                actor=request.user, org_kind=kind, org_id=pk, **serializer.validated_data
            )
        except services.MembershipError as exc:
            raise WorkspaceAPIError(str(exc), code="membership_error") from exc
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)


class MemberEndView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["workspaces"],
        summary="End a staff membership (owner only)",
        request=None,
        responses=MemberSerializer,
    )
    def post(self, request, kind, pk, member_id):
        _require(_role_or_404(request, kind, pk), "members.manage")
        try:
            member = services.end_member(
                actor=request.user, org_kind=kind, org_id=pk, member_id=member_id
            )
        except services.MembershipError as exc:
            raise NotFound(str(exc)) from exc
        return Response(MemberSerializer(member).data)
