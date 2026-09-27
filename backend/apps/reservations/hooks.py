"""Reservation domain events for the future notification module.

Phase 4 owns the domain event boundary but does not create notification rows,
send push messages, or add a worker. Receivers added in Phase 9 can subscribe
without changing reservation transaction code. Events fire only after commit,
so rolled-back reservations never produce notifications.
"""

from __future__ import annotations

from django.db import transaction
from django.dispatch import Signal

reservation_created = Signal()
reservation_status_changed = Signal()


def emit_created(reservation) -> None:
    reservation_id = reservation.pk
    patient_id = reservation.patient_id
    provider_id = reservation.provider_id

    transaction.on_commit(
        lambda: reservation_created.send(
            sender=reservation.__class__,
            reservation_id=reservation_id,
            patient_id=patient_id,
            provider_id=provider_id,
        )
    )


def emit_status_changed(reservation, *, previous_status: str, actor) -> None:
    reservation_id = reservation.pk
    patient_id = reservation.patient_id
    provider_id = reservation.provider_id
    status = reservation.status
    actor_id = getattr(actor, "pk", None)

    transaction.on_commit(
        lambda: reservation_status_changed.send(
            sender=reservation.__class__,
            reservation_id=reservation_id,
            patient_id=patient_id,
            provider_id=provider_id,
            previous_status=previous_status,
            status=status,
            actor_id=actor_id,
        )
    )
