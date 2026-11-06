from django.db import models


class NotificationCategory(models.TextChoices):
    RESERVATION = "RESERVATION", "Reservation"
    ORDER = "ORDER", "Store order"
    QUOTE = "QUOTE", "Quote request"
    # Marketing: created only with the recipient's in-app consent for the topic (apps.preferences),
    # bounded per day, deduplicated. Transactional categories above never consult preferences.
    MARKETING = "MARKETING", "Sponsored / promotion"


class NotificationEventType(models.TextChoices):
    RESERVATION_CREATED = "RESERVATION_CREATED", "Reservation created"
    # The new status travels in the payload, not in a per-status event type.
    RESERVATION_STATUS_CHANGED = "RESERVATION_STATUS_CHANGED", "Reservation status changed"
    ORDER_PLACED = "ORDER_PLACED", "New store order"
    ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED", "Order status changed"
    QUOTE_REQUESTED = "QUOTE_REQUESTED", "New quote request"
    QUOTE_UPDATED = "QUOTE_UPDATED", "Quote request updated"
    SPONSORED_PRODUCT = "SPONSORED_PRODUCT", "Sponsored product in your field"
    PROPERTY_PROMOTION = "PROPERTY_PROMOTION", "Promoted medical property"
    STOCK_LOW = "STOCK_LOW", "Product stock is low"
    SETTLEMENT_PAID = "SETTLEMENT_PAID", "Seller payout recorded (simulated)"


class NotificationResourceType(models.TextChoices):
    RESERVATION = "RESERVATION", "Reservation"
    ORDER = "ORDER", "Order"
    QUOTE = "QUOTE", "Quote request"
    PRODUCT = "PRODUCT", "Product"
    LISTING = "LISTING", "Property listing"


# Only these payload keys are ever stored. Anything else (patient notes, phone,
# email, contact details, tokens, account data) must never reach the table.
SAFE_PAYLOAD_KEYS = (
    "reservation_id",
    "service_title",
    "provider_name",
    "starts_at",
    "previous_status",
    "status",
    "order_number",
    "merchant_name",
    "product_title",
    "quantity",
    "company_name",
    "listing_title",
    "amount",
    "currency",
)


class PushPlatform(models.TextChoices):
    ANDROID = "ANDROID", "Android"
    IOS = "IOS", "iOS"
    WEB = "WEB", "Web"
