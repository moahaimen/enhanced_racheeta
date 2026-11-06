"""Order lifecycle after checkout: seller fulfillment, buyer confirmation, simulated payment,
completion (commission accrual), returns, refunds and disputes.

Who may do what (server-enforced; docs/MARKETPLACE_COMMERCE.md §Lifecycle):
  seller staff   accept / decline / ship; approve or reject a return; mark returned goods received
  buyer          cancel before shipping; confirm receipt; request a return; open a dispute
  finance        verify a (simulated) payment, confirm delivery, complete the order (accrual),
                 execute refunds, resolve disputes — Racheeta staff with the finance permission
Every money movement posts ONE idempotent, balanced ledger entry. Nothing is ever charged.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.ledger import posting
from apps.ledger.posting import Line, dinars
from apps.ledger.types import Account, EntryKind
from apps.notifications.types import NotificationEventType

from . import inventory
from .checkout import notify, release_coupons
from .errors import CommerceError
from .models import Dispute, Order, OrderItem, OrderTransition, Refund, ReturnLine, ReturnRequest
from .types import (
    BUYER_CANCELLABLE,
    MERCHANT_TRANSITIONS,
    RETURN_WINDOW_DAYS,
    RETURNABLE_STATUSES,
    DisputeStatus,
    OrderStatus,
    PaymentStatus,
    ReturnStatus,
    SettlementState,
)

ZERO = Decimal("0")
FINANCE_PERMISSION = "ledger.change_settlementbatch"


class LifecycleError(CommerceError):
    code = "invalid_transition"


def require_finance(actor) -> None:
    """Only an authorized Racheeta finance operator (staff + finance permission)."""
    if not (actor and actor.is_active and actor.is_staff and actor.has_perm(FINANCE_PERMISSION)):
        raise LifecycleError("Racheeta finance only.", "not_allowed")


def _lock(order_id, **scope) -> Order:
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("merchant", "buyer")
        .filter(pk=order_id, **scope)
        .first()
    )
    if order is None:
        raise LifecycleError("Order not found.", "not_found")
    return order


def _move(order: Order, to_status: str, actor, reason: str = "", **fields) -> Order:
    previous = order.status
    order.status = to_status
    order.status_changed_at = timezone.now()
    for key, value in fields.items():
        setattr(order, key, value)
    order.save()
    OrderTransition.objects.create(
        order=order, actor=actor, from_status=previous, to_status=to_status, reason=reason[:500]
    )
    audit.record(
        actor=actor,
        action="commerce.order.status_changed",
        target=order,
        summary=f"{previous} -> {to_status}",
        data={"from_status": previous, "to_status": to_status},
    )
    recipient = order.buyer_id if actor.pk != order.buyer_id else order.merchant.account_id
    notify(
        recipient,
        NotificationEventType.ORDER_STATUS_CHANGED,
        order,
        to_status,
        {
            "order_number": order.number,
            "merchant_name": order.merchant.name,
            "previous_status": previous,
            "status": to_status,
        },
    )
    return order


def _note(order: Order, actor, label: str, data: dict | None = None) -> None:
    OrderTransition.objects.create(
        order=order, actor=actor, from_status=order.status, to_status=label[:24]
    )
    audit.record(
        actor=actor,
        action=f"commerce.order.{label.lower()}",
        target=order,
        summary=order.number,
        data=data or {},
    )


def _cancel(order: Order, actor, reason: str) -> Order:
    inventory.release(order, actor=actor)
    release_coupons(order)
    extra = {}
    if order.payment_status == PaymentStatus.PAID:
        extra["payment_status"] = PaymentStatus.REFUND_PENDING  # finance refunds the full amount
    return _move(order, OrderStatus.CANCELLED, actor, reason, **extra)


# ---- seller -------------------------------------------------------------------------------------


@transaction.atomic
def seller_transition(
    order_id, *, company_id, actor, to_status: str, reason: str = "", shipping_reference: str = ""
) -> Order:
    order = _lock(order_id, merchant_id=company_id)
    if to_status not in MERCHANT_TRANSITIONS.get(order.status, frozenset()):
        raise LifecycleError(f"An order cannot move from {order.status} to {to_status}.")
    if to_status == OrderStatus.CANCELLED:
        return _cancel(order, actor, reason or "Declined by the seller")
    if to_status == OrderStatus.SHIPPED:
        inventory.consume(order, actor=actor)
        return _move(
            order,
            to_status,
            actor,
            reason,
            shipped_at=timezone.now(),
            shipping_reference=shipping_reference.strip()[:120],
        )
    return _move(order, to_status, actor, reason)


# ---- buyer --------------------------------------------------------------------------------------


@transaction.atomic
def buyer_cancel(order_id, *, buyer, reason: str = "") -> Order:
    order = _lock(order_id, buyer=buyer)
    if order.status not in BUYER_CANCELLABLE:
        raise LifecycleError("This order can no longer be cancelled.")
    return _cancel(order, buyer, reason or "Cancelled by the buyer")


@transaction.atomic
def confirm_delivery(order_id, *, actor, as_finance: bool = False) -> Order:
    if as_finance:
        require_finance(actor)
        order = _lock(order_id)
    else:
        order = _lock(order_id, buyer=actor)
    if order.status != OrderStatus.SHIPPED:
        raise LifecycleError("Only a shipped order can be confirmed as delivered.")
    return _move(
        order, OrderStatus.DELIVERED, actor, "Delivery confirmed", delivered_at=timezone.now()
    )


# ---- finance: payment, completion ---------------------------------------------------------------


@transaction.atomic
def verify_payment(order_id, *, actor, reference: str) -> Order:
    """Record SIMULATED payment evidence (cash remitted / transfer seen). Never real money."""
    require_finance(actor)
    order = _lock(order_id)
    if order.payment_status != PaymentStatus.UNPAID:
        return order  # idempotent: verifying twice changes nothing and posts nothing
    if order.status == OrderStatus.CANCELLED:
        raise LifecycleError("A cancelled order cannot be paid.")
    reference = (reference or "").strip()
    if not reference:
        raise LifecycleError("Enter the (simulated) payment reference.", "invalid")
    if order.total > 0:
        posting.post(
            f"order:{order.pk}:payment",
            kind=EntryKind.PAYMENT,
            order=order,
            actor=actor,
            memo=f"Simulated payment for {order.number} ({reference})",
            lines=[
                Line(Account.PLATFORM_CASH, debit=order.total),
                Line(Account.CUSTOMER_FUNDS_HELD, credit=order.total),
            ],
        )
    order.payment_status = PaymentStatus.PAID
    order.payment_reference = reference[:120]
    order.paid_at = timezone.now()
    order.payment_verified_by = actor
    order.save()
    _note(order, actor, "PAYMENT_VERIFIED", {"reference": reference, "amount": str(order.total)})
    notify(
        order.merchant.account_id,
        NotificationEventType.ORDER_STATUS_CHANGED,
        order,
        "paid",
        {"order_number": order.number, "status": "PAID"},
    )
    return order


def _remaining(item: OrderItem) -> dict:
    return {
        "buyer_paid": item.buyer_paid - item.refunded_buyer_paid,
        "platform": item.platform_discount - item.refunded_platform_discount,
        "commission": item.commission - item.refunded_commission,
        "seller": item.seller_payable - item.refunded_seller_payable,
    }


@transaction.atomic
def complete(order_id, *, actor) -> Order:
    """DELIVERED + PAID + no open return/dispute -> COMPLETED; accrue commission and seller
    payable from the REMAINING (non-refunded) line amounts. Exactly once."""
    require_finance(actor)
    order = _lock(order_id)
    if order.settlement_state == SettlementState.ACCRUED:
        return order
    if order.status != OrderStatus.DELIVERED:
        raise LifecycleError("Only a delivered order can be completed.")
    if order.payment_status not in (PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED):
        raise LifecycleError("The payment has not been verified.")
    if order.returns.filter(status__in=["REQUESTED", "APPROVED", "RECEIVED"]).exists():
        raise LifecycleError("A return is still open.")
    if order.disputes.filter(status=DisputeStatus.OPEN).exists():
        raise LifecycleError("A dispute is still open.")
    totals = {"buyer_paid": ZERO, "platform": ZERO, "commission": ZERO, "seller": ZERO}
    for item in order.items.all():
        for key, value in _remaining(item).items():
            totals[key] += value
    if totals["seller"] + totals["commission"] > 0:
        posting.post(
            f"order:{order.pk}:accrual",
            kind=EntryKind.ACCRUAL,
            order=order,
            actor=actor,
            memo=f"Sale completed: {order.number}",
            lines=[
                Line(Account.CUSTOMER_FUNDS_HELD, debit=totals["buyer_paid"]),
                Line(Account.PLATFORM_PROMO_EXPENSE, debit=totals["platform"]),
                Line(Account.SELLER_PAYABLE, credit=totals["seller"], company_id=order.merchant_id),
                Line(Account.COMMISSION_REVENUE, credit=totals["commission"]),
            ],
        )
    order.settlement_state = SettlementState.ACCRUED
    return _move(
        order,
        OrderStatus.COMPLETED,
        actor,
        "Completed; commission accrued",
        completed_at=timezone.now(),
    )


# ---- refunds ------------------------------------------------------------------------------------


def _split(item: OrderItem, quantity: int) -> dict:
    """Refund components for `quantity` more units of a line. Cumulative rounding: refunding a
    line in several steps adds up exactly to refunding it at once. seller = buyer + platform -
    commission keeps every refund entry balanced."""
    done, total = item.refunded_quantity, item.quantity
    after = done + quantity

    def part(amount: Decimal) -> Decimal:
        return dinars(amount * after / total) - dinars(amount * done / total)

    buyer_paid = part(item.buyer_paid)
    platform = part(item.platform_discount)
    commission = part(item.commission)
    return {
        "buyer_paid": buyer_paid,
        "platform": platform,
        "commission": commission,
        "seller": buyer_paid + platform - commission,
    }


def _refund(order: Order, quantities: dict, *, actor, reason: str, return_request=None) -> Refund:
    if order.payment_status not in (
        PaymentStatus.PAID,
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUND_PENDING,
    ):
        raise LifecycleError("There is no verified payment to refund.")
    items = {i.pk: i for i in OrderItem.objects.select_for_update().filter(order=order)}
    totals = {"buyer_paid": ZERO, "platform": ZERO, "commission": ZERO, "seller": ZERO}
    for item_id, qty in quantities.items():
        item = items[item_id]
        if qty <= 0 or item.refunded_quantity + qty > item.quantity:
            raise LifecycleError("Refund quantity exceeds what was bought.")
        parts = _split(item, qty)
        item.refunded_quantity += qty
        item.refunded_buyer_paid += parts["buyer_paid"]
        item.refunded_platform_discount += parts["platform"]
        item.refunded_commission += parts["commission"]
        item.refunded_seller_payable += parts["seller"]
        item.save()
        for key in totals:
            totals[key] += parts[key]
    refund = Refund.objects.create(
        order=order,
        return_request=return_request,
        amount=totals["buyer_paid"],
        reason=reason[:300],
        executed_by=actor,
    )
    if order.settlement_state == SettlementState.ACCRUED:
        lines = [
            Line(Account.SELLER_PAYABLE, debit=totals["seller"], company_id=order.merchant_id),
            Line(Account.COMMISSION_REVENUE, debit=totals["commission"]),
            Line(Account.PLATFORM_PROMO_EXPENSE, credit=totals["platform"]),
            Line(Account.PLATFORM_CASH, credit=totals["buyer_paid"]),
        ]
    else:  # money held, nothing earned yet: give the buyer's money back
        lines = [
            Line(Account.CUSTOMER_FUNDS_HELD, debit=totals["buyer_paid"]),
            Line(Account.PLATFORM_CASH, credit=totals["buyer_paid"]),
        ]
    lines = [line for line in lines if line.debit or line.credit]
    if lines:
        posting.post(
            f"refund:{refund.pk}",
            kind=EntryKind.REFUND,
            order=order,
            actor=actor,
            memo=f"Simulated refund for {order.number}",
            lines=lines,
        )
    order.refunded_total += totals["buyer_paid"]
    fully = all(i.refunded_quantity == i.quantity for i in items.values())
    order.payment_status = PaymentStatus.REFUNDED if fully else PaymentStatus.PARTIALLY_REFUNDED
    order.save()
    _note(
        order,
        actor,
        "REFUNDED" if fully else "PARTIAL_REFUND",
        {"amount": str(totals["buyer_paid"]), "refund": str(refund.pk)},
    )
    notify(
        order.buyer_id,
        NotificationEventType.ORDER_STATUS_CHANGED,
        order,
        f"refund:{refund.pk}",
        {"order_number": order.number, "status": order.payment_status},
    )
    return refund


def _all_remaining(order: Order) -> dict:
    return {
        i.pk: i.quantity - i.refunded_quantity
        for i in order.items.all()
        if i.quantity > i.refunded_quantity
    }


@transaction.atomic
def refund_cancelled(order_id, *, actor) -> Refund:
    """A paid order cancelled before delivery: return everything the buyer paid."""
    require_finance(actor)
    order = _lock(order_id)
    if (
        order.status != OrderStatus.CANCELLED
        or order.payment_status != PaymentStatus.REFUND_PENDING
    ):
        raise LifecycleError("No cancellation refund is pending for this order.")
    return _refund(order, _all_remaining(order), actor=actor, reason="Order cancelled")


# ---- returns ------------------------------------------------------------------------------------


@transaction.atomic
def request_return(order_id, *, buyer, lines: list[dict], reason: str) -> ReturnRequest:
    order = _lock(order_id, buyer=buyer)
    if order.status not in RETURNABLE_STATUSES or order.delivered_at is None:
        raise LifecycleError("Only a delivered order can be returned.")
    if timezone.now() > order.delivered_at + timedelta(days=RETURN_WINDOW_DAYS):
        raise LifecycleError(f"Returns are possible within {RETURN_WINDOW_DAYS} days of delivery.")
    if order.returns.filter(status__in=["REQUESTED", "APPROVED", "RECEIVED"]).exists():
        raise LifecycleError("A return is already open for this order.")
    reason = (reason or "").strip()
    if not reason:
        raise LifecycleError("Tell the seller why you are returning the items.", "invalid")
    items = {str(i.pk): i for i in order.items.all()}
    if not lines:
        raise LifecycleError("Choose at least one item to return.", "invalid")
    request = ReturnRequest.objects.create(order=order, reason=reason[:500])
    for line in lines:
        item = items.get(str(line["item"]))
        qty = int(line["quantity"])
        if item is None or qty < 1 or qty > item.quantity - item.refunded_quantity:
            raise LifecycleError("Invalid return quantity.", "invalid")
        ReturnLine.objects.create(request=request, item=item, quantity=qty)
    _note(order, buyer, "RETURN_REQUESTED", {"return": str(request.pk)})
    notify(
        order.merchant.account_id,
        NotificationEventType.ORDER_STATUS_CHANGED,
        order,
        f"return:{request.pk}",
        {"order_number": order.number, "status": "RETURN_REQUESTED"},
    )
    return request


def _lock_return(return_id, **scope) -> ReturnRequest:
    request = (
        ReturnRequest.objects.select_for_update(of=("self",))
        .select_related("order")
        .filter(pk=return_id, **scope)
        .first()
    )
    if request is None:
        raise LifecycleError("Return not found.", "not_found")
    return request


@transaction.atomic
def decide_return(return_id, *, company_id, actor, approve: bool, note: str = "") -> ReturnRequest:
    request = _lock_return(return_id, order__merchant_id=company_id)
    if request.status != ReturnStatus.REQUESTED:
        raise LifecycleError("This return has already been decided.")
    request.status = ReturnStatus.APPROVED if approve else ReturnStatus.REJECTED
    request.decided_by, request.decided_at = actor, timezone.now()
    request.decision_note = note.strip()[:300]
    request.save()
    audit.record(
        actor=actor, action="commerce.return.decided", target=request, summary=request.status
    )
    return request


@transaction.atomic
def receive_return(return_id, *, company_id, actor) -> ReturnRequest:
    request = _lock_return(return_id, order__merchant_id=company_id)
    if request.status != ReturnStatus.APPROVED:
        raise LifecycleError("Only an approved return can be received.")
    for line in request.lines.select_related("item"):
        inventory.restock(line.item, line.quantity, order=request.order, actor=actor)
    request.status = ReturnStatus.RECEIVED
    request.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=actor, action="commerce.return.received", target=request, summary=request.order.number
    )
    return request


@transaction.atomic
def refund_return(return_id, *, actor) -> Refund:
    require_finance(actor)
    request = _lock_return(return_id)
    if request.status != ReturnStatus.RECEIVED:
        raise LifecycleError("Refund after the seller has received the items.")
    order = _lock(request.order_id)
    quantities = {line.item_id: line.quantity for line in request.lines.all()}
    refund = _refund(
        order, quantities, actor=actor, reason=f"Return: {request.reason}", return_request=request
    )
    request.status = ReturnStatus.REFUNDED
    request.save(update_fields=["status", "updated_at"])
    return refund


# ---- disputes -----------------------------------------------------------------------------------


@transaction.atomic
def open_dispute(order_id, *, buyer, reason: str) -> Dispute:
    order = _lock(order_id, buyer=buyer)
    if order.status not in (OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED):
        raise LifecycleError("A dispute can be opened once the order has shipped.")
    if order.disputes.filter(status=DisputeStatus.OPEN).exists():
        raise LifecycleError("A dispute is already open.")
    reason = (reason or "").strip()
    if not reason:
        raise LifecycleError("Describe the problem.", "invalid")
    dispute = Dispute.objects.create(order=order, opened_by=buyer, reason=reason[:1000])
    _note(order, buyer, "DISPUTE_OPENED", {"dispute": str(dispute.pk)})
    return dispute


@transaction.atomic
def resolve_dispute(dispute_id, *, actor, refund: bool, note: str) -> Dispute:
    require_finance(actor)
    dispute = Dispute.objects.select_for_update(of=("self",)).filter(pk=dispute_id).first()
    if dispute is None:
        raise LifecycleError("Dispute not found.", "not_found")
    if dispute.status != DisputeStatus.OPEN:
        return dispute
    if not (note or "").strip():
        raise LifecycleError("Record the resolution.", "invalid")
    order = _lock(dispute.order_id)
    if refund:
        remaining = _all_remaining(order)
        if remaining:
            _refund(order, remaining, actor=actor, reason=f"Dispute: {note.strip()}")
    dispute.status = DisputeStatus.RESOLVED_REFUND if refund else DisputeStatus.RESOLVED_REJECTED
    dispute.resolution_note = note.strip()[:500]
    dispute.resolved_by, dispute.resolved_at = actor, timezone.now()
    dispute.save()
    _note(order, actor, "DISPUTE_RESOLVED", {"outcome": dispute.status})
    return dispute
