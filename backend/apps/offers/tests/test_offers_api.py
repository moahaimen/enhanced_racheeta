from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.offers.models import Offer
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import ProviderType, VerificationStatus


def _provider(account_factory, *, visible=True):
    account = account_factory(role=AccountRole.PROVIDER)
    provider = ProviderProfile.objects.create(
        account=account,
        provider_type=ProviderType.DOCTOR,
        display_name="Dr Offer",
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


@pytest.mark.django_db
def test_provider_creates_offer_and_public_sees_active_window(api_client, account_factory):
    provider, service = _provider(account_factory)
    api_client.force_authenticate(user=provider.account)
    now = timezone.now()

    created = api_client.post(
        "/api/v1/offers/provider",
        {
            "service": str(service.pk),
            "title": "Consultation offer",
            "description": "Limited time",
            "offer_price": "20000.00",
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
        },
        format="json",
    )

    assert created.status_code == 201, created.content
    offer_id = created.json()["id"]

    api_client.force_authenticate(user=None)
    public = api_client.get(f"/api/v1/providers/{provider.pk}/offers")

    assert public.status_code == 200
    body = public.json()  # the standard paginated envelope, never a raw array
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 1 and [row["id"] for row in body["results"]] == [offer_id]


@pytest.mark.django_db
def test_offer_price_must_be_below_owned_active_service(api_client, account_factory):
    provider, service = _provider(account_factory)
    _, other_service = _provider(account_factory)
    api_client.force_authenticate(user=provider.account)
    now = timezone.now()
    base = {
        "title": "Offer",
        "offer_price": "20000.00",
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(days=1)).isoformat(),
    }

    foreign = api_client.post(
        "/api/v1/offers/provider",
        {**base, "service": str(other_service.pk)},
        format="json",
    )
    expensive = api_client.post(
        "/api/v1/offers/provider",
        {**base, "service": str(service.pk), "offer_price": "25000.00"},
        format="json",
    )

    assert foreign.status_code == 409
    assert expensive.status_code == 400
    assert Offer.objects.count() == 0


@pytest.mark.django_db
def test_expired_inactive_or_hidden_provider_offer_is_not_public(api_client, account_factory):
    provider, service = _provider(account_factory)
    now = timezone.now()
    offer = Offer.objects.create(
        provider=provider,
        service=service,
        service_title_snapshot=service.title,
        title="Offer",
        original_price_snapshot=service.price,
        offer_price=Decimal("20000"),
        currency_snapshot=service.currency,
        starts_at=now - timedelta(days=2),
        ends_at=now - timedelta(days=1),
    )

    assert api_client.get(f"/api/v1/providers/{provider.pk}/offers").json()["count"] == 0

    offer.ends_at = now + timedelta(days=1)
    offer.is_active = False
    offer.save(update_fields=["ends_at", "is_active", "updated_at"])
    assert api_client.get(f"/api/v1/providers/{provider.pk}/offers").json()["count"] == 0

    provider.is_visible = False
    provider.save(update_fields=["is_visible", "updated_at"])
    assert api_client.get(f"/api/v1/providers/{provider.pk}/offers").status_code == 404


@pytest.mark.django_db
def test_provider_can_deactivate_own_offer_but_not_foreign(api_client, account_factory):
    provider, service = _provider(account_factory)
    other, _ = _provider(account_factory)
    now = timezone.now()
    offer = Offer.objects.create(
        provider=provider,
        service=service,
        service_title_snapshot=service.title,
        title="Offer",
        original_price_snapshot=service.price,
        offer_price=Decimal("20000"),
        currency_snapshot=service.currency,
        starts_at=now,
        ends_at=now + timedelta(days=1),
    )

    api_client.force_authenticate(user=other.account)
    foreign = api_client.patch(
        f"/api/v1/offers/provider/{offer.pk}",
        {"is_active": False},
        format="json",
    )
    api_client.force_authenticate(user=provider.account)
    own = api_client.patch(
        f"/api/v1/offers/provider/{offer.pk}",
        {"is_active": False},
        format="json",
    )

    assert foreign.status_code == 404
    assert own.status_code == 200
    offer.refresh_from_db()
    assert offer.is_active is False
