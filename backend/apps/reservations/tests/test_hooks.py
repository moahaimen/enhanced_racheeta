import pytest

from apps.reservations import hooks, services
from apps.reservations.types import ReservationStatus

from .test_state_machine import _setup


@pytest.mark.django_db(transaction=True)
def test_reservation_status_hook_fires_after_commit(account_factory):
    provider, provider_account, _, reservation = _setup(account_factory)
    received = []

    def receiver(sender, **payload):
        received.append(payload)

    hooks.reservation_status_changed.connect(receiver)
    try:
        services.transition_as_provider(
            reservation.pk,
            provider=provider,
            actor=provider_account,
            target_status=ReservationStatus.CONFIRMED,
        )
    finally:
        hooks.reservation_status_changed.disconnect(receiver)

    assert len(received) == 1
    assert received[0]["reservation_id"] == reservation.pk
    assert received[0]["previous_status"] == ReservationStatus.PENDING
    assert received[0]["status"] == ReservationStatus.CONFIRMED
    assert received[0]["actor_id"] == provider_account.pk
