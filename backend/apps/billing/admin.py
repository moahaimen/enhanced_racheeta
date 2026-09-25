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
    UsageEvent,
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
            if cleaned.get("is_default") or self.instance.is_default:
                self.add_error(
                    "is_active",
                    "This is the default plan of its audience; make another plan the default "
                    "before retiring it.",
                )
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

    def has_delete_permission(self, request, obj=None):
        # The default plan is what every unsubscribed account resolves to.
        return obj is None or not obj.is_default


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
    actions = None  # no bulk delete of lifecycle history

    def has_add_permission(self, request):
        return False  # subscriptions are requested by owners and activated by services

    def has_delete_permission(self, request, obj=None):
        return False  # history is part of the audit trail


class InspectionOnlyAdmin(admin.ModelAdmin):
    """Service-managed state: search, filter and read, never add, edit or delete.
    Every field is read-only; bulk actions are removed (no delete_selected)."""

    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.concrete_fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # view-only pages: no save row, POSTs are refused

    def has_delete_permission(self, request, obj=None):
        return False


class CreditBalanceInline(ReadOnlyInline):
    model = CreditBalance
    readonly_fields = ("key", "balance", "updated_at")


class SubscriptionInline(ReadOnlyInline):
    model = Subscription
    fields = ("plan", "status", "starts_at", "ends_at", "created_at")
    readonly_fields = fields
    show_change_link = True


@admin.register(BillingAccount)
class BillingAccountAdmin(InspectionOnlyAdmin):
    """Identity (subject_type, subject_id, audience) binds subscriptions, usage
    and credits to an organisation or account: created by services on first
    use, never re-bound or deleted here."""

    list_display = ("subject_type", "subject_id", "audience", "created_at")
    list_filter = ("subject_type", "audience")
    search_fields = ("subject_id",)
    inlines = [SubscriptionInline, CreditBalanceInline]


@admin.register(CreditBalance)
class CreditBalanceAdmin(InspectionOnlyAdmin):
    """Balances move only through `services.grant_credits` (locked, ledgered,
    audited); the row itself is never created, moved between accounts or deleted."""

    list_display = ("billing_account", "key", "balance", "updated_at")
    list_filter = ("key",)
    search_fields = ("billing_account__subject_id",)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(InspectionOnlyAdmin):
    list_display = ("billing_account", "key", "delta", "reason", "actor", "created_at")
    list_filter = ("reason", "key")
    search_fields = ("billing_account__subject_id", "reference")


@admin.register(UsageCounter)
class UsageCounterAdmin(InspectionOnlyAdmin):
    list_display = ("billing_account", "key", "period_start", "used")
    list_filter = ("key",)
    search_fields = ("billing_account__subject_id",)


@admin.register(UsageEvent)
class UsageEventAdmin(InspectionOnlyAdmin):
    list_display = (
        "billing_account",
        "key",
        "amount",
        "reference",
        "covered_by_credit",
        "created_at",
    )
    list_filter = ("key", "covered_by_credit")
    search_fields = ("billing_account__subject_id", "reference")


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(InspectionOnlyAdmin):
    list_display = ("subscription", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)


@admin.register(PaymentRecord)
class PaymentRecordAdmin(InspectionOnlyAdmin):
    list_display = (
        "subscription",
        "amount",
        "currency",
        "method",
        "reference",
        "status",
        "created_at",
    )
    list_filter = ("method", "status")
    search_fields = ("reference",)
