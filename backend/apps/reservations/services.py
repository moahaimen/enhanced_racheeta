from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.audit import services as audit_services
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import VerificationStatus

from . import hooks
from .models import AvailabilitySlot, Reservation, ReservationTransition
from .types import PROVIDER_TRANSITIONS, ReservationStatus

LIVE_STATUSES = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED)


class ReservationError(Exception):
    code = "reservation_error"


class InvalidTransition(ReservationError):
    code = "invalid_transition"


class NotAParty(ReservationError):
    code = "not_found"


class InvalidAvailability(ReservationError):
    code = "invalid_availability"


class SlotConflict(ReservationError):
    code = "slot_conflict"


class SlotUnavailable(ReservationError):
    code = "slot_unavailable"


class ServiceUnavailable(ReservationError):
    code = "service_unavailable"


class ProviderUnavailable(ReservationError):
    code = "provider_unavailable"


def slot_matches_current_service(slot: AvailabilitySlot) -> bool:
    """A published slot must still match the service duration used to book it."""
    duration = slot.service.duration_minutes
    return bool(
        duration
        and slot.ends_at == slot.starts_at + timedelta(minutes=duration)
    )


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
    hooks.emit_status_changed(reservation, previous_status=previous, actor=actor)
    return reservation


@transaction.atomic
def create_availability_slot(
    provider: ProviderProfile,
    *,
    service_id,
    starts_at,
) -> AvailabilitySlot:
    provider = ProviderProfile.objects.select_for_update(of=("self",)).get(pk=provider.pk)
    try:
        service = ServiceOffering.objects.select_for_update(of=("self",)).get(pk=service_id)
    except ServiceOffering.DoesNotExist as exc:
        raise ServiceUnavailable("The selected service is unavailable.") from exc

    if service.provider_id != provider.pk or not service.is_active:
        raise ServiceUnavailable("The selected service is unavailable.")
    if not service.duration_minutes:
        raise ServiceUnavailable("Set a duration for this service before creating availability.")
    if starts_at <= timezone.now():
        raise InvalidAvailability("Availability must start in the future.")

    ends_at = starts_at + timedelta(minutes=service.duration_minutes)
    overlaps = AvailabilitySlot.objects.filter(
        provider=provider,
        is_active=True,
        starts_at__lt=ends_at,
        ends_at__gt=starts_at,
    ).exists()
    if overlaps:
        raise SlotConflict("This availability overlaps another active slot.")

    try:
        with transaction.atomic():
            return AvailabilitySlot.objects.create(
                provider=provider,
                service=service,
                starts_at=starts_at,
                ends_at=ends_at,
            )
    except IntegrityError as exc:
        raise SlotConflict("This availability conflicts with another slot.") from exc


@transaction.atomic
def deactivate_availability_slot(
    provider: ProviderProfile,
    *,
    slot_id,
) -> AvailabilitySlot:
    try:
        slot = AvailabilitySlot.objects.select_for_update().get(pk=slot_id, provider=provider)
    except AvailabilitySlot.DoesNotExist as exc:
        raise NotAParty("Availability slot not found.") from exc

    if Reservation.objects.filter(
        availability_slot=slot,
        status__in=LIVE_STATUSES,
    ).exists():
        raise SlotUnavailable("A live reservation is using this slot.")
    slot.is_active = False
    slot.save(update_fields=["is_active", "updated_at"])
    return slot


@transaction.atomic
def create_reservation(
    *,
    patient,
    slot_id,
    patient_note: str = "",
) -> Reservation:
    try:
        slot = (
            AvailabilitySlot.objects.select_for_update(of=("self",))
            .select_related("provider", "service")
            .get(pk=slot_id)
        )
    except AvailabilitySlot.DoesNotExist as exc:
        raise SlotUnavailable("This appointment slot is unavailable.") from exc

    provider = ProviderProfile.objects.select_for_update(of=("self",)).get(pk=slot.provider_id)
    account = Account.objects.select_for_update().get(pk=provider.account_id)
    try:
        service = ServiceOffering.objects.select_for_update(of=("self",)).get(pk=slot.service_id)
    except ServiceOffering.DoesNotExist as exc:
        raise ServiceUnavailable("The selected service is unavailable.") from exc

    if (
        not slot.is_active
        or slot.starts_at <= timezone.now()
        or Reservation.objects.filter(
            availability_slot=slot,
            status__in=LIVE_STATUSES,
        ).exists()
    ):
        raise SlotUnavailable("This appointment slot is unavailable.")

    if (
        provider.verification_status != VerificationStatus.VERIFIED
        or not provider.is_visible
        or not account.is_active
    ):
        raise ProviderUnavailable("This provider is not available for new reservations.")

    if (
        not service.is_active
        or service.provider_id != provider.pk
        or not slot_matches_current_service(slot)
    ):
        raise ServiceUnavailable("This service is not available for this appointment slot.")

    try:
        with transaction.atomic():
            reservation = Reservation.objects.create(
                patient=patient,
                provider=provider,
                service=service,
                availability_slot=slot,
                provider_name_snapshot=provider.display_name,
                service_title_snapshot=service.title,
                price_snapshot=service.price,
                currency_snapshot=service.currency,
                duration_minutes_snapshot=service.duration_minutes,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                patient_note=patient_note,
            )
    except IntegrityError as exc:
        raise SlotUnavailable("This appointment slot was already reserved.") from exc

    ReservationTransition.objects.create(
        reservation=reservation,
        actor=patient,
        from_status="",
        to_status=ReservationStatus.PENDING,
        reason="",
    )
    audit_services.record(
        actor=patient,
        action="reservation.created",
        target=reservation,
        summary="Reservation created",
        data={"status": ReservationStatus.PENDING},
    )
    hooks.emit_created(reservation)
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
    now = timezone.now()
    if target_status == ReservationStatus.CONFIRMED and reservation.starts_at <= now:
        raise InvalidTransition("A past reservation cannot be confirmed.")
    if target_status in {ReservationStatus.COMPLETED, ReservationStatus.NO_SHOW}:
        if reservation.starts_at > now:
            raise InvalidTransition("This transition is only valid after the appointment starts.")

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
    if reservation.starts_at <= timezone.now():
        raise InvalidTransition("A reservation cannot be cancelled after the appointment starts.")
    return _apply_transition(
        reservation,
        target_status=ReservationStatus.CANCELLED,
        actor=patient,
        reason=reason,
    )
