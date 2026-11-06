"""Phase F: online booking is switched off reversibly by one server setting.

`RACHEETA["RESERVATIONS_ENABLED"]` (env `RESERVATIONS_ENABLED`):
* production default is OFF (config/settings.py); the legacy booking suite runs with it ON
  (config/test_settings.py) and keeps passing, which is the "ON restores" evidence;
* OFF: new bookings and new appointment slots get the typed error `service_disabled` (403),
  public availability is empty, dashboards drop booking modules, and the web app reads the switch
  from the public `GET /api/v1/platform/features`;
* OFF never deletes or hides history: patients and providers still list and open their past
  reservations, and a live booking can still be cancelled.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reservations.models import AvailabilitySlot, Reservation
from apps.reservations.types import ReservationStatus

from .test_booking_api import _provider_and_service

pytestmark = pytest.mark.django_db

FEATURES = "/api/v1/platform/features"


def _switch(settings, on: bool):
    settings.RACHEETA = {**settings.RACHEETA, "RESERVATIONS_ENABLED": on}


@pytest.fixture
def booked(account_factory):
    """A provider with one free slot and one existing (history) reservation."""
    provider, service = _provider_and_service(account_factory)
    patient = account_factory(role="PATIENT")
    start = timezone.now() + timedelta(days=2)
    free = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
    )
    taken_slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=start + timedelta(hours=2),
        ends_at=start + timedelta(hours=2, minutes=30),
    )
    reservation = Reservation.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        availability_slot=taken_slot,
        starts_at=taken_slot.starts_at,
        ends_at=taken_slot.ends_at,
        status=ReservationStatus.PENDING,
        price_snapshot=service.price,
        currency_snapshot=service.currency,
        duration_minutes_snapshot=30,
    )
    return provider, service, patient, free, reservation


def test_production_default_is_off():
    """config/settings.py reads `RESERVATIONS_ENABLED` with default False; only the test
    settings turn it on (for the legacy booking suite)."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3]
    source = (root / "config" / "settings.py").read_text()
    assert 'env.bool("RESERVATIONS_ENABLED", default=False)' in source
    assert (
        'os.environ.setdefault("RESERVATIONS_ENABLED", "true")'
        in (root / "config" / "test_settings.py").read_text()
    )


@pytest.mark.parametrize("on", [True, False])
def test_features_endpoint_is_public_and_follows_the_switch(api_client, settings, on):
    _switch(settings, on)
    response = api_client.get(FEATURES)
    assert response.status_code == 200
    assert response.json() == {"reservations_enabled": on}


def test_off_refuses_a_new_booking_with_a_typed_error(api_client, settings, booked):
    _switch(settings, False)
    _, _, patient, free, _ = booked
    api_client.force_authenticate(user=patient)
    response = api_client.post(
        "/api/v1/reservations", {"availability_slot": str(free.pk)}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "service_disabled"
    assert Reservation.objects.filter(availability_slot=free).count() == 0


def test_off_refuses_new_appointment_slots(api_client, settings, booked):
    _switch(settings, False)
    provider, service, *_ = booked
    api_client.force_authenticate(user=provider.account)
    response = api_client.post(
        "/api/v1/reservations/provider/availability",
        {"service": str(service.pk), "starts_at": (timezone.now() + timedelta(days=5)).isoformat()},
        format="json",
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "service_disabled"


def test_off_shows_no_public_availability(api_client, settings, booked):
    provider = booked[0]
    _switch(settings, True)
    assert len(api_client.get(f"/api/v1/providers/{provider.pk}/availability").json()) == 1
    _switch(settings, False)
    response = api_client.get(f"/api/v1/providers/{provider.pk}/availability")
    assert response.status_code == 200 and response.json() == []


def test_off_keeps_history_for_patient_and_provider(api_client, settings, booked):
    _switch(settings, False)
    provider, _, patient, _, reservation = booked
    api_client.force_authenticate(user=patient)
    mine = api_client.get("/api/v1/reservations/me")
    assert mine.status_code == 200
    assert [r["id"] for r in mine.json()["results"]] == [str(reservation.pk)]
    assert api_client.get(f"/api/v1/reservations/me/{reservation.pk}").status_code == 200
    api_client.force_authenticate(user=provider.account)
    theirs = api_client.get("/api/v1/reservations/provider")
    assert [r["id"] for r in theirs.json()["results"]] == [str(reservation.pk)]
    assert api_client.get("/api/v1/reservations/provider/availability").status_code == 200


def test_off_still_lets_a_patient_cancel_a_live_booking(api_client, settings, booked):
    _switch(settings, False)
    _, _, patient, _, reservation = booked
    api_client.force_authenticate(user=patient)
    response = api_client.post(
        f"/api/v1/reservations/me/{reservation.pk}/cancel", {"reason": "No longer needed"}
    )
    assert response.status_code == 200, response.json()
    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.CANCELLED


def test_on_restores_booking(api_client, settings, booked):
    _switch(settings, True)
    _, _, patient, free, _ = booked
    api_client.force_authenticate(user=patient)
    response = api_client.post(
        "/api/v1/reservations", {"availability_slot": str(free.pk)}, format="json"
    )
    assert response.status_code == 201, response.json()


def test_off_drops_booking_modules_from_dashboards(api_client, settings, booked):
    _switch(settings, False)
    provider, _, patient, _, _ = booked
    for account in (provider.account, patient):
        api_client.force_authenticate(user=account)
        dash = api_client.get("/api/v1/workspaces/dashboard").json()
        assert dash["header"]["reservations_enabled"] is False
        assert "reservations" not in {m["key"] for m in dash["modules"]}


def test_seeded_history_survives_with_the_switch_off(settings, booked):
    """The services refuse new bookings, but the demo seeder may still write history."""
    from apps.reservations import services

    _switch(settings, False)
    provider, service, patient, free, _ = booked
    with pytest.raises(services.BookingDisabled):
        services.create_reservation(patient=patient, slot_id=free.pk)
    made = services.create_reservation(patient=patient, slot_id=free.pk, enforce_switch=False)
    assert made.status == ReservationStatus.PENDING


def test_off_refuses_accepting_a_pending_booking_but_allows_winding_it_down(
    api_client, settings, booked
):
    _switch(settings, False)
    provider, _, _, _, reservation = booked
    api_client.force_authenticate(user=provider.account)
    url = f"/api/v1/reservations/provider/{reservation.pk}/transition"
    refused = api_client.post(url, {"status": "CONFIRMED"}, format="json")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "service_disabled"
    rejected = api_client.post(url, {"status": "REJECTED", "reason": "Booking closed"})
    assert rejected.status_code == 200, rejected.json()
    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.REJECTED


def test_on_still_lets_a_provider_accept(api_client, settings, booked):
    _switch(settings, True)
    provider, _, _, _, reservation = booked
    api_client.force_authenticate(user=provider.account)
    url = f"/api/v1/reservations/provider/{reservation.pk}/transition"
    assert api_client.post(url, {"status": "CONFIRMED"}, format="json").status_code == 200


def test_off_refuses_facility_team_accepting_a_booking(api_client, settings, account_factory):
    """Same rule in the facility workspace (owner acting for the facility)."""
    from decimal import Decimal

    from apps.geography.models import Governorate
    from apps.providers.models import ProviderProfile, ServiceOffering

    owner = account_factory(role="PROVIDER")
    facility = ProviderProfile.objects.create(
        account=owner,
        provider_type="HOSPITAL",
        display_name="Demo Hospital",
        governorate=Governorate.objects.get(slug="baghdad"),
        verification_status="VERIFIED",
    )
    service = ServiceOffering.objects.create(
        provider=facility, title="Check-up", price=Decimal("10000"), currency="IQD",
        duration_minutes=30,
    )  # fmt: skip
    start = timezone.now() + timedelta(days=3)
    slot = AvailabilitySlot.objects.create(
        provider=facility, service=service, starts_at=start, ends_at=start + timedelta(minutes=30)
    )
    reservation = Reservation.objects.create(
        patient=account_factory(role="PATIENT"), provider=facility, service=service,
        availability_slot=slot, starts_at=slot.starts_at, ends_at=slot.ends_at,
        status=ReservationStatus.PENDING, price_snapshot=service.price,
        currency_snapshot="IQD", duration_minutes_snapshot=30,
    )  # fmt: skip
    _switch(settings, False)
    api_client.force_authenticate(user=owner)
    url = f"/api/v1/workspaces/facility/{facility.pk}/reservations/{reservation.pk}/transition"
    refused = api_client.post(url, {"status": "CONFIRMED"}, format="json")
    assert refused.status_code == 403, refused.json()
    assert refused.json()["error"]["code"] == "service_disabled"
    history = api_client.get(f"/api/v1/workspaces/facility/{facility.pk}/reservations")
    assert history.status_code == 200
