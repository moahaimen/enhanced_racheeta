from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import ProviderType, VerificationStatus
from apps.reservations.models import AvailabilitySlot, Reservation
from apps.reservations.types import ReservationStatus


def _provider_and_service(account_factory, *, verified=True):
    account = account_factory(role=AccountRole.PROVIDER)
    governorate = Governorate.objects.get(slug="baghdad")
    provider = ProviderProfile.objects.create(
        account=account,
        provider_type=ProviderType.DOCTOR,
        display_name="Dr Booking",
        governorate=governorate,
        verification_status=(
            VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED
        ),
    )
    service = ServiceOffering.objects.create(
        provider=provider,
        title="Consultation",
        price=Decimal("25000"),
        currency="IQD",
        duration_minutes=30,
    )
    return provider, service


@pytest.mark.django_db
def test_provider_creates_slot_and_public_can_see_it(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    api_client.force_authenticate(user=provider.account)
    starts_at = timezone.now() + timedelta(days=1)

    response = api_client.post(
        "/api/v1/reservations/provider/availability",
        {"service": str(service.pk), "starts_at": starts_at.isoformat()},
        format="json",
    )

    assert response.status_code == 201, response.content
    slot_id = response.json()["id"]

    api_client.force_authenticate(user=None)
    public = api_client.get(f"/api/v1/providers/{provider.pk}/availability")

    assert public.status_code == 200
    assert [row["id"] for row in public.json()] == [slot_id]


@pytest.mark.django_db
def test_overlapping_provider_slots_are_rejected(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    api_client.force_authenticate(user=provider.account)
    starts_at = timezone.now() + timedelta(days=1)

    first = api_client.post(
        "/api/v1/reservations/provider/availability",
        {"service": str(service.pk), "starts_at": starts_at.isoformat()},
        format="json",
    )
    second = api_client.post(
        "/api/v1/reservations/provider/availability",
        {
            "service": str(service.pk),
            "starts_at": (starts_at + timedelta(minutes=15)).isoformat(),
        },
        format="json",
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "slot_conflict"


@pytest.mark.django_db
def test_patient_booking_hides_slot_and_blocks_double_booking(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    patient = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=patient)

    booked = api_client.post(
        "/api/v1/reservations",
        {"availability_slot": str(slot.pk), "patient_note": "First visit"},
        format="json",
    )

    assert booked.status_code == 201, booked.content
    body = booked.json()
    assert body["status"] == ReservationStatus.PENDING
    assert body["provider_name_snapshot"] == provider.display_name
    assert body["service_title_snapshot"] == service.title
    assert len(body["transitions"]) == 1

    other = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=other)
    duplicate = api_client.post(
        "/api/v1/reservations",
        {"availability_slot": str(slot.pk)},
        format="json",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "slot_unavailable"

    api_client.force_authenticate(user=None)
    public = api_client.get(f"/api/v1/providers/{provider.pk}/availability")
    assert public.status_code == 200
    assert public.json() == []


@pytest.mark.django_db
def test_patient_cancel_releases_slot_for_booking(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    patient = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=patient)

    booked = api_client.post(
        "/api/v1/reservations",
        {"availability_slot": str(slot.pk)},
        format="json",
    )
    reservation_id = booked.json()["id"]
    cancelled = api_client.post(
        f"/api/v1/reservations/me/{reservation_id}/cancel",
        {"reason": "Changed plans"},
        format="json",
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == ReservationStatus.CANCELLED

    other = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=other)
    rebooked = api_client.post(
        "/api/v1/reservations",
        {"availability_slot": str(slot.pk)},
        format="json",
    )
    assert rebooked.status_code == 201


@pytest.mark.django_db
def test_provider_lists_and_confirms_received_reservation(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    patient = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=patient)
    booked = api_client.post(
        "/api/v1/reservations",
        {"availability_slot": str(slot.pk)},
        format="json",
    )
    reservation_id = booked.json()["id"]

    api_client.force_authenticate(user=provider.account)
    listing = api_client.get("/api/v1/reservations/provider")
    confirmed = api_client.post(
        f"/api/v1/reservations/provider/{reservation_id}/transition",
        {"status": ReservationStatus.CONFIRMED},
        format="json",
    )

    assert listing.status_code == 200
    assert listing.json()["results"][0]["patient"]["id"] == str(patient.pk)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == ReservationStatus.CONFIRMED


@pytest.mark.django_db
def test_foreign_provider_cannot_manage_reservation(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    patient = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=patient)
    booked = api_client.post(
        "/api/v1/reservations",
        {"availability_slot": str(slot.pk)},
        format="json",
    )

    foreign_provider, _ = _provider_and_service(account_factory)
    api_client.force_authenticate(user=foreign_provider.account)
    response = api_client.post(
        f"/api/v1/reservations/provider/{booked.json()['id']}/transition",
        {"status": ReservationStatus.CONFIRMED},
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unverified_provider_has_no_public_availability(api_client, account_factory):
    provider, service = _provider_and_service(account_factory, verified=False)
    starts_at = timezone.now() + timedelta(days=1)
    AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )

    response = api_client.get(f"/api/v1/providers/{provider.pk}/availability")

    assert response.status_code == 404


@pytest.mark.django_db
def test_provider_cannot_deactivate_booked_slot(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    patient = account_factory(role=AccountRole.PATIENT)
    Reservation.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        availability_slot=slot,
        provider_name_snapshot=provider.display_name,
        service_title_snapshot=service.title,
        price_snapshot=service.price,
        currency_snapshot=service.currency,
        duration_minutes_snapshot=30,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        status=ReservationStatus.PENDING,
    )
    api_client.force_authenticate(user=provider.account)

    response = api_client.delete(f"/api/v1/reservations/provider/availability/{slot.pk}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_unavailable"


@pytest.mark.django_db
def test_public_availability_hides_slot_after_service_duration_changes(api_client, account_factory):
    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    service.duration_minutes = 45
    service.save(update_fields=["duration_minutes", "updated_at"])

    response = api_client.get(f"/api/v1/providers/{provider.pk}/availability")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_public_availability_hides_slot_if_service_moves_to_another_provider(
    api_client, account_factory
):
    provider, service = _provider_and_service(account_factory)
    other, _ = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    service.provider = other
    service.title = "Moved consultation"
    service.save(update_fields=["provider", "title", "updated_at"])

    response = api_client.get(f"/api/v1/providers/{provider.pk}/availability")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_patient_account_delete_is_protected_when_reservation_exists(account_factory):
    from django.db.models.deletion import ProtectedError

    provider, service = _provider_and_service(account_factory)
    starts_at = timezone.now() + timedelta(days=1)
    slot = AvailabilitySlot.objects.create(
        provider=provider,
        service=service,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )
    patient = account_factory(role=AccountRole.PATIENT)
    reservation = Reservation.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        availability_slot=slot,
        provider_name_snapshot=provider.display_name,
        service_title_snapshot=service.title,
        price_snapshot=service.price,
        currency_snapshot=service.currency,
        duration_minutes_snapshot=30,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        status=ReservationStatus.PENDING,
    )

    with pytest.raises(ProtectedError):
        patient.delete()

    assert Reservation.objects.filter(pk=reservation.pk).exists()
    assert AvailabilitySlot.objects.filter(pk=slot.pk).exists()
