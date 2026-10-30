"""Local commerce vocabularies (docs/COMMERCE.md).

Payment is NEVER processed: cash on delivery, or a manual bank transfer the merchant confirms.
No card data is collected anywhere. The demo labels this explicitly.
"""

from django.db import models


class OrderStatus(models.TextChoices):
    PLACED = "PLACED", "Placed"
    CONFIRMED = "CONFIRMED", "Confirmed by the store"
    SHIPPED = "SHIPPED", "Shipped"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentMethod(models.TextChoices):
    CASH_ON_DELIVERY = "CASH_ON_DELIVERY", "Cash on delivery"
    MANUAL_TRANSFER = "MANUAL_TRANSFER", "Manual transfer (confirmed by the store)"


class PaymentStatus(models.TextChoices):
    UNPAID = "UNPAID", "Not paid yet"
    PAID = "PAID", "Payment received (recorded by the store)"
    REFUND_DUE = "REFUND_DUE", "Refund due"


# Merchant (store staff) transitions.
MERCHANT_TRANSITIONS = {
    OrderStatus.PLACED: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
}
# Buyer may cancel until the order ships.
BUYER_CANCELLABLE = frozenset({OrderStatus.PLACED, OrderStatus.CONFIRMED})

MAX_QUANTITY_PER_LINE = 20
MAX_LINES = 20


class QuoteStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    QUOTED = "QUOTED", "Quoted"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


OPEN_QUOTE_STATUSES = frozenset({QuoteStatus.REQUESTED, QuoteStatus.QUOTED})
