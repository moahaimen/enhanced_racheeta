from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import ProviderType, VerificationStatus
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus
from apps.reviews.models import Review


def _provider(account_factory, *, visible=True):
    account = account_factory(role=AccountRole.PROVIDER)
    provider = ProviderProfile.objects.create(
        account=account,
        provider_type=ProviderType.DOCTOR,
        display_name="Dr Review",
        governorate=Governorate.objects.get(slug="baghdad"),
        verification_status=VerificationStatus.VERIFIED,
        is_visible=visible,
    )
    service = ServiceOffering.objects.create(
        provider=provider,
        title="Consultation",
        price=Decimal("25000"),
        currency="IQD",
        duration_minutes=30,
    )
    return provider, service


def _reservation(account_factory, provider, service, *, status=ReservationStatus.COMPLETED):
    patient = account_factory(role=AccountRole.PATIENT)
    starts_at = timezone.now() - timedelta(days=1)
    reservation = Reservation.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        provider_name_snapshot=provider.display_name,
        service_title_snapshot=service.title,
        price_snapshot=service.price,
        currency_snapshot=service.currency,
        duration_minutes_snapshot=30,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
    )
    return patient, reservation


@pytest.mark.django_db
def test_completed_reservation_can_be_reviewed_once(api_client, account_factory):
    provider, service = _provider(account_factory)
    patient, reservation = _reservation(account_factory, provider, service)
    api_client.force_authenticate(user=patient)

    created = api_client.post(
        "/api/v1/reviews",
        {"reservation": str(reservation.pk), "rating": 5, "comment": "Excellent"},
        format="json",
    )
    duplicate = api_client.post(
        "/api/v1/reviews",
        {"reservation": str(reservation.pk), "rating": 4},
        format="json",
    )

    assert created.status_code == 201, created.content
    assert created.json()["rating"] == 5
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_reviewed"
    assert Review.objects.filter(reservation=reservation).count() == 1

    mine = api_client.get("/api/v1/reservations/me")
    assert mine.status_code == 200
    assert mine.json()["results"][0]["review_id"] == created.json()["id"]


@pytest.mark.django_db
def test_non_completed_or_foreign_reservation_cannot_be_reviewed(api_client, account_factory):
    provider, service = _provider(account_factory)
    patient, pending = _reservation(
        account_factory, provider, service, status=ReservationStatus.CONFIRMED
    )
    other = account_factory(role=AccountRole.PATIENT)
    api_client.force_authenticate(user=patient)

    pending_response = api_client.post(
        "/api/v1/reviews",
        {"reservation": str(pending.pk), "rating": 5},
        format="json",
    )
    api_client.force_authenticate(user=other)
    foreign_response = api_client.post(
        "/api/v1/reviews",
        {"reservation": str(pending.pk), "rating": 5},
        format="json",
    )

    assert pending_response.status_code == 409
    assert foreign_response.status_code == 409
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_public_reviews_and_rating_summary_require_discoverable_provider(
    api_client, account_factory
):
    provider, service = _provider(account_factory)
    patient, reservation = _reservation(account_factory, provider, service)
    Review.objects.create(
        reservation=reservation,
        patient=patient,
        provider=provider,
        provider_name_snapshot=provider.display_name,
        service_title_snapshot=service.title,
        rating=4,
        comment="Good",
    )

    reviews = api_client.get(f"/api/v1/providers/{provider.pk}/reviews")
    detail = api_client.get(f"/api/v1/providers/{provider.pk}")

    assert reviews.status_code == 200
    assert reviews.json()["count"] == 1
    assert reviews.json()["results"][0]["rating"] == 4
    assert "patient" not in reviews.json()["results"][0]
    assert detail.status_code == 200
    assert detail.json()["average_rating"] == 4.0
    assert detail.json()["review_count"] == 1

    provider.is_visible = False
    provider.save(update_fields=["is_visible", "updated_at"])
    assert api_client.get(f"/api/v1/providers/{provider.pk}/reviews").status_code == 404
