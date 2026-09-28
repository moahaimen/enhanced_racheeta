from django.contrib.admin.sites import AdminSite

from apps.reservations.admin import (
    AvailabilitySlotAdmin,
    ReservationAdmin,
    ReservationTransitionAdmin,
)
from apps.reservations.models import AvailabilitySlot, Reservation, ReservationTransition


def _assert_inspection_only(admin_class, model, protected_fields):
    model_admin = admin_class(model, AdminSite())
    readonly = set(model_admin.get_readonly_fields(None))
    assert protected_fields <= readonly
    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_delete_permission(None) is False


def test_availability_admin_cannot_bypass_slot_invariants():
    _assert_inspection_only(
        AvailabilitySlotAdmin,
        AvailabilitySlot,
        {"provider", "service", "starts_at", "ends_at", "is_active"},
    )


def test_reservation_admin_cannot_bypass_state_machine():
    _assert_inspection_only(
        ReservationAdmin,
        Reservation,
        {"status", "status_changed_at", "patient", "provider", "service"},
    )


def test_transition_history_is_inspection_only_in_admin():
    _assert_inspection_only(
        ReservationTransitionAdmin,
        ReservationTransition,
        {"reservation", "actor", "from_status", "to_status", "reason"},
    )
