from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount

from . import services
from .models import BillingAccount, PaymentRecord, Plan, Subscription
from .serializers import (
    ActivateSerializer,
    AdminSubscriptionSerializer,
    BillingSummarySerializer,
    CreditBalanceSerializer,
    CreditGrantSerializer,
    EntitlementSerializer,
    PlanSerializer,
    ReasonSerializer,
)
from .types import Audience, PaymentMethod, PaymentStatus


def billing_summary(ent: services.EntitlementService) -> dict:
    """Build the self-service summary for any subject (used by jobs endpoints)."""
    acc = ent.billing_account
    return {
        "plan": ent.plan,
        "subscription": ent.subscription,
        "entitlements": [EntitlementSerializer.from_entitlement(e) for e in ent.all()],
        "requestable_plans": list(
            Plan.objects.filter(
                audience=acc.audience, is_active=True, is_public=True
            ).prefetch_related("entitlements")
        ),
    }


@extend_schema(
    tags=["billing"],
    summary="Public plan catalogue",
    parameters=[OpenApiParameter("audience", str)],
)
class PlanListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PlanSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {"audience": ["exact"]}
    queryset = Plan.objects.filter(is_active=True, is_public=True).prefetch_related("entitlements")


# ---- administrators ---------------------------------------------------------


@extend_schema(tags=["admin"], summary="Subscriptions (administrators)")
class AdminSubscriptionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = AdminSubscriptionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        "status": ["exact"],
        "billing_account__subject_type": ["exact"],
        "plan__code": ["exact"],
    }
    queryset = (
        Subscription.objects.select_related("plan", "billing_account", "requested_by")
        .prefetch_related("plan__entitlements", "events__actor", "payments")
        .order_by("-created_at")
    )


class _AdminSubscriptionAction(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = ReasonSerializer
    audit_action = ""

    def _get(self, pk) -> Subscription:
        return get_object_or_404(
            Subscription.objects.select_related("plan", "billing_account"), pk=pk
        )

    def _respond(self, sub: Subscription) -> Response:
        sub = (
            Subscription.objects.select_related("plan", "billing_account", "requested_by")
            .prefetch_related("plan__entitlements", "events__actor", "payments")
            .get(pk=sub.pk)
        )
        return Response(AdminSubscriptionSerializer(sub).data)


@extend_schema(tags=["admin"], summary="Activate a subscription after verifying payment manually")
class AdminSubscriptionActivateView(_AdminSubscriptionAction):
    serializer_class = ActivateSerializer

    @extend_schema(request=ActivateSerializer, responses={200: AdminSubscriptionSerializer})
    def post(self, request, pk):
        sub = self._get(pk)
        serializer = ActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            services.activate_subscription(
                sub,
                admin=request.user,
                term_days=data.get("term_days"),
                reference=data.get("reference", ""),
                note=data.get("note", ""),
            )
        except services.SubscriptionError as exc:
            raise ValidationError(
                {"non_field_errors": [str(exc)]}, code="invalid_transition"
            ) from exc
        if data.get("payment"):
            PaymentRecord.objects.create(
                subscription=sub, recorded_by=request.user, **data["payment"]
            )
        elif data.get("reference"):
            # Minimal bookkeeping: the off-platform payment the administrator verified.
            PaymentRecord.objects.create(
                subscription=sub,
                recorded_by=request.user,
                reference=data["reference"],
                method=PaymentMethod.OTHER,
                status=PaymentStatus.VERIFIED,
                note=data.get("note", ""),
            )
        return self._respond(sub)


def _reason_view(fn, summary):
    @extend_schema(tags=["admin"], summary=summary)
    class View(_AdminSubscriptionAction):
        @extend_schema(request=ReasonSerializer, responses={200: AdminSubscriptionSerializer})
        def post(self, request, pk):
            sub = self._get(pk)
            serializer = ReasonSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                fn(sub, admin=request.user, reason=serializer.validated_data.get("reason", ""))
            except services.SubscriptionError as exc:
                raise ValidationError(
                    {"non_field_errors": [str(exc)]}, code="invalid_transition"
                ) from exc
            return self._respond(sub)

    View.__name__ = f"AdminSubscription{fn.__name__.split('_')[0].title()}View"
    return View


AdminSubscriptionRejectView = _reason_view(
    services.reject_subscription, "Reject a pending subscription request"
)
AdminSubscriptionSuspendView = _reason_view(
    services.suspend_subscription, "Suspend an active subscription"
)
AdminSubscriptionCancelView = _reason_view(services.cancel_subscription, "Cancel a subscription")


@extend_schema(tags=["admin"], summary="Grant or revoke extra credits for an entitlement key")
class AdminCreditGrantView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = CreditGrantSerializer

    @extend_schema(request=CreditGrantSerializer, responses={200: CreditBalanceSerializer})
    def post(self, request):
        serializer = CreditGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        account = get_object_or_404(BillingAccount, pk=data["billing_account"])
        try:
            balance = services.grant_credits(
                account, data["key"], data["amount"], admin=request.user, note=data.get("note", "")
            )
        except services.SubscriptionError as exc:
            raise ValidationError({"amount": [str(exc)]}, code="invalid_amount") from exc
        return Response(CreditBalanceSerializer(balance).data, status=status.HTTP_200_OK)


@extend_schema(tags=["admin"], summary="Entitlement state of a billing account (administrators)")
class AdminBillingAccountView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = BillingSummarySerializer

    @extend_schema(responses={200: BillingSummarySerializer})
    def get(self, request, pk):
        account = get_object_or_404(BillingAccount, pk=pk)
        ent = services.EntitlementService(account)
        return Response(BillingSummarySerializer(billing_summary(ent)).data)


__all__ = ["Audience"]
