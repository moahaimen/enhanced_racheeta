from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import ProviderType, VerificationStatus
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus


def make_reservation_world(account_factory):
    provider_account = account_factory(role=AccountRole.PROVIDER, full_name="Dr Chat")
    patient = account_factory(role=AccountRole.PATIENT, full_name="Patient Chat")
    outsider = account_factory(role=AccountRole.PATIENT, full_name="Outsider")
    provider = ProviderProfile.objects.create(
        account=provider_account,
        provider_type=ProviderType.DOCTOR,
        display_name="Dr Chat",
        governorate=Governorate.objects.get(slug="baghdad"),
        verification_status=VerificationStatus.VERIFIED,
    )
    service = ServiceOffering.objects.create(
        provider=provider,
        title="Consultation",
        price=Decimal("25000"),
        currency="IQD",
        duration_minutes=30,
    )
    starts_at = timezone.now() + timedelta(days=2)
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
        status=ReservationStatus.PENDING,
    )
    return provider_account, patient, outsider, reservation
