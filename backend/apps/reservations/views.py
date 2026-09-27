from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import has_role
from apps.accounts.roles import AccountRole
from apps.providers.models import ProviderProfile
from apps.providers.permissions import HasProviderProfile

from . import services
from .models import AvailabilitySlot, Reservation
from .serializers import (
    AvailabilityQuerySerializer,
    AvailabilitySlotCreateSerializer,
    AvailabilitySlotSerializer,
    ProviderTransitionSerializer,
    ReservationCancelSerializer,
    ReservationCreateSerializer,
    ReservationPatientSerializer,
    ReservationProviderSerializer,
)
from .types import ReservationStatus

IsPatientAccount = has_role(AccountRole.PATIENT)


class ReservationsAPIError(APIException):
    status_code = status.HTTP_409_CONFLICT


STATUS_FOR_CODE = {
    "invalid_transition": status.HTTP_400_BAD_REQUEST,
    "invalid_availability": status.HTTP_400_BAD_REQUEST,
    "slot_conflict": status.HTTP_409_CONFLICT,
    "slot_unavailable": status.HTTP_409_CONFLICT,
    "service_unavailable": status.HTTP_409_CONFLICT,
    "provider_unavailable": status.HTTP_409_CONFLICT,
    "not_found": status.HTTP_404_NOT_FOUND,
}


def raise_api(exc: services.ReservationError):
    err = ReservationsAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


def reservation_queryset():
    return (
        Reservation.objects.select_related(
            "patient",
            "provider",
            "service",
            "availability_slot",
        )
        .prefetch_related("transitions")
        .order_by("-starts_at")
    )


@extend_schema(
    tags=["reservations"],
    summary="Public available appointment slots",
    parameters=[
        OpenApiParameter("service", str, description="Service UUID"),
        OpenApiParameter("from", str, description="UTC datetime lower bound"),
        OpenApiParameter("to", str, description="UTC datetime upper bound"),
    ],
)
class PublicAvailabilityView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = AvailabilitySlotSerializer

    def get(self, request, provider_id):
        provider = get_object_or_404(
            ProviderProfile.objects.discoverable(),
            pk=provider_id,
        )
        query_data = {}
        if "service" in request.query_params:
            query_data["service"] = request.query_params["service"]
        if "from" in request.query_params:
            query_data["from_at"] = request.query_params["from"]
        if "to" in request.query_params:
            query_data["to_at"] = request.query_params["to"]
        query = AvailabilityQuerySerializer(data=query_data)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        qs = (
            AvailabilitySlot.objects.filter(
                provider=provider,
                is_active=True,
                service__is_active=True,
                starts_at__gt=timezone.now(),
            )
            .select_related("provider", "service", "service__specialty")
            .exclude(
                reservations__status__in=[
                    ReservationStatus.PENDING,
                    ReservationStatus.CONFIRMED,
                ]
            )
            .order_by("starts_at")
        )
        if service_id := data.get("service"):
            qs = qs.filter(service_id=service_id)
        if from_at := data.get("from_at"):
            qs = qs.filter(starts_at__gte=from_at)
        if to_at := data.get("to_at"):
            qs = qs.filter(starts_at__lt=to_at)

        return Response(AvailabilitySlotSerializer(qs, many=True).data)


@extend_schema(tags=["provider-reservations"])
class ProviderAvailabilityListView(generics.GenericAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = AvailabilitySlotSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AvailabilitySlot.objects.none()
        return AvailabilitySlot.objects.filter(
            provider=self.request.user.provider_profile
        ).select_related("provider", "service", "service__specialty")

    @extend_schema(summary="My appointment availability")
    def get(self, request):
        qs = self.get_queryset().order_by("starts_at")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(AvailabilitySlotSerializer(page, many=True).data)
        return Response(AvailabilitySlotSerializer(qs, many=True).data)

    @extend_schema(
        summary="Create an appointment slot",
        request=AvailabilitySlotCreateSerializer,
        responses={201: AvailabilitySlotSerializer},
    )
    def post(self, request):
        serializer = AvailabilitySlotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            slot = services.create_availability_slot(
                request.user.provider_profile,
                service_id=serializer.validated_data["service"],
                starts_at=serializer.validated_data["starts_at"],
            )
        except services.ReservationError as exc:
            raise_api(exc)
        slot = self.get_queryset().get(pk=slot.pk)
        return Response(AvailabilitySlotSerializer(slot).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["provider-reservations"],
    summary="Deactivate an unbooked appointment slot",
)
class ProviderAvailabilityDetailView(APIView):
    permission_classes = [HasProviderProfile]
    serializer_class = AvailabilitySlotSerializer

    def delete(self, request, pk):
        try:
            services.deactivate_availability_slot(
                request.user.provider_profile,
                slot_id=pk,
            )
        except services.ReservationError as exc:
            raise_api(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["reservations"],
    summary="Create a reservation from an available slot",
)
class ReservationCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = ReservationCreateSerializer

    @extend_schema(
        request=ReservationCreateSerializer,
        responses={201: ReservationPatientSerializer},
    )
    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reservation = services.create_reservation(
                patient=request.user,
                slot_id=serializer.validated_data["availability_slot"],
                patient_note=serializer.validated_data.get("patient_note", ""),
            )
        except services.ReservationError as exc:
            raise_api(exc)
        reservation = reservation_queryset().get(pk=reservation.pk)
        return Response(
            ReservationPatientSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["reservations"], summary="My reservations")
class MyReservationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = ReservationPatientSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Reservation.objects.none()
        return reservation_queryset().filter(patient=self.request.user)


@extend_schema(tags=["reservations"], summary="One of my reservations")
class MyReservationDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = ReservationPatientSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Reservation.objects.none()
        return reservation_queryset().filter(patient=self.request.user)


@extend_schema(tags=["reservations"], summary="Cancel one of my reservations")
class MyReservationCancelView(APIView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = ReservationCancelSerializer

    @extend_schema(
        request=ReservationCancelSerializer,
        responses={200: ReservationPatientSerializer},
    )
    def post(self, request, pk):
        serializer = ReservationCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.cancel_as_patient(
                pk,
                patient=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )
        except (services.ReservationError, Reservation.DoesNotExist) as exc:
            if isinstance(exc, Reservation.DoesNotExist):
                exc = services.NotAParty("Reservation not found.")
            raise_api(exc)
        reservation = reservation_queryset().get(pk=pk)
        return Response(ReservationPatientSerializer(reservation).data)


@extend_schema(tags=["provider-reservations"], summary="Reservations received by my provider")
class ProviderReservationListView(generics.ListAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = ReservationProviderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Reservation.objects.none()
        return reservation_queryset().filter(provider=self.request.user.provider_profile)


@extend_schema(tags=["provider-reservations"], summary="One reservation received by my provider")
class ProviderReservationDetailView(generics.RetrieveAPIView):
    permission_classes = [HasProviderProfile]
    serializer_class = ReservationProviderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Reservation.objects.none()
        return reservation_queryset().filter(provider=self.request.user.provider_profile)


@extend_schema(tags=["provider-reservations"], summary="Transition a received reservation")
class ProviderReservationTransitionView(APIView):
    permission_classes = [HasProviderProfile]
    serializer_class = ProviderTransitionSerializer

    @extend_schema(
        request=ProviderTransitionSerializer,
        responses={200: ReservationProviderSerializer},
    )
    def post(self, request, pk):
        serializer = ProviderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.transition_as_provider(
                pk,
                provider=request.user.provider_profile,
                actor=request.user,
                target_status=serializer.validated_data["status"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except (services.ReservationError, Reservation.DoesNotExist) as exc:
            if isinstance(exc, Reservation.DoesNotExist):
                exc = services.NotAParty("Reservation not found.")
            raise_api(exc)
        reservation = reservation_queryset().get(pk=pk)
        return Response(ReservationProviderSerializer(reservation).data)
