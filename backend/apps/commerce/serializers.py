from rest_framework import serializers

from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer

from .models import Order, OrderItem, OrderTransition, QuoteRequest
from .types import MAX_LINES, MAX_QUANTITY_PER_LINE, OrderStatus, PaymentMethod, QuoteStatus


class CartLineSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_LINE)


class CheckoutSerializer(serializers.Serializer):
    """Only product ids and quantities come from the client; prices and totals never do."""

    items = CartLineSerializer(many=True, allow_empty=False, max_length=MAX_LINES)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    address = serializers.CharField(max_length=255)
    phone = serializers.RegexField(r"^\+?[0-9 ]{7,20}$", max_length=32)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        city = attrs.get("city")
        if city is not None and city.governorate_id != attrs["governorate"].pk:
            raise serializers.ValidationError(
                {"city": "This city does not belong to the governorate."}
            )
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product_id", "title_snapshot", "unit_price", "quantity", "line_total")
        read_only_fields = fields


class OrderTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTransition
        fields = ("from_status", "to_status", "reason", "created_at")
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    transitions = OrderTransitionSerializer(many=True, read_only=True)
    merchant = serializers.SerializerMethodField()
    delivery_governorate = GovernorateSerializer(read_only=True)
    delivery_city = CitySerializer(read_only=True, allow_null=True)
    buyer_name = serializers.SerializerMethodField()

    def get_merchant(self, obj) -> dict:
        return {"id": str(obj.merchant_id), "name": obj.merchant.name}

    def get_buyer_name(self, obj) -> str:
        return obj.buyer.full_name

    class Meta:
        model = Order
        fields = (
            "id",
            "number",
            "status",
            "payment_method",
            "payment_status",
            "total",
            "currency",
            "merchant",
            "buyer_name",
            "delivery_governorate",
            "delivery_city",
            "delivery_address",
            "contact_phone",
            "note",
            "items",
            "transitions",
            "created_at",
            "status_changed_at",
        )
        read_only_fields = fields


class OrderTransitionRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            (s, s)
            for s in (
                OrderStatus.CONFIRMED,
                OrderStatus.SHIPPED,
                OrderStatus.DELIVERED,
                OrderStatus.CANCELLED,
            )
        ]
    )
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


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
            "closed_at",
            "created_at",
        )
        read_only_fields = fields
