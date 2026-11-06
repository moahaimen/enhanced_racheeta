"""Seller payouts, merchant statements and finance reconciliation (all SIMULATED money).

* `prepare(company)` drafts a payout of the seller's whole accrued payable (one draft per seller);
* `confirm(batch)` — an authorized Racheeta finance operator records that the (simulated) transfer
  happened: posts ONE PAYOUT entry (Dr SELLER_PAYABLE, Cr PLATFORM_CASH) and marks it PAID;
  a payout can never exceed what is owed at that moment;
* a refund AFTER the seller was paid out never makes the payable negative: the part that is no
  longer held for the seller becomes SELLER_RECEIVABLE (the seller owes Racheeta). It is offset
  first against the seller's next completed sales, or `record_recovery()` (finance, simulated);
* `reconciliation()` re-derives every ledger balance from the order snapshots and compares.

Lock order (no deadlocks): order rows first, then the seller (MedicalCompany) row, then batches.
Every code path that reads a seller's payable/receivable to decide an amount holds the seller row.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from apps.audit import services as audit

from . import posting
from .models import LedgerEntry, LedgerLine, SellerRecovery, SettlementBatch
from .posting import LedgerError, Line
from .types import SUPPORTED_CURRENCY, Account, EntryKind, SettlementStatus

ZERO = Decimal("0")
FINANCE_PERMISSION = "ledger.change_settlementbatch"


class SettlementError(LedgerError):
    def __init__(self, message: str, code: str = "invalid_settlement"):
        super().__init__(message)
        self.code = code


def is_finance(actor) -> bool:
    return bool(actor and actor.is_active and actor.is_staff and actor.has_perm(FINANCE_PERMISSION))


def require_finance(actor) -> None:
    if not is_finance(actor):
        raise SettlementError("Racheeta finance only.", "not_allowed")


def payable(company_id) -> Decimal:
    return posting.balance(Account.SELLER_PAYABLE, company_id=company_id)


def receivable(company_id) -> Decimal:
    """What the seller owes Racheeta (refunds after payout not yet offset or recovered)."""
    return posting.debit_balance(Account.SELLER_RECEIVABLE, company_id=company_id)


def lock_seller(company_id):
    """Serialize every decision about one seller's balances (refund, accrual, payout, recovery)."""
    from apps.marketplace.models import MedicalCompany

    return MedicalCompany.objects.select_for_update().get(pk=company_id)


def seller_credit_lines(company_id, amount: Decimal) -> list[Line]:
    """Crediting a seller (sale completed): first settle what it owes, then add to its payable.
    The caller holds `lock_seller(company_id)`."""
    owed = max(receivable(company_id), ZERO)
    offset = min(owed, amount)
    return [
        Line(Account.SELLER_RECEIVABLE, credit=offset, company_id=company_id),
        Line(Account.SELLER_PAYABLE, credit=amount - offset, company_id=company_id),
    ]


def seller_debit_lines(company_id, amount: Decimal) -> list[Line]:
    """Debiting a seller (refund after completion): take it from what is still held for the
    seller; whatever was already paid out becomes a receivable. The payable never goes negative.
    The caller holds `lock_seller(company_id)`."""
    held = max(payable(company_id), ZERO)
    from_payable = min(held, amount)
    return [
        Line(Account.SELLER_PAYABLE, debit=from_payable, company_id=company_id),
        Line(Account.SELLER_RECEIVABLE, debit=amount - from_payable, company_id=company_id),
    ]


def _notify_seller(batch: SettlementBatch) -> None:
    from apps.notifications import services as notifications
    from apps.notifications.types import NotificationCategory, NotificationEventType

    owner_id, batch_id, amount = batch.company.account_id, batch.pk, str(batch.amount)
    transaction.on_commit(
        lambda: notifications.create_notification(
            recipient_id=owner_id,
            category=NotificationCategory.ORDER,
            event_type=NotificationEventType.SETTLEMENT_PAID,
            dedupe_key=f"settlement:{batch_id}:paid",
            payload={"amount": amount, "currency": SUPPORTED_CURRENCY},
        ),
        robust=True,
    )


@transaction.atomic
def prepare(company_id, *, actor) -> SettlementBatch:
    """Draft (or refresh the existing draft of) a payout of everything owed to this seller."""
    from apps.marketplace.models import MedicalCompany

    require_finance(actor)
    company = MedicalCompany.objects.select_for_update().filter(pk=company_id).first()
    if company is None:
        raise SettlementError("Seller not found.", "not_found")
    owed = payable(company.pk)
    draft = (
        SettlementBatch.objects.select_for_update()
        .filter(company=company, currency=SUPPORTED_CURRENCY, status=SettlementStatus.DRAFT)
        .first()
    )
    if owed <= 0:
        if draft is not None:
            draft.status = SettlementStatus.CANCELLED
            draft.save(update_fields=["status", "updated_at"])
        raise SettlementError("Nothing is owed to this seller right now.", "nothing_owed")
    if draft is None:
        draft = SettlementBatch.objects.create(
            company=company, currency=SUPPORTED_CURRENCY, amount=owed, prepared_by=actor
        )
    elif draft.amount != owed:
        draft.amount, draft.prepared_by = owed, actor
        draft.save(update_fields=["amount", "prepared_by", "updated_at"])
    audit.record(
        actor=actor,
        action="ledger.settlement.prepared",
        target=draft,
        summary=f"{company.name}: {owed} {SUPPORTED_CURRENCY}",
    )
    return draft


@transaction.atomic
def confirm(batch_id, *, actor, reference_note: str) -> SettlementBatch:
    """Finance marks a draft payout PAID (simulated transfer). Exactly one PAYOUT entry."""
    require_finance(actor)
    batch = (
        SettlementBatch.objects.select_for_update(of=("self",))
        .select_related("company")
        .filter(pk=batch_id)
        .first()
    )
    if batch is None:
        raise SettlementError("Settlement not found.", "not_found")
    if batch.status == SettlementStatus.PAID:
        return batch
    if batch.status != SettlementStatus.DRAFT:
        raise SettlementError("Only a draft settlement can be confirmed.", "invalid_transition")
    note = (reference_note or "").strip()
    if not note:
        raise SettlementError("Record the (simulated) transfer reference.", "invalid")
    # Lock the seller so a concurrent refund cannot reduce the payable under us.
    lock_seller(batch.company_id)
    if batch.amount > payable(batch.company_id):
        raise SettlementError(
            "The amount owed changed (refund?) — prepare the settlement again.", "stale"
        )
    posting.post(
        f"settlement:{batch.pk}:payout",
        kind=EntryKind.PAYOUT,
        settlement=batch,
        actor=actor,
        memo=f"Simulated payout to {batch.company.name} ({note})",
        lines=[
            Line(Account.SELLER_PAYABLE, debit=batch.amount, company_id=batch.company_id),
            Line(Account.PLATFORM_CASH, credit=batch.amount),
        ],
    )
    batch.status = SettlementStatus.PAID
    batch.confirmed_by, batch.confirmed_at = actor, timezone.now()
    batch.reference_note = note[:200]
    batch.save()
    audit.record(
        actor=actor,
        action="ledger.settlement.paid",
        target=batch,
        summary=f"{batch.company.name}: {batch.amount} {batch.currency}",
    )
    _notify_seller(batch)
    return batch


@transaction.atomic
def cancel(batch_id, *, actor) -> SettlementBatch:
    require_finance(actor)
    batch = SettlementBatch.objects.select_for_update().filter(pk=batch_id).first()
    if batch is None:
        raise SettlementError("Settlement not found.", "not_found")
    if batch.status != SettlementStatus.DRAFT:
        raise SettlementError("Only a draft settlement can be cancelled.", "invalid_transition")
    batch.status = SettlementStatus.CANCELLED
    batch.save(update_fields=["status", "updated_at"])
    return batch


@transaction.atomic
def record_recovery(company_id, *, actor, amount, reference_note: str) -> SellerRecovery:
    """Finance records that the seller paid back (simulated) part or all of what it owes."""
    require_finance(actor)
    company = lock_seller(company_id)
    amount = Decimal(amount)
    if amount <= 0 or amount != posting.dinars(amount):
        raise SettlementError("Enter a whole-dinar amount above zero.", "invalid")
    owed = receivable(company.pk)
    if amount > owed:
        raise SettlementError("That is more than the seller owes.", "invalid")
    note = (reference_note or "").strip()
    if not note:
        raise SettlementError("Record the (simulated) transfer reference.", "invalid")
    recovery = SellerRecovery.objects.create(
        company=company,
        currency=SUPPORTED_CURRENCY,
        amount=amount,
        reference_note=note[:200],
        recorded_by=actor,
    )
    posting.post(
        f"recovery:{recovery.pk}",
        kind=EntryKind.RECOVERY,
        actor=actor,
        memo=f"Simulated recovery from {company.name} ({note})",
        lines=[
            Line(Account.PLATFORM_CASH, debit=amount),
            Line(Account.SELLER_RECEIVABLE, credit=amount, company_id=company.pk),
        ],
    )
    audit.record(
        actor=actor,
        action="ledger.recovery.recorded",
        target=recovery,
        summary=f"{company.name}: {amount} {SUPPORTED_CURRENCY}",
    )
    return recovery


# ---- reporting ----------------------------------------------------------------------------------


def _sum(qs, field) -> Decimal:
    return qs.aggregate(v=Sum(field))["v"] or ZERO


def statement(company_id) -> dict:
    """What the seller sold, what Racheeta kept, what was refunded, paid out and is still owed."""
    from apps.commerce.models import Order, OrderItem
    from apps.commerce.types import SettlementState

    orders = Order.objects.filter(merchant_id=company_id)
    accrued_all = OrderItem.objects.filter(
        order__merchant_id=company_id, order__settlement_state=SettlementState.ACCRUED
    )
    # Sales figures are merchandise only; delivery fees and seller-declared tax are pass-through
    # charges the seller receives in full (no commission), reported on their own lines.
    accrued = accrued_all.filter(kind="MERCHANDISE")
    pending = orders.filter(
        paid_at__isnull=False, settlement_state=SettlementState.NOT_ELIGIBLE
    ).exclude(status="CANCELLED")
    paid_out = SettlementBatch.objects.filter(company_id=company_id, status=SettlementStatus.PAID)
    lines = (
        LedgerLine.objects.filter(
            account__in=[Account.SELLER_PAYABLE, Account.SELLER_RECEIVABLE], company_id=company_id
        )
        .select_related("entry", "entry__order")
        .order_by("-entry__created_at", "id")[:200]
    )
    return {
        "currency": SUPPORTED_CURRENCY,
        "gross_sales": _sum(accrued, "line_total"),
        "seller_discounts": _sum(accrued, "seller_discount"),
        "merchandise_net": _sum(accrued, "merchandise_net"),
        "commission": _sum(accrued, "commission"),
        "refunded_commission": _sum(accrued, "refunded_commission"),
        "refunded_seller_payable": _sum(accrued_all, "refunded_seller_payable"),
        "shipping_collected": _sum(accrued_all.filter(kind="SHIPPING"), "seller_payable")
        - _sum(accrued_all.filter(kind="SHIPPING"), "refunded_seller_payable"),
        "tax_collected": _sum(accrued_all.filter(kind="TAX"), "seller_payable")
        - _sum(accrued_all.filter(kind="TAX"), "refunded_seller_payable"),
        "seller_earnings": _sum(accrued_all, "seller_payable")
        - _sum(accrued_all, "refunded_seller_payable"),
        "paid_out": _sum(paid_out, "amount"),
        "payable": payable(company_id),
        "receivable": receivable(company_id),
        "recovered": _sum(SellerRecovery.objects.filter(company_id=company_id), "amount"),
        "pending_orders": pending.count(),
        "pending_seller_payable": _sum(pending, "seller_payable_total"),
        "draft_settlement": SettlementBatch.objects.filter(
            company_id=company_id, status=SettlementStatus.DRAFT
        )
        .values("id", "amount")
        .first(),
        "entries": [
            {
                "reference": line.entry.reference,
                "kind": line.entry.kind,
                "account": line.account,
                "order_number": line.entry.order.number if line.entry.order else "",
                "memo": line.entry.memo,
                "debit": line.debit,
                "credit": line.credit,
                "created_at": line.entry.created_at,
            }
            for line in lines
        ],
    }


def _debit_balance(account) -> Decimal:
    return -posting.balance(account)


def reconciliation() -> dict:
    """Every ledger balance re-derived independently from the order/settlement snapshots."""
    from apps.commerce.models import Order, OrderItem, Refund
    from apps.commerce.types import SettlementState

    accrued = OrderItem.objects.filter(order__settlement_state=SettlementState.ACCRUED)
    paid_orders = Order.objects.filter(paid_at__isnull=False)
    held_orders = paid_orders.filter(settlement_state=SettlementState.NOT_ELIGIBLE)
    payouts = SettlementBatch.objects.filter(status=SettlementStatus.PAID)

    recoveries = SellerRecovery.objects.all()

    expected = {
        Account.PLATFORM_CASH: _sum(paid_orders, "total")
        - _sum(Refund.objects.all(), "amount")
        - _sum(payouts, "amount")
        + _sum(recoveries, "amount"),
        Account.CUSTOMER_FUNDS_HELD: _sum(held_orders, "total")
        - _sum(held_orders, "refunded_total"),
        Account.COMMISSION_REVENUE: _sum(accrued, "commission")
        - _sum(accrued, "refunded_commission"),
        Account.PLATFORM_PROMO_EXPENSE: _sum(accrued, "platform_discount")
        - _sum(accrued, "refunded_platform_discount"),
        # The seller's NET position: what Racheeta owes sellers minus what sellers owe Racheeta.
        "SELLER_NET": _sum(accrued, "seller_payable")
        - _sum(accrued, "refunded_seller_payable")
        - _sum(payouts, "amount")
        + _sum(recoveries, "amount"),
    }
    actual = {
        Account.PLATFORM_CASH: _debit_balance(Account.PLATFORM_CASH),
        Account.CUSTOMER_FUNDS_HELD: posting.balance(Account.CUSTOMER_FUNDS_HELD),
        Account.COMMISSION_REVENUE: posting.balance(Account.COMMISSION_REVENUE),
        Account.PLATFORM_PROMO_EXPENSE: _debit_balance(Account.PLATFORM_PROMO_EXPENSE),
        "SELLER_NET": posting.balance(Account.SELLER_PAYABLE)
        - _debit_balance(Account.SELLER_RECEIVABLE),
    }
    checks = [
        {
            "name": f"balance:{account}",
            "expected": expected[account],
            "actual": actual[account],
            "ok": expected[account] == actual[account],
        }
        for account in expected
    ]
    unbalanced = posting.unbalanced_entries()
    checks.append(
        {"name": "entries_balanced", "expected": 0, "actual": len(unbalanced), "ok": not unbalanced}
    )
    per_seller = {
        row["company_id"]: row
        for row in LedgerLine.objects.filter(
            account__in=[Account.SELLER_PAYABLE, Account.SELLER_RECEIVABLE]
        )
        .values("company_id")
        .annotate(
            payable=Sum(F("credit") - F("debit"), filter=Q(account=Account.SELLER_PAYABLE)),
            receivable=Sum(F("debit") - F("credit"), filter=Q(account=Account.SELLER_RECEIVABLE)),
        )
    }
    negative_payable = [k for k, r in per_seller.items() if (r["payable"] or ZERO) < 0]
    negative_receivable = [k for k, r in per_seller.items() if (r["receivable"] or ZERO) < 0]
    both = [
        k
        for k, r in per_seller.items()
        if (r["payable"] or ZERO) > 0 and (r["receivable"] or ZERO) > 0
    ]
    for name, offenders in (
        ("no_negative_seller_payable", negative_payable),
        ("no_negative_seller_receivable", negative_receivable),
        ("payable_and_receivable_netted", both),
    ):
        checks.append({"name": name, "expected": 0, "actual": len(offenders), "ok": not offenders})
    with_payment = LedgerEntry.objects.filter(kind=EntryKind.PAYMENT).values("order_id")
    missing_payment = paid_orders.exclude(total=0).exclude(pk__in=with_payment).count()
    checks.append(
        {
            "name": "every_paid_order_has_payment_entry",
            "expected": 0,
            "actual": missing_payment,
            "ok": missing_payment == 0,
        }
    )
    double_accrual = (
        LedgerEntry.objects.filter(kind=EntryKind.ACCRUAL)
        .values("order_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .count()
    )
    checks.append(
        {
            "name": "single_accrual_per_order",
            "expected": 0,
            "actual": double_accrual,
            "ok": double_accrual == 0,
        }
    )
    return {
        "currency": SUPPORTED_CURRENCY,
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "balances": {
            Account.PLATFORM_CASH: actual[Account.PLATFORM_CASH],
            Account.CUSTOMER_FUNDS_HELD: actual[Account.CUSTOMER_FUNDS_HELD],
            Account.COMMISSION_REVENUE: actual[Account.COMMISSION_REVENUE],
            Account.SELLER_PAYABLE: posting.balance(Account.SELLER_PAYABLE),
            Account.SELLER_RECEIVABLE: _debit_balance(Account.SELLER_RECEIVABLE),
            Account.PLATFORM_PROMO_EXPENSE: actual[Account.PLATFORM_PROMO_EXPENSE],
        },
        "totals": {
            "orders_paid": paid_orders.count(),
            "orders_accrued": Order.objects.filter(
                settlement_state=SettlementState.ACCRUED
            ).count(),
            "refunds": Refund.objects.count(),
            "payouts": payouts.count(),
            "recoveries": recoveries.count(),
            "entries": LedgerEntry.objects.count(),
        },
    }
