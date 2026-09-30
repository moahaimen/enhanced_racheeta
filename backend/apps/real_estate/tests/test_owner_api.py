"""Seller self-service: roles, ownership, onboarding, payload protection,
draft creation and validation, dashboard."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit.models import AuditEvent
from apps.real_estate.models import PropertyListing, RealEstateSeller
from apps.real_estate.types import PublicationStatus, SellerType

from .conftest import (
    OWNER,
    OWNER_LISTINGS,
    PUBLIC_LISTINGS,
    client_for,
    complete_payload,
    create_payload,
)

pytestmark = pytest.mark.django_db

SELLER_PAYLOAD = {"seller_type": "AGENT", "display_name": "Al-Noor Realty"}


def _codes(resp):
    return resp.json()["error"]["codes"]


# ---- access ----


@pytest.mark.parametrize(
    "path",
    [
        OWNER,
        f"{OWNER}/dashboard",
        OWNER_LISTINGS,
        f"{OWNER_LISTINGS}/{'0' * 8}-0000-0000-0000-{'0' * 12}",
    ],
)
def test_anonymous_cannot_use_owner_apis(path):
    from rest_framework.test import APIClient

    assert APIClient().get(path).status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        AccountRole.PATIENT,
        AccountRole.PROVIDER,
        AccountRole.MEDICAL_COMPANY,
    ],
)
def test_other_roles_cannot_use_owner_apis(account_factory, role):
    client = client_for(account_factory(role=role))
    assert client.get(OWNER).status_code == 403
    assert client.post(OWNER, SELLER_PAYLOAD, format="json").status_code == 403
    assert client.get(OWNER_LISTINGS).status_code == 403
    assert client.post(OWNER_LISTINGS, {}, format="json").status_code == 403


def test_listing_apis_need_a_seller_profile_first(account_factory):
    client = client_for(account_factory(role=AccountRole.REAL_ESTATE_SELLER))
    assert client.get(OWNER).status_code == 404  # non-disclosing normal 404
    for path in (f"{OWNER}/dashboard", OWNER_LISTINGS):
        assert client.get(path).status_code == 403


# ---- seller profile ----


def test_onboarding_creates_exactly_one_profile(account_factory):
    account = account_factory(role=AccountRole.REAL_ESTATE_SELLER)
    client = client_for(account)
    created = client.post(OWNER, SELLER_PAYLOAD, format="json")
    assert created.status_code == 201
    body = created.json()
    assert body["seller_type"] == SellerType.AGENT and body["display_name"] == "Al-Noor Realty"
    assert "account" not in body and "email" not in body
    again = client.post(OWNER, SELLER_PAYLOAD, format="json")
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_exists"
    assert RealEstateSeller.objects.filter(account=account).count() == 1
    assert client.get(OWNER).json()["id"] == body["id"]
    assert AuditEvent.objects.filter(action="real_estate.seller.created").count() == 1


def test_profile_needs_type_and_name_and_a_known_type(account_factory):
    client = client_for(account_factory(role=AccountRole.REAL_ESTATE_SELLER))
    assert client.post(OWNER, {}, format="json").status_code == 400
    bad = client.post(OWNER, {"seller_type": "BROKER", "display_name": "X"}, format="json")
    assert bad.status_code == 400 and "seller_type" in bad.json()["error"]["details"]


def test_profile_update_changes_only_editable_fields(seller_factory):
    seller = seller_factory(display_name="Old")
    client = client_for(seller.account)
    resp = client.patch(
        OWNER, {"display_name": "New", "about": "Bio", "phone": "0770"}, format="json"
    )
    assert resp.status_code == 200 and resp.json()["display_name"] == "New"
    seller.refresh_from_db()
    assert (seller.display_name, seller.about, seller.phone) == ("New", "Bio", "0770")
    assert AuditEvent.objects.filter(action="real_estate.seller.updated").count() == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("account", "00000000-0000-0000-0000-000000000000"),
        ("account_id", "00000000-0000-0000-0000-000000000000"),
        ("role", "ADMIN"),
        ("is_staff", True),
        ("is_superuser", True),
        ("created_at", "2020-01-01T00:00:00Z"),
        ("verification_status", "VERIFIED"),
    ],
)
def test_seller_payload_cannot_carry_ownership_or_internal_state(
    seller_factory, account_factory, field, value
):
    seller = seller_factory()
    other = account_factory(role=AccountRole.REAL_ESTATE_SELLER)
    if field in ("account", "account_id"):
        value = str(other.pk)
    resp = client_for(seller.account).patch(OWNER, {field: value}, format="json")
    assert resp.status_code == 400 and _codes(resp)[field] == ["field_not_allowed"]
    seller.refresh_from_db()
    assert seller.account_id != other.pk
    seller.account.refresh_from_db()
    assert seller.account.role == AccountRole.REAL_ESTATE_SELLER and not seller.account.is_staff


# ---- listing creation / validation ----


def test_incomplete_draft_can_be_created(seller_factory, baghdad):
    seller = seller_factory()
    resp = client_for(seller.account).post(OWNER_LISTINGS, create_payload(baghdad), format="json")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["publication_status"] == "DRAFT" and body["published_at"] is None
    assert body["is_public"] is False and body["is_expired"] is False
    assert body["suitable_uses"] == [] and body["area_sqm"] is None and body["price"] is None
    assert AuditEvent.objects.filter(action="real_estate.listing.created").count() == 1


def test_complete_payload_round_trips_with_structured_uses(seller_factory, baghdad, baghdad_city):
    seller = seller_factory()
    payload = complete_payload(
        baghdad, city=str(baghdad_city.pk), latitude="33.3152", longitude="44.3661"
    )
    resp = client_for(seller.account).post(OWNER_LISTINGS, payload, format="json")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["suitable_uses"] == ["CLINIC", "LABORATORY"]
    assert body["city"]["id"] == str(baghdad_city.pk) and body["governorate"]["id"] == str(
        baghdad.pk
    )
    assert body["latitude"] == "33.315200" and body["area_sqm"] == "95.50"
    assert body["contact_method"] == "BOTH" and body["currency"] == "IQD"
    assert seller.listings.get().suitable_uses.count() == 2


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"property_type": "CASTLE"}, "property_type"),
        ({"transaction_type": "LEASE"}, "transaction_type"),
        ({"contact_method": "PIGEON"}, "contact_method"),
        ({"suitable_uses": ["CLINIC", "ZOO"]}, "suitable_uses"),
        ({"currency": "EUR"}, "currency"),
        ({"area_sqm": "0"}, "area_sqm"),
        ({"area_sqm": "-5"}, "area_sqm"),
        ({"price": "-1"}, "price"),
        ({"latitude": "91", "longitude": "10"}, "latitude"),
        ({"latitude": "10", "longitude": "181"}, "longitude"),
        ({"latitude": "10"}, "latitude"),  # only one coordinate
        ({"longitude": "10"}, "latitude"),
        ({"suitable_uses": ["CLINIC", "CLINIC"]}, "suitable_uses"),
        ({"contact_email": "not-an-email"}, "contact_email"),
    ],
)
def test_invalid_values_are_rejected(seller_factory, baghdad, overrides, field):
    resp = client_for(seller_factory().account).post(
        OWNER_LISTINGS, create_payload(baghdad, **overrides), format="json"
    )
    assert resp.status_code == 400 and field in resp.json()["error"]["details"], resp.json()


def test_duplicate_suitable_use_is_a_typed_error(seller_factory, baghdad):
    resp = client_for(seller_factory().account).post(
        OWNER_LISTINGS, create_payload(baghdad, suitable_uses=["CLINIC", "CLINIC"]), format="json"
    )
    assert _codes(resp)["suitable_uses"] == ["duplicate_suitable_use"]


def test_price_null_means_price_on_request_and_zero_is_allowed(seller_factory, baghdad):
    client = client_for(seller_factory().account)
    assert (
        client.post(OWNER_LISTINGS, create_payload(baghdad, price=None), format="json").json()[
            "price"
        ]
        is None
    )
    zero = client.post(OWNER_LISTINGS, create_payload(baghdad, price="0"), format="json")
    assert zero.status_code == 201 and zero.json()["price"] == "0.00"


def test_city_must_belong_to_the_governorate(seller_factory, baghdad, basra_city):
    resp = client_for(seller_factory().account).post(
        OWNER_LISTINGS, create_payload(baghdad, city=str(basra_city.pk)), format="json"
    )
    assert resp.status_code == 400 and "city" in resp.json()["error"]["details"]


def test_patch_cannot_smuggle_a_mismatched_city(seller_factory, listing_factory, basra_city):
    listing = listing_factory(seller_factory())
    resp = client_for(listing.seller.account).patch(
        f"{OWNER_LISTINGS}/{listing.pk}", {"city": str(basra_city.pk)}, format="json"
    )
    assert resp.status_code == 400 and "city" in resp.json()["error"]["details"]


def test_inactive_reference_rows_cannot_be_chosen(seller_factory, baghdad, basra):
    basra.is_active = False
    basra.save()
    resp = client_for(seller_factory().account).post(
        OWNER_LISTINGS, create_payload(basra), format="json"
    )
    assert resp.status_code == 400 and "governorate" in resp.json()["error"]["details"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("seller", "x"),
        ("seller_id", "x"),
        ("owner", "x"),
        ("owner_id", "x"),
        ("account", "x"),
        ("publication_status", "PUBLISHED"),
        ("published_at", "2020-01-01T00:00:00Z"),
        ("is_public", True),
        ("is_expired", False),
        ("created_at", "2020-01-01T00:00:00Z"),
        ("updated_at", "2020-01-01T00:00:00Z"),
        ("audience", ["PROVIDER"]),
        ("targeting", "x"),
        ("featured", True),
        ("is_featured", True),
        ("sponsored", True),
        ("payment", "x"),
        ("campaign", "x"),
        ("images", ["https://x/y.png"]),
        ("image_url", "https://x/y.png"),
    ],
)
def test_listing_payload_cannot_drive_server_state(
    seller_factory, listing_factory, baghdad, field, value
):
    seller = seller_factory()
    client = client_for(seller.account)
    created = client.post(OWNER_LISTINGS, create_payload(baghdad, **{field: value}), format="json")
    assert created.status_code == 400 and _codes(created)[field] == ["field_not_allowed"]
    listing = listing_factory(seller)
    patched = client.patch(f"{OWNER_LISTINGS}/{listing.pk}", {field: value}, format="json")
    assert patched.status_code == 400 and _codes(patched)[field] == ["field_not_allowed"]
    listing.refresh_from_db()
    assert listing.publication_status == PublicationStatus.DRAFT and listing.published_at is None


# ---- ownership ----


def test_a_seller_sees_and_touches_only_their_own_listings(seller_factory, listing_factory):
    mine = listing_factory(seller_factory(), title="Mine")
    theirs = listing_factory(seller_factory(), title="Theirs")
    client = client_for(mine.seller.account)
    assert [r["title"] for r in client.get(OWNER_LISTINGS).json()["results"]] == ["Mine"]
    for method, suffix, body in (
        ("get", "", None),
        ("patch", "", {"title": "Hijacked"}),
        ("post", "/publish", None),
        ("post", "/unpublish", None),
    ):
        resp = getattr(client, method)(f"{OWNER_LISTINGS}/{theirs.pk}{suffix}", body, format="json")
        assert resp.status_code == 404, (method, suffix)
    theirs.refresh_from_db()
    assert theirs.title == "Theirs" and theirs.publication_status == PublicationStatus.DRAFT


def test_there_is_no_delete_endpoint(seller_factory, listing_factory):
    listing = listing_factory(seller_factory())
    assert (
        client_for(listing.seller.account).delete(f"{OWNER_LISTINGS}/{listing.pk}").status_code
        == 405
    )


# ---- updates ----


def test_patch_writes_only_the_sent_fields_and_replaces_uses(seller_factory, listing_factory):
    listing = listing_factory(seller_factory(), uses=["CLINIC", "PHARMACY"])
    client = client_for(listing.seller.account)
    resp = client.patch(
        f"{OWNER_LISTINGS}/{listing.pk}",
        {"title": "Renamed", "suitable_uses": ["LABORATORY"]},
        format="json",
    )
    assert resp.status_code == 200, resp.json()
    assert resp.json()["title"] == "Renamed" and resp.json()["suitable_uses"] == ["LABORATORY"]
    listing.refresh_from_db()
    assert listing.description == "Bright ground floor." and listing.district == "Karrada"
    assert list(listing.suitable_uses.values_list("use", flat=True)) == ["LABORATORY"]
    # omitting suitable_uses leaves them alone
    client.patch(f"{OWNER_LISTINGS}/{listing.pk}", {"district": "Mansour"}, format="json")
    assert list(listing.suitable_uses.values_list("use", flat=True)) == ["LABORATORY"]
    assert AuditEvent.objects.filter(action="real_estate.listing.updated").count() == 2


def test_a_draft_can_be_cleared_of_uses(seller_factory, listing_factory):
    listing = listing_factory(seller_factory())
    resp = client_for(listing.seller.account).patch(
        f"{OWNER_LISTINGS}/{listing.pk}", {"suitable_uses": []}, format="json"
    )
    assert resp.status_code == 200 and resp.json()["suitable_uses"] == []


# ---- listing list / dashboard ----


def test_owner_list_is_paginated_newest_first_and_filterable(seller_factory, listing_factory):
    seller = seller_factory()
    for i in range(23):
        listing_factory(seller, title=f"L{i:02d}")
    listing_factory(seller, title="Live", publication_status=PublicationStatus.PUBLISHED)
    client = client_for(seller.account)
    first = client.get(OWNER_LISTINGS).json()
    assert first["count"] == 24 and len(first["results"]) == 20 and first["next"]
    assert first["results"][0]["title"] == "Live"
    second = client.get(f"{OWNER_LISTINGS}?page=2").json()
    assert len(second["results"]) == 4
    only = client.get(f"{OWNER_LISTINGS}?publication_status=PUBLISHED").json()
    assert [r["title"] for r in only["results"]] == ["Live"]
    assert client.get(f"{OWNER_LISTINGS}?publication_status=BOGUS").status_code == 400


def test_dashboard_counts_are_backend_computed(
    seller_factory, listing_factory, published, account_factory
):
    seller = seller_factory()
    now = timezone.now()
    listing_factory(seller, transaction_type="SALE")
    listing_factory(seller)
    published(seller, transaction_type="SALE")
    expired = published(seller)
    PropertyListing.objects.filter(pk=expired.pk).update(expires_at=now - timedelta(days=1))
    published(seller_factory())  # someone else's listing never counts
    body = client_for(seller.account).get(f"{OWNER}/dashboard").json()
    assert body == {
        "listings_total": 4,
        "listings_draft": 2,
        "listings_published": 2,
        "listings_visible": 1,
        "listings_expired": 1,
        "listings_sale": 2,
        "listings_rent": 2,
    }
    assert (
        client_for(seller.account).get(f"{OWNER_LISTINGS}/{expired.pk}").json()["is_expired"]
        is True
    )


def test_public_catalogue_ignores_drafts_created_here(seller_factory, baghdad):
    client = client_for(seller_factory().account)
    client.post(OWNER_LISTINGS, complete_payload(baghdad), format="json")
    from rest_framework.test import APIClient

    assert APIClient().get(PUBLIC_LISTINGS).json()["count"] == 0


def test_owner_listing_reports_the_current_state_of_its_geography(
    listing_factory, baghdad, baghdad_city, basra
):
    from apps.geography.models import City

    listing = listing_factory(city=baghdad_city)
    client = client_for(listing.seller.account)
    row = client.get(f"{OWNER_LISTINGS}/{listing.pk}").json()
    assert set(row["governorate"]) == {"id", "country", "slug", "name_ar", "name_en", "is_active"}
    assert set(row["city"]) == {"id", "governorate", "slug", "name_ar", "name_en", "is_active"}
    assert row["governorate"]["is_active"] is True and row["city"]["is_active"] is True
    assert row["city"]["governorate"] == str(baghdad.pk)
    # deactivated and moved references are visible to the owner (for recovery), not hidden
    City.objects.filter(pk=baghdad_city.pk).update(is_active=False, governorate=basra)
    baghdad.is_active = False
    baghdad.save()
    row = client.get(f"{OWNER_LISTINGS}/{listing.pk}").json()
    assert row["governorate"]["is_active"] is False and row["city"]["is_active"] is False
    assert row["city"]["governorate"] == str(basra.pk)
    assert client.get(OWNER_LISTINGS).json()["results"][0]["city"]["is_active"] is False


def test_the_public_geography_representation_is_unchanged(published, baghdad_city):
    from rest_framework.test import APIClient

    published(city=baghdad_city)
    row = APIClient().get(PUBLIC_LISTINGS).json()["results"][0]
    assert set(row["governorate"]) == {"id", "country", "slug", "name_ar", "name_en"}
    assert set(row["city"]) == {"id", "governorate", "slug", "name_ar", "name_en"}


def test_owner_endpoints_refuse_an_account_that_lost_the_role(listing_factory):
    from apps.accounts.models import Account

    listing = listing_factory()
    client = client_for(listing.seller.account)
    Account.objects.filter(pk=listing.seller.account_id).update(role=AccountRole.PATIENT)
    assert client.get(OWNER).status_code == 403
    assert client.patch(OWNER, {"about": "x"}, format="json").status_code == 403
