"""Buyer documents (docs/MARKETPLACE_COMMERCE.md §Invoices). LOCAL DEMO: amounts are simulated.

* INVOICE and RECEIPT are issued once when Racheeta finance verifies the (simulated) payment;
* a CREDIT_NOTE is issued for every refund;
* each document stores a frozen snapshot (seller, buyer, lines, charges, totals), so later edits
  of products, names or addresses never change an issued document;
* orders paid before documents existed get theirs on first request (`ensure_issued`, idempotent).
The seller is the seller of record; Racheeta operates the marketplace and collects the payment.
Tax lines appear only when the SELLER declared a tax treatment (Racheeta decides none).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Invoice, Order, Refund
from .types import InvoiceKind, ItemKind, PaymentStatus

DEMO_NOTICE = "Local demonstration document. Fictional data; no real payment was made or received."
PAID_STATUSES = frozenset(
    {
        PaymentStatus.PAID,
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUNDED,
        PaymentStatus.REFUND_PENDING,
    }
)
PREFIX = {InvoiceKind.INVOICE: "INV", InvoiceKind.RECEIPT: "RCP", InvoiceKind.CREDIT_NOTE: "CRN"}


def _money(value) -> str:
    return f"{Decimal(value):.2f}"


def _snapshot(order: Order, kind: str, refund: Refund | None = None) -> dict:
    merchant = order.merchant
    items = list(order.items.order_by("created_at", "id"))
    merchandise = [i for i in items if i.kind == ItemKind.MERCHANDISE]
    taxes = {i.parent_item_id: i for i in items if i.kind == ItemKind.TAX}
    lines = []
    for item in merchandise:
        tax = taxes.get(item.pk)
        lines.append(
            {
                "title": item.title_snapshot,
                "variant": item.variant_label_snapshot,
                "sku": item.sku_snapshot,
                "quantity": item.quantity,
                "unit_price": _money(item.unit_price),
                "line_total": _money(item.line_total),
                "seller_discount": _money(item.seller_discount),
                "platform_discount": _money(item.platform_discount),
                "tax": _money(tax.buyer_paid if tax else 0),
                "total": _money(item.buyer_paid + (tax.buyer_paid if tax else 0)),
                "refunded_quantity": item.refunded_quantity,
            }
        )
    snapshot = {
        "kind": kind,
        "issued_at": timezone.now().isoformat(),
        "currency": order.currency,
        "notice": DEMO_NOTICE,
        "seller": {
            "name": merchant.name,
            "business_type": merchant.business_type,
            "address": merchant.address,
            "governorate": merchant.governorate.name_en if merchant.governorate_id else "",
            "phone": merchant.phone,
            "email": merchant.public_email,
            "tax_registration_number": order.tax_registration_number,
        },
        "operator": "Racheeta marketplace (collects payment on behalf of the seller)",
        "buyer": {
            "name": order.buyer.full_name,
            "address": order.delivery_address,
            "governorate": order.delivery_governorate.name_en,
            "city": order.delivery_city.name_en if order.delivery_city_id else "",
            "phone": order.contact_phone,
        },
        "order": {
            "number": order.number,
            "checkout": order.checkout.number if order.checkout_id else "",
            "placed_at": order.created_at.isoformat(),
            "channel": order.channel,
            "payment_method": order.payment_method,
            "payment_reference": order.payment_reference,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        },
        "lines": lines,
        "tax": {
            "mode": order.tax_mode,
            "rate": _money(order.tax_rate),
            "label": order.tax_label,
            "added": _money(order.tax_total),
            "included": _money(order.tax_included_total),
        },
        "totals": {
            "list": _money(order.list_total),
            "seller_discount": _money(order.seller_discount_total),
            "platform_discount": _money(order.platform_discount_total),
            "shipping": _money(order.shipping_total),
            "tax": _money(order.tax_total),
            "total": _money(order.total),
            "refunded": _money(order.refunded_total),
        },
    }
    if refund is not None:
        snapshot["refund"] = {
            "amount": _money(refund.amount),
            "reason": refund.reason,
            "executed_at": refund.created_at.isoformat(),
        }
    return snapshot


def _number(order: Order, kind: str, refund: Refund | None) -> str:
    base = order.number.split("-", 1)[-1]
    if refund is None:
        return f"{PREFIX[kind]}-{base}"
    n = Invoice.objects.filter(order=order, kind=InvoiceKind.CREDIT_NOTE).count() + 1
    return f"{PREFIX[kind]}-{base}-{n}"


def _issue(order: Order, kind: str, *, total, refund: Refund | None = None) -> Invoice | None:
    existing = Invoice.objects.filter(order=order, kind=kind, refund=refund).first()
    if existing is not None:
        return existing
    try:
        with transaction.atomic():
            return Invoice.objects.create(
                order=order,
                kind=kind,
                number=_number(order, kind, refund),
                refund=refund,
                total=total,
                snapshot=_snapshot(order, kind, refund),
            )
    except IntegrityError:  # issued concurrently: the first one stands
        return Invoice.objects.filter(order=order, kind=kind, refund=refund).first()


def on_payment(order: Order) -> None:
    """Called inside verify_payment's transaction (the order row is locked)."""
    _issue(order, InvoiceKind.INVOICE, total=order.total)
    _issue(order, InvoiceKind.RECEIPT, total=order.total)


def on_refund(order: Order, refund: Refund) -> None:
    _issue(order, InvoiceKind.CREDIT_NOTE, total=refund.amount, refund=refund)


def ensure_issued(order: Order) -> None:
    """Backfill for orders paid before documents existed (idempotent)."""
    if order.payment_status not in PAID_STATUSES or order.paid_at is None:
        return
    with transaction.atomic():
        if not Invoice.objects.filter(order=order, kind=InvoiceKind.INVOICE).exists():
            _issue(order, InvoiceKind.INVOICE, total=order.total)
            _issue(order, InvoiceKind.RECEIPT, total=order.total)
        issued = set(
            Invoice.objects.filter(order=order, kind=InvoiceKind.CREDIT_NOTE).values_list(
                "refund_id", flat=True
            )
        )
        for refund in order.refunds.order_by("created_at", "id"):
            if refund.pk not in issued:
                on_refund(order, refund)
