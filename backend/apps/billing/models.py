"""Billing & entitlements. Independent of any business module: subjects are
identified by (subject_type, subject_id), and capabilities by string keys.
Prices are administrator-set and deliberately unset in seeds."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import ProtectedError, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.core.models import BaseModel

from .types import (
    KNOWN_KEYS,
    Audience,
    BillingPeriod,
    CreditReason,
    EntitlementKind,
    PaymentMethod,
    PaymentStatus,
    SubjectType,
    SubscriptionStatus,
    UsagePeriod,
)


class Plan(BaseModel):
    code = models.SlugField(max_length=40, unique=True)
    audience = models.CharField(max_length=20, choices=Audience.choices)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    description_ar = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    billing_period = models.CharField(
        max_length=12, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY
    )
    term_days = models.PositiveSmallIntegerField(
        default=30, help_text="Length of one subscription term"
    )
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, default="IQD")
    is_active = models.BooleanField(default=True)

    is_public = models.BooleanField(default=True, help_text="Shown to users as requestable")
    is_default = models.BooleanField(
        default=False, help_text="Applies to subjects of this audience with no active subscription"
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "billing_plan"
        ordering = ["audience", "sort_order", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["audience"],
                condition=Q(is_default=True),
                name="billing_plan_one_default_per_audience",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.audience})"

    def _validate_default_identity(self) -> None:
        """Invariant: every audience keeps exactly one usable default plan.
        The partial unique constraint gives AT MOST one; this gives AT LEAST
        one by making `is_default` and `audience` immutable once a plan exists
        (there is no default-switch operation in Phase 3, so no ordinary write
        may clear an audience's fallback or move it to another audience), and
        by refusing a second default at creation with a clear error instead of
        a constraint violation. Applies to `save()`; `QuerySet.update()` is not
        used for these columns by any application path (see docs/BILLING.md)."""
        if self._state.adding:  # UUID primary keys are set before the first save
            if (
                self.is_default
                and Plan.objects.filter(audience=self.audience, is_default=True).exists()
            ):
                raise ValidationError(
                    {"is_default": ["This audience already has a default plan."]},
                    code="default_exists",
                )
            return
        stored = Plan.objects.filter(pk=self.pk).values("is_default", "audience").first()
        if stored is None:
            return
        errors = {}
        if stored["is_default"] and not self.is_default:
            errors["is_default"] = [
                "This is the default plan of its audience; every account without a "
                "subscription resolves to it. Switching defaults is not supported."
            ]
        if not stored["is_default"] and self.is_default:
            errors["is_default"] = ["Defaults are fixed; this plan cannot become the default."]
        if stored["audience"] != self.audience:
            errors["audience"] = ["The audience of an existing plan cannot change."]
        if errors:
            raise ValidationError(errors, code="default_fixed")

    def clean(self):
        super().clean()
        self._validate_default_identity()

    def save(self, *args, **kwargs):
        """Invariants: (1) every audience keeps exactly one default plan
        (`_validate_default_identity`); (2) an ACTIVE subscription never
        references a retired plan. Retiring (`is_active` true → false) locks
        this row — the same row lock `activate_subscription` takes before it
        re-reads the plan — and is refused while ACTIVE subscriptions reference
        it, so activation and retirement serialise and can never commit
        ACTIVE + inactive."""
        self._validate_default_identity()
        if self.pk is not None and not self.is_active:
            if self.is_default:
                raise ValidationError(
                    {
                        "is_active": [
                            "This is the default plan of its audience; every account without a "
                            "subscription resolves to it. Make another plan the default first."
                        ]
                    },
                    code="default_plan",
                )
            with transaction.atomic():
                was_active = (
                    Plan.objects.select_for_update()
                    .filter(pk=self.pk)
                    .values_list("is_active", flat=True)
                    .first()
                )
                if was_active:
                    blocking = self.subscriptions.filter(status="ACTIVE").count()
                    if blocking:
                        raise ValidationError(
                            {
                                "is_active": [
                                    f"{blocking} active subscription(s) still reference this "
                                    "plan. Suspend, cancel or let them expire through the "
                                    "subscription lifecycle before retiring it."
                                ]
                            },
                            code="plan_in_use",
                        )
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


@receiver(pre_delete, sender=Plan)
def _refuse_default_plan_deletion(sender, instance: Plan, **kwargs) -> None:
    """The default plan of an audience is what every unsubscribed account
    resolves to. Refused for every ORM path (instance and queryset deletes,
    including admin bulk actions); the surrounding delete transaction rolls
    back, so a mixed selection deletes nothing."""
    if instance.is_default:
        raise ProtectedError(
            f"'{instance.code}' is the default plan of its audience and cannot be deleted.",
            {instance},
        )


class PlanEntitlement(BaseModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="entitlements")
    key = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, choices=EntitlementKind.choices)
    enabled = models.BooleanField(default=True)
    limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="LIMIT kind: null = unlimited"
    )
    period = models.CharField(max_length=14, choices=UsagePeriod.choices, default=UsagePeriod.NONE)

    def validate_shape(self) -> None:
        """Every KNOWN key has one canonical shape (kind, period) in
        `KNOWN_KEYS`, and the services rely on it (`consume()` only counts LIMIT
        rows, periods decide the usage bucket). Refused on every write path,
        not only in the admin form. Unknown keys keep their free shape."""
        expected = KNOWN_KEYS.get(self.key)
        if expected is None:
            return
        kind, period = expected
        errors = {}
        if self.kind != kind:
            errors["kind"] = [f"'{self.key}' is a {kind} entitlement."]
        if self.period != period:
            errors["period"] = [f"'{self.key}' is counted per {period}."]
        if errors:
            raise ValidationError(errors, code="entitlement_shape")

    def clean(self):
        super().clean()
        self.validate_shape()

    def save(self, *args, **kwargs):
        self.validate_shape()
        return super().save(*args, **kwargs)

    class Meta:
        db_table = "billing_plan_entitlement"
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "key"], name="billing_plan_entitlement_unique")
        ]

    def __str__(self) -> str:
        return f"{self.plan.code}:{self.key}"


class BillingAccount(BaseModel):
    """The subject of subscriptions, usage and credits (an organisation or an account)."""

    subject_type = models.CharField(max_length=20, choices=SubjectType.choices)
    subject_id = models.UUIDField()
    audience = models.CharField(max_length=20, choices=Audience.choices)

    class Meta:
        db_table = "billing_account"
        constraints = [
            models.UniqueConstraint(
                fields=["subject_type", "subject_id"], name="billing_account_subject_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.subject_type}:{self.subject_id}"


class Subscription(BaseModel):
    billing_account = models.ForeignKey(
        BillingAccount, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(
        max_length=12, choices=SubscriptionStatus.choices, default=SubscriptionStatus.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    requester_note = models.CharField(max_length=500, blank=True, default="")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    admin_reference = models.CharField(
        max_length=120, blank=True, default="", help_text="External payment/agreement reference"
    )
    admin_note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "billing_subscription"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_account"],
                condition=Q(status__in=["PENDING", "ACTIVE"]),
                name="billing_subscription_one_live_per_account",
            )
        ]
        indexes = [
            models.Index(fields=["billing_account", "status"], name="billing_subscription_acc_idx")
        ]

    def __str__(self) -> str:
        return f"{self.billing_account} {self.plan.code} [{self.status}]"


class SubscriptionEvent(BaseModel):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=12, blank=True, default="")
    to_status = models.CharField(max_length=12)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "billing_subscription_event"
        ordering = ["created_at"]


class PaymentRecord(BaseModel):
    """Minimal manual payment record: reference/amount/status only. No files, no card data."""

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="IQD")
    method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER
    )
    reference = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.RECORDED
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "billing_payment_record"
        ordering = ["-created_at"]


class CreditBalance(BaseModel):
    billing_account = models.ForeignKey(
        BillingAccount, on_delete=models.CASCADE, related_name="credits"
    )
    key = models.CharField(max_length=60)
    balance = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_credit_balance"
        constraints = [
            models.UniqueConstraint(
                fields=["billing_account", "key"], name="billing_credit_balance_unique"
            )
        ]


class CreditTransaction(BaseModel):
    billing_account = models.ForeignKey(
        BillingAccount, on_delete=models.CASCADE, related_name="credit_transactions"
    )
    key = models.CharField(max_length=60)
    delta = models.IntegerField()
    reason = models.CharField(max_length=10, choices=CreditReason.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reference = models.CharField(max_length=120, blank=True, default="")
    note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "billing_credit_transaction"
        ordering = ["-created_at"]


class UsageCounter(BaseModel):
    billing_account = models.ForeignKey(
        BillingAccount, on_delete=models.CASCADE, related_name="usage"
    )
    key = models.CharField(max_length=60)
    period_start = models.DateField()
    used = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_usage_counter"
        constraints = [
            models.UniqueConstraint(
                fields=["billing_account", "key", "period_start"],
                name="billing_usage_counter_unique",
            )
        ]


class UsageEvent(BaseModel):
    """One row per consumption; `reference` makes retries idempotent."""

    billing_account = models.ForeignKey(
        BillingAccount, on_delete=models.CASCADE, related_name="usage_events"
    )
    key = models.CharField(max_length=60)
    amount = models.PositiveSmallIntegerField(default=1)
    reference = models.CharField(max_length=160, blank=True, default="")
    covered_by_credit = models.BooleanField(default=False)

    class Meta:
        db_table = "billing_usage_event"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_account", "key", "reference"],
                condition=~Q(reference=""),
                name="billing_usage_event_reference_unique",
            )
        ]
