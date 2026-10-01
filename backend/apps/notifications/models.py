from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel

from .types import NotificationCategory, NotificationEventType, NotificationResourceType


class Notification(BaseModel):
    """A persistent, recipient-owned notification.

    PostgreSQL is authoritative. Rows are created only by backend code reacting
    to domain events. No translated prose is stored: `title`/`body` are rendered
    at read time from `event_type` + `payload` (see `presentation`). `payload`
    holds a small allow-listed set of non-sensitive facts only.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(max_length=32, choices=NotificationCategory.choices)
    event_type = models.CharField(max_length=48, choices=NotificationEventType.choices)
    resource_type = models.CharField(
        max_length=32, choices=NotificationResourceType.choices, blank=True, default=""
    )
    resource_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    # Backend-only idempotency key; never serialized to clients.
    dedupe_key = models.CharField(max_length=200, editable=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["dedupe_key"], name="notification_dedupe_key_unique"),
            models.CheckConstraint(
                condition=(Q(resource_type="") & Q(resource_id__isnull=True))
                | (~Q(resource_type="") & Q(resource_id__isnull=False)),
                name="notification_resource_coherent",
            ),
        ]
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="notif_recipient_read_idx"),
            models.Index(fields=["recipient", "-created_at"], name="notif_recipient_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} → {self.recipient_id}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
