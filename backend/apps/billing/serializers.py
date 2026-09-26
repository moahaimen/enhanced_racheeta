from rest_framework import serializers

from .models import (
    CreditBalance,
    PaymentRecord,
    Plan,
    PlanEntitlement,
    Subscription,
    SubscriptionEvent,
)
from .services import Entitlement


class PlanEntitlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanEntitlement
        fields = ("key", "kind", "enabled", "limit", "period")
        read_only_fields = fields


class PlanSerializer(serializers.ModelSerializer):
    entitlements = PlanEntitlementSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = (
            "id",
            "code",
            "audience",
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
            "billing_period",
            "term_days",
            "price_amount",
            "price_currency",
            "is_default",
            "entitlements",
        )
        read_only_fields = fields


class EntitlementSerializer(serializers.Serializer):
    key = serializers.CharField()
    kind = serializers.CharField()
    enabled = serializers.BooleanField()
    limit = serializers.IntegerField(allow_null=True)
    period = serializers.CharField()
    used = serializers.IntegerField()
    credits = serializers.IntegerField()
    remaining = serializers.IntegerField(allow_null=True)

    @classmethod
    def from_entitlement(cls, ent: Entitlement) -> dict:
        return {
            "key": ent.key,
            "kind": ent.kind,
            "enabled": ent.enabled,
            "limit": ent.limit,
            "period": ent.period,
            "used": ent.used,
            "credits": ent.credits,
            "remaining": ent.remaining,
        }


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ("id", "plan", "status", "requester_note", "starts_at", "ends_at", "created_at")
        read_only_fields = fields


class BillingSummarySerializer(serializers.Serializer):
    """What a subject sees about its own commercial state. No admin notes."""

    plan = PlanSerializer(allow_null=True)
    # The ACTIVE subscription the entitlements resolve through (null when the
    # audience default plan applies).
    subscription = SubscriptionSerializer(allow_null=True)
    # A request waiting for an administrator. Never affects entitlements; it
    # exists so the client can keep showing the pending state across reloads.
    pending_subscription = SubscriptionSerializer(allow_null=True)
    entitlements = EntitlementSerializer(many=True)
    requestable_plans = PlanSerializer(many=True)


class SubscriptionRequestSerializer(serializers.Serializer):
    plan = serializers.SlugRelatedField(
        slug_field="code", queryset=Plan.objects.filter(is_active=True, is_public=True)
    )
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


# ---- administrators ---------------------------------------------------------


class SubscriptionEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = SubscriptionEvent
        fields = ("from_status", "to_status", "actor_email", "reason", "created_at")
        read_only_fields = fields


class PaymentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRecord
        fields = ("id", "amount", "currency", "method", "reference", "status", "note", "created_at")
        read_only_fields = ("id", "created_at")


class AdminSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    subject_type = serializers.CharField(source="billing_account.subject_type", read_only=True)
    subject_id = serializers.UUIDField(source="billing_account.subject_id", read_only=True)
    billing_account_id = serializers.UUIDField(source="billing_account.id", read_only=True)
    requested_by_email = serializers.EmailField(
        source="requested_by.email", read_only=True, default=None
    )
    events = SubscriptionEventSerializer(many=True, read_only=True)
    payments = PaymentRecordSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "billing_account_id",
            "subject_type",
            "subject_id",
            "plan",
            "status",
            "requested_by_email",
            "requester_note",
            "starts_at",
            "ends_at",
            "admin_reference",
            "admin_note",
            "events",
            "payments",
            "created_at",
        )
        read_only_fields = fields


class ActivationPaymentSerializer(serializers.ModelSerializer):
    """The payment an administrator verified before activating. Its status is
    not an input: activation succeeds only for a verified payment, so the
    server records VERIFIED (see ActivateSerializer.validate)."""

    class Meta:
        model = PaymentRecord
        fields = ("amount", "currency", "method", "reference", "note")


class ActivateSerializer(serializers.Serializer):
    term_days = serializers.IntegerField(required=False, min_value=1, max_value=3660)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    payment = ActivationPaymentSerializer(required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # Nested serializers see no raw input, so the refusal lives here: a
        # client never chooses the verification status of an activation payment.
        payment = (getattr(self, "initial_data", None) or {}).get("payment")
        if isinstance(payment, dict) and "status" in payment:
            raise serializers.ValidationError(
                {
                    "payment": {
                        "status": [
                            serializers.ErrorDetail(
                                "This field cannot be set by a client.", code="field_not_allowed"
                            )
                        ]
                    }
                }
            )
        return attrs


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class CreditGrantSerializer(serializers.Serializer):
    billing_account = serializers.UUIDField()
    key = serializers.CharField(max_length=60)
    amount = serializers.IntegerField(min_value=-100000, max_value=100000)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class CreditBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditBalance
        fields = ("key", "balance")
        read_only_fields = fields
