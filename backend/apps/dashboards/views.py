"""Dashboard views: small, read-only, parameterless.

Pattern for every view: authenticate -> permission class resolves the caller's own state ->
service aggregates rows already scoped to it -> the response serializer emits only declared
fields. Nothing here reads an id or filter from the request.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount
from apps.chat import services as chat_services
from apps.notifications import services as notification_services

from . import access
from .permissions import (
    HasCompanyProfile,
    IsFacilityProvider,
    IsPatientAccount,
    IsPractitionerProvider,
    IsRecruitingOrganizationMember,
)
from .serializers import (
    AdminDashboardSerializer,
    CompanyDashboardSerializer,
    DashboardIndexSerializer,
    DoctorDashboardSerializer,
    FacilityDashboardSerializer,
    PatientDashboardSerializer,
    RecruiterDashboardSerializer,
)
from .services import admin as admin_services
from .services import company as company_services
from .services import providers as provider_services
from .services import recruiter as recruiter_services
from .services import reservations as reservation_services


def _unread(account) -> dict:
    return {
        "notifications": notification_services.unread_count(account),
        "messages": chat_services.unread_count(account),
    }


def _provider_payload(profile, account) -> dict:
    return {
        "profile": {
            "display_name": profile.display_name,
            "provider_type": profile.provider_type,
            "verification_status": profile.verification_status,
            "is_visible": profile.is_visible,
        },
        **reservation_services.provider_summary(profile),
        "reviews": provider_services.review_summary(profile),
        "offers": provider_services.offer_summary(profile),
        "unread": _unread(account),
    }


class _DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    # Read-only and personal: never cache in a shared cache.
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


@extend_schema(tags=["dashboards"])
class DashboardIndexView(_DashboardView):
    serializer_class = DashboardIndexSerializer

    @extend_schema(
        summary="Dashboards I can open",
        description=(
            "Decided by the server from current account state; the web app renders only these."
        ),
        responses={200: DashboardIndexSerializer},
    )
    def get(self, request):
        return Response(
            DashboardIndexSerializer({"dashboards": access.available_dashboards(request.user)}).data
        )


@extend_schema(tags=["dashboards"])
class PatientDashboardView(_DashboardView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = PatientDashboardSerializer

    @extend_schema(summary="Patient dashboard", responses={200: PatientDashboardSerializer})
    def get(self, request):
        payload = {
            **reservation_services.patient_summary(request.user),
            "unread": _unread(request.user),
        }
        return Response(PatientDashboardSerializer(payload).data)


@extend_schema(tags=["dashboards"])
class DoctorDashboardView(_DashboardView):
    permission_classes = [IsAuthenticated, IsPractitionerProvider]
    serializer_class = DoctorDashboardSerializer

    @extend_schema(
        summary="Doctor (practitioner) dashboard", responses={200: DoctorDashboardSerializer}
    )
    def get(self, request):
        payload = _provider_payload(request.provider_profile, request.user)
        return Response(DoctorDashboardSerializer(payload).data)


@extend_schema(tags=["dashboards"])
class FacilityDashboardView(_DashboardView):
    permission_classes = [IsAuthenticated, IsFacilityProvider]
    serializer_class = FacilityDashboardSerializer

    @extend_schema(summary="Facility dashboard", responses={200: FacilityDashboardSerializer})
    def get(self, request):
        profile = request.provider_profile
        payload = {
            **_provider_payload(profile, request.user),
            "practitioners": provider_services.facility_membership_summary(profile),
        }
        return Response(FacilityDashboardSerializer(payload).data)


@extend_schema(tags=["dashboards"])
class CompanyDashboardView(_DashboardView):
    permission_classes = [IsAuthenticated, HasCompanyProfile]
    serializer_class = CompanyDashboardSerializer

    @extend_schema(
        summary="Medical company dashboard",
        description=(
            "Composes the existing marketplace and advertising summaries and adds payment status. "
            "No impressions, clicks, conversions or revenue exist, so none are reported."
        ),
        responses={200: CompanyDashboardSerializer},
    )
    def get(self, request):
        return Response(
            CompanyDashboardSerializer(
                company_services.company_summary(request.medical_company)
            ).data
        )


@extend_schema(tags=["dashboards"])
class RecruiterDashboardView(_DashboardView):
    permission_classes = [IsAuthenticated, IsRecruitingOrganizationMember]
    serializer_class = RecruiterDashboardSerializer

    @extend_schema(
        summary="Recruiter dashboard (my organisation)",
        responses={200: RecruiterDashboardSerializer},
    )
    def get(self, request):
        return Response(
            RecruiterDashboardSerializer(
                recruiter_services.recruiter_summary(request.employer_membership)
            ).data
        )


@extend_schema(tags=["dashboards"])
class AdminDashboardView(_DashboardView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = AdminDashboardSerializer

    @extend_schema(
        summary="Administrator operational summary (counts only)",
        responses={200: AdminDashboardSerializer},
    )
    def get(self, request):
        return Response(AdminDashboardSerializer(admin_services.admin_summary()).data)
