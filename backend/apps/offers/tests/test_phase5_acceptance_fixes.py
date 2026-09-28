"""Phase 5 acceptance review (commit a387bc7): offers may only be (re)activated
on a currently valid service, the public offer list is paginated, and a
historical offer whose service was deleted stays readable by its owner."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.offers import services
from apps.offers.models import Offer
from apps.offers.tests.test_offers_api import _provider
from apps.providers.models import ServiceOffering

pytestmark = pytest.mark.django_db
MY = "/api/v1/offers/provider"


def _offer(provider, service, **overrides):
    now = timezone.now()
    fields = {
        "provider": provider,
        "service": service,
        "service_title_snapshot": service.title,
        "title": "Offer",
        "original_price_snapshot": service.price,
        "offer_price": Decimal("20000"),
        "currency_snapshot": service.currency,
        "starts_at": now - timedelta(hours=1),
        "ends_at": now + timedelta(days=1),
        "is_active": False,
    }
    fields.update(overrides)
    return Offer.objects.create(**fields)


def _patch(api_client, provider, offer, payload):
    api_client.force_authenticate(user=provider.account)
    return api_client.patch(f"{MY}/{offer.pk}", payload, format="json")


def _snapshot(offer):
    offer.refresh_from_db()
    return {
        f: getattr(offer, f)
        for f in (
            "title",
            "description",
            "offer_price",
            "starts_at",
            "ends_at",
            "is_active",
            "service_id",
        )
    }


# ---- P2 #1: (re)activation requires a currently valid service ---------------------------------


def test_activation_on_an_active_owned_service_succeeds(api_client, account_factory):
    provider, service = _provider(account_factory)
    offer = _offer(provider, service)
    resp = _patch(api_client, provider, offer, {"is_active": True, "title": "Back on"})
    assert resp.status_code == 200 and resp.json()["is_active"] is True
    assert _snapshot(offer)["title"] == "Back on"


@pytest.mark.parametrize("how", ["inactive", "deleted", "foreign"])
def test_activation_on_a_stale_service_is_refused_and_changes_nothing(
    api_client, account_factory, how
):
    provider, service = _provider(account_factory)
    offer = _offer(provider, service)
    if how == "inactive":
        service.is_active = False
        service.save(update_fields=["is_active", "updated_at"])
    elif how == "deleted":
        service.delete()  # SET_NULL: the offer keeps its snapshots
    else:
        _, foreign = _provider(account_factory)
        Offer.objects.filter(pk=offer.pk).update(service=foreign)  # never reachable via the API
    before = _snapshot(offer)
    resp = _patch(api_client, provider, offer, {"is_active": True, "title": "Should not stick"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "service_unavailable"
    assert _snapshot(offer) == before  # nothing partially applied
    from apps.audit.models import AuditEvent

    assert not AuditEvent.objects.filter(action="offer.updated", target_id=str(offer.pk)).exists()


@pytest.mark.parametrize("how", ["inactive", "deleted"])
def test_a_stale_offer_can_still_be_deactivated_and_stays_as_history(
    api_client, account_factory, how
):
    provider, service = _provider(account_factory)
    offer = _offer(provider, service, is_active=True)
    if how == "inactive":
        service.is_active = False
        service.save(update_fields=["is_active", "updated_at"])
    else:
        service.delete()
    resp = _patch(api_client, provider, offer, {"is_active": False})
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    api_client.force_authenticate(user=provider.account)
    listed = api_client.get(MY).json()
    assert str(offer.pk) in {row["id"] for row in listed["results"]}  # history is kept
    row = next(r for r in listed["results"] if r["id"] == str(offer.pk))
    assert row["service_title_snapshot"] == "Consultation"
    assert row["service_id"] == (None if how == "deleted" else str(service.pk))


def test_existing_price_and_window_validation_is_intact(api_client, account_factory):
    provider, service = _provider(account_factory)
    offer = _offer(provider, service)
    now = timezone.now()
    assert (
        _patch(
            api_client, provider, offer, {"is_active": True, "offer_price": "25000.00"}
        ).status_code
        == 400
    )
    assert (
        _patch(
            api_client,
            provider,
            offer,
            {"is_active": True, "ends_at": (now - timedelta(hours=1)).isoformat()},
        ).status_code
        == 400
    )
    assert _snapshot(offer)["is_active"] is False


def test_create_and_update_share_one_definition_of_a_valid_service(account_factory):
    provider, service = _provider(account_factory)
    service.is_active = False
    service.save(update_fields=["is_active", "updated_at"])
    now = timezone.now()
    with pytest.raises(services.ServiceUnavailable):
        services.create_offer(
            provider,
            service_id=service.pk,
            title="x",
            description="",
            offer_price=Decimal("1"),
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )
    offer = _offer(provider, service)
    with pytest.raises(services.ServiceUnavailable):
        services.update_offer(provider, offer_id=offer.pk, changes={"is_active": True})


# ---- P2 #2: the public list is paginated -------------------------------------------------------


def test_public_offers_are_paginated_and_all_reachable(api_client, account_factory):
    provider, service = _provider(account_factory)
    now = timezone.now()
    ids = [
        str(
            _offer(
                provider,
                service,
                is_active=True,
                title=f"Offer {i}",
                ends_at=now + timedelta(days=i + 1),
            ).pk
        )
        for i in range(23)
    ]
    # noise that must not inflate the count
    _offer(provider, service, is_active=False, title="inactive")
    _offer(
        provider,
        service,
        is_active=True,
        title="expired",
        starts_at=now - timedelta(days=3),
        ends_at=now - timedelta(days=1),
    )
    _offer(
        provider,
        service,
        is_active=True,
        title="future",
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=2),
    )
    stale_service = ServiceOffering.objects.create(
        provider=provider,
        title="Old",
        price=Decimal("30000"),
        currency="IQD",
        duration_minutes=30,
        is_active=False,
    )
    _offer(provider, stale_service, is_active=True, title="stale service")

    url = f"/api/v1/providers/{provider.pk}/offers"
    first = api_client.get(url).json()
    assert first["count"] == 23 and len(first["results"]) == 20
    assert first["previous"] is None and first["next"] is not None
    second = api_client.get(url, {"page": 2}).json()
    assert len(second["results"]) == 3 and second["next"] is None and second["previous"] is not None
    seen = [row["id"] for row in first["results"]] + [row["id"] for row in second["results"]]
    assert seen == ids  # ends_at ascending, every current offer reachable exactly once
    assert api_client.get(url, {"page": 3}).status_code == 404


def test_hidden_provider_offers_stay_inaccessible(api_client, account_factory):
    provider, service = _provider(account_factory, visible=False)
    _offer(provider, service, is_active=True)
    assert api_client.get(f"/api/v1/providers/{provider.pk}/offers").status_code == 404


# ---- P2 #5: owner still reads a historical offer whose service was deleted --------------------


def test_owner_reads_an_offer_whose_service_was_deleted(api_client, account_factory):
    provider, service = _provider(account_factory)
    offer = _offer(provider, service, is_active=True)
    service.delete()
    api_client.force_authenticate(user=provider.account)
    rows = api_client.get(MY).json()["results"]
    row = next(r for r in rows if r["id"] == str(offer.pk))
    assert row["service_id"] is None and row["service_title_snapshot"] == "Consultation"
    assert (
        api_client.get(f"/api/v1/providers/{provider.pk}/offers").json()["count"] == 0
    )  # not public
