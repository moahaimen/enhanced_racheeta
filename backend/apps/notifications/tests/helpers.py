from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.notifications.models import Notification
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import ProviderType, VerificationStatus
from apps.reservations import services as reservation_services


def make_booking_world(account_factory):
    provider_account = account_factory(role=AccountRole.PROVIDER)
    patient = account_factory(role=AccountRole.PATIENT)
    provider = ProviderProfile.objects.create(
        account=provider_account,
        provider_type=ProviderType.DOCTOR,
        display_name="Dr Notify",
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
    slot = reservation_services.create_availability_slot(
        provider,
        service_id=service.pk,
        starts_at=timezone.now() + timedelta(days=2),
    )
    return provider, provider_account, patient, service, slot


def book(patient, slot, note="private note"):
    return reservation_services.create_reservation(
        patient=patient, slot_id=slot.pk, patient_note=note
    )


def notifications_for(account):
    return list(Notification.objects.filter(recipient=account).order_by("created_at", "id"))
