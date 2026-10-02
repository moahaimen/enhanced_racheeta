from django.db import models


class NotificationCategory(models.TextChoices):
    RESERVATION = "RESERVATION", "Reservation"


class NotificationEventType(models.TextChoices):
    RESERVATION_CREATED = "RESERVATION_CREATED", "Reservation created"
    # The new status travels in the payload, not in a per-status event type.
    RESERVATION_STATUS_CHANGED = "RESERVATION_STATUS_CHANGED", "Reservation status changed"


class NotificationResourceType(models.TextChoices):
    RESERVATION = "RESERVATION", "Reservation"


# Only these payload keys are ever stored. Anything else (patient notes, phone,
# email, contact details, tokens, account data) must never reach the table.
SAFE_PAYLOAD_KEYS = (
    "reservation_id",
    "service_title",
    "provider_name",
    "starts_at",
    "previous_status",
    "status",
)


class PushPlatform(models.TextChoices):
    ANDROID = "ANDROID", "Android"
    IOS = "IOS", "iOS"
    WEB = "WEB", "Web"
