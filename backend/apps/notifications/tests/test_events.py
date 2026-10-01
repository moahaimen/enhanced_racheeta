import pytest
from django.db import transaction

from apps.notifications import receivers
from apps.notifications.models import Notification
from apps.notifications.types import NotificationEventType
from apps.reservations import hooks, services
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus

from .helpers import book, make_booking_world, notifications_for


@pytest.mark.django_db
def test_created_notifies_provider_only(account_factory, django_capture_on_commit_callbacks):
    provider, provider_account, patient, service, slot = make_booking_world(account_factory)
    with django_capture_on_commit_callbacks(execute=True):
        reservation = book(patient, slot)

    rows = notifications_for(provider_account)
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == NotificationEventType.RESERVATION_CREATED
    assert row.resource_type == "RESERVATION"
    assert row.resource_id == reservation.pk
    assert row.read_at is None
    assert row.payload["service_title"] == "Consultation"
    assert row.payload["provider_name"] == "Dr Notify"
    assert row.payload["reservation_id"] == str(reservation.pk)
    assert notifications_for(patient) == []


@pytest.mark.django_db
def test_payload_never_contains_private_data(account_factory, django_capture_on_commit_callbacks):
    _, provider_account, patient, _, slot = make_booking_world(account_factory)
    with django_capture_on_commit_callbacks(execute=True):
        book(patient, slot, note="secret-patient-note")

    row = notifications_for(provider_account)[0]
    blob = str(row.payload).lower()
    assert "secret-patient-note" not in blob
    assert patient.email.lower() not in blob
    assert set(row.payload) <= {
        "reservation_id",
        "service_title",
        "provider_name",
        "starts_at",
        "previous_status",
        "status",
    }


@pytest.mark.django_db
def test_rolled_back_booking_creates_no_notification(
    account_factory, django_capture_on_commit_callbacks
):
    _, provider_account, patient, _, slot = make_booking_world(account_factory)

    class Boom(Exception):
        pass

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(Boom), transaction.atomic():
            book(patient, slot)
            raise Boom

    assert Notification.objects.count() == 0
    assert Reservation.objects.count() == 0


def _booked(account_factory, capture):
    provider, provider_account, patient, _, slot = make_booking_world(account_factory)
    with capture(execute=True):
        reservation = book(patient, slot)
    return provider, provider_account, patient, reservation


def _provider_acts(provider, provider_account, reservation, target, capture):
    with capture(execute=True):
        services.transition_as_provider(
            reservation.pk, provider=provider, actor=provider_account, target_status=target
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target",
    [ReservationStatus.CONFIRMED, ReservationStatus.REJECTED, ReservationStatus.CANCELLED],
)
def test_provider_status_change_notifies_patient_not_actor(
    account_factory, django_capture_on_commit_callbacks, target
):
    provider, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )
    before_provider = len(notifications_for(provider_account))
    _provider_acts(
        provider, provider_account, reservation, target, django_capture_on_commit_callbacks
    )

    rows = notifications_for(patient)
    assert len(rows) == 1
    assert rows[0].event_type == NotificationEventType.RESERVATION_STATUS_CHANGED
    assert rows[0].payload["status"] == target
    assert rows[0].payload["previous_status"] == ReservationStatus.PENDING
    assert len(notifications_for(provider_account)) == before_provider


@pytest.mark.django_db
@pytest.mark.parametrize("target", [ReservationStatus.COMPLETED, ReservationStatus.NO_SHOW])
def test_provider_complete_and_no_show_notify_patient(
    account_factory, django_capture_on_commit_callbacks, target
):
    provider, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )
    _provider_acts(
        provider,
        provider_account,
        reservation,
        ReservationStatus.CONFIRMED,
        django_capture_on_commit_callbacks,
    )
    # Completion needs the slot to be in the past.
    Reservation.objects.filter(pk=reservation.pk).update(
        starts_at=reservation.starts_at.replace(year=2020),
        ends_at=reservation.ends_at.replace(year=2020),
    )
    _provider_acts(
        provider, provider_account, reservation, target, django_capture_on_commit_callbacks
    )

    statuses = [r.payload["status"] for r in notifications_for(patient)]
    assert statuses == [ReservationStatus.CONFIRMED, target]


@pytest.mark.django_db
def test_patient_cancel_notifies_provider_not_patient(
    account_factory, django_capture_on_commit_callbacks
):
    _, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.cancel_as_patient(reservation.pk, patient=patient, reason="")

    provider_rows = notifications_for(provider_account)
    assert [r.event_type for r in provider_rows] == [
        NotificationEventType.RESERVATION_CREATED,
        NotificationEventType.RESERVATION_STATUS_CHANGED,
    ]
    assert provider_rows[1].payload["status"] == ReservationStatus.CANCELLED
    assert notifications_for(patient) == []


@pytest.mark.django_db
def test_non_participant_actor_notifies_both_never_actor(
    account_factory, django_capture_on_commit_callbacks
):
    _, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )
    stranger = account_factory()
    with django_capture_on_commit_callbacks(execute=True):
        hooks.emit_status_changed(reservation, previous_status="PENDING", actor=stranger)

    # Receivers perform no authorization inference; the status comes from the event.
    assert notifications_for(stranger) == []
    assert len(notifications_for(patient)) == 1
    assert len(notifications_for(provider_account)) == 2  # created + status


@pytest.mark.django_db
def test_replayed_event_is_deduplicated(account_factory, django_capture_on_commit_callbacks):
    _, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )
    for _ in range(3):
        receivers.on_reservation_created(
            Reservation, reservation_id=reservation.pk, patient_id=patient.pk
        )
    assert len(notifications_for(provider_account)) == 1

    for _ in range(2):
        receivers.on_reservation_status_changed(
            Reservation,
            reservation_id=reservation.pk,
            previous_status="PENDING",
            status="CONFIRMED",
            actor_id=provider_account.pk,
        )
    assert len(notifications_for(patient)) == 1


@pytest.mark.django_db
def test_dedupe_keys_are_stable(account_factory, django_capture_on_commit_callbacks):
    _, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )
    key = notifications_for(provider_account)[0].dedupe_key
    assert key == f"reservation:{reservation.pk}:created:{provider_account.pk}"
    receivers.on_reservation_status_changed(
        Reservation,
        reservation_id=reservation.pk,
        previous_status="PENDING",
        status="CONFIRMED",
        actor_id=provider_account.pk,
    )
    assert (
        notifications_for(patient)[0].dedupe_key
        == f"reservation:{reservation.pk}:status:CONFIRMED:{patient.pk}"
    )


@pytest.mark.django_db
def test_receiver_failure_never_breaks_the_business_action(
    account_factory, django_capture_on_commit_callbacks, monkeypatch
):
    provider, provider_account, patient, reservation = _booked(
        account_factory, django_capture_on_commit_callbacks
    )

    def boom(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("apps.notifications.services.notify_reservation_status_changed", boom)
    _provider_acts(
        provider,
        provider_account,
        reservation,
        ReservationStatus.CONFIRMED,
        django_capture_on_commit_callbacks,
    )
    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.CONFIRMED


def test_receivers_register_once_with_dispatch_uid():
    before = len(hooks.reservation_created.receivers)
    receivers.connect()
    receivers.connect()
    assert len(hooks.reservation_created.receivers) == before
