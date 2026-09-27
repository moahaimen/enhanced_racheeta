from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import ProviderType, VerificationStatus
from apps.reservations import services
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus


def _setup(account_factory):
    provider_account = account_factory(role=AccountRole.PROVIDER)
    patient = account_factory(role=AccountRole.PATIENT)
    governorate = Governorate.objects.get(slug="baghdad")
    provider = ProviderProfile.objects.create(
        account=provider_account,
        provider_type=ProviderType.DOCTOR,
        display_name="Dr Test",
        governorate=governorate,
        verification_status=VerificationStatus.VERIFIED,
    )
    service = ServiceOffering.objects.create(
        provider=provider,
        title="Consultation",
        price=Decimal("25000"),
        currency="IQD",
        duration_minutes=30,
    )
    starts_at = timezone.now() + timedelta(days=1)
    reservation = Reservation.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        provider_name_snapshot=provider.display_name,
        service_title_snapshot=service.title,
        price_snapshot=service.price,
        currency_snapshot=service.currency,
        duration_minutes_snapshot=service.duration_minutes,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=service.duration_minutes),
    )
    return provider, provider_account, patient, reservation


@pytest.mark.django_db
def test_provider_can_confirm_pending_reservation(account_factory):
    provider, provider_account, _, reservation = _setup(account_factory)

    result = services.transition_as_provider(
        reservation.pk,
        provider=provider,
        actor=provider_account,
        target_status=ReservationStatus.CONFIRMED,
    )

    assert result.status == ReservationStatus.CONFIRMED
    transition = result.transitions.get()
    assert transition.from_status == ReservationStatus.PENDING
    assert transition.to_status == ReservationStatus.CONFIRMED
    assert transition.actor_id == provider_account.pk


@pytest.mark.django_db
def test_patient_can_cancel_confirmed_reservation(account_factory):
    provider, provider_account, patient, reservation = _setup(account_factory)
    services.transition_as_provider(
        reservation.pk,
        provider=provider,
        actor=provider_account,
        target_status=ReservationStatus.CONFIRMED,
    )

    result = services.cancel_as_patient(
        reservation.pk,
        patient=patient,
        reason="Cannot attend",
    )

    assert result.status == ReservationStatus.CANCELLED
    assert result.transitions.count() == 2
    assert result.transitions.order_by("created_at").last().reason == "Cannot attend"


@pytest.mark.django_db
def test_provider_cannot_complete_pending_reservation(account_factory):
    provider, provider_account, _, reservation = _setup(account_factory)

    with pytest.raises(services.InvalidTransition):
        services.transition_as_provider(
            reservation.pk,
            provider=provider,
            actor=provider_account,
            target_status=ReservationStatus.COMPLETED,
        )

    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.PENDING
    assert reservation.transitions.count() == 0


@pytest.mark.django_db
def test_foreign_provider_cannot_manage_reservation(account_factory):
    provider, provider_account, _, reservation = _setup(account_factory)
    governorate = Governorate.objects.get(slug="baghdad")
    foreign_account = account_factory(role=AccountRole.PROVIDER)
    foreign_provider = ProviderProfile.objects.create(
        account=foreign_account,
        provider_type=ProviderType.DOCTOR,
        display_name="Other Doctor",
        governorate=governorate,
        verification_status=VerificationStatus.VERIFIED,
    )

    with pytest.raises(services.NotAParty):
        services.transition_as_provider(
            reservation.pk,
            provider=foreign_provider,
            actor=foreign_account,
            target_status=ReservationStatus.CONFIRMED,
        )

    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.PENDING
    assert reservation.transitions.count() == 0


@pytest.mark.django_db
def test_patient_cannot_cancel_someone_elses_reservation(account_factory):
    _, _, _, reservation = _setup(account_factory)
    stranger = account_factory(role=AccountRole.PATIENT)

    with pytest.raises(services.NotAParty):
        services.cancel_as_patient(reservation.pk, patient=stranger)

    reservation.refresh_from_db()
    assert reservation.status == ReservationStatus.PENDING
