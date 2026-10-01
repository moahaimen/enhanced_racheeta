"""Subscriptions to other modules' domain events.

Reservations only emit signals after commit; this module turns them into
persistent notifications. Receivers never decide authorization — they derive
recipients from the committed participants and the acting account id carried by
the event. A failure here must never break the already-committed business action.
"""

from __future__ import annotations

import logging

from apps.reservations import hooks as reservation_hooks
from apps.reservations.models import Reservation

from . import services

logger = logging.getLogger(__name__)

CREATED_UID = "notifications.reservation_created"
STATUS_UID = "notifications.reservation_status_changed"


def _load(reservation_id):
    return Reservation.objects.select_related("provider").filter(pk=reservation_id).first()


def _payload(reservation: Reservation) -> dict:
    # Snapshots only; never patient_note or any contact data.
    return {
        "service_title": reservation.service_title_snapshot,
        "provider_name": reservation.provider_name_snapshot,
        "starts_at": reservation.starts_at.isoformat(),
    }


def _provider_account_id(reservation: Reservation):
    return reservation.provider.account_id if reservation.provider_id else None


def on_reservation_created(sender, *, reservation_id, **kwargs) -> None:
    try:
        reservation = _load(reservation_id)
        if reservation is None:
            return
        recipient_id = _provider_account_id(reservation)
        if recipient_id is None:
            return
        services.notify_reservation_created(
            recipient_id=recipient_id,
            reservation_id=reservation.pk,
            payload=_payload(reservation),
        )
    except Exception:  # noqa: BLE001
        logger.exception("notification for reservation_created failed")


def on_reservation_status_changed(
    sender, *, reservation_id, previous_status, status, actor_id=None, **kwargs
) -> None:
    try:
        reservation = _load(reservation_id)
        if reservation is None:
            return
        participants = {reservation.patient_id, _provider_account_id(reservation)}
        recipients = [pk for pk in participants if pk is not None and pk != actor_id]
        for recipient_id in recipients:
            services.notify_reservation_status_changed(
                recipient_id=recipient_id,
                reservation_id=reservation.pk,
                status=status,
                payload={**_payload(reservation), "previous_status": previous_status},
            )
    except Exception:  # noqa: BLE001
        logger.exception("notification for reservation_status_changed failed")


def connect() -> None:
    reservation_hooks.reservation_created.connect(on_reservation_created, dispatch_uid=CREATED_UID)
    reservation_hooks.reservation_status_changed.connect(
        on_reservation_status_changed, dispatch_uid=STATUS_UID
    )
