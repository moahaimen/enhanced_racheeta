import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.notifications.models import Notification
from apps.preferences import services as prefs
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus
from apps.real_estate.models import ListingPromotion

from .conftest import client_for

pytestmark = pytest.mark.django_db

OWNER = "/api/v1/real-estate/owner/promotions"
ADMIN = "/api/v1/admin/real-estate/promotions"
FEED = "/api/v1/real-estate/promoted"


@pytest.fixture
def provider(account_factory, baghdad):
    def _make(
        provider_type=ProviderType.PHARMACY, opted_in=True, status=VerificationStatus.VERIFIED
    ):
        account = account_factory(role=AccountRole.PROVIDER)
        profile = ProviderProfile.objects.create(
            account=account,
            provider_type=provider_type,
            display_name=f"Demo {provider_type}",
            governorate=baghdad,
            verification_status=status,
        )
        if opted_in:
            prefs.update(account, {"real_estate_promotions": True})
        return profile

    return _make


def _request(seller, listing, types=("PHARMACY",), days=7):
    return client_for(seller.account).post(
        OWNER,
        {"listing": str(listing.pk), "target_provider_types": list(types), "days": days},
        format="json",
    )


def test_full_flow_reaches_only_opted_in_targeted_verified_providers(
    published, admin_client, provider, django_capture_on_commit_callbacks
):
    listing = published()
    seller = listing.seller
    pharmacy = provider()
    opted_out_pharmacy = provider(opted_in=False)
    doctor = provider(provider_type=ProviderType.DOCTOR)
    unverified = provider(status=VerificationStatus.PENDING)

    response = _request(seller, listing)
    assert response.status_code == 201, response.json()
    promotion_id = response.json()["id"]
    assert client_for(pharmacy.account).get(FEED).json()["results"] == []  # not approved yet

    with django_capture_on_commit_callbacks(execute=True):
        approved = admin_client.post(f"{ADMIN}/{promotion_id}/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "ACTIVE"

    feed = client_for(pharmacy.account).get(FEED).json()["results"]
    assert [row["listing"]["id"] for row in feed] == [str(listing.pk)]
    assert feed[0]["sponsored"] is True
    assert client_for(opted_out_pharmacy.account).get(FEED).json()["results"] == []
    assert client_for(doctor.account).get(FEED).json()["results"] == []
    assert client_for(unverified.account).get(FEED).status_code == 403

    recipients = set(
        Notification.objects.filter(event_type="PROPERTY_PROMOTION").values_list(
            "recipient_id", flat=True
        )
    )
    assert recipients == {pharmacy.account_id}


def test_opting_out_hides_the_promotion_at_once(published, admin_client, provider):
    listing = published()
    pharmacy = provider()
    promotion_id = _request(listing.seller, listing).json()["id"]
    admin_client.post(f"{ADMIN}/{promotion_id}/approve")
    assert len(client_for(pharmacy.account).get(FEED).json()["results"]) == 1
    prefs.update(pharmacy.account, {"real_estate_promotions": False})
    assert client_for(pharmacy.account).get(FEED).json()["results"] == []


def test_unpublished_or_expired_listing_drops_out_of_the_feed(published, admin_client, provider):
    listing = published()
    pharmacy = provider()
    promotion_id = _request(listing.seller, listing).json()["id"]
    admin_client.post(f"{ADMIN}/{promotion_id}/approve")
    listing.expires_at = timezone.now()
    listing.save(update_fields=["expires_at"])
    assert client_for(pharmacy.account).get(FEED).json()["results"] == []


def test_request_rules(published, listing_factory, seller_factory):
    listing = published()
    draft = listing_factory(listing.seller)
    other_seller = seller_factory()
    assert _request(listing.seller, draft).status_code == 404  # not public
    assert _request(other_seller, listing).status_code == 404  # not yours
    assert _request(listing.seller, listing, types=("NOT_A_TYPE",)).status_code == 400
    assert _request(listing.seller, listing, days=0).status_code == 400
    assert _request(listing.seller, listing, days=61).status_code == 400
    assert _request(listing.seller, listing).status_code == 201
    assert _request(listing.seller, listing).status_code == 409  # one open promotion per listing


def test_only_admins_decide_and_reject_needs_reason(published, admin_client, provider):
    listing = published()
    promotion_id = _request(listing.seller, listing).json()["id"]
    assert (
        client_for(listing.seller.account).post(f"{ADMIN}/{promotion_id}/approve").status_code
        == 403
    )
    assert client_for(provider().account).get(ADMIN).status_code == 403
    assert (
        admin_client.post(
            f"{ADMIN}/{promotion_id}/reject", {"reason": ""}, format="json"
        ).status_code
        == 400
    )
    rejected = admin_client.post(
        f"{ADMIN}/{promotion_id}/reject", {"reason": "Demo: photos missing"}, format="json"
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    assert admin_client.post(f"{ADMIN}/{promotion_id}/approve").status_code == 400


def test_seller_can_end_only_own_promotion(published, seller_factory, admin_client):
    listing = published()
    promotion_id = _request(listing.seller, listing).json()["id"]
    admin_client.post(f"{ADMIN}/{promotion_id}/approve")
    intruder = seller_factory()
    assert client_for(intruder.account).post(f"{OWNER}/{promotion_id}/end").status_code == 404
    assert client_for(intruder.account).get(OWNER).json()["results"] == []
    ended = client_for(listing.seller.account).post(f"{OWNER}/{promotion_id}/end")
    assert ended.status_code == 200 and ended.json()["status"] == "ENDED"
    assert ListingPromotion.objects.get(pk=promotion_id).ends_at is not None
