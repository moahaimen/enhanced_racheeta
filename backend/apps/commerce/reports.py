"""Accounting reports (docs/MARKETPLACE_COMMERCE.md §Reports). Read-only, derived from the order
snapshots and the immutable ledger; every figure is whole Iraqi dinars (simulated money).

* seller report: the acting business's orders in a period, with merchandise, discounts, the 20%
  commission, delivery and tax charges, refunds and earnings, plus monthly totals and payouts;
* platform report (Racheeta finance): per seller GMV, commission, Racheeta-funded discounts,
  refunds, payouts and balances, with the reconciliation verdict.
Both can be downloaded as CSV (spreadsheet-safe: cells never start with = + - @).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from apps.ledger import settlement
from apps.ledger.models import SellerRecovery, SettlementBatch
from apps.ledger.types import SettlementStatus
from apps.marketplace.models import MedicalCompany

from .models import Order, OrderItem, Refund
from .types import ItemKind, SettlementState

ZERO = Decimal("0")
MAX_DAYS = 366


class ReportError(Exception):
    code = "invalid"


def period(raw_from: str | None, raw_to: str | None) -> tuple[date, date]:
    today = timezone.localdate()
    try:
        end = date.fromisoformat(raw_to) if raw_to else today
        start = date.fromisoformat(raw_from) if raw_from else end - timedelta(days=89)
    except ValueError as exc:
        raise ReportError("Dates are YYYY-MM-DD.") from exc
    if start > end:
        raise ReportError("The start date is after the end date.")
    if (end - start).days > MAX_DAYS:
        raise ReportError("A report covers at most one year.")
    return start, end


def _bounds(start: date, end: date):
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start, time.min), tz),
        timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz),
    )


def _sum(qs, field) -> Decimal:
    return qs.aggregate(v=Sum(field))["v"] or ZERO


def _item_totals(order: Order) -> dict:
    out = defaultdict(lambda: ZERO)
    for item in order.items.all():
        if item.kind == ItemKind.MERCHANDISE:
            out["list"] += item.line_total
            out["seller_discount"] += item.seller_discount
            out["merchandise_net"] += item.merchandise_net
            out["commission"] += item.commission - item.refunded_commission
        elif item.kind == ItemKind.SHIPPING:
            out["shipping"] += item.seller_payable - item.refunded_seller_payable
        else:
            out["tax"] += item.seller_payable - item.refunded_seller_payable
        out["refunded"] += item.refunded_buyer_paid
        out["earnings"] += item.seller_payable - item.refunded_seller_payable
    return out


ORDER_COLUMNS = (
    "order",
    "placed",
    "completed",
    "status",
    "payment",
    "list",
    "seller_discount",
    "merchandise_net",
    "commission",
    "shipping",
    "tax",
    "refunded",
    "earnings",
    "settled",
)


def seller_report(company_id, start: date, end: date) -> dict:
    lo, hi = _bounds(start, end)
    orders = (
        Order.objects.filter(merchant_id=company_id, created_at__gte=lo, created_at__lt=hi)
        .prefetch_related("items")
        .order_by("created_at", "id")
    )
    rows, totals = [], defaultdict(lambda: ZERO)
    monthly = defaultdict(lambda: defaultdict(lambda: ZERO))
    for order in orders:
        t = _item_totals(order)
        accrued = order.settlement_state == SettlementState.ACCRUED
        row = {
            "order": order.number,
            "placed": order.created_at.date().isoformat(),
            "completed": order.completed_at.date().isoformat() if order.completed_at else "",
            "status": order.status,
            "payment": order.payment_status,
            "list": t["list"],
            "seller_discount": t["seller_discount"],
            "merchandise_net": t["merchandise_net"],
            "commission": t["commission"] if accrued else ZERO,
            "shipping": t["shipping"],
            "tax": t["tax"],
            "refunded": t["refunded"],
            "earnings": t["earnings"] if accrued else ZERO,
            "settled": "yes" if accrued else "no",
        }
        rows.append(row)
        for key in ("list", "seller_discount", "merchandise_net", "refunded"):
            totals[key] += row[key]
        if accrued:
            month = order.completed_at.strftime("%Y-%m")
            for key in ("commission", "shipping", "tax", "earnings", "merchandise_net"):
                totals[f"settled_{key}"] += row[key]
                monthly[month][key] += row[key]
            monthly[month]["orders"] += 1
    payouts = SettlementBatch.objects.filter(
        company_id=company_id,
        status=SettlementStatus.PAID,
        confirmed_at__gte=lo,
        confirmed_at__lt=hi,
    )
    for batch in payouts:
        monthly[batch.confirmed_at.strftime("%Y-%m")]["paid_out"] += batch.amount
    statement = settlement.statement(company_id)
    return {
        "company_id": str(company_id),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "currency": "IQD",
        "commission_note": "Commission is 20% of merchandise after seller discounts; "
        "delivery fees and seller-declared tax carry no commission.",
        "orders": rows,
        "totals": {
            "orders": len(rows),
            "list": totals["list"],
            "seller_discount": totals["seller_discount"],
            "merchandise_net": totals["merchandise_net"],
            "refunded": totals["refunded"],
            "settled_merchandise_net": totals["settled_merchandise_net"],
            "settled_commission": totals["settled_commission"],
            "settled_shipping": totals["settled_shipping"],
            "settled_tax": totals["settled_tax"],
            "settled_earnings": totals["settled_earnings"],
            "paid_out": _sum(payouts, "amount"),
        },
        "months": [
            {"month": m, **{k: v for k, v in values.items()}}
            for m, values in sorted(monthly.items())
        ],
        "balances": {
            "payable": statement["payable"],
            "receivable": statement["receivable"],
        },
    }


SELLER_COLUMNS = (
    "seller",
    "business_type",
    "orders_paid",
    "gmv",
    "refunds",
    "commission",
    "racheeta_discounts",
    "charges_passed_through",
    "paid_out",
    "recovered",
    "payable",
    "receivable",
)


def platform_report(start: date, end: date) -> dict:
    lo, hi = _bounds(start, end)
    paid = Order.objects.filter(paid_at__gte=lo, paid_at__lt=hi)
    accrued = OrderItem.objects.filter(
        order__settlement_state=SettlementState.ACCRUED,
        order__completed_at__gte=lo,
        order__completed_at__lt=hi,
    )
    refunds = Refund.objects.filter(created_at__gte=lo, created_at__lt=hi)
    payouts = SettlementBatch.objects.filter(
        status=SettlementStatus.PAID, confirmed_at__gte=lo, confirmed_at__lt=hi
    )
    recoveries = SellerRecovery.objects.filter(created_at__gte=lo, created_at__lt=hi)
    seller_ids = (
        set(paid.values_list("merchant_id", flat=True))
        | set(accrued.values_list("order__merchant_id", flat=True))
        | set(payouts.values_list("company_id", flat=True))
        | set(recoveries.values_list("company_id", flat=True))
    )
    companies = {c.pk: c for c in MedicalCompany.objects.filter(pk__in=seller_ids)}
    rows = []
    for cid in sorted(seller_ids, key=lambda k: companies[k].name):
        c = companies[cid]
        mine = accrued.filter(order__merchant_id=cid)
        rows.append(
            {
                "seller": c.name,
                "business_type": c.business_type,
                "orders_paid": paid.filter(merchant_id=cid).count(),
                "gmv": _sum(paid.filter(merchant_id=cid), "total"),
                "refunds": _sum(refunds.filter(order__merchant_id=cid), "amount"),
                "commission": _sum(mine, "commission") - _sum(mine, "refunded_commission"),
                "racheeta_discounts": _sum(mine, "platform_discount")
                - _sum(mine, "refunded_platform_discount"),
                "charges_passed_through": _sum(
                    mine.filter(~Q(kind=ItemKind.MERCHANDISE)), "seller_payable"
                )
                - _sum(mine.filter(~Q(kind=ItemKind.MERCHANDISE)), "refunded_seller_payable"),
                "paid_out": _sum(payouts.filter(company_id=cid), "amount"),
                "recovered": _sum(recoveries.filter(company_id=cid), "amount"),
                "payable": settlement.payable(cid),
                "receivable": settlement.receivable(cid),
            }
        )
    totals = {
        key: sum((r[key] for r in rows), ZERO)
        for key in SELLER_COLUMNS
        if key not in ("seller", "business_type")
    }
    recon = settlement.reconciliation()
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "currency": "IQD",
        "sellers": rows,
        "totals": totals,
        "reconciliation_ok": recon["ok"],
        "balances": recon["balances"],
    }


def _cell(value) -> str:
    text = f"{value:.0f}" if isinstance(value, Decimal) else str(value)
    if text and text[0] in "=+-@\t\r" and not _numeric(text):
        text = "'" + text  # never let a spreadsheet run a formula from report data
    return text


def _numeric(text: str) -> bool:
    try:
        Decimal(text)
    except Exception:  # noqa: BLE001 - any non-number is text
        return False
    return True


def to_csv(rows: list[dict], columns: tuple[str, ...]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(c, "")) for c in columns])
    return buffer.getvalue()
