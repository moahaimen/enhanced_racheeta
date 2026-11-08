"""Bounded, consent-gated in-app marketing notifications.

Every marketing notification goes through `deliver`, which enforces, per recipient
and from CURRENT database state:

* consent: the in-app channel and the topic's opt-in (`services.wants_in_app`);
* a daily cap (`DAILY_CAP` marketing notifications per account per local day),
  counted under a lock on the recipient's account row so parallel sends cannot
  overshoot it;
* idempotency: one row per `dedupe_prefix` + recipient (the notification's unique
  `dedupe_key`), so replays never notify twice;
* a per-send cap (`SEND_CAP` recipients), so one campaign cannot fan out unbounded.

Nothing here reveals who received what to the advertiser.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, time
from typing import Any
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.notifications.types import NotificationCategory

from .services import wants_in_app

logger = logging.getLogger(__name__)

DAILY_CAP = 3
SEND_CAP = 200


def _start_of_today() -> datetime:
    today = timezone.localdate()
    return timezone.make_aware(datetime.combine(today, time.min))


def marketing_sent_today(account_id) -> int:
    return Notification.objects.filter(
        recipient_id=account_id,
        category=NotificationCategory.MARKETING,
        created_at__gte=_start_of_today(),
    ).count()


def deliver(
    *,
    account_ids: Iterable[Any],
    topic: str,
    event_type: str,
    dedupe_prefix: str,
    resource_type: str,
    resource_id: UUID,
    payload: dict[str, Any],
    limit: int = SEND_CAP,
) -> int:
    """Create at most `limit` new marketing notifications; returns how many were created."""
    account_model = get_user_model()
    created_count = 0
    seen: set = set()
    for account_id in account_ids:
        if created_count >= limit:
            break
        if account_id in seen:
            continue
        seen.add(account_id)
        with transaction.atomic():
            locked = (
                account_model.objects.select_for_update()
                .filter(pk=account_id, is_active=True)
                .values_list("pk", flat=True)
                .first()
            )
            if locked is None or not wants_in_app(account_id, topic):
                continue
            dedupe_key = f"{dedupe_prefix}:{account_id}"
            if Notification.objects.filter(dedupe_key=dedupe_key).exists():
                continue
            if marketing_sent_today(account_id) >= DAILY_CAP:
                continue
            _, created = create_notification(
                recipient_id=account_id,
                category=NotificationCategory.MARKETING,
                event_type=event_type,
                dedupe_key=dedupe_key,
                payload=payload,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            created_count += int(created)
    return created_count
