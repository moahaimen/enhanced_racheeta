"""Commerce writes: the only place orders and quote requests are created or change state.

Rules (docs/COMMERCE.md):
* store checkout re-reads every product under row lock with THE public-store rule
  (`Product.objects.consumer_store()`); restricted/prescription items, B2B-only items, unverified or
  non-retail businesses and inactive categories can never be bought, whatever the client sends;
* prices and totals come from the locked rows; client totals are ignored;
* stock is decremented under the same lock (no oversell under concurrency) and restored when an
  order is cancelled;
* quote requests are only possible for a product that THE targeting rule shows to the requesting
  provider right now (`Product.objects.targeted_for`).
"""

from __future__ import annotations

import secrets
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.marketplace.models import MedicalCompany, Product
from apps.notifications import services as notifications
from apps.notifications.types import (
    NotificationCategory,
    NotificationEventType,
    NotificationResourceType,
)

from .models import Order, OrderItem, OrderTransition, QuoteRequest
from .types import (
    BUYER_CANCELLABLE,
    MAX_LINES,
    MAX_QUANTITY_PER_LINE,
    MERCHANT_TRANSITIONS,
    OPEN_QUOTE_STATUSES,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
)

BUYER_ROLES = frozenset({AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.REAL_ESTATE_SELLER})


class CommerceError(Exception):
    code = "commerce_error"


class NotAllowed(CommerceError):
    code = "not_allowed"


class InvalidCart(CommerceError):
    code = "invalid_cart"


class OutOfStock(CommerceError):
    code = "out_of_stock"


class InvalidTransition(CommerceError):
    code = "invalid_transition"


class NotFound(CommerceError):
    code = "not_found"


def _number() -> str:
    return f"RCH-{timezone.localdate():%y%m%d}-{secrets.token_hex(3).upper()}"


def _notify(recipient_id, event, resource_type, resource_id, dedupe, payload):
    category = (
        NotificationCategory.ORDER
        if resource_type == NotificationResourceType.ORDER
        else NotificationCategory.QUOTE
    )
    transaction.on_commit(
        lambda: notifications.create_notification(
            recipient_id=recipient_id,
            category=category,
            event_type=event,
            dedupe_key=dedupe,
            payload=payload,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    )


# ---- store orders -------------------------------------------------------------------------------


@transaction.atomic
def place_order(buyer, *, items: list[dict], delivery: dict, payment_method: str) -> Order:
    if buyer.role not in BUYER_ROLES or not buyer.is_active:
        raise NotAllowed("This account cannot place store orders.")
    if not buyer.email_verified_at:
        raise NotAllowed("Verify your e-mail address before ordering.")
    if payment_method not in PaymentMethod.values:
        raise InvalidCart("Choose cash on delivery or manual transfer.")
    if not items or len(items) > MAX_LINES:
        raise InvalidCart(f"An order has between 1 and {MAX_LINES} lines.")
    wanted: dict = {}
    for line in items:
        qty = int(line["quantity"])
        if not 1 <= qty <= MAX_QUANTITY_PER_LINE:
            raise InvalidCart(f"Quantity must be between 1 and {MAX_QUANTITY_PER_LINE}.")
        wanted[line["product"]] = wanted.get(line["product"], 0) + qty
    # Lock in a stable order (by id) so concurrent checkouts never deadlock.
    products = list(
        Product.objects.consumer_store()
        .select_for_update(of=("self",))
        .filter(pk__in=list(wanted))
        .order_by("pk")
    )
    if len(products) != len(wanted):
        raise InvalidCart("Some products are not available in the store.")
    merchants = {p.company_id for p in products}
    if len(merchants) != 1:
        raise InvalidCart("One order contains products of one store; split the cart per store.")
    merchant = MedicalCompany.objects.get(pk=merchants.pop())
    if merchant.account_id == buyer.pk:
        raise NotAllowed("A business cannot order from itself.")
    total = Decimal("0")
    lines = []
    for product in products:
        qty = wanted[product.pk]
        if product.stock_quantity is None or product.stock_quantity < qty:
            raise OutOfStock(f"Not enough stock for “{product.title}”.")
        line_total = (product.price * qty).quantize(Decimal("0.01"))
        total += line_total
        lines.append((product, qty, line_total))
    order = Order.objects.create(
        number=_number(),
        buyer=buyer,
        merchant=merchant,
        payment_method=payment_method,
        total=total,
        currency=products[0].currency,
        delivery_governorate=delivery["governorate"],
        delivery_city=delivery.get("city"),
        delivery_address=delivery["address"].strip(),
        delivery_latitude=delivery.get("latitude"),
        delivery_longitude=delivery.get("longitude"),
        contact_phone=delivery["phone"].strip(),
        note=delivery.get("note", "").strip(),
        status_changed_at=timezone.now(),
    )
    for product, qty, line_total in lines:
        OrderItem.objects.create(
            order=order,
            product=product,
            title_snapshot=product.title,
            unit_price=product.price,
            quantity=qty,
            line_total=line_total,
        )
        product.stock_quantity -= qty
        product.save(update_fields=["stock_quantity", "updated_at"])
    OrderTransition.objects.create(order=order, actor=buyer, to_status=OrderStatus.PLACED)
    audit.record(
        actor=buyer,
        action="commerce.order.placed",
        target=order,
        summary=order.number,
        data={"lines": len(lines), "total": str(total)},
    )
    _notify(
        merchant.account_id,
        NotificationEventType.ORDER_PLACED,
        NotificationResourceType.ORDER,
        order.pk,
        f"order:{order.pk}:placed",
        {"order_number": order.number, "status": OrderStatus.PLACED},
    )
    return order


def _restore_stock(order: Order) -> None:
    for item in order.items.select_related(None).order_by("product_id"):
        product = Product.objects.select_for_update(of=("self",)).get(pk=item.product_id)
        if product.stock_quantity is not None:
            product.stock_quantity += item.quantity
            product.save(update_fields=["stock_quantity", "updated_at"])


def _transition(order: Order, *, actor, to_status: str, reason: str = "") -> Order:
    previous = order.status
    order.status = to_status
    order.status_changed_at = timezone.now()
    fields = ["status", "status_changed_at", "updated_at"]
    if to_status == OrderStatus.CANCELLED:
        _restore_stock(order)
        if order.payment_status == PaymentStatus.PAID:
            order.payment_status = PaymentStatus.REFUND_DUE
            fields.append("payment_status")
    if (
        to_status == OrderStatus.DELIVERED
        and order.payment_method == PaymentMethod.CASH_ON_DELIVERY
    ):
        order.payment_status = (
            PaymentStatus.PAID
        )  # cash collected at the door (recorded, not processed)
        fields.append("payment_status")
    order.save(update_fields=fields)
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
    _notify(
        recipient,
        NotificationEventType.ORDER_STATUS_CHANGED,
        NotificationResourceType.ORDER,
        order.pk,
        f"order:{order.pk}:{to_status}",
        {
            "order_number": order.number,
            "merchant_name": order.merchant.name,
            "previous_status": previous,
            "status": to_status,
        },
    )
    return order


@transaction.atomic
def cancel_as_buyer(order_id, *, buyer, reason: str = "") -> Order:
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("merchant")
        .filter(pk=order_id, buyer=buyer)
        .first()
    )
    if order is None:
        raise NotFound("Order not found.")
    if order.status not in BUYER_CANCELLABLE:
        raise InvalidTransition("This order can no longer be cancelled.")
    return _transition(order, actor=buyer, to_status=OrderStatus.CANCELLED, reason=reason)


@transaction.atomic
def transition_as_merchant(
    order_id, *, company_id, actor, to_status: str, reason: str = ""
) -> Order:
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("merchant")
        .filter(pk=order_id, merchant_id=company_id)
        .first()
    )
    if order is None:
        raise NotFound("Order not found.")
    if to_status not in MERCHANT_TRANSITIONS.get(order.status, frozenset()):
        raise InvalidTransition(f"An order cannot move from {order.status} to {to_status}.")
    return _transition(order, actor=actor, to_status=to_status, reason=reason)


@transaction.atomic
def record_payment(order_id, *, company_id, actor) -> Order:
    """Store staff confirm a manual transfer was received (no money moves through Racheeta)."""
    order = (
        Order.objects.select_for_update(of=("self",))
        .filter(pk=order_id, merchant_id=company_id)
        .first()
    )
    if order is None:
        raise NotFound("Order not found.")
    if order.status == OrderStatus.CANCELLED or order.payment_status != PaymentStatus.UNPAID:
        raise InvalidTransition("Payment cannot be recorded for this order.")
    order.payment_status = PaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])
    audit.record(
        actor=actor, action="commerce.order.payment_recorded", target=order, summary=order.number
    )
    return order


# ---- B2B quote requests -------------------------------------------------------------------------


@transaction.atomic
def request_quote(
    provider, *, account, product_id, quantity: int, message: str = ""
) -> QuoteRequest:
    product = (
        Product.objects.targeted_for(provider)
        .filter(pk=product_id)
        .select_related("company")
        .first()
    )
    if product is None:
        raise NotFound("Product not found.")
    if not 1 <= quantity <= 10000:
        raise InvalidCart("Quantity must be between 1 and 10000.")
    if QuoteRequest.objects.filter(
        requester=provider, product=product, status__in=OPEN_QUOTE_STATUSES
    ).exists():
        raise InvalidTransition("You already have an open quote request for this product.")
    try:
        with transaction.atomic():
            quote = QuoteRequest.objects.create(
                requester=provider,
                requested_by=account,
                company=product.company,
                product=product,
                quantity=quantity,
                message=message.strip()[:1000],
            )
    except IntegrityError as exc:  # a parallel request won the unique-open constraint
        raise InvalidTransition("You already have an open quote request for this product.") from exc
    audit.record(
        actor=account, action="commerce.quote.requested", target=quote, summary=product.title
    )
    _notify(
        product.company.account_id,
        NotificationEventType.QUOTE_REQUESTED,
        NotificationResourceType.QUOTE,
        quote.pk,
        f"quote:{quote.pk}:requested",
        {"product_title": product.title, "quantity": quantity, "status": quote.status},
    )
    return quote


def _locked_quote(quote_id, **scope) -> QuoteRequest:
    quote = (
        QuoteRequest.objects.select_for_update(of=("self",))
        .select_related("product", "company", "requester")
        .filter(pk=quote_id, **scope)
        .first()
    )
    if quote is None:
        raise NotFound("Quote request not found.")
    return quote


def _quote_changed(quote: QuoteRequest, *, actor, previous: str, notify_account_id) -> QuoteRequest:
    audit.record(
        actor=actor,
        action="commerce.quote.status_changed",
        target=quote,
        summary=f"{previous} -> {quote.status}",
    )
    _notify(
        notify_account_id,
        NotificationEventType.QUOTE_UPDATED,
        NotificationResourceType.QUOTE,
        quote.pk,
        f"quote:{quote.pk}:{quote.status}",
        {
            "product_title": quote.product.title,
            "company_name": quote.company.name,
            "previous_status": previous,
            "status": quote.status,
        },
    )
    return quote


@transaction.atomic
def respond_quote(
    quote_id, *, company_id, actor, unit_price: Decimal, note: str = ""
) -> QuoteRequest:
    quote = _locked_quote(quote_id, company_id=company_id)
    if quote.status != QuoteStatus.REQUESTED:
        raise InvalidTransition("Only a new request can be quoted.")
    if unit_price < 0:
        raise InvalidCart("The price must be zero or more.")
    previous = quote.status
    quote.status = QuoteStatus.QUOTED
    quote.quoted_unit_price = unit_price
    quote.quoted_currency = quote.product.currency
    quote.quoted_note = note.strip()[:1000]
    quote.quoted_at = timezone.now()
    quote.save()
    return _quote_changed(
        quote, actor=actor, previous=previous, notify_account_id=quote.requested_by_id
    )


@transaction.atomic
def decline_as_company(quote_id, *, company_id, actor) -> QuoteRequest:
    quote = _locked_quote(quote_id, company_id=company_id)
    if quote.status not in OPEN_QUOTE_STATUSES:
        raise InvalidTransition("This request is already closed.")
    previous = quote.status
    quote.status = QuoteStatus.DECLINED
    quote.closed_at = timezone.now()
    quote.save()
    return _quote_changed(
        quote, actor=actor, previous=previous, notify_account_id=quote.requested_by_id
    )


@transaction.atomic
def close_as_requester(quote_id, *, provider, actor, outcome: str) -> QuoteRequest:
    quote = _locked_quote(quote_id, requester=provider)
    allowed = {
        QuoteStatus.ACCEPTED: {QuoteStatus.QUOTED},
        QuoteStatus.DECLINED: {QuoteStatus.QUOTED},
        QuoteStatus.WITHDRAWN: {QuoteStatus.REQUESTED, QuoteStatus.QUOTED},
    }
    if outcome not in allowed or quote.status not in allowed[outcome]:
        raise InvalidTransition(f"A {quote.status} request cannot become {outcome}.")
    previous = quote.status
    quote.status = outcome
    quote.closed_at = timezone.now()
    quote.save()
    return _quote_changed(
        quote, actor=actor, previous=previous, notify_account_id=quote.company.account_id
    )
