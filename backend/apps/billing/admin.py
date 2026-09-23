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


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
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


class SubscriptionEventInline(admin.TabularInline):
    model = SubscriptionEvent
    extra = 0
    readonly_fields = ("from_status", "to_status", "actor", "reason", "created_at")
    can_delete = False


class PaymentInline(admin.TabularInline):
    model = PaymentRecord
    extra = 0


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
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SubscriptionEventInline, PaymentInline]


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
