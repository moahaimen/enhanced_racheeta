"""The only writer of ledger rows.

`post(reference, ...)` is idempotent: the first call creates the entry, every later call with the
same reference returns the existing entry and writes nothing. It refuses unbalanced entries,
mixed or unsupported currencies, negative amounts and seller lines without a seller.
All amounts are whole Iraqi dinars (Decimal, ROUND_HALF_UP), never binary floats.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum

from .models import LedgerEntry, LedgerLine, MarketplaceCommissionPolicy
from .types import SUPPORTED_CURRENCY, Account

ZERO = Decimal("0")
DINAR = Decimal("1")


class LedgerError(Exception):
    code = "ledger_error"


def dinars(value) -> Decimal:
    """Whole dinars, half-up. The single rounding rule for every marketplace amount."""
    return Decimal(value).quantize(DINAR, rounding=ROUND_HALF_UP)


def commission_of(base: Decimal, rate_percent: Decimal) -> Decimal:
    return dinars(Decimal(base) * Decimal(rate_percent) / Decimal("100"))


def current_policy(at=None) -> MarketplaceCommissionPolicy:
    from django.utils import timezone

    at = at or timezone.now()
    policy = (
        MarketplaceCommissionPolicy.objects.filter(effective_from__lte=at)
        .order_by("-effective_from", "-version")
        .first()
    )
    if policy is None:
        raise LedgerError("No commission policy is in effect.")
    return policy


@dataclass(frozen=True)
class Line:
    account: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    company_id: object = None


def post(
    reference: str,
    *,
    kind: str,
    lines: list[Line],
    currency: str = SUPPORTED_CURRENCY,
    memo: str = "",
    order=None,
    settlement=None,
    actor=None,
) -> tuple[LedgerEntry, bool]:
    """Post one balanced entry once. Returns (entry, created)."""
    existing = LedgerEntry.objects.filter(reference=reference).first()
    if existing is not None:
        return existing, False
    if currency != SUPPORTED_CURRENCY:
        raise LedgerError(f"Unsupported currency {currency!r}; no exchange-rate snapshot exists.")
    merged: dict[tuple[str, object, str], Decimal] = defaultdict(lambda: ZERO)
    for line in lines:
        if line.debit < 0 or line.credit < 0:
            raise LedgerError("Negative ledger amount.")
        if line.debit != dinars(line.debit) or line.credit != dinars(line.credit):
            raise LedgerError("Ledger amounts must be whole dinars.")
        if (line.account == Account.SELLER_PAYABLE) != (line.company_id is not None):
            raise LedgerError("Seller payable lines (and only they) carry a seller.")
        if line.debit:
            merged[(line.account, line.company_id, "debit")] += line.debit
        if line.credit:
            merged[(line.account, line.company_id, "credit")] += line.credit
    total_debit = sum((v for (_, _, side), v in merged.items() if side == "debit"), ZERO)
    total_credit = sum((v for (_, _, side), v in merged.items() if side == "credit"), ZERO)
    if total_debit != total_credit:
        raise LedgerError(f"Unbalanced entry {reference}: {total_debit} != {total_credit}.")
    if total_debit == 0:
        raise LedgerError("Empty ledger entry.")
    try:
        with transaction.atomic():
            entry = LedgerEntry.objects.create(
                reference=reference,
                kind=kind,
                currency=currency,
                memo=memo[:300],
                order=order,
                settlement=settlement,
                posted_by=actor if getattr(actor, "is_authenticated", False) else None,
            )
            LedgerLine.objects.bulk_create(
                [
                    LedgerLine(
                        entry=entry,
                        account=account,
                        company_id=company_id,
                        debit=amount if side == "debit" else ZERO,
                        credit=amount if side == "credit" else ZERO,
                    )
                    for (account, company_id, side), amount in sorted(
                        merged.items(), key=lambda kv: (kv[0][2], kv[0][0], str(kv[0][1]))
                    )
                    if amount > 0
                ]
            )
    except IntegrityError:  # a concurrent worker posted the same reference first
        return LedgerEntry.objects.get(reference=reference), False
    return entry, True


def balance(account: str, *, company_id=None) -> Decimal:
    """Credit-minus-debit balance (positive = liability/revenue owed or earned)."""
    qs = LedgerLine.objects.filter(account=account)
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    row = qs.aggregate(d=Sum("debit"), c=Sum("credit"))
    return (row["c"] or ZERO) - (row["d"] or ZERO)


def unbalanced_entries() -> list[str]:
    """References of entries whose lines do not balance (must always be empty)."""
    from django.db.models import F

    rows = (
        LedgerEntry.objects.annotate(d=Sum("lines__debit"), c=Sum("lines__credit"))
        .filter(~Q(d=F("c")))
        .values_list("reference", flat=True)
    )
    return list(rows)
