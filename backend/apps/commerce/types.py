"""Marketplace commerce vocabularies (docs/MARKETPLACE_COMMERCE.md).

Three independent, server-owned state machines per seller order:
  fulfillment  PLACED -> CONFIRMED (seller accepted) -> SHIPPED -> DELIVERED -> COMPLETED
               PLACED/CONFIRMED -> CANCELLED (buyer before shipping, or seller declines)
  payment      UNPAID -> PAID (simulated evidence, finance only) -> PARTIALLY_REFUNDED / REFUNDED
               a paid order cancelled before delivery -> REFUND_PENDING -> REFUNDED
  settlement   NOT_ELIGIBLE -> ACCRUED (completed + paid + no open return/dispute) [-> per refund]
Sellers can accept, decline and ship. They can never mark an order paid, delivered, completed,
refunded or settled. Payment is NEVER processed: everything financial is simulated and labelled so.
"""

from django.db import models


class OrderStatus(models.TextChoices):
    PLACED = "PLACED", "Placed"
    CONFIRMED = "CONFIRMED", "Accepted by the seller"
    SHIPPED = "SHIPPED", "Shipped"
    DELIVERED = "DELIVERED", "Delivered"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentMethod(models.TextChoices):
    CASH_ON_DELIVERY = "CASH_ON_DELIVERY", "Cash on delivery (remitted to Racheeta, simulated)"
    MANUAL_TRANSFER = "MANUAL_TRANSFER", "Manual transfer to Racheeta (simulated)"


class PaymentStatus(models.TextChoices):
    UNPAID = "UNPAID", "Not paid yet"
    PAID = "PAID", "Payment verified by Racheeta finance (simulated)"
    REFUND_PENDING = "REFUND_PENDING", "Refund pending"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially refunded"
    REFUNDED = "REFUNDED", "Refunded"


class SettlementState(models.TextChoices):
    NOT_ELIGIBLE = "NOT_ELIGIBLE", "Not eligible yet"
    ACCRUED = "ACCRUED", "Commission and seller payable accrued"


class SalesChannel(models.TextChoices):
    B2C = "B2C", "Public store"
    B2B = "B2B", "Verified professional"


# Seller-side fulfillment transitions (accept / decline / ship). DELIVERED and COMPLETED are not
# reachable by a seller: the buyer (or Racheeta) confirms receipt, finance completes.
MERCHANT_TRANSITIONS = {
    OrderStatus.PLACED: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
}
# Buyer may cancel until the order ships.
BUYER_CANCELLABLE = frozenset({OrderStatus.PLACED, OrderStatus.CONFIRMED})
RETURNABLE_STATUSES = frozenset({OrderStatus.DELIVERED, OrderStatus.COMPLETED})
RETURN_WINDOW_DAYS = 14

MAX_QUANTITY_PER_LINE = 20
MAX_LINES = 20


class QuoteStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    QUOTED = "QUOTED", "Quoted"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"
    ORDERED = "ORDERED", "Converted to an order"
    EXPIRED = "EXPIRED", "Expired"


OPEN_QUOTE_STATUSES = frozenset({QuoteStatus.REQUESTED, QuoteStatus.QUOTED})
QUOTE_VALID_DAYS = 14


class CouponFunding(models.TextChoices):
    SELLER = "SELLER", "Seller-funded (reduces the seller's merchandise value)"
    PLATFORM = "PLATFORM", "Platform-funded (paid by Racheeta)"


class DiscountKind(models.TextChoices):
    PERCENT = "PERCENT", "Percent"
    FIXED = "FIXED", "Fixed amount"


class StockMovementKind(models.TextChoices):
    RESERVE = "RESERVE", "Reserved for an order"
    RELEASE = "RELEASE", "Reservation released"
    CONSUME = "CONSUME", "Shipped (consumed)"
    RESTOCK = "RESTOCK", "Returned to stock"
    ADJUST = "ADJUST", "Manual adjustment"


class ReturnStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested by the buyer"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    RECEIVED = "RECEIVED", "Items received back"
    REFUNDED = "REFUNDED", "Refunded"


class DisputeStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED_REFUND = "RESOLVED_REFUND", "Resolved with refund"
    RESOLVED_REJECTED = "RESOLVED_REJECTED", "Resolved without refund"
