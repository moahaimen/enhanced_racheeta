from datetime import timedelta
from decimal import Decimal

from rest_framework import serializers

from apps.core.phone import IraqiPhoneField
from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer

from .models import (
    Checkout,
    Coupon,
    Dispute,
    Order,
    OrderItem,
    OrderTransition,
    ProductOffer,
    QuoteRequest,
    Refund,
    ReturnLine,
    ReturnRequest,
    StockMovement,
)
from .types import (
    MAX_LINES,
    MAX_QUANTITY_PER_LINE,
    RETURN_WINDOW_DAYS,
    DiscountKind,
    OrderStatus,
    PaymentMethod,
    QuoteStatus,
)


class CartLineSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_LINE)


class CouponCodesMixin(serializers.Serializer):
    coupons = serializers.ListField(
        child=serializers.CharField(max_length=32), required=False, default=list, max_length=4
    )


class CartPreviewRequestSerializer(CouponCodesMixin):
    items = CartLineSerializer(many=True, allow_empty=False, max_length=MAX_LINES)


class DeliverySerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    address = serializers.CharField(max_length=255)
    phone = IraqiPhoneField(allow_landline=False)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, min_value=-90, max_value=90, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
        required=False,
        allow_null=True,
    )
    # One per click of "Place order": a retried request returns the first checkout unchanged.
    idempotency_key = serializers.CharField(min_length=8, max_length=64)

    def validate(self, attrs):
        if (attrs.get("latitude") is None) != (attrs.get("longitude") is None):
            raise serializers.ValidationError(
                {"latitude": "Send both latitude and longitude, or neither."}
            )
        city = attrs.get("city")
        if city is not None and city.governorate_id != attrs["governorate"].pk:
            raise serializers.ValidationError(
                {"city": "This city does not belong to the governorate."}
            )
        return attrs

    def delivery(self) -> dict:
        data = self.validated_data
        return {
            "governorate": data["governorate"],
            "city": data.get("city"),
            "address": data["address"],
            "phone": data["phone"],
            "note": data.get("note", ""),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }


class CheckoutSerializer(DeliverySerializer, CouponCodesMixin):
    """Only product ids, quantities and coupon codes come from the client; prices, discounts,
    fees and totals never do."""

    items = CartLineSerializer(many=True, allow_empty=False, max_length=MAX_LINES)


class QuoteOrderSerializer(DeliverySerializer):
    pass


MONEY_FIELD = {"max_digits": 16, "decimal_places": 2, "read_only": True}


class PreviewLineSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    title = serializers.CharField()
    image_url = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(**MONEY_FIELD)
    line_total = serializers.DecimalField(**MONEY_FIELD)
    seller_discount = serializers.DecimalField(**MONEY_FIELD)
    platform_discount = serializers.DecimalField(**MONEY_FIELD)
    buyer_paid = serializers.DecimalField(**MONEY_FIELD)
    channel = serializers.CharField()


class PreviewOrderSerializer(serializers.Serializer):
    merchant = serializers.DictField()
    seller_coupon = serializers.CharField(allow_null=True)
    lines = PreviewLineSerializer(many=True)
    list_total = serializers.DecimalField(**MONEY_FIELD)
    seller_discount_total = serializers.DecimalField(**MONEY_FIELD)
    platform_discount_total = serializers.DecimalField(**MONEY_FIELD)
    total = serializers.DecimalField(**MONEY_FIELD)


class CheckoutPreviewSerializer(serializers.Serializer):
    currency = serializers.CharField()
    orders = PreviewOrderSerializer(many=True)
    platform_coupon = serializers.CharField(allow_null=True)
    list_total = serializers.DecimalField(**MONEY_FIELD)
    seller_discount_total = serializers.DecimalField(**MONEY_FIELD)
    platform_discount_total = serializers.DecimalField(**MONEY_FIELD)
    total = serializers.DecimalField(**MONEY_FIELD)


def preview_payload(priced) -> dict:
    def line(pl):
        return {
            "product": pl.product.pk,
            "title": pl.product.title,
            "image_url": pl.product.image_url or "",
            "quantity": pl.quantity,
            "unit_price": pl.unit_price,
            "line_total": pl.line_total,
            "seller_discount": pl.seller_discount,
            "platform_discount": pl.platform_discount,
            "buyer_paid": pl.buyer_paid,
            "channel": pl.channel,
        }

    return {
        "currency": "IQD",
        "orders": [
            {
                "merchant": {"id": str(o.company.pk), "name": o.company.name},
                "seller_coupon": o.seller_coupon.code if o.seller_coupon else None,
                "lines": [line(pl) for pl in o.lines],
                "list_total": o.total("line_total"),
                "seller_discount_total": o.total("seller_discount"),
                "platform_discount_total": o.total("platform_discount"),
                "total": o.total("buyer_paid"),
            }
            for o in priced.orders
        ],
        "platform_coupon": priced.platform_coupon.code if priced.platform_coupon else None,
        "list_total": priced.total("line_total"),
        "seller_discount_total": priced.total("seller_discount"),
        "platform_discount_total": priced.total("platform_discount"),
        "total": priced.total("buyer_paid"),
    }


BUYER_ITEM_FIELDS = (
    "id",
    "product_id",
    "image_url",
    "title_snapshot",
    "unit_price",
    "quantity",
    "line_total",
    "seller_discount",
    "platform_discount",
    "buyer_paid",
    "refunded_quantity",
    "refunded_buyer_paid",
)
SELLER_ITEM_FIELDS = BUYER_ITEM_FIELDS + (
    "merchandise_net",
    "commission_rate",
    "commission",
    "seller_payable",
    "refunded_commission",
    "refunded_seller_payable",
    "refunded_platform_discount",
)


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(read_only=True)
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj) -> str:
        return obj.product.image_url or ""

    class Meta:
        model = OrderItem
        fields = BUYER_ITEM_FIELDS
        read_only_fields = fields


class SellerOrderItemSerializer(OrderItemSerializer):
    class Meta:
        model = OrderItem
        fields = SELLER_ITEM_FIELDS
        read_only_fields = fields


class OrderTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTransition
        fields = ("from_status", "to_status", "reason", "created_at")
        read_only_fields = fields


class ReturnLineSerializer(serializers.ModelSerializer):
    item = serializers.UUIDField(source="item_id", read_only=True)
    title = serializers.CharField(source="item.title_snapshot", read_only=True)

    class Meta:
        model = ReturnLine
        fields = ("item", "title", "quantity")
        read_only_fields = fields


class ReturnSerializer(serializers.ModelSerializer):
    lines = ReturnLineSerializer(many=True, read_only=True)
    order = serializers.SerializerMethodField()

    def get_order(self, obj) -> dict:
        return {"id": str(obj.order_id), "number": obj.order.number}

    class Meta:
        model = ReturnRequest
        fields = (
            "id",
            "order",
            "status",
            "reason",
            "decision_note",
            "decided_at",
            "lines",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DisputeSerializer(serializers.ModelSerializer):
    order = serializers.SerializerMethodField()

    def get_order(self, obj) -> dict:
        return {"id": str(obj.order_id), "number": obj.order.number}

    class Meta:
        model = Dispute
        fields = (
            "id",
            "order",
            "status",
            "reason",
            "resolution_note",
            "resolved_at",
            "created_at",
        )
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ("id", "amount", "reason", "created_at")
        read_only_fields = fields


ORDER_FIELDS = (
    "id",
    "number",
    "checkout_number",
    "channel",
    "status",
    "payment_method",
    "payment_status",
    "currency",
    "list_total",
    "seller_discount_total",
    "platform_discount_total",
    "total",
    "refunded_total",
    "merchant",
    "buyer_name",
    "delivery_governorate",
    "delivery_city",
    "delivery_address",
    "delivery_latitude",
    "delivery_longitude",
    "contact_phone",
    "note",
    "shipping_reference",
    "paid_at",
    "shipped_at",
    "delivered_at",
    "completed_at",
    "items",
    "transitions",
    "returns",
    "disputes",
    "refunds",
    "return_deadline",
    "created_at",
    "status_changed_at",
)
SELLER_ORDER_FIELDS = ORDER_FIELDS + (
    "merchandise_net",
    "commission_rate",
    "commission_policy_version",
    "commission_total",
    "seller_payable_total",
    "settlement_state",
)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    transitions = OrderTransitionSerializer(many=True, read_only=True)
    returns = ReturnSerializer(many=True, read_only=True)
    disputes = DisputeSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    merchant = serializers.SerializerMethodField()
    delivery_governorate = GovernorateSerializer(read_only=True)
    delivery_city = CitySerializer(read_only=True, allow_null=True)
    buyer_name = serializers.SerializerMethodField()
    checkout_number = serializers.SerializerMethodField()
    return_deadline = serializers.SerializerMethodField()

    def get_merchant(self, obj) -> dict:
        return {"id": str(obj.merchant_id), "name": obj.merchant.name}

    def get_buyer_name(self, obj) -> str:
        return obj.buyer.full_name

    def get_checkout_number(self, obj) -> str:
        return obj.checkout.number if obj.checkout_id else ""

    def get_return_deadline(self, obj) -> str | None:
        if obj.delivered_at is None:
            return None
        return (obj.delivered_at + timedelta(days=RETURN_WINDOW_DAYS)).isoformat()

    class Meta:
        model = Order
        fields = ORDER_FIELDS
        read_only_fields = fields


class SellerOrderSerializer(OrderSerializer):
    items = SellerOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = SELLER_ORDER_FIELDS
        read_only_fields = fields


class AdminOrderSerializer(SellerOrderSerializer):
    buyer_email = serializers.EmailField(source="buyer.email", read_only=True)
    payment_verified_by = serializers.SerializerMethodField()

    def get_payment_verified_by(self, obj) -> str:
        return obj.payment_verified_by.email if obj.payment_verified_by_id else ""

    class Meta:
        model = Order
        fields = SELLER_ORDER_FIELDS + ("buyer_email", "payment_reference", "payment_verified_by")
        read_only_fields = fields


class CheckoutResultSerializer(serializers.ModelSerializer):
    orders = OrderSerializer(many=True, read_only=True)

    class Meta:
        model = Checkout
        fields = (
            "id",
            "number",
            "currency",
            "list_total",
            "seller_discount_total",
            "platform_discount_total",
            "total",
            "orders",
            "created_at",
        )
        read_only_fields = fields


class OrderTransitionRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            (s, s) for s in (OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.CANCELLED)
        ]
    )
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    shipping_reference = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )


class ReturnRequestLineSerializer(serializers.Serializer):
    item = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_LINE)


class ReturnCreateSerializer(serializers.Serializer):
    lines = ReturnRequestLineSerializer(many=True, allow_empty=False, max_length=MAX_LINES)
    reason = serializers.CharField(max_length=500)


class ReturnDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class DisputeCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class DisputeResolveSerializer(serializers.Serializer):
    refund = serializers.BooleanField()
    note = serializers.CharField(max_length=500)


class VerifyPaymentSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=120)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class QuoteCreateSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=10000)
    message = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class QuoteRespondSerializer(serializers.Serializer):
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class QuoteCloseSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=[
            (s, s) for s in (QuoteStatus.ACCEPTED, QuoteStatus.DECLINED, QuoteStatus.WITHDRAWN)
        ]
    )


class QuoteSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()
    requester = serializers.SerializerMethodField()

    def get_product(self, obj) -> dict:
        return {"id": str(obj.product_id), "title": obj.product.title}

    def get_company(self, obj) -> dict:
        return {"id": str(obj.company_id), "name": obj.company.name}

    def get_requester(self, obj) -> dict:
        # Business-to-business contact: the professional's public display name and type only.
        return {
            "id": str(obj.requester_id),
            "display_name": obj.requester.display_name,
            "provider_type": obj.requester.provider_type,
        }

    class Meta:
        model = QuoteRequest
        fields = (
            "id",
            "status",
            "quantity",
            "message",
            "product",
            "company",
            "requester",
            "quoted_unit_price",
            "quoted_currency",
            "quoted_note",
            "quoted_at",
            "expires_at",
            "closed_at",
            "created_at",
        )
        read_only_fields = fields


class DeliveryDefaultsSerializer(serializers.Serializer):
    """Pre-fill for checkout: the buyer's last delivery details, else their account phone."""

    governorate = serializers.CharField(allow_null=True)
    city = serializers.CharField(allow_null=True)
    address = serializers.CharField()
    phone = serializers.CharField()


# ---- seller tools: inventory, coupons, offers ---------------------------------------------------


class InventoryRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    image_url = serializers.CharField()
    is_active = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    on_hand = serializers.IntegerField(allow_null=True)
    reserved = serializers.IntegerField()
    available = serializers.IntegerField(allow_null=True)
    reorder_threshold = serializers.IntegerField(allow_null=True)
    low = serializers.BooleanField()


class StockAdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField(min_value=-100000, max_value=100000)
    reason = serializers.CharField(max_length=200)


class StockThresholdSerializer(serializers.Serializer):
    threshold = serializers.IntegerField(min_value=0, max_value=100000, allow_null=True)


class StockMovementSerializer(serializers.ModelSerializer):
    order_number = serializers.SerializerMethodField()

    def get_order_number(self, obj) -> str:
        return obj.order.number if obj.order_id else ""

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "kind",
            "quantity",
            "on_hand_after",
            "reserved_after",
            "order_number",
            "reason",
            "created_at",
        )
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()

    def get_company(self, obj) -> dict | None:
        return {"id": str(obj.company_id), "name": obj.company.name} if obj.company_id else None

    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "funded_by",
            "company",
            "kind",
            "value",
            "max_discount",
            "min_subtotal",
            "starts_at",
            "ends_at",
            "max_redemptions",
            "redemptions",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class CouponCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    kind = serializers.ChoiceField(choices=DiscountKind.choices)
    value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    max_discount = serializers.DecimalField(
        max_digits=12, decimal_places=0, required=False, allow_null=True
    )
    min_subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=0, required=False, default=0, min_value=0
    )
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField()
    max_redemptions = serializers.IntegerField(
        min_value=1, max_value=1000000, required=False, allow_null=True
    )


class ProductSaleSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, obj) -> dict:
        return {"id": str(obj.product_id), "title": obj.product.title}

    class Meta:
        model = ProductOffer
        fields = ("id", "product", "percent", "starts_at", "ends_at", "is_active", "created_at")
        read_only_fields = fields


class ProductSaleCreateSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("1"), max_value=Decimal("90")
    )
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField()
