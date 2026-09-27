from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit_services
from apps.providers.models import ProviderProfile

from .models import Reservation, ReservationTransition
from .types import PROVIDER_TRANSITIONS, ReservationStatus


class InvalidTransition(Exception):
    pass


class NotAParty(Exception):
    pass


def _apply_transition(
    reservation: Reservation,
    *,
    target_status: str,
    actor,
    reason: str = "",
) -> Reservation:
    previous = reservation.status
    reservation.status = target_status
    reservation.status_changed_at = timezone.now()
    reservation.save(update_fields=["status", "status_changed_at", "updated_at"])

    ReservationTransition.objects.create(
        reservation=reservation,
        actor=actor,
        from_status=previous,
        to_status=target_status,
        reason=reason[:500],
    )
    audit_services.record(
        actor=actor,
        action="reservation.status_changed",
        target=reservation,
        summary=f"{previous} -> {target_status}",
        data={"from_status": previous, "to_status": target_status},
    )
    return reservation


@transaction.atomic
def transition_as_provider(
    reservation_id,
    *,
    provider: ProviderProfile,
    actor,
    target_status: str,
    reason: str = "",
) -> Reservation:
    reservation = (
        Reservation.objects.select_for_update(of=("self",))
        .select_related("provider")
        .get(pk=reservation_id)
    )
    if reservation.provider_id != provider.pk:
        raise NotAParty

    allowed = PROVIDER_TRANSITIONS.get(reservation.status, frozenset())
    if target_status not in allowed:
        raise InvalidTransition(
            f"Reservation cannot move from {reservation.status} to {target_status}."
        )
    return _apply_transition(
        reservation,
        target_status=target_status,
        actor=actor,
        reason=reason,
    )


@transaction.atomic
def cancel_as_patient(
    reservation_id,
    *,
    patient,
    reason: str = "",
) -> Reservation:
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)
    if reservation.patient_id != patient.pk:
        raise NotAParty
    if reservation.status not in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
    }:
        raise InvalidTransition(f"Reservation cannot be cancelled from {reservation.status}.")
    return _apply_transition(
        reservation,
        target_status=ReservationStatus.CANCELLED,
        actor=patient,
        reason=reason,
    )
