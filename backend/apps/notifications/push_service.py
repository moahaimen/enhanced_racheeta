"""Push device lifecycle and best-effort delivery.

Three concerns, kept apart:

* authoritative state — `Notification` / chat `Message` rows (not touched here);
* delivery registration — `PushDevice` (token ownership), managed below;
* delivery attempt — `push.PushSender`, called from `deliver`.

`deliver` never raises: Firebase being down, a rejected token or missing credentials
must not turn an already-committed business action into an error. Triggers register
delivery with `transaction.on_commit`, so a rolled-back change never pushes.

`on_commit` is not asynchronous: the callback runs in the originating request. `deliver`
therefore makes exactly one sender call per delivery (`send_batch`, bounded by a hard
deadline in `push.py`), so the latency it adds is a constant, never devices × timeout.
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


# --- registration -------------------------------------------------------------------------
#
# Ownership ordering protocol
# ---------------------------
# A token's owner/active state is changed by two operations: register and unregister. HTTP gives
# no ordering between requests (a request can be delayed, retried or arrive after a newer one that
# committed first), so each operation carries a client sequence (`ownership_seq`, strictly
# increasing per installation) and the decision is made under the token row lock:
#
#   * the row has no stored sequence (never sequenced / legacy): any request is applied, as before;
#   * the row has a stored sequence S: a request is applied only if it carries a sequence > S.
#     An older, EQUAL or MISSING sequence changes nothing at all (owner, platform, active state,
#     timestamps and the stored sequence stay exactly as they were) — a legacy unsequenced request
#     can therefore never supersede sequenced ownership, and an exact replay is idempotent.
#
# Consequences: the final state depends on the sequences, not on arrival or commit order; a
# register that overtakes nothing cannot resurrect a token a newer unregister already deactivated;
# and an unregister that arrives BEFORE the register it follows leaves an inactive ordering marker
# (a row for the caller with `is_active = False`) so the late, older register is rejected.


class StaleOwnership(Exception):
    """A registration lost to a newer (or equal, or unsequenced-on-sequenced) operation."""


def _accepts(device: PushDevice, seq: int | None) -> bool:
    if device.ownership_seq is None:
        return True  # legacy row: unchanged behaviour
    return seq is not None and seq > device.ownership_seq


def register_device(account, *, token: str, platform: str, ownership_seq: int | None = None):
    """Idempotent, ordered upsert; the account is always the authenticated caller.

    The token is globally unique in the database. If it belonged to another account it
    is *transferred*: the previous owner immediately stops receiving pushes through it.
    Raises `StaleOwnership` (HTTP 409) when a newer operation already governs the token; an exact
    replay by the current owner is returned unchanged.
    """
    with transaction.atomic():
        device = PushDevice.objects.select_for_update().filter(token=token).first()
        if device is None:
            try:
                with transaction.atomic():
                    device = PushDevice.objects.create(
                        account=account,
                        token=token,
                        platform=platform,
                        ownership_seq=ownership_seq,
                    )
            except IntegrityError:
                # A concurrent operation created it first; lock and decide against its sequence.
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

        if not _accepts(device, ownership_seq):
            if (
                ownership_seq is not None
                and ownership_seq == device.ownership_seq
                and device.account_id == account.pk
                and device.is_active
            ):
                return device  # exact replay by the owner: idempotent, nothing changes
            raise StaleOwnership

        transferred = device.account_id != account.pk
        device.account = account
        device.platform = platform
        device.is_active = True
        device.last_registered_at = timezone.now()
        fields = ["account", "platform", "is_active", "last_registered_at", "updated_at"]
        if ownership_seq is not None:
            device.ownership_seq = ownership_seq
            fields.append("ownership_seq")
        device.save(update_fields=fields)
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


# Sequenced inactive rows are durable ownership-ordering state, not disposable history.
# Deleting one would forget the highest accepted ownership_seq for that token and could let an
# older delayed register become authoritative later. They therefore have no count- or time-based
# pruning in this protocol.

def unregister_device(
    account, *, token: str, ownership_seq: int | None = None, platform: str = "ANDROID"
) -> bool:
    """Ordered deactivation of the caller's own registration; returns whether it deactivated.

    * Foreign tokens change nothing (the caller cannot tell the difference); a sequence is never
      recorded on another account's registration.
    * A stale, equal or missing sequence on a sequenced token changes nothing.
    * A newer sequence by the owner deactivates the registration AND stores the sequence, so an
      older register arriving later is rejected (it cannot resurrect the account).
    * A sequenced unregister for a token the server has not seen yet records an inactive ordering
      marker for the caller, so the register it follows cannot be applied after it.
    """
    with transaction.atomic():
        device = PushDevice.objects.select_for_update().filter(token=token).first()
        if device is None:
            if ownership_seq is None:
                return False
            try:
                with transaction.atomic():
                    marker = PushDevice.objects.create(
                        account=account,
                        token=token,
                        platform=platform,
                        is_active=False,
                        ownership_seq=ownership_seq,
                    )
            except IntegrityError:
                device = PushDevice.objects.select_for_update().get(token=token)
            else:
                # This row is an ownership tombstone. Keep it durably: its stored sequence is what
                # makes any older delayed registration for this token stale.
                return False

        if device.account_id != account.pk or not _accepts(device, ownership_seq):
            return False
        was_active = device.is_active
        device.is_active = False
        fields = ["is_active", "updated_at"]
        if ownership_seq is not None:
            device.ownership_seq = ownership_seq
            fields.append("ownership_seq")
        device.save(update_fields=fields)
        if was_active:
            audit_services.record(
                actor=account,
                action="push_device.unregistered",
                target=device,
                summary="device unregistered",
                data={"platform": device.platform},
            )
        return was_active


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
    tokens = [device.token for device in devices]

    # ONE bounded operation for every device of this recipient. The sender owns the latency
    # bound (push.py); never loop over devices here, that would add one wait per device.
    try:
        results = push.get_sender().send_batch(tokens, message)
    except push.PushDeadlineExceeded:
        logger.warning("push batch missed its deadline devices=%d", len(devices))
        return 0
    except push.PushDeliveryUnavailable as exc:
        logger.info("push batch skipped devices=%d reason=%s", len(devices), type(exc).__name__)
        return 0
    except Exception as exc:  # noqa: BLE001 - a whole-batch failure says nothing about tokens
        logger.warning("push batch failed devices=%d error=%s", len(devices), type(exc).__name__)
        return 0

    sent = 0
    rejected: list[str] = []
    transient = 0
    for token in tokens:
        result = results.get(token, PushResult.TRANSIENT_FAILURE)
        if result is PushResult.SENT:
            sent += 1
        elif result is PushResult.INVALID_TOKEN:
            rejected.append(token)
        else:
            transient += 1
    if rejected:
        # Only permanent per-token rejections deactivate a registration (one UPDATE).
        PushDevice.objects.filter(token__in=rejected, is_active=True).update(is_active=False)
        logger.info("push tokens rejected permanently count=%d", len(rejected))
    if transient:
        logger.warning("push transient failures count=%d", transient)
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
