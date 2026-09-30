"""Publication: the one authoritative gate, unpublish, expiry evaluated at read
time, seller role/state loss, and the re-validation of edits to PUBLISHED listings."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.audit.models import AuditEvent
from apps.real_estate import services
from apps.real_estate.models import PropertyListing
from apps.real_estate.types import ContactMethod, PublicationStatus

from .conftest import OWNER_LISTINGS, PUBLIC_LISTINGS, client_for

pytestmark = pytest.mark.django_db


def _publish(listing):
    return client_for(listing.seller.account).post(f"{OWNER_LISTINGS}/{listing.pk}/publish")


def _public_count():
    return APIClient().get(PUBLIC_LISTINGS).json()["count"]


def _codes(resp):
    return resp.json()["error"]["codes"]


def test_publishing_a_complete_listing_makes_it_public(listing_factory):
    listing = listing_factory()
    before = timezone.now()
    resp = _publish(listing)
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["publication_status"] == "PUBLISHED" and body["is_public"] is True
    assert body["published_at"] is not None
    listing.refresh_from_db()
    assert listing.published_at >= before  # server-owned
    assert _public_count() == 1
    assert AuditEvent.objects.filter(action="real_estate.listing.published").count() == 1


def test_publishing_twice_and_unpublishing_a_draft_are_typed_errors(listing_factory):
    listing = listing_factory()
    assert _publish(listing).status_code == 200
    again = _publish(listing)
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_transition"
    other = listing_factory()
    resp = client_for(other.seller.account).post(f"{OWNER_LISTINGS}/{other.pk}/unpublish")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_transition"


def test_unpublish_removes_exposure_immediately_and_returns_to_draft(published):
    listing = published()
    assert _public_count() == 1
    resp = client_for(listing.seller.account).post(f"{OWNER_LISTINGS}/{listing.pk}/unpublish")
    assert resp.status_code == 200 and resp.json()["publication_status"] == "DRAFT"
    assert resp.json()["is_public"] is False
    assert _public_count() == 0
    assert AuditEvent.objects.filter(action="real_estate.listing.unpublished").count() == 1
    # re-publishing stamps a new server time
    first = listing.published_at
    assert _publish(listing).status_code == 200
    listing.refresh_from_db()
    assert listing.published_at > first


# ---- the gate ----


@pytest.mark.parametrize(
    "changes,field,code",
    [
        ({"expires_at": None}, "expires_at", "expiry_required"),
        ({"expires_at": timezone.now() - timedelta(minutes=1)}, "expires_at", "expiry_in_past"),
        ({"area_sqm": None}, "area_sqm", "area_required"),
        ({"title": "   "}, "title", "title_required"),
        (
            {"contact_method": ContactMethod.PHONE, "contact_phone": ""},
            "contact_phone",
            "contact_phone_required",
        ),
        (
            {"contact_method": ContactMethod.EMAIL, "contact_email": ""},
            "contact_email",
            "contact_email_required",
        ),
        (
            {"contact_method": ContactMethod.BOTH, "contact_phone": "0770", "contact_email": ""},
            "contact_email",
            "contact_email_required",
        ),
        (
            {"contact_method": ContactMethod.BOTH, "contact_phone": "", "contact_email": "a@b.co"},
            "contact_phone",
            "contact_phone_required",
        ),
    ],
)
def test_publication_fails_on_each_missing_requirement(listing_factory, changes, field, code):
    listing = listing_factory(**changes)
    resp = _publish(listing)
    assert resp.status_code == 400, resp.json()
    assert _codes(resp)[field] == [code]
    listing.refresh_from_db()
    assert listing.publication_status == PublicationStatus.DRAFT and listing.published_at is None
    assert _public_count() == 0


def test_publication_fails_without_a_suitable_use(listing_factory):
    listing = listing_factory(uses=())
    resp = _publish(listing)
    assert resp.status_code == 400 and _codes(resp)["suitable_uses"] == ["suitable_use_required"]


def test_publication_reports_every_problem_at_once(listing_factory):
    listing = listing_factory(uses=(), area_sqm=None, expires_at=None)
    assert set(_codes(_publish(listing))) == {"suitable_uses", "area_sqm", "expires_at"}


def test_an_incomplete_draft_exists_but_is_never_public(listing_factory):
    listing_factory(uses=(), area_sqm=None, expires_at=None)
    assert _public_count() == 0


def test_publication_fails_when_the_governorate_was_deactivated(listing_factory, baghdad):
    listing = listing_factory()
    baghdad.is_active = False
    baghdad.save()
    resp = _publish(listing)
    assert resp.status_code == 400 and _codes(resp)["governorate"] == ["geography_inactive"]


def test_publication_fails_when_the_city_was_deactivated(listing_factory, baghdad_city):
    listing = listing_factory(city=baghdad_city)
    baghdad_city.is_active = False
    baghdad_city.save()
    resp = _publish(listing)
    assert resp.status_code == 400 and _codes(resp)["city"] == ["city_inactive"]


def test_publication_succeeds_with_an_active_city(listing_factory, baghdad_city):
    assert _publish(listing_factory(city=baghdad_city)).status_code == 200


def test_publication_fails_for_a_city_of_another_governorate(listing_factory, basra_city):
    listing = listing_factory()
    PropertyListing.objects.filter(pk=listing.pk).update(city=basra_city)  # bypasses the API
    resp = _publish(listing)
    assert resp.status_code == 400 and _codes(resp)["city"] == ["city_mismatch"]


def test_publication_fails_on_state_the_api_would_never_store(listing_factory):
    listing = listing_factory()
    PropertyListing.objects.filter(pk=listing.pk).update(currency="EUR")
    assert _codes(_publish(listing))["currency"] == ["currency_unsupported"]


# ---- seller state ----


@pytest.mark.parametrize(
    "role", [AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.MEDICAL_COMPANY]
)
def test_role_loss_blocks_publication_and_hides_the_seller(listing_factory, published, role):
    draft = listing_factory()
    live = published(draft.seller)
    assert _public_count() == 1
    Account.objects.filter(pk=draft.seller.account_id).update(role=role)
    assert _public_count() == 0  # exposure ends at once, nothing was touched
    # the seller can no longer use the owner APIs at all (permission) …
    assert _publish(draft).status_code == 403
    # … and the service refuses on the CURRENT account state
    with pytest.raises(services.SellerNotEligible):
        services.publish_listing(draft.seller, draft.pk)
    draft.refresh_from_db()
    assert draft.publication_status == PublicationStatus.DRAFT
    # restoring the role restores exposure
    Account.objects.filter(pk=draft.seller.account_id).update(role=AccountRole.REAL_ESTATE_SELLER)
    assert _public_count() == 1
    assert live.pk


def test_inactive_account_blocks_publication(listing_factory):
    listing = listing_factory()
    Account.objects.filter(pk=listing.seller.account_id).update(is_active=False)
    with pytest.raises(services.SellerNotEligible):
        services.publish_listing(listing.seller, listing.pk)


def test_unpublish_stays_possible_after_role_loss(published):
    listing = published()
    Account.objects.filter(pk=listing.seller.account_id).update(role=AccountRole.PATIENT)
    services.unpublish_listing(listing.seller, listing.pk)
    listing.refresh_from_db()
    assert listing.publication_status == PublicationStatus.DRAFT


# ---- expiry (evaluated at read time; no scheduler) ----


def test_a_listing_disappears_when_server_time_passes_its_expiry(published):
    listing = published(expires_at=timezone.now() + timedelta(days=1))
    detail = f"{PUBLIC_LISTINGS}/{listing.pk}"
    assert _public_count() == 1 and APIClient().get(detail).status_code == 200
    # time passes: no worker ran, the stored row is still PUBLISHED
    PropertyListing.objects.filter(pk=listing.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    listing.refresh_from_db()
    assert listing.publication_status == PublicationStatus.PUBLISHED
    assert _public_count() == 0 and APIClient().get(detail).status_code == 404
    assert (
        client_for(listing.seller.account)
        .get(f"{OWNER_LISTINGS}/{listing.pk}")
        .json()["is_expired"]
        is True
    )


def test_expiry_boundary_is_exclusive(published):
    listing = published()
    now = timezone.now()
    PropertyListing.objects.filter(pk=listing.pk).update(expires_at=now)
    assert not PropertyListing.objects.publicly_visible(now).filter(pk=listing.pk).exists()
    assert (
        PropertyListing.objects.publicly_visible(now - timedelta(microseconds=1))
        .filter(pk=listing.pk)
        .exists()
    )


# ---- editing a PUBLISHED listing re-runs the gate ----


def test_editing_a_published_listing_revalidates_the_resulting_state(published):
    listing = published()
    client = client_for(listing.seller.account)
    url = f"{OWNER_LISTINGS}/{listing.pk}"
    ok = client.patch(url, {"title": "Better title", "price": "2000000"}, format="json")
    assert ok.status_code == 200 and ok.json()["publication_status"] == "PUBLISHED"
    for changes, field in (
        ({"expires_at": None}, "expires_at"),
        ({"expires_at": (timezone.now() - timedelta(days=1)).isoformat()}, "expires_at"),
        ({"area_sqm": None}, "area_sqm"),
        ({"suitable_uses": []}, "suitable_uses"),
        ({"contact_phone": ""}, "contact_phone"),
        ({"title": ""}, "title"),
    ):
        resp = client.patch(url, changes, format="json")
        assert resp.status_code == 400 and field in resp.json()["error"]["details"], (
            changes,
            resp.json(),
        )
    listing.refresh_from_db()
    assert listing.title == "Better title" and listing.area_sqm and listing.contact_phone
    assert listing.suitable_uses.count() == 1  # the refused edit did not touch children
    assert _public_count() == 1


def test_a_published_listing_can_be_extended_with_a_valid_update(published):
    listing = published()
    PropertyListing.objects.filter(pk=listing.pk).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    client = client_for(listing.seller.account)
    url = f"{OWNER_LISTINGS}/{listing.pk}"
    # an edit that leaves it expired is refused …
    assert client.patch(url, {"title": "x"}, format="json").status_code == 400
    # … extending it in the same update is accepted and it is public again
    new = (timezone.now() + timedelta(days=60)).isoformat()
    resp = client.patch(url, {"expires_at": new}, format="json")
    assert (
        resp.status_code == 200
        and resp.json()["is_public"] is True
        and resp.json()["is_expired"] is False
    )
    assert _public_count() == 1


def test_a_published_edit_after_role_loss_is_refused_by_the_service(published):
    listing = published()
    Account.objects.filter(pk=listing.seller.account_id).update(role=AccountRole.PATIENT)
    with pytest.raises(services.SellerNotEligible):
        services.update_listing(listing.seller, listing.pk, {"title": "Sneaky"})
    listing.refresh_from_db()
    assert listing.title != "Sneaky"


def test_editing_a_draft_never_publishes_it(listing_factory):
    listing = listing_factory()
    resp = client_for(listing.seller.account).patch(
        f"{OWNER_LISTINGS}/{listing.pk}", {"title": "Edited"}, format="json"
    )
    assert resp.status_code == 200 and resp.json()["publication_status"] == "DRAFT"
    assert _public_count() == 0
