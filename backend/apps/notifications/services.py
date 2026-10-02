"""Notification writes. This module is the only place rows are created or changed.

Creation is backend-only (called by event receivers); the REST API can only read
and mark-read. Every create is idempotent through the unique `dedupe_key`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from . import push_service
from .models import Notification
from .types import (
    SAFE_PAYLOAD_KEYS,
    NotificationCategory,
    NotificationEventType,
    NotificationResourceType,
)


def safe_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only allow-listed, JSON-safe, non-empty scalar facts."""
    cleaned: dict[str, Any] = {}
    for key in SAFE_PAYLOAD_KEYS:
        value = raw.get(key)
        if value is None or value == "":
            continue
        cleaned[key] = str(value)
    return cleaned


def create_notification(
    *,
    recipient_id: Any,
    category: str,
    event_type: str,
    dedupe_key: str,
    payload: dict[str, Any],
    resource_type: str = "",
    resource_id: UUID | None = None,
) -> tuple[Notification, bool]:
    """Create a notification once per `dedupe_key`; replays return the existing row."""
    with transaction.atomic():
        notification, created = Notification.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "recipient_id": recipient_id,
                "category": category,
                "event_type": event_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "payload": safe_payload(payload),
            },
        )
        if created:
            # Delivery hint only, after the row is durable; replays (created=False) never push.
            notification_id = notification.pk
            transaction.on_commit(lambda: push_service.send_notification_push(notification_id))
        return notification, created


def notify_reservation_created(*, recipient_id: Any, reservation_id: UUID, payload: dict) -> bool:
    _, created = create_notification(
        recipient_id=recipient_id,
        category=NotificationCategory.RESERVATION,
        event_type=NotificationEventType.RESERVATION_CREATED,
        dedupe_key=f"reservation:{reservation_id}:created:{recipient_id}",
        resource_type=NotificationResourceType.RESERVATION,
        resource_id=reservation_id,
        payload={**payload, "reservation_id": reservation_id},
    )
    return created


def notify_reservation_status_changed(
    *, recipient_id: Any, reservation_id: UUID, status: str, payload: dict
) -> bool:
    _, created = create_notification(
        recipient_id=recipient_id,
        category=NotificationCategory.RESERVATION,
        event_type=NotificationEventType.RESERVATION_STATUS_CHANGED,
        dedupe_key=f"reservation:{reservation_id}:status:{status}:{recipient_id}",
        resource_type=NotificationResourceType.RESERVATION,
        resource_id=reservation_id,
        payload={**payload, "reservation_id": reservation_id, "status": status},
    )
    return created


def unread_count(account) -> int:
    return Notification.objects.filter(recipient=account, read_at__isnull=True).count()


def mark_read(account, notification_id: UUID) -> Notification | None:
    """Mark one of the account's own notifications read. Idempotent: the original
    `read_at` is kept. Returns None for unknown / foreign ids (non-disclosing)."""
    with transaction.atomic():
        notification = (
            Notification.objects.select_for_update()
            .filter(pk=notification_id, recipient=account)
            .first()
        )
        if notification is None:
            return None
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return notification


def mark_all_read(account) -> int:
    """One UPDATE over the account's own unread rows with a single server timestamp."""
    now = timezone.now()
    return Notification.objects.filter(recipient=account, read_at__isnull=True).update(
        read_at=now, updated_at=now
    )
