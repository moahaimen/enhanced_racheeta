"""Multi-vendor marketplace: checkouts split into seller orders, immutable line financial snapshots,
coupons and offers, the stock movement ledger, returns, refunds, disputes and B2B quotes.
Money is never processed; every amount is computed by the server (docs/MARKETPLACE_COMMERCE.md)."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel

from .types import (
    CouponFunding,
    DiscountKind,
    DisputeStatus,
    InvoiceKind,
    ItemKind,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
    ReturnStatus,
    SalesChannel,
    SettlementState,
    StockMovementKind,
    TrackingStatus,
)

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}


class Checkout(BaseModel):
    """One buyer action that may create several seller orders (multi-vendor cart). Buyers see the
    checkout; each seller sees only its own order. The idempotency key makes a double click or a
    retried request return the same checkout instead of buying twice."""

    number = models.CharField(max_length=24, unique=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="checkouts"
    )
    idempotency_key = models.CharField(max_length=64)
    # SHA-256 of the canonical request (items, coupons, delivery, payment, quote). A reused key with
    # a DIFFERENT request is refused instead of silently returning the first checkout.
    request_hash = models.CharField(max_length=64, blank=True, default="")
    currency = models.CharField(max_length=3, default="IQD")
    list_total = models.DecimalField(**MONEY)
    seller_discount_total = models.DecimalField(**MONEY)
    platform_discount_total = models.DecimalField(**MONEY)
    shipping_total = models.DecimalField(**MONEY)
    tax_total = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)

    class Meta:
        db_table = "commerce_checkout"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "idempotency_key"], name="commerce_checkout_idempotent"
            )
        ]


class Order(BaseModel):
    number = models.CharField(max_length=24, unique=True)
    checkout = models.ForeignKey(
        Checkout, on_delete=models.PROTECT, null=True, blank=True, related_name="orders"
    )
    channel = models.CharField(max_length=3, choices=SalesChannel.choices, default=SalesChannel.B2C)
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
        max_length=18, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    # Server-computed from locked product prices at checkout; never from the client.
    # total = what the buyer pays (list - seller discounts - platform discounts).
    total = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="IQD")
    list_total = models.DecimalField(**MONEY)
    seller_discount_total = models.DecimalField(**MONEY)
    platform_discount_total = models.DecimalField(**MONEY)
    merchandise_net = models.DecimalField(**MONEY)  # commission base
    commission_total = models.DecimalField(**MONEY)
    seller_payable_total = models.DecimalField(**MONEY)
    refunded_total = models.DecimalField(**MONEY)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_policy_version = models.PositiveIntegerField(null=True, blank=True)
    settlement_state = models.CharField(
        max_length=14, choices=SettlementState.choices, default=SettlementState.NOT_ELIGIBLE
    )
    # Simulated payment evidence recorded by Racheeta finance (never real money).
    payment_reference = models.CharField(max_length=120, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    shipping_reference = models.CharField(max_length=120, blank=True, default="")
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    quote = models.OneToOneField(
        "commerce.QuoteRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order",
    )
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
    # Pass-through charges (SHIPPING / TAX order lines; no commission). Snapshots at checkout.
    shipping_total = models.DecimalField(**MONEY)
    shipping_min_days = models.PositiveSmallIntegerField(null=True, blank=True)
    shipping_max_days = models.PositiveSmallIntegerField(null=True, blank=True)
    tax_mode = models.CharField(max_length=10, default="NONE")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_label = models.CharField(max_length=40, blank=True, default="")
    tax_registration_number = models.CharField(max_length=40, blank=True, default="")
    tax_total = models.DecimalField(**MONEY)  # EXCLUSIVE tax added on top (a TAX line)
    tax_included_total = models.DecimalField(**MONEY)  # INCLUSIVE: informational only
    courier_name = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        db_table = "commerce_order"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name="commerce_order_total_ge0"),
            models.CheckConstraint(
                condition=Q(refunded_total__lte=models.F("total")),
                name="commerce_order_refund_le_paid",
            ),
        ]
        indexes = [
            models.Index(fields=["buyer", "-created_at"], name="commerce_order_buyer_idx"),
            models.Index(fields=["merchant", "status"], name="commerce_order_merchant_idx"),
        ]

    def __str__(self) -> str:
        return self.number


class OrderItem(BaseModel):
    """Immutable financial snapshot of one line at checkout (whole dinars). The refunded_* fields
    only ever grow, in step with compensating ledger entries."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=12, choices=ItemKind.choices, default=ItemKind.MERCHANDISE)
    # Null only for charge lines (delivery fee, tax).
    product = models.ForeignKey(
        "marketplace.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
        null=True,
        blank=True,
    )
    variant = models.ForeignKey(
        "marketplace.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
        null=True,
        blank=True,
    )
    # A TAX line belongs to the merchandise line it was computed on (refunded in step with it).
    parent_item = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="charges"
    )
    sku_snapshot = models.CharField(max_length=64, blank=True, default="")
    variant_label_snapshot = models.CharField(max_length=80, blank=True, default="")
    title_snapshot = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=14, decimal_places=2)  # list value (price x qty)
    seller_discount = models.DecimalField(**MONEY)  # offer + seller coupon (seller-funded)
    platform_discount = models.DecimalField(**MONEY)  # platform coupon (Racheeta-funded)
    merchandise_net = models.DecimalField(**MONEY)  # line_total - seller_discount = commission base
    buyer_paid = models.DecimalField(**MONEY)  # merchandise_net - platform_discount
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission = models.DecimalField(**MONEY)
    seller_payable = models.DecimalField(**MONEY)  # merchandise_net - commission
    stock_tracked = models.BooleanField(default=True)
    refunded_quantity = models.PositiveIntegerField(default=0)
    refunded_buyer_paid = models.DecimalField(**MONEY)
    refunded_platform_discount = models.DecimalField(**MONEY)
    refunded_commission = models.DecimalField(**MONEY)
    refunded_seller_payable = models.DecimalField(**MONEY)

    class Meta:
        db_table = "commerce_order_item"
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="commerce_item_qty_ge1"),
            models.UniqueConstraint(
                fields=["order", "product", "variant"],
                condition=Q(kind="MERCHANDISE"),
                name="commerce_item_one_per_product_variant",
                nulls_distinct=False,
            ),
            models.UniqueConstraint(
                fields=["order"], condition=Q(kind="SHIPPING"), name="commerce_item_one_shipping"
            ),
            # Merchandise names a product; a charge names none and never carries commission.
            models.CheckConstraint(
                condition=(Q(kind="MERCHANDISE") & Q(product__isnull=False))
                | (
                    ~Q(kind="MERCHANDISE")
                    & Q(product__isnull=True)
                    & Q(variant__isnull=True)
                    & Q(commission=0)
                    & Q(seller_discount=0)
                    & Q(platform_discount=0)
                    & Q(stock_tracked=False)
                ),
                name="commerce_item_kind_shape",
            ),
            models.CheckConstraint(
                condition=Q(refunded_quantity__lte=models.F("quantity")),
                name="commerce_item_refund_qty_le_qty",
            ),
            models.CheckConstraint(
                condition=Q(merchandise_net=models.F("line_total") - models.F("seller_discount")),
                name="commerce_item_net_consistent",
            ),
            models.CheckConstraint(
                condition=Q(seller_payable=models.F("merchandise_net") - models.F("commission")),
                name="commerce_item_payable_consistent",
            ),
        ]


class OrderTransition(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="transitions")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    from_status = models.CharField(max_length=16, blank=True, default="")
    to_status = models.CharField(max_length=24)
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
    variant = models.ForeignKey(
        "marketplace.ProductVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quote_requests",
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
    expires_at = models.DateTimeField(null=True, blank=True)
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


class Coupon(BaseModel):
    """A discount code. SELLER coupons belong to one seller and reduce that seller's merchandise
    value (and so the commission base). PLATFORM coupons are paid by Racheeta: the seller's
    merchandise value and commission base are untouched."""

    code = models.CharField(max_length=32, unique=True)
    funded_by = models.CharField(max_length=8, choices=CouponFunding.choices)
    company = models.ForeignKey(
        "marketplace.MedicalCompany",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coupons",
    )
    kind = models.CharField(max_length=8, choices=DiscountKind.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    min_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    redemptions = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "commerce_coupon"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(funded_by="SELLER", company__isnull=False))
                | (Q(funded_by="PLATFORM", company__isnull=True)),
                name="commerce_coupon_funding_owner",
            ),
            models.CheckConstraint(condition=Q(value__gt=0), name="commerce_coupon_value_gt0"),
            models.CheckConstraint(
                condition=~Q(kind="PERCENT") | Q(value__lte=90),
                name="commerce_coupon_percent_le_90",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")), name="commerce_coupon_window"
            ),
            models.CheckConstraint(
                condition=Q(max_redemptions__isnull=True)
                | Q(redemptions__lte=models.F("max_redemptions")),
                name="commerce_coupon_redemptions_le_max",
            ),
        ]


class CouponRedemption(BaseModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="uses")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="coupon_uses")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField(**MONEY)
    released = models.BooleanField(default=False)  # order cancelled: the use no longer counts

    class Meta:
        db_table = "commerce_coupon_redemption"
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "buyer"],
                condition=Q(released=False),
                name="commerce_coupon_once_per_buyer",
            ),
        ]


class ProductOffer(BaseModel):
    """A seller-funded percentage discount on one product for a period (sale price)."""

    company = models.ForeignKey(
        "marketplace.MedicalCompany", on_delete=models.CASCADE, related_name="offers"
    )
    product = models.ForeignKey(
        "marketplace.Product", on_delete=models.CASCADE, related_name="offers"
    )
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "commerce_product_offer"
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(percent__gt=0) & Q(percent__lte=90), name="commerce_offer_percent"
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")), name="commerce_offer_window"
            ),
        ]


class StockMovement(BaseModel):
    """Append-only inventory ledger: every change to on-hand or reserved units, with its reason,
    actor and order, and the resulting balances."""

    product = models.ForeignKey(
        "marketplace.Product", on_delete=models.PROTECT, related_name="stock_movements"
    )
    variant = models.ForeignKey(
        "marketplace.ProductVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    kind = models.CharField(max_length=8, choices=StockMovementKind.choices)
    quantity = models.IntegerField()
    on_hand_after = models.PositiveIntegerField()
    reserved_after = models.PositiveIntegerField()
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reason = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "commerce_stock_movement"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product", "variant", "kind"],
                condition=Q(order__isnull=False),
                name="commerce_stock_once_per_order_event",
                nulls_distinct=False,
            )
        ]


class ReturnRequest(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="returns")
    status = models.CharField(
        max_length=10, choices=ReturnStatus.choices, default=ReturnStatus.REQUESTED
    )
    reason = models.CharField(max_length=500)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "commerce_return"
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status__in=["REQUESTED", "APPROVED", "RECEIVED"]),
                name="commerce_one_open_return_per_order",
            )
        ]


class ReturnLine(BaseModel):
    request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()

    class Meta:
        db_table = "commerce_return_line"
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="commerce_return_qty_ge1"),
            models.UniqueConstraint(fields=["request", "item"], name="commerce_return_line_once"),
        ]


class Refund(BaseModel):
    """A (simulated) refund executed by Racheeta finance. Exactly one ledger entry per refund."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="refunds")
    return_request = models.OneToOneField(
        ReturnRequest, on_delete=models.PROTECT, null=True, blank=True, related_name="refund"
    )
    amount = models.DecimalField(**MONEY)
    reason = models.CharField(max_length=300)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "commerce_refund"
        ordering = ["-created_at", "id"]


class Dispute(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="disputes")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=1000)
    status = models.CharField(
        max_length=18, choices=DisputeStatus.choices, default=DisputeStatus.OPEN
    )
    resolution_note = models.CharField(max_length=500, blank=True, default="")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "commerce_dispute"
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order"], condition=Q(status="OPEN"), name="commerce_one_open_dispute"
            )
        ]


class TrackingEvent(BaseModel):
    """Delivery progress reported by the seller's fulfillment staff after shipping (append-only).
    Visible to the buyer and the seller; it never changes the order or payment status."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tracking_events")
    status = models.CharField(max_length=20, choices=TrackingStatus.choices)
    note = models.CharField(max_length=300, blank=True, default="")
    location = models.CharField(max_length=120, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "commerce_tracking_event"
        ordering = ["created_at", "id"]


class Invoice(BaseModel):
    """An issued buyer document (invoice at payment, receipt, credit note per refund). Its content
    is a frozen snapshot: later changes to products, names or addresses never alter it."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="invoices")
    kind = models.CharField(max_length=12, choices=InvoiceKind.choices)
    number = models.CharField(max_length=32, unique=True)
    refund = models.OneToOneField(
        Refund, on_delete=models.PROTECT, null=True, blank=True, related_name="credit_note"
    )
    total = models.DecimalField(**MONEY)
    snapshot = models.JSONField()

    class Meta:
        db_table = "commerce_invoice"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "kind"],
                condition=Q(kind__in=["INVOICE", "RECEIPT"]),
                name="commerce_invoice_one_per_order",
            ),
            models.CheckConstraint(
                condition=Q(kind="CREDIT_NOTE", refund__isnull=False)
                | (~Q(kind="CREDIT_NOTE") & Q(refund__isnull=True)),
                name="commerce_invoice_credit_note_has_refund",
            ),
        ]
