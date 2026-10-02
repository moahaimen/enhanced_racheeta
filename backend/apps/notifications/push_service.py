"""Push device lifecycle and best-effort delivery.

Three concerns, kept apart:

* authoritative state — `Notification` / chat `Message` rows (not touched here);
* delivery registration — `PushDevice` (token ownership), managed below;
* delivery attempt — `push.PushSender`, called from `deliver`.

`deliver` never raises: Firebase being down, a rejected token or missing credentials
must not turn an already-committed business action into an error. Triggers register
delivery with `transaction.on_commit`, so a rolled-back change never pushes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit_services

from . import push
from .models import Notification, PushDevice
from .presentation import normalize_language, render
from .push import PushMessage, PushResult

logger = logging.getLogger(__name__)

# Bounds both stored registrations per account and delivery fan-out (no worker queue yet).
MAX_ACTIVE_DEVICES = 10

_GENERIC_BODY = {
    "ar": "افتح رشيتا لعرض التفاصيل.",
    "en": "Open Racheeta to view the details.",
}
_CHAT_TITLE = {"ar": "رسالة جديدة", "en": "New message"}


def _fingerprint(token: str) -> str:
    """Safe log identifier for a token: never the full value."""
    return f"…{token[-6:]}" if len(token) > 12 else "…"


# --- registration -------------------------------------------------------------------------


def register_device(account, *, token: str, platform: str) -> PushDevice:
    """Idempotent upsert; the account is always the authenticated caller.

    The token is globally unique in the database. If it belonged to another account it
    is *transferred*: the previous owner immediately stops receiving pushes through it.
    """
    with transaction.atomic():
        device = PushDevice.objects.select_for_update().filter(token=token).first()
        if device is None:
            try:
                with transaction.atomic():
                    device = PushDevice.objects.create(
                        account=account, token=token, platform=platform
                    )
            except IntegrityError:
                # A concurrent registration created it first; lock and take it over.
                device = PushDevice.objects.select_for_update().get(token=token)
            else:
                audit_services.record(
                    actor=account,
                    action="push_device.registered",
                    target=device,
                    summary=f"{platform} device registered",
                    data={"platform": platform},
                )
                _enforce_device_cap(account, keep=device.pk)
                return device

        transferred = device.account_id != account.pk
        device.account = account
        device.platform = platform
        device.is_active = True
        device.last_registered_at = timezone.now()
        device.save(
            update_fields=["account", "platform", "is_active", "last_registered_at", "updated_at"]
        )
        if transferred:
            audit_services.record(
                actor=account,
                action="push_device.transferred",
                target=device,
                summary="device token moved to a different account",
                data={"platform": platform},
            )
        _enforce_device_cap(account, keep=device.pk)
        return device


def _enforce_device_cap(account, *, keep: UUID) -> None:
    surplus = list(
        PushDevice.objects.filter(account=account, is_active=True)
        .exclude(pk=keep)
        .order_by("-last_registered_at", "-id")
        .values_list("pk", flat=True)[MAX_ACTIVE_DEVICES - 1 :]
    )
    if surplus:
        PushDevice.objects.filter(pk__in=surplus).update(is_active=False)


def unregister_device(account, *, token: str) -> bool:
    """Deactivate the caller's own registration. Foreign or unknown tokens change nothing;
    the caller cannot tell the difference (the API answers identically)."""
    with transaction.atomic():
        device = PushDevice.objects.select_for_update().filter(token=token, account=account).first()
        if device is None or not device.is_active:
            return False
        device.is_active = False
        device.save(update_fields=["is_active", "updated_at"])
        audit_services.record(
            actor=account,
            action="push_device.unregistered",
            target=device,
            summary="device unregistered",
            data={"platform": device.platform},
        )
        return True


# --- delivery -----------------------------------------------------------------------------


def deliver(account_id: Any, build: Callable[[str], PushMessage]) -> int:
    """Best-effort fan-out to the recipient's active devices. Never raises.

    `build(language)` returns the localized message. Returns the number of accepted sends.
    """
    try:
        if not push.is_enabled():
            return 0
        return _deliver(account_id, build)
    except Exception:  # noqa: BLE001 - delivery must never break a committed action
        logger.exception("push delivery aborted")
        return 0


def _deliver(account_id: Any, build: Callable[[str], PushMessage]) -> int:
    from apps.accounts.models import Account

    recipient = Account.objects.filter(pk=account_id, is_active=True).first()
    if recipient is None:
        return 0
    devices = list(
        PushDevice.objects.filter(account=recipient, is_active=True)[:MAX_ACTIVE_DEVICES]
    )
    if not devices:
        return 0
    message = build(normalize_language(recipient.preferred_language))
    sender = push.get_sender()
    sent = 0
    for device in devices:
        try:
            result = sender.send(device.token, message)
        except Exception as exc:  # noqa: BLE001 - one broken token must not stop the rest
            logger.warning(
                "push send failed device=%s token=%s error=%s",
                device.pk,
                _fingerprint(device.token),
                type(exc).__name__,
            )
            continue
        if result is PushResult.SENT:
            sent += 1
        elif result is PushResult.INVALID_TOKEN:
            logger.info("push token rejected permanently device=%s", device.pk)
            try:
                PushDevice.objects.filter(pk=device.pk, token=device.token).update(is_active=False)
            except Exception:  # noqa: BLE001
                logger.exception("could not deactivate rejected push device=%s", device.pk)
        else:
            logger.warning("push transient failure device=%s", device.pk)
    return sent


def _notification_message(notification: Notification, language: str) -> PushMessage:
    # Title only (no service/provider names): lock screens are visible to bystanders.
    title, _ = render(notification.event_type, notification.payload, language)
    return PushMessage(
        title=title,
        body=_GENERIC_BODY[language],
        data={
            "type": "notification",
            "notification_id": str(notification.pk),
            "event_type": notification.event_type,
        },
    )


def send_notification_push(notification_id: UUID) -> None:
    """Push for one persistent notification row. Runs after the creating transaction commits."""
    try:
        notification = Notification.objects.filter(pk=notification_id).first()
        if notification is None:
            return
        deliver(
            notification.recipient_id,
            lambda language: _notification_message(notification, language),
        )
    except Exception:  # noqa: BLE001
        logger.exception("push for notification aborted")


def send_chat_message_push(*, recipient_id: Any, conversation_id: UUID) -> None:
    """Content-free chat push: the app fetches the authoritative messages after opening."""
    deliver(
        recipient_id,
        lambda language: PushMessage(
            title=_CHAT_TITLE[language],
            body=_GENERIC_BODY[language],
            data={"type": "chat_message", "conversation_id": str(conversation_id)},
        ),
    )
