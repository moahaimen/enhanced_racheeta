"""Finance API (Racheeta staff with the finance permission) and the seller's own statement."""

from decimal import Decimal

from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commerce.views import COMPANY_PARAM, ERRORS, FINANCE, _merchant_company_id, raise_api
from apps.marketplace.models import MedicalCompany

from . import settlement
from .models import (
    LedgerEntry,
    LedgerLine,
    MarketplaceCommissionPolicy,
    SellerRecovery,
    SettlementBatch,
)
from .posting import current_policy
from .serializers import (
    LedgerEntrySerializer,
    PolicySerializer,
    ReconciliationSerializer,
    RecoveryCreateSerializer,
    RecoverySerializer,
    SellerPayableSerializer,
    SettlementConfirmSerializer,
    SettlementPrepareSerializer,
    SettlementSerializer,
    StatementSerializer,
)
from .types import Account, SettlementStatus


def _statement(company_id) -> dict:
    data = settlement.statement(company_id)
    data["commission_rate"] = current_policy().rate_percent
    data["settlements"] = SettlementBatch.objects.filter(company_id=company_id).select_related(
        "company", "confirmed_by"
    )[:50]
    return data


class SellerStatementView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="My merchant statement: sales, 20% commission, refunds, payouts, amount owed",
        parameters=[COMPANY_PARAM],
        responses=StatementSerializer,
    )
    def get(self, request):
        company_id = _merchant_company_id(request, "company.finance.view")
        return Response(StatementSerializer(_statement(company_id)).data)


class AdminStatementView(APIView):
    permission_classes = FINANCE

    @extend_schema(tags=["finance"], summary="A seller's statement", responses=StatementSerializer)
    def get(self, request, pk):
        return Response(StatementSerializer(_statement(pk)).data)


class ReconciliationView(APIView):
    permission_classes = FINANCE

    @extend_schema(
        tags=["finance"],
        summary="Ledger reconciliation: balances re-derived from orders, settlements and refunds",
        responses=ReconciliationSerializer,
    )
    def get(self, request):
        return Response(ReconciliationSerializer(settlement.reconciliation()).data)


@extend_schema(tags=["finance"], summary="Ledger entries (immutable, newest first)")
class LedgerEntryListView(generics.ListAPIView):
    permission_classes = FINANCE
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        qs = LedgerEntry.objects.select_related("order").prefetch_related("lines__company")
        kind = self.request.query_params.get("kind")
        return (qs.filter(kind=kind) if kind else qs).order_by("-created_at", "id")


class SellerPayableListView(APIView):
    permission_classes = FINANCE

    @extend_schema(
        tags=["finance"],
        summary="What Racheeta owes each seller, and what each seller owes Racheeta, right now",
        responses=SellerPayableSerializer(many=True),
    )
    def get(self, request):
        rows = (
            LedgerLine.objects.filter(
                account__in=[Account.SELLER_PAYABLE, Account.SELLER_RECEIVABLE]
            )
            .values("company_id")
            .annotate(
                payable=Coalesce(
                    Sum(F("credit") - F("debit"), filter=Q(account=Account.SELLER_PAYABLE)),
                    Value(Decimal("0")),
                ),
                receivable=Coalesce(
                    Sum(F("debit") - F("credit"), filter=Q(account=Account.SELLER_RECEIVABLE)),
                    Value(Decimal("0")),
                ),
            )
            .order_by("-payable", "-receivable")
        )
        names = dict(
            MedicalCompany.objects.filter(pk__in=[r["company_id"] for r in rows]).values_list(
                "pk", "name"
            )
        )
        drafts = {
            d["company_id"]: {"id": str(d["id"]), "amount": d["amount"]}
            for d in SettlementBatch.objects.filter(status=SettlementStatus.DRAFT).values(
                "id", "company_id", "amount"
            )
        }
        payload = [
            {
                "company": {"id": str(r["company_id"]), "name": names.get(r["company_id"], "")},
                "payable": r["payable"],
                "receivable": r["receivable"],
                "draft_settlement": drafts.get(r["company_id"]),
            }
            for r in rows
        ]
        return Response(SellerPayableSerializer(payload, many=True).data)


class SettlementListView(generics.ListAPIView):
    permission_classes = FINANCE
    serializer_class = SettlementSerializer

    def get_queryset(self):
        qs = SettlementBatch.objects.select_related("company", "confirmed_by")
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs

    @extend_schema(tags=["finance"], summary="Seller settlements (payout batches)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SettlementPrepareView(APIView):
    permission_classes = FINANCE

    @extend_schema(
        tags=["finance"],
        summary="Prepare (preview) a payout of everything owed to one seller",
        request=SettlementPrepareSerializer,
        responses={201: SettlementSerializer},
    )
    def post(self, request):
        serializer = SettlementPrepareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch = settlement.prepare(serializer.validated_data["company"], actor=request.user)
        except ERRORS as exc:
            raise_api(exc)
        return Response(SettlementSerializer(batch).data, status=status.HTTP_201_CREATED)


class SettlementConfirmView(APIView):
    permission_classes = FINANCE

    @extend_schema(
        tags=["finance"],
        summary="Mark a prepared payout PAID (simulated transfer) — posts the payout entry once",
        request=SettlementConfirmSerializer,
        responses=SettlementSerializer,
    )
    def post(self, request, pk):
        serializer = SettlementConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch = settlement.confirm(
                pk, actor=request.user, reference_note=serializer.validated_data["reference_note"]
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(SettlementSerializer(batch).data)


class SettlementCancelView(APIView):
    permission_classes = FINANCE

    @extend_schema(
        tags=["finance"],
        summary="Cancel a prepared payout",
        request=None,
        responses=SettlementSerializer,
    )
    def post(self, request, pk):
        try:
            batch = settlement.cancel(pk, actor=request.user)
        except ERRORS as exc:
            raise_api(exc)
        return Response(SettlementSerializer(batch).data)


class PolicyListView(generics.ListAPIView):
    """Commission policy versions (read-only here; a new version is a reviewed migration)."""

    permission_classes = FINANCE
    serializer_class = PolicySerializer
    pagination_class = None

    def get_queryset(self):
        return MarketplaceCommissionPolicy.objects.order_by("-effective_from", "-version")

    @extend_schema(tags=["finance"], summary="Commission policy versions (current first)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RecoveryListView(generics.ListAPIView):
    """Recoveries from sellers (refunds after payout that the seller paid back; simulated)."""

    permission_classes = FINANCE
    serializer_class = RecoverySerializer

    def get_queryset(self):
        return SellerRecovery.objects.select_related("company")

    @extend_schema(tags=["finance"], summary="Amounts recovered from sellers (simulated)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["finance"],
        summary="Record that a seller paid back what it owes (simulated; never more than owed)",
        request=RecoveryCreateSerializer,
        responses={201: RecoverySerializer},
    )
    def post(self, request):
        serializer = RecoveryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            recovery = settlement.record_recovery(
                data["company"],
                actor=request.user,
                amount=data["amount"],
                reference_note=data["reference_note"],
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(RecoverySerializer(recovery).data, status=status.HTTP_201_CREATED)
