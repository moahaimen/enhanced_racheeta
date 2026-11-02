"""Store orders (B2C, allowed products only) and B2B quote requests."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel

from .types import OrderStatus, PaymentMethod, PaymentStatus, QuoteStatus


class Order(BaseModel):
    number = models.CharField(max_length=24, unique=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="store_orders"
    )
    merchant = models.ForeignKey(
        "marketplace.MedicalCompany", on_delete=models.PROTECT, related_name="store_orders"
    )
    status = models.CharField(
        max_length=16, choices=OrderStatus.choices, default=OrderStatus.PLACED
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    # Server-computed from locked product prices at checkout; never from the client.
    total = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="IQD")
    # Minimal delivery data, visible only to the buyer and the merchant's authorized staff.
    delivery_governorate = models.ForeignKey(
        "geography.Governorate", on_delete=models.PROTECT, related_name="+"
    )
    delivery_city = models.ForeignKey(
        "geography.City", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    delivery_address = models.CharField(max_length=255)
    # Optional pin the buyer shared from their device (with permission) to help the delivery.
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    contact_phone = models.CharField(max_length=32)
    note = models.CharField(max_length=500, blank=True, default="")
    status_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "commerce_order"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name="commerce_order_total_ge0"),
        ]
        indexes = [
            models.Index(fields=["buyer", "-created_at"], name="commerce_order_buyer_idx"),
            models.Index(fields=["merchant", "status"], name="commerce_order_merchant_idx"),
        ]

    def __str__(self) -> str:
        return self.number


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "marketplace.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    title_snapshot = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "commerce_order_item"
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="commerce_item_qty_ge1"),
            models.UniqueConstraint(
                fields=["order", "product"], name="commerce_item_one_per_product"
            ),
        ]


class OrderTransition(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="transitions")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    from_status = models.CharField(max_length=16, blank=True, default="")
    to_status = models.CharField(max_length=16)
    reason = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "commerce_order_transition"
        ordering = ["created_at", "id"]


class QuoteRequest(BaseModel):
    """A verified provider asks a business for a price on a product targeted at that provider."""

    requester = models.ForeignKey(
        "providers.ProviderProfile", on_delete=models.PROTECT, related_name="quote_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    company = models.ForeignKey(
        "marketplace.MedicalCompany", on_delete=models.PROTECT, related_name="quote_requests"
    )
    product = models.ForeignKey(
        "marketplace.Product", on_delete=models.PROTECT, related_name="quote_requests"
    )
    quantity = models.PositiveIntegerField()
    message = models.CharField(max_length=1000, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=QuoteStatus.choices, default=QuoteStatus.REQUESTED
    )
    quoted_unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quoted_currency = models.CharField(max_length=3, blank=True, default="")
    quoted_note = models.CharField(max_length=1000, blank=True, default="")
    quoted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "commerce_quote_request"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="commerce_quote_qty_ge1"),
            models.UniqueConstraint(
                fields=["requester", "product"],
                condition=Q(status__in=["REQUESTED", "QUOTED"]),
                name="commerce_quote_one_open_per_product",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status"], name="commerce_quote_company_idx"),
            models.Index(fields=["requester", "status"], name="commerce_quote_req_idx"),
        ]
