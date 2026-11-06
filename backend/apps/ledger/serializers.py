from rest_framework import serializers

from .models import LedgerEntry, LedgerLine, MarketplaceCommissionPolicy, SettlementBatch

MONEY = {"max_digits": 16, "decimal_places": 2}


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceCommissionPolicy
        fields = ("version", "rate_percent", "effective_from", "note", "created_at")
        read_only_fields = fields


class LedgerLineSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()

    def get_company(self, obj) -> dict | None:
        return {"id": str(obj.company_id), "name": obj.company.name} if obj.company_id else None

    class Meta:
        model = LedgerLine
        fields = ("account", "company", "debit", "credit")
        read_only_fields = fields


class LedgerEntrySerializer(serializers.ModelSerializer):
    lines = LedgerLineSerializer(many=True, read_only=True)
    order_number = serializers.SerializerMethodField()

    def get_order_number(self, obj) -> str:
        return obj.order.number if obj.order_id else ""

    class Meta:
        model = LedgerEntry
        fields = (
            "id",
            "reference",
            "kind",
            "currency",
            "memo",
            "order_number",
            "lines",
            "created_at",
        )
        read_only_fields = fields


class SettlementSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()
    confirmed_by = serializers.SerializerMethodField()

    def get_company(self, obj) -> dict:
        return {"id": str(obj.company_id), "name": obj.company.name}

    def get_confirmed_by(self, obj) -> str:
        return obj.confirmed_by.email if obj.confirmed_by_id else ""

    class Meta:
        model = SettlementBatch
        fields = (
            "id",
            "company",
            "currency",
            "amount",
            "status",
            "reference_note",
            "confirmed_by",
            "confirmed_at",
            "created_at",
        )
        read_only_fields = fields


class SettlementPrepareSerializer(serializers.Serializer):
    company = serializers.UUIDField()


class SettlementConfirmSerializer(serializers.Serializer):
    reference_note = serializers.CharField(max_length=200)


class SellerPayableSerializer(serializers.Serializer):
    company = serializers.DictField()
    payable = serializers.DecimalField(**MONEY)
    draft_settlement = serializers.DictField(allow_null=True)


class CheckSerializer(serializers.Serializer):
    name = serializers.CharField()
    expected = serializers.DecimalField(**MONEY)
    actual = serializers.DecimalField(**MONEY)
    ok = serializers.BooleanField()


class ReconciliationSerializer(serializers.Serializer):
    currency = serializers.CharField()
    ok = serializers.BooleanField()
    checks = CheckSerializer(many=True)
    balances = serializers.DictField(child=serializers.DecimalField(**MONEY))
    totals = serializers.DictField(child=serializers.IntegerField())


class StatementEntrySerializer(serializers.Serializer):
    reference = serializers.CharField()
    kind = serializers.CharField()
    order_number = serializers.CharField()
    memo = serializers.CharField()
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    created_at = serializers.DateTimeField()


class StatementSerializer(serializers.Serializer):
    currency = serializers.CharField()
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    gross_sales = serializers.DecimalField(**MONEY)
    seller_discounts = serializers.DecimalField(**MONEY)
    merchandise_net = serializers.DecimalField(**MONEY)
    commission = serializers.DecimalField(**MONEY)
    refunded_commission = serializers.DecimalField(**MONEY)
    refunded_seller_payable = serializers.DecimalField(**MONEY)
    seller_earnings = serializers.DecimalField(**MONEY)
    paid_out = serializers.DecimalField(**MONEY)
    payable = serializers.DecimalField(**MONEY)
    pending_orders = serializers.IntegerField()
    pending_seller_payable = serializers.DecimalField(**MONEY)
    draft_settlement = serializers.DictField(allow_null=True)
    entries = StatementEntrySerializer(many=True)
    settlements = SettlementSerializer(many=True)
