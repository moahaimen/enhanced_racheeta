"""B2B quotations: request -> seller quote (valid QUOTE_VALID_DAYS) -> buyer accepts -> order.

Store checkout lives in `checkout.py`, the order lifecycle in `lifecycle.py`.
* a quote can only be requested for a product THE targeting rule shows to the provider now;
* an accepted, unexpired quote becomes ONE order at the quoted price, with the same commission
  snapshot, ledger and stock reservation as any other order (`checkout.persist`).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.ledger.posting import current_policy, dinars
from apps.marketplace.models import Product
from apps.marketplace.types import NOT_PURCHASABLE_CLASSES, CompanyVerificationStatus
from apps.notifications import services as notifications
from apps.notifications.types import (
    NotificationCategory,
    NotificationEventType,
    NotificationResourceType,
)

from . import checkout as store
from .errors import CommerceError
from .models import Checkout, QuoteRequest
from .pricing import PricedCheckout, PricedLine, PricedOrder
from .types import OPEN_QUOTE_STATUSES, QUOTE_VALID_DAYS, PaymentMethod, QuoteStatus

__all__ = ["CommerceError"]


class NotAllowed(CommerceError):
    code = "not_allowed"


class InvalidCart(CommerceError):
    code = "invalid_cart"


class InvalidTransition(CommerceError):
    code = "invalid_transition"


class NotFound(CommerceError):
    code = "not_found"


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
        ),
        robust=True,
    )


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
    quote.expires_at = quote.quoted_at + timedelta(days=QUOTE_VALID_DAYS)
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
    if outcome == QuoteStatus.ACCEPTED and _expired(quote):
        raise InvalidTransition("This quotation has expired; ask for a new one.")
    previous = quote.status
    quote.status = outcome
    quote.closed_at = timezone.now()
    quote.save()
    return _quote_changed(
        quote, actor=actor, previous=previous, notify_account_id=quote.company.account_id
    )


def _expired(quote: QuoteRequest) -> bool:
    return quote.expires_at is not None and timezone.now() >= quote.expires_at


@transaction.atomic
def order_from_quote(
    quote_id, *, provider, account, delivery: dict, payment_method: str, idempotency_key: str
) -> tuple[Checkout, bool]:
    """Accepted quote -> one order at the quoted unit price. Idempotent per key and per quote."""
    if payment_method not in PaymentMethod.values:
        raise InvalidCart("Choose cash on delivery or manual transfer.")
    key = (idempotency_key or "").strip()[:64]
    if not key:
        raise InvalidCart("Missing idempotency key.")
    fingerprint = store.request_fingerprint(
        items=[], coupons=[], delivery=delivery, payment_method=payment_method, quote=quote_id
    )
    existing = Checkout.objects.filter(buyer=account, idempotency_key=key).first()
    if existing is not None:
        return store.replay(existing, fingerprint)
    quote = _locked_quote(quote_id, requester=provider)
    if quote.status == QuoteStatus.ORDERED:
        raise InvalidTransition("This quotation has already been ordered.")
    if quote.status != QuoteStatus.ACCEPTED:
        raise InvalidTransition("Accept the quotation before ordering.")
    if _expired(quote):
        quote.status = QuoteStatus.EXPIRED
        quote.closed_at = timezone.now()
        quote.save()
        raise InvalidTransition("This quotation has expired; ask for a new one.")
    store.check_buyer(account)
    product = (
        Product.objects.select_for_update(of=("self",))
        .select_related("company", "company__account", "category")
        .get(pk=quote.product_id)
    )
    company = product.company
    if company.verification_status != CompanyVerificationStatus.VERIFIED or not (
        company.account.is_active
    ):
        raise NotAllowed("The seller cannot sell right now.")
    if (
        not product.is_active
        or product.is_restricted
        or product.category.compliance_class in NOT_PURCHASABLE_CLASSES
    ):
        raise NotAllowed("This product can no longer be ordered.")
    if quote.quoted_unit_price is None or quote.quoted_currency != store.CURRENCY:
        raise InvalidCart("Only quotations in Iraqi dinars can be ordered.")
    if company.account_id == account.pk:
        raise NotAllowed("A business cannot buy from itself.")
    left = store.inventory.available(product)
    if left is not None and left < quote.quantity:
        raise CommerceError(f"Not enough stock for “{product.title}”.", "out_of_stock")
    policy = current_policy()
    unit = dinars(quote.quoted_unit_price)
    line = PricedLine(
        product=product,
        quantity=quote.quantity,
        unit_price=unit,
        line_total=dinars(unit * quote.quantity),
        commission_rate=policy.rate_percent,
        channel="B2B",
    )
    priced = PricedCheckout(orders=[PricedOrder(company=company, lines=[line])])
    checkout, created = store.persist(
        account,
        priced,
        policy,
        delivery=delivery,
        payment_method=payment_method,
        key=key,
        fingerprint=fingerprint,
        quote=quote,
    )
    previous = quote.status
    quote.status = QuoteStatus.ORDERED
    quote.closed_at = timezone.now()
    quote.save()
    _quote_changed(
        quote, actor=account, previous=previous, notify_account_id=quote.company.account_id
    )
    return checkout, created
