from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import BaseModel

from .types import (
    NotificationCategory,
    NotificationEventType,
    NotificationResourceType,
    PushPlatform,
)


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


class PushDevice(BaseModel):
    """One FCM registration token and the single account that currently owns it.

    This is delivery *registration* only: it never decides whether a notification or
    message exists (PostgreSQL rows do). The token is a credential-like opaque value:
    it is never serialized to clients, logged in full, or copied into payloads.

    `token` is globally unique, so one physical app/browser token can belong to at
    most one account at any time. Registering it under another account transfers
    ownership (see `push_service.register_device`); the previous owner stops
    receiving pushes through it. The database enforces this, not application code.
    """

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_devices"
    )
    token = models.CharField(max_length=1024, editable=False)
    platform = models.CharField(max_length=16, choices=PushPlatform.choices)
    is_active = models.BooleanField(default=True)
    # Refreshed on every (idempotent) registration: the only lifecycle signal needed to
    # prefer fresh devices and cap fan-out. No device name/model/fingerprint is collected.
    last_registered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-last_registered_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["token"], name="push_device_token_unique"),
            models.CheckConstraint(condition=~Q(token=""), name="push_device_token_not_empty"),
        ]
        indexes = [
            models.Index(fields=["account", "is_active"], name="push_device_account_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.platform} device of {self.account_id}"

    @property
    def masked_token(self) -> str:
        return f"…{self.token[-6:]}" if len(self.token) > 12 else "…"
