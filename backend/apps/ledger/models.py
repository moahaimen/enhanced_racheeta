"""Commission policy, immutable double-entry journal and seller settlements."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel

from .types import Account, EntryKind, SettlementStatus


class MarketplaceCommissionPolicy(BaseModel):
    """Centrally controlled commission rate. Sellers can never edit it. A new version applies only
    to orders placed after it takes effect; every order line snapshots the version it used."""

    version = models.PositiveIntegerField(unique=True)
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    effective_from = models.DateTimeField()
    note = models.CharField(max_length=300, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "ledger_commission_policy"
        ordering = ["-effective_from", "-version"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rate_percent__gte=0) & Q(rate_percent__lte=100),
                name="ledger_policy_rate_range",
            )
        ]

    def __str__(self) -> str:
        return f"v{self.version}: {self.rate_percent}%"


class _Immutable(models.Model):
    """Rows are written once. Updates and deletes are refused in Python AND by a PostgreSQL
    trigger (migration 0002); only the guarded demo cleaner may purge registered demo rows."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Ledger records are immutable; post a compensating entry.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Ledger records are immutable; post a compensating entry.")


class LedgerEntry(_Immutable, BaseModel):
    # One business event = one entry. The unique reference makes posting idempotent: a retry, a
    # double click or two workers racing can never post the same event twice.
    reference = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=10, choices=EntryKind.choices)
    currency = models.CharField(max_length=3)
    memo = models.CharField(max_length=300, blank=True, default="")
    order = models.ForeignKey(
        "commerce.Order", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    settlement = models.ForeignKey(
        "ledger.SettlementBatch", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "ledger_entry"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["kind", "created_at"], name="ledger_entry_kind_idx")]

    def __str__(self) -> str:
        return self.reference


class LedgerLine(_Immutable, BaseModel):
    entry = models.ForeignKey(LedgerEntry, on_delete=models.PROTECT, related_name="lines")
    account = models.CharField(max_length=24, choices=Account.choices)
    # The seller dimension (only seller payable/receivable lines carry it; a DB constraint).
    company = models.ForeignKey(
        "marketplace.MedicalCompany",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    debit = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        db_table = "ledger_line"
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0)),
                name="ledger_line_one_side_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(account__in=["SELLER_PAYABLE", "SELLER_RECEIVABLE"], company__isnull=False)
                )
                | (
                    ~Q(account__in=["SELLER_PAYABLE", "SELLER_RECEIVABLE"])
                    & Q(company__isnull=True)
                ),
                name="ledger_line_seller_dimension",
            ),
        ]
        indexes = [models.Index(fields=["account", "company"], name="ledger_line_acct_idx")]

    def __str__(self) -> str:
        return f"{self.account} D{self.debit} C{self.credit}"


class SettlementBatch(BaseModel):
    """A payout to one seller of its accrued payable. Prepared by finance, confirmed (simulated)
    by an authorized finance operator; confirmation posts the PAYOUT entry exactly once."""

    company = models.ForeignKey(
        "marketplace.MedicalCompany", on_delete=models.PROTECT, related_name="settlements"
    )
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=SettlementStatus.choices, default=SettlementStatus.DRAFT
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reference_note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "ledger_settlement"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_settlement_amount_gt0"),
            models.UniqueConstraint(
                fields=["company", "currency"],
                condition=Q(status="DRAFT"),
                name="ledger_one_draft_settlement_per_seller",
            ),
        ]


class SellerRecovery(BaseModel):
    """Finance recorded that a seller paid back (simulated) what it owed after a refund that came
    after its payout. Posts ONE RECOVERY entry: Dr PLATFORM_CASH, Cr SELLER_RECEIVABLE."""

    company = models.ForeignKey(
        "marketplace.MedicalCompany", on_delete=models.PROTECT, related_name="recoveries"
    )
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    reference_note = models.CharField(max_length=200)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "ledger_recovery"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_recovery_amount_gt0"),
        ]

    def __str__(self) -> str:
        return f"{self.company_id} {self.amount}"
