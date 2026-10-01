from collections.abc import Mapping

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ErrorDetail, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount
from apps.marketplace.models import MedicalCompany, ProductCategory
from apps.marketplace.permissions import (
    BROWSE_DENIED,
    CanBrowseMarketplace,
    HasMedicalCompany,
    current_verified_provider,
)

from . import services
from .filters import AdminCampaignFilter, OwnerCampaignFilter
from .models import AdvertisingCampaign
from .serializers import (
    CampaignAdminSerializer,
    CampaignDashboardSerializer,
    CampaignOwnerSerializer,
    CampaignWriteSerializer,
    PaginatedCampaignOwnerSerializer,
    PaymentRejectionSerializer,
    PaymentVerificationSerializer,
    QuoteDatesSerializer,
    QuoteResponseSerializer,
    SponsoredCampaignSerializer,
)
from .types import CampaignStatus


class AdvertisingAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


STATUS_FOR_CODE = {
    "quote_amount_too_large": status.HTTP_409_CONFLICT,
    "payment_quote_mismatch": status.HTTP_409_CONFLICT,
    "pricing_unavailable": status.HTTP_409_CONFLICT,
    "campaign_not_editable": status.HTTP_409_CONFLICT,
    "campaign_not_submittable": status.HTTP_409_CONFLICT,
    "company_not_eligible": status.HTTP_403_FORBIDDEN,
    "product_unavailable": status.HTTP_409_CONFLICT,
    "invalid_transition": status.HTTP_400_BAD_REQUEST,
    "payment_not_pending": status.HTTP_409_CONFLICT,
    "campaign_ended": status.HTTP_409_CONFLICT,
    "not_found": status.HTTP_404_NOT_FOUND,
}


def raise_api(exc: services.AdvertisingError):
    """Service errors -> the uniform envelope: field problems are a validation
    error with typed per-field codes; everything else carries its own code."""
    if isinstance(exc, services.CampaignProblems):
        raise ValidationError(
            {
                field: [ErrorDetail(services.PROBLEM_MESSAGES.get(code, code), code=code)]
                for field, code in exc.problems.items()
            }
        ) from exc
    err = AdvertisingAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


def _require_no_body(request) -> None:
    """Lifecycle actions (submit, cancel) take NO client data. Allowed: no body, or an
    empty JSON object / empty form (an empty mapping). Everything else is refused with
    `field_not_allowed` — any key of a non-empty object, and any non-object body (a JSON
    array even when empty, a string, a number, a boolean, an explicit null) — never
    silently ignored. Mapping semantics, not truthiness: `[]`, `false`, `0` and `""`
    are falsey but are still request bodies."""
    data = request.data
    if isinstance(data, Mapping):
        if len(data) == 0:
            return
        keys = list(data.keys())
    else:
        keys = ["non_field_errors"]
    raise ValidationError(
        {
            key: [ErrorDetail("This field cannot be set by a client.", code="field_not_allowed")]
            for key in keys
        },
        code="field_not_allowed",
    )


def _own_company(request) -> MedicalCompany:
    try:
        return MedicalCompany.objects.select_related("account").get(account=request.user)
    except MedicalCompany.DoesNotExist as exc:
        raise NotFound("You have not created a company profile yet.") from exc


def _with_relations(qs):
    return qs.select_related("product", "product__category", "payment").prefetch_related(
        "target_provider_types",
        "target_specialties__specialty",
        "target_governorates__governorate",
    )


def _own_campaigns(request):
    return _with_relations(
        AdvertisingCampaign.objects.filter(company__account=request.user).with_live_state()
    )


def _own_response(request, pk, status_code=status.HTTP_200_OK):
    return Response(
        CampaignOwnerSerializer(_own_campaigns(request).get(pk=pk)).data, status=status_code
    )


def _targets(data: dict) -> dict:
    return {
        "provider_types": data.pop("provider_types", None),
        "specialties": data.pop("specialties", None),
        "governorates": data.pop("governorates", None),
    }


# ---- company ---------------------------------------------------------------------------------


@extend_schema(tags=["advertising-company"])
class CampaignListView(generics.GenericAPIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = CampaignOwnerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = OwnerCampaignFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AdvertisingCampaign.objects.none()
        return _own_campaigns(self.request).order_by("-created_at", "id")

    @extend_schema(
        summary="My campaigns (paginated, newest first)",
        parameters=[
            OpenApiParameter("page", int, description="Page number (20 per page)."),
            OpenApiParameter(
                "status", str, enum=CampaignStatus.values, description="Filter by status."
            ),
        ],
        responses={200: PaginatedCampaignOwnerSerializer},
    )
    def get(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(CampaignOwnerSerializer(page, many=True).data)
        return Response(CampaignOwnerSerializer(qs, many=True).data)

    @extend_schema(
        summary="Create a campaign (always a DRAFT)",
        request=CampaignWriteSerializer,
        responses={201: CampaignOwnerSerializer},
    )
    def post(self, request):
        company = _own_company(request)
        serializer = CampaignWriteSerializer(data=request.data, context={"company": company})
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        targets = _targets(data)
        try:
            campaign = services.create_campaign(company, data, **targets)
        except services.AdvertisingError as exc:
            raise_api(exc)
        return _own_response(request, campaign.pk, status.HTTP_201_CREATED)


@extend_schema(tags=["advertising-company"])
class CampaignDetailView(APIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = CampaignOwnerSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: CampaignOwnerSerializer}, summary="One of my campaigns")
    def get(self, request, pk):
        return Response(
            CampaignOwnerSerializer(get_object_or_404(_own_campaigns(request), pk=pk)).data
        )

    @extend_schema(
        request=CampaignWriteSerializer,
        responses={200: CampaignOwnerSerializer},
        summary="Edit a DRAFT campaign (anything else is frozen)",
    )
    def patch(self, request, pk):
        company = _own_company(request)
        campaign = get_object_or_404(_own_campaigns(request), pk=pk)
        serializer = CampaignWriteSerializer(
            campaign, data=request.data, partial=True, context={"company": company}
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        targets = _targets(data)
        try:
            services.update_campaign(company, campaign.pk, data, **targets)
        except services.AdvertisingError as exc:
            raise_api(exc)
        return _own_response(request, campaign.pk)


def _lifecycle_view(action_name: str, summary: str):
    @extend_schema(tags=["advertising-company"], summary=summary)
    class View(APIView):
        permission_classes = [HasMedicalCompany]
        serializer_class = None

        @extend_schema(request=None, responses={200: CampaignOwnerSerializer})
        def post(self, request, pk):
            _require_no_body(request)
            action = getattr(services, action_name)
            try:
                campaign = action(_own_company(request), pk)
            except services.AdvertisingError as exc:
                raise_api(exc)
            return _own_response(request, campaign.pk)

    View.__name__ = (
        "CampaignSubmitView" if action_name == "submit_campaign" else "CampaignCancelView"
    )
    return View


CampaignSubmitView = _lifecycle_view(
    "submit_campaign", "Submit a draft: the backend prices it and awaits payment verification"
)
CampaignCancelView = _lifecycle_view("cancel_campaign", "Cancel an active campaign")


@extend_schema(tags=["advertising-company"])
class QuoteView(APIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = QuoteDatesSerializer

    @extend_schema(
        request=QuoteDatesSerializer,
        responses={200: QuoteResponseSerializer},
        summary="Price preview from the current backend rate (submission recomputes it)",
    )
    def post(self, request):
        serializer = QuoteDatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = services.quote_for_dates(
                serializer.validated_data["starts_on"], serializer.validated_data["ends_on"]
            )
        except services.AdvertisingError as exc:
            raise_api(exc)
        return Response(
            QuoteResponseSerializer(
                {
                    "days": quote.days,
                    "daily_rate": quote.daily_rate,
                    "total": quote.total,
                    "currency": quote.currency,
                }
            ).data
        )


@extend_schema(tags=["advertising-company"])
class DashboardView(APIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = CampaignDashboardSerializer

    @extend_schema(responses={200: CampaignDashboardSerializer}, summary="My campaign counts")
    def get(self, request):
        return Response(
            CampaignDashboardSerializer(services.dashboard_summary(_own_company(request))).data
        )


# ---- providers ---------------------------------------------------------------------------------


@extend_schema(
    tags=["advertising"],
    summary="Sponsored campaigns targeted at my provider profile (paginated)",
)
class SponsoredCampaignListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, CanBrowseMarketplace]
    serializer_class = SponsoredCampaignSerializer
    filter_backends: list = []  # no client filtering: the backend alone decides who sees what
    queryset = AdvertisingCampaign.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AdvertisingCampaign.objects.none()
        provider = current_verified_provider(self.request.user)  # re-read, never cached
        if provider is None:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(BROWSE_DENIED)
        return (
            AdvertisingCampaign.objects.visible_to(provider)
            .select_related(
                "product",
                "product__company",
                "product__company__governorate",
                "product__company__city",
            )
            .prefetch_related(
                Prefetch(
                    "product__category", queryset=ProductCategory.objects.with_publishability()
                )
            )
            .order_by("ends_on", "id")
        )


# ---- administrators ----------------------------------------------------------------------------


def _admin_campaigns():
    # The admin payload shows who verified a payment: load that account in the same
    # statement (owner/provider queries deliberately do not).
    return _with_relations(
        AdvertisingCampaign.objects.with_live_state().select_related(
            "company__account", "payment__verified_by"
        )
    )


@extend_schema(tags=["admin-advertising"])
class AdminCampaignListView(generics.ListAPIView):
    permission_classes = [IsAdminAccount]
    serializer_class = CampaignAdminSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = AdminCampaignFilter
    queryset = AdvertisingCampaign.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AdvertisingCampaign.objects.none()
        return _admin_campaigns().order_by("-created_at", "id")

    @extend_schema(summary="All campaigns (paginated; filters: status, company, payment_status)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(tags=["admin-advertising"], summary="One campaign with its payment")
class AdminCampaignDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminAccount]
    serializer_class = CampaignAdminSerializer
    queryset = AdvertisingCampaign.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AdvertisingCampaign.objects.none()
        return _admin_campaigns()


def _admin_response(pk):
    return Response(CampaignAdminSerializer(_admin_campaigns().get(pk=pk)).data)


@extend_schema(tags=["admin-advertising"])
class AdminVerifyPaymentView(APIView):
    permission_classes = [IsAdminAccount]
    serializer_class = PaymentVerificationSerializer

    @extend_schema(
        request=PaymentVerificationSerializer,
        responses={200: CampaignAdminSerializer},
        summary="Verify the off-platform payment: the campaign becomes ACTIVE",
    )
    def post(self, request, pk):
        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.verify_campaign_payment(
                pk, verified_by=request.user, **serializer.validated_data
            )
        except services.AdvertisingError as exc:
            raise_api(exc)
        return _admin_response(pk)


@extend_schema(tags=["admin-advertising"])
class AdminRejectPaymentView(APIView):
    permission_classes = [IsAdminAccount]
    serializer_class = PaymentRejectionSerializer

    @extend_schema(
        request=PaymentRejectionSerializer,
        responses={200: CampaignAdminSerializer},
        summary="Reject the payment: the campaign becomes REJECTED (history)",
    )
    def post(self, request, pk):
        serializer = PaymentRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.reject_campaign_payment(
                pk, reason=serializer.validated_data["reason"], rejected_by=request.user
            )
        except services.AdvertisingError as exc:
            raise_api(exc)
        return _admin_response(pk)
