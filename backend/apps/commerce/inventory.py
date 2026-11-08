"""Inventory: on hand, reserved, available, and the append-only movement ledger.

Policy (docs/MARKETPLACE_COMMERCE.md §Inventory):
* placing an order RESERVES units (reserved += q) — refused when available < q;
* cancelling before shipment RELEASES them (reserved -= q), exactly once per order;
* shipping CONSUMES them (on hand -= q, reserved -= q);
* a received return RESTOCKS them (on hand += q);
* a seller ADJUSTMENT changes on hand with a reason; it can never drop below what is reserved.
Every call runs on a row-locked stock unit; the database also refuses reserved > on hand.
A stock unit is the VARIANT when the line names one, otherwise the product (products without
variants behave exactly as before). Units with no stock figure (null) are untracked
(professional products sold to order).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.marketplace.models import Product, ProductVariant
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


def available(unit) -> int | None:
    if unit.stock_quantity is None:
        return None
    return unit.stock_quantity - unit.stock_reserved


def _lock(product_id, variant_id=None):
    if variant_id:
        return (
            ProductVariant.objects.select_for_update(of=("self",))
            .select_related("product", "product__company")
            .get(pk=variant_id, product_id=product_id)
        )
    return (
        Product.objects.select_for_update(of=("self",)).select_related("company").get(pk=product_id)
    )


def _ids(unit) -> dict:
    """product / variant of a stock unit, for movement rows and lookups."""
    if isinstance(unit, ProductVariant):
        return {"product_id": unit.product_id, "variant_id": unit.pk}
    return {"product_id": unit.pk, "variant_id": None}


def _company(unit):
    return unit.product.company if isinstance(unit, ProductVariant) else unit.company


def _record(unit, kind, quantity, *, order=None, actor=None, reason="") -> bool:
    """Write the movement; returns False when this order event was already recorded."""
    try:
        with transaction.atomic():
            StockMovement.objects.create(
                **_ids(unit),
                kind=kind,
                quantity=quantity,
                on_hand_after=unit.stock_quantity or 0,
                reserved_after=unit.stock_reserved,
                order=order,
                actor=actor if getattr(actor, "is_authenticated", False) else None,
                reason=reason[:200],
            )
    except IntegrityError:
        return False
    return True


def _low_stock_alert(unit) -> None:
    left = available(unit)
    if unit.reorder_threshold is None or left is None or left > unit.reorder_threshold:
        return
    ids = _ids(unit)
    product_id, owner_id, title = ids["product_id"], _company(unit).account_id, unit.title
    key = f"{product_id}:{ids['variant_id']}" if ids["variant_id"] else str(product_id)
    today = timezone.localdate().isoformat()
    transaction.on_commit(
        lambda: notifications.create_notification(
            recipient_id=owner_id,
            category=NotificationCategory.ORDER,
            event_type=NotificationEventType.STOCK_LOW,
            dedupe_key=f"stock-low:{key}:{today}",
            payload={"product_title": title, "quantity": left},
            resource_type=NotificationResourceType.PRODUCT,
            resource_id=product_id,
        ),
        robust=True,
    )


def reserve(unit, quantity: int, *, order, actor=None) -> None:
    """`unit` (product or variant) must already be row-locked by the caller (checkout locks all
    lines in id order)."""
    if unit.stock_quantity is None:
        return
    if available(unit) < quantity:
        raise NotEnoughStock(f"Not enough stock for “{unit.title}”.")
    if StockMovement.objects.filter(order=order, **_ids(unit), kind="RESERVE").exists():
        return
    unit.stock_reserved += quantity
    unit.save(update_fields=["stock_reserved", "updated_at"])
    _record(unit, StockMovementKind.RESERVE, quantity, order=order, actor=actor)
    _low_stock_alert(unit)


def _tracked_items(order):
    return order.items.filter(stock_tracked=True).order_by("product_id", "variant_id")


def release(order, *, actor=None) -> None:
    """Release every reservation of an order that has not shipped — once (idempotent)."""
    for item in _tracked_items(order):
        if StockMovement.objects.filter(
            order=order,
            product_id=item.product_id,
            variant_id=item.variant_id,
            kind__in=["RELEASE", "CONSUME"],
        ).exists():
            continue
        unit = _lock(item.product_id, item.variant_id)
        unit.stock_reserved -= item.quantity
        unit.save(update_fields=["stock_reserved", "updated_at"])
        _record(unit, StockMovementKind.RELEASE, -item.quantity, order=order, actor=actor)


def consume(order, *, actor=None) -> None:
    """Shipping: reserved units leave the warehouse — once per order."""
    for item in _tracked_items(order):
        if StockMovement.objects.filter(
            order=order,
            product_id=item.product_id,
            variant_id=item.variant_id,
            kind__in=["CONSUME", "RELEASE"],
        ).exists():
            continue
        unit = _lock(item.product_id, item.variant_id)
        unit.stock_reserved -= item.quantity
        unit.stock_quantity -= item.quantity
        unit.save(update_fields=["stock_reserved", "stock_quantity", "updated_at"])
        _record(unit, StockMovementKind.CONSUME, -item.quantity, order=order, actor=actor)


def restock(item, quantity: int, *, order, actor=None, reason="") -> None:
    if not item.stock_tracked or quantity <= 0:
        return
    unit = _lock(item.product_id, item.variant_id)
    unit.stock_quantity = (unit.stock_quantity or 0) + quantity
    unit.save(update_fields=["stock_quantity", "updated_at"])
    StockMovement.objects.create(
        **_ids(unit),
        kind=StockMovementKind.RESTOCK,
        quantity=quantity,
        on_hand_after=unit.stock_quantity,
        reserved_after=unit.stock_reserved,
        order=None,  # several returns per order are possible; the reason names the order
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        reason=(reason or f"Return of order {order.number}")[:200],
    )


def _own_unit(product_id, company_id, variant_id=None):
    """The acting business's product (or one of its variants), row-locked; 404 otherwise."""
    if variant_id:
        unit = (
            ProductVariant.objects.select_for_update(of=("self",))
            .filter(pk=variant_id, product_id=product_id, company_id=company_id)
            .select_related("product", "product__company")
            .first()
        )
        if unit is None:
            raise InventoryError("Product not found.", "not_found")
        return unit
    unit = (
        Product.objects.select_for_update(of=("self",))
        .filter(pk=product_id, company_id=company_id)
        .select_related("company")
        .first()
    )
    if unit is None:
        raise InventoryError("Product not found.", "not_found")
    if unit.variants.exists():
        raise InventoryError("This product has variants: adjust the stock of a variant.")
    return unit


@transaction.atomic
def adjust(product_id, *, company_id, delta: int, reason: str, actor, variant_id=None):
    """Seller adjustment of on-hand units (receiving goods, damage, count correction)."""
    reason = (reason or "").strip()
    if not reason:
        raise InventoryError("Give a reason for the stock adjustment.")
    if not isinstance(delta, int) or delta == 0 or abs(delta) > 100000:
        raise InventoryError("Enter a non-zero whole number.")
    unit = _own_unit(product_id, company_id, variant_id)
    on_hand = (unit.stock_quantity or 0) + delta
    if on_hand < unit.stock_reserved:
        raise InventoryError("Stock cannot drop below the units reserved for open orders.")
    unit.stock_quantity = on_hand
    unit.save(update_fields=["stock_quantity", "updated_at"])
    StockMovement.objects.create(
        **_ids(unit),
        kind=StockMovementKind.ADJUST,
        quantity=delta,
        on_hand_after=on_hand,
        reserved_after=unit.stock_reserved,
        actor=actor,
        reason=reason[:200],
    )
    _low_stock_alert(unit)
    return unit


@transaction.atomic
def set_threshold(product_id, *, company_id, threshold, variant_id=None):
    unit = _own_unit(product_id, company_id, variant_id)
    if threshold is not None and (not isinstance(threshold, int) or threshold < 0):
        raise InventoryError("The alert level is a whole number of units.")
    unit.reorder_threshold = threshold
    unit.save(update_fields=["reorder_threshold", "updated_at"])
    return unit
