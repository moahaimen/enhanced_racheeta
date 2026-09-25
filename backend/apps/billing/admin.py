from django import forms
from django.contrib import admin

from .models import (
    BillingAccount,
    CreditBalance,
    CreditTransaction,
    PaymentRecord,
    Plan,
    PlanEntitlement,
    Subscription,
    SubscriptionEvent,
    UsageCounter,
)


class PlanEntitlementInline(admin.TabularInline):
    model = PlanEntitlement
    extra = 0


class PlanAdminForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
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
            "is_active",
            "is_public",
            "is_default",
            "sort_order",
        ]

    def clean(self):
        cleaned = super().clean()
        # Same invariant the model enforces, raised here so the admin renders a
        # normal field error instead of a 500. The model still guards every path.
        if self.instance.pk and cleaned.get("is_active") is False:
            blocking = self.instance.subscriptions.filter(status="ACTIVE").count()
            if blocking:
                self.add_error(
                    "is_active",
                    f"{blocking} active subscription(s) still reference this plan; move them "
                    "through the subscription lifecycle first.",
                )
        return cleaned


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanAdminForm
    list_display = (
        "code",
        "audience",
        "name_en",
        "billing_period",
        "term_days",
        "price_amount",
        "price_currency",
        "is_active",
        "is_public",
        "is_default",
        "sort_order",
    )
    list_filter = ("audience", "is_active", "is_public", "is_default")
    search_fields = ("code", "name_en", "name_ar")
    inlines = [PlanEntitlementInline]

    def get_readonly_fields(self, request, obj=None):
        # Prices, limits and flags are legitimate configuration; the identity
        # (code, audience) that subscriptions and seeds reference is not.
        return ("code", "audience") if obj is not None else ()


# Lifecycle state is owned by apps.billing.services (request → activate /
# reject / suspend / cancel / expire, each locked, evented and audited). The
# Django admin is for inspection, search and filtering only: nothing here may
# become a second state machine.
SUBSCRIPTION_LIFECYCLE_FIELDS = (
    "billing_account",
    "plan",
    "status",
    "starts_at",
    "ends_at",
    "requested_by",
    "requester_note",
    "activated_by",
    "admin_reference",
)


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class SubscriptionEventInline(ReadOnlyInline):
    model = SubscriptionEvent
    readonly_fields = ("from_status", "to_status", "actor", "reason", "created_at")


class PaymentInline(ReadOnlyInline):
    model = PaymentRecord
    readonly_fields = (
        "amount",
        "currency",
        "method",
        "reference",
        "status",
        "recorded_by",
        "note",
        "created_at",
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "billing_account",
        "plan",
        "status",
        "starts_at",
        "ends_at",
        "requested_by",
        "created_at",
    )
    list_filter = ("status", "plan")
    search_fields = ("billing_account__subject_id", "requested_by__email", "admin_reference")
    readonly_fields = ("id", "created_at", "updated_at", *SUBSCRIPTION_LIFECYCLE_FIELDS)
    inlines = [SubscriptionEventInline, PaymentInline]

    def has_add_permission(self, request):
        return False  # subscriptions are requested by owners and activated by services

    def has_delete_permission(self, request, obj=None):
        return False  # history is part of the audit trail


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    list_display = ("subject_type", "subject_id", "audience", "created_at")
    list_filter = ("subject_type", "audience")
    search_fields = ("subject_id",)


@admin.register(CreditBalance)
class CreditBalanceAdmin(admin.ModelAdmin):
    list_display = ("billing_account", "key", "balance")
    readonly_fields = ("balance",)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ("billing_account", "key", "delta", "reason", "actor", "created_at")
    readonly_fields = (
        "billing_account",
        "key",
        "delta",
        "reason",
        "actor",
        "reference",
        "note",
        "created_at",
    )


@admin.register(UsageCounter)
class UsageCounterAdmin(admin.ModelAdmin):
    list_display = ("billing_account", "key", "period_start", "used")
    readonly_fields = ("billing_account", "key", "period_start", "used")

    def has_add_permission(self, request):
        return False
