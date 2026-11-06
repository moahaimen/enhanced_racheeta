"""Inventory: on hand, reserved, available, and the append-only movement ledger.

Policy (docs/MARKETPLACE_COMMERCE.md §Inventory):
* placing an order RESERVES units (reserved += q) — refused when available < q;
* cancelling before shipment RELEASES them (reserved -= q), exactly once per order;
* shipping CONSUMES them (on hand -= q, reserved -= q);
* a received return RESTOCKS them (on hand += q);
* a seller ADJUSTMENT changes on hand with a reason; it can never drop below what is reserved.
Every call runs on a row-locked product; the database also refuses reserved > on hand.
Products with no stock figure (null) are untracked (professional products sold to order).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.marketplace.models import Product
from apps.notifications import services as notifications
from apps.notifications.types import (
    NotificationCategory,
    NotificationEventType,
    NotificationResourceType,
)

from .errors import CommerceError
from .models import StockMovement
from .types import StockMovementKind


class InventoryError(CommerceError):
    code = "inventory_error"


class NotEnoughStock(InventoryError):
    code = "out_of_stock"


def available(product: Product) -> int | None:
    if product.stock_quantity is None:
        return None
    return product.stock_quantity - product.stock_reserved


def _lock(product_id) -> Product:
    return (
        Product.objects.select_for_update(of=("self",)).select_related("company").get(pk=product_id)
    )


def _record(product, kind, quantity, *, order=None, actor=None, reason="") -> bool:
    """Write the movement; returns False when this order event was already recorded."""
    try:
        with transaction.atomic():
            StockMovement.objects.create(
                product=product,
                kind=kind,
                quantity=quantity,
                on_hand_after=product.stock_quantity or 0,
                reserved_after=product.stock_reserved,
                order=order,
                actor=actor if getattr(actor, "is_authenticated", False) else None,
                reason=reason[:200],
            )
    except IntegrityError:
        return False
    return True


def _low_stock_alert(product: Product) -> None:
    left = available(product)
    if product.reorder_threshold is None or left is None or left > product.reorder_threshold:
        return
    product_id, owner_id, title = product.pk, product.company.account_id, product.title
    today = timezone.localdate().isoformat()
    transaction.on_commit(
        lambda: notifications.create_notification(
            recipient_id=owner_id,
            category=NotificationCategory.ORDER,
            event_type=NotificationEventType.STOCK_LOW,
            dedupe_key=f"stock-low:{product_id}:{today}",
            payload={"product_title": title, "quantity": left},
            resource_type=NotificationResourceType.PRODUCT,
            resource_id=product_id,
        ),
        robust=True,
    )


def reserve(product: Product, quantity: int, *, order, actor=None) -> None:
    """`product` must already be row-locked by the caller (checkout locks all lines in id order)."""
    if product.stock_quantity is None:
        return
    if available(product) < quantity:
        raise NotEnoughStock(f"Not enough stock for “{product.title}”.")
    if StockMovement.objects.filter(order=order, product=product, kind="RESERVE").exists():
        return
    product.stock_reserved += quantity
    product.save(update_fields=["stock_reserved", "updated_at"])
    _record(product, StockMovementKind.RESERVE, quantity, order=order, actor=actor)
    _low_stock_alert(product)


def release(order, *, actor=None) -> None:
    """Release every reservation of an order that has not shipped — once (idempotent)."""
    for item in order.items.order_by("product_id"):
        if not item.stock_tracked:
            continue
        if StockMovement.objects.filter(
            order=order, product_id=item.product_id, kind__in=["RELEASE", "CONSUME"]
        ).exists():
            continue
        product = _lock(item.product_id)
        product.stock_reserved -= item.quantity
        product.save(update_fields=["stock_reserved", "updated_at"])
        _record(product, StockMovementKind.RELEASE, -item.quantity, order=order, actor=actor)


def consume(order, *, actor=None) -> None:
    """Shipping: reserved units leave the warehouse — once per order."""
    for item in order.items.order_by("product_id"):
        if not item.stock_tracked:
            continue
        if StockMovement.objects.filter(
            order=order, product_id=item.product_id, kind__in=["CONSUME", "RELEASE"]
        ).exists():
            continue
        product = _lock(item.product_id)
        product.stock_reserved -= item.quantity
        product.stock_quantity -= item.quantity
        product.save(update_fields=["stock_reserved", "stock_quantity", "updated_at"])
        _record(product, StockMovementKind.CONSUME, -item.quantity, order=order, actor=actor)


def restock(item, quantity: int, *, order, actor=None, reason="") -> None:
    if not item.stock_tracked or quantity <= 0:
        return
    product = _lock(item.product_id)
    product.stock_quantity = (product.stock_quantity or 0) + quantity
    product.save(update_fields=["stock_quantity", "updated_at"])
    StockMovement.objects.create(
        product=product,
        kind=StockMovementKind.RESTOCK,
        quantity=quantity,
        on_hand_after=product.stock_quantity,
        reserved_after=product.stock_reserved,
        order=None,  # several returns per order are possible; the reason names the order
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        reason=(reason or f"Return of order {order.number}")[:200],
    )


@transaction.atomic
def adjust(product_id, *, company_id, delta: int, reason: str, actor) -> Product:
    """Seller adjustment of on-hand units (receiving goods, damage, count correction)."""
    reason = (reason or "").strip()
    if not reason:
        raise InventoryError("Give a reason for the stock adjustment.")
    if not isinstance(delta, int) or delta == 0 or abs(delta) > 100000:
        raise InventoryError("Enter a non-zero whole number.")
    product = (
        Product.objects.select_for_update(of=("self",))
        .filter(pk=product_id, company_id=company_id)
        .select_related("company")
        .first()
    )
    if product is None:
        raise InventoryError("Product not found.", "not_found")
    on_hand = (product.stock_quantity or 0) + delta
    if on_hand < product.stock_reserved:
        raise InventoryError("Stock cannot drop below the units reserved for open orders.")
    product.stock_quantity = on_hand
    product.save(update_fields=["stock_quantity", "updated_at"])
    StockMovement.objects.create(
        product=product,
        kind=StockMovementKind.ADJUST,
        quantity=delta,
        on_hand_after=on_hand,
        reserved_after=product.stock_reserved,
        actor=actor,
        reason=reason[:200],
    )
    _low_stock_alert(product)
    return product


@transaction.atomic
def set_threshold(product_id, *, company_id, threshold) -> Product:
    product = (
        Product.objects.select_for_update(of=("self",))
        .filter(pk=product_id, company_id=company_id)
        .first()
    )
    if product is None:
        raise InventoryError("Product not found.", "not_found")
    if threshold is not None and (not isinstance(threshold, int) or threshold < 0):
        raise InventoryError("The alert level is a whole number of units.")
    product.reorder_threshold = threshold
    product.save(update_fields=["reorder_threshold", "updated_at"])
    return product
