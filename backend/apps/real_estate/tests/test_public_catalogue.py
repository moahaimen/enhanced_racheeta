"""The public catalogue: one visibility rule for list and detail, non-disclosing
404s, what the response exposes, filters that only narrow, safe orderings,
stable pagination and bounded queries."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.real_estate.models import PropertyListing
from apps.real_estate.types import ContactMethod, PublicationStatus

from .conftest import PUBLIC_LISTINGS, client_for

pytestmark = pytest.mark.django_db


def _get(query="", client=None):
    return (client or APIClient()).get(f"{PUBLIC_LISTINGS}{query}")


def _titles(resp):
    return [row["title"] for row in resp.json()["results"]]


# ---- visibility ---------------------------------------------------------------------------


def test_publicly_visible_listing_is_listed_and_readable_by_anyone(published, account_factory):
    listing = published()
    for client in (
        APIClient(),
        client_for(account_factory(role=AccountRole.PATIENT)),
        client_for(account_factory(role=AccountRole.PROVIDER)),
        client_for(listing.seller.account),
    ):
        assert _get(client=client).json()["count"] == 1
        assert client.get(f"{PUBLIC_LISTINGS}/{listing.pk}").status_code == 200


def _hide_draft(listing):
    PropertyListing.objects.filter(pk=listing.pk).update(publication_status=PublicationStatus.DRAFT)


def _hide_expired(listing):
    PropertyListing.objects.filter(pk=listing.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )


def _hide_role(listing):
    Account.objects.filter(pk=listing.seller.account_id).update(role=AccountRole.PROVIDER)


def _hide_account(listing):
    Account.objects.filter(pk=listing.seller.account_id).update(is_active=False)


def _hide_governorate(listing):
    listing.governorate.is_active = False
    listing.governorate.save()


def _hide_city(listing):
    listing.city.is_active = False
    listing.city.save()


@pytest.mark.parametrize(
    "hide",
    [_hide_draft, _hide_expired, _hide_role, _hide_account, _hide_governorate, _hide_city],
    ids=lambda f: f.__name__.removeprefix("_hide_"),
)
def test_hidden_listings_are_absent_and_their_detail_is_a_plain_404(published, baghdad_city, hide):
    listing = published(
        title="Secret Title",
        city=baghdad_city,
        contact_phone="07799999999",
        contact_email="secret@example.com",
        contact_method=ContactMethod.BOTH,
        seller=None,
    )
    listing.seller.display_name = "Secret Seller"
    listing.seller.save()
    assert _get().json()["count"] == 1
    hide(listing)
    assert _get().json()["count"] == 0
    resp = APIClient().get(f"{PUBLIC_LISTINGS}/{listing.pk}")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"
    body = resp.content.decode()
    for secret in ("Secret Title", "Secret Seller", "07799999999", "secret@example.com"):
        assert secret not in body
    # indistinguishable from an id that never existed
    unknown = APIClient().get(f"{PUBLIC_LISTINGS}/{uuid.uuid4()}")
    assert unknown.status_code == 404 and unknown.json() == resp.json()


def test_restoring_the_state_restores_exposure(published):
    listing = published()
    _hide_role(listing)
    assert _get().json()["count"] == 0
    Account.objects.filter(pk=listing.seller.account_id).update(role=AccountRole.REAL_ESTATE_SELLER)
    assert _get().json()["count"] == 1


def test_list_and_detail_share_the_same_rule(published):
    live = published()
    dead = published()
    _hide_expired(dead)
    listed = {row["id"] for row in _get().json()["results"]}
    for listing in (live, dead):
        status = APIClient().get(f"{PUBLIC_LISTINGS}/{listing.pk}").status_code
        assert (str(listing.pk) in listed) == (status == 200)


# ---- what is exposed ------------------------------------------------------------------------


def test_public_response_carries_listing_data_and_no_account_identity(published, baghdad_city):
    listing = published(
        city=baghdad_city, latitude="33.3152", longitude="44.3661", uses=["CLINIC", "PHARMACY"]
    )
    row = _get().json()["results"][0]
    assert set(row) == {
        "id", "title", "description", "property_type", "transaction_type", "governorate", "city",
        "district", "latitude", "longitude", "area_sqm", "price", "currency", "suitable_uses",
        "facilities", "contact_method", "contact_phone", "contact_email", "seller", "published_at",
        "expires_at", "created_at", "updated_at",
    }  # fmt: skip
    assert row["suitable_uses"] == ["CLINIC", "PHARMACY"]
    assert row["governorate"]["slug"] == "baghdad" and row["city"]["id"] == str(baghdad_city.pk)
    assert set(row["seller"]) == {"id", "display_name", "seller_type"}
    assert row["seller"]["id"] == str(listing.seller.pk)
    text = str(row)
    assert listing.seller.account.email not in text and str(listing.seller.account_id) not in text


@pytest.mark.parametrize(
    "method,phone,email",
    [
        (ContactMethod.PHONE, "0770", None),
        (ContactMethod.EMAIL, None, "a@b.co"),
        (ContactMethod.BOTH, "0770", "a@b.co"),
    ],
)
def test_only_the_contact_values_the_method_makes_public_are_returned(
    published, method, phone, email
):
    published(contact_method=method, contact_phone="0770", contact_email="a@b.co")
    row = _get().json()["results"][0]
    assert (row["contact_phone"], row["contact_email"]) == (phone, email)


def test_price_on_request_and_coordinates_are_null_not_invented(published):
    published(price=None)
    row = _get().json()["results"][0]
    assert row["price"] is None and row["latitude"] is None and row["longitude"] is None


# ---- filters ---------------------------------------------------------------------------------


SPECS = {
    # name: (title, transaction, property type, price, area, uses, district, extra)
    "clinic_rent": ("Karrada clinic", "RENT", "CLINIC", "1000000", "80", ["CLINIC"], "Karrada", {}),
    "lab_sale": (
        "Lab building", "SALE", "LABORATORY_LOCATION", "250000000", "300",
        ["LABORATORY", "MEDICAL_CENTER"], "Ashar", {},
    ),
    "land_sale": (
        "Investment land", "SALE", "MEDICAL_INVESTMENT_LAND", None, "1500",
        ["MEDICAL_INVESTMENT", "HOSPITAL"], "Zayouna",
        {"description": "Corner plot near the hospital"},
    ),
    "pharmacy_rent": (
        "Pharmacy shop", "RENT", "PHARMACY_LOCATION", "600000", "45", ["PHARMACY"], "Mansour", {},
    ),
    "center_rent": (
        "Medical center floor", "RENT", "MEDICAL_CENTER", "4000000", "500",
        ["MEDICAL_CENTER", "CLINIC"], "Adhamiyah", {},
    ),
}  # fmt: skip


@pytest.fixture
def catalogue(published, seller_factory, basra, baghdad_city):
    """Five published listings that differ along every filter axis, plus hidden
    lookalikes that would match any filter if the queryset were not restricted first."""
    seller = seller_factory()
    rows = {}
    for name, (title, txn, ptype, price, area, uses, district, extra) in SPECS.items():
        fields = {"governorate": basra} if name == "lab_sale" else {}
        if name == "clinic_rent":
            fields["city"] = baghdad_city
        rows[name] = published(
            seller, title=title, transaction_type=txn, property_type=ptype, price=price,
            area_sqm=area, uses=uses, district=district, **fields, **extra,
        )  # fmt: skip
    for name, hide in (("clinic_rent", _hide_draft), ("lab_sale", _hide_expired)):
        source = rows[name]
        twin = published(
            seller,
            title=f"Hidden {name}",
            transaction_type=source.transaction_type,
            property_type=source.property_type,
            price=source.price,
            area_sqm=source.area_sqm,
            governorate=source.governorate,
            district=source.district,
            uses=[u.use for u in source.suitable_uses.all()],
        )
        hide(twin)
    return rows


def _names(catalogue, resp):
    by_id = {str(v.pk): k for k, v in catalogue.items()}
    return {by_id[row["id"]] for row in resp.json()["results"]}


def test_baseline_counts_only_visible_listings(catalogue):
    assert _get().json()["count"] == 5


@pytest.mark.parametrize(
    "query,expected",
    [
        ("?transaction_type=SALE", {"lab_sale", "land_sale"}),
        ("?transaction_type=RENT", {"clinic_rent", "pharmacy_rent", "center_rent"}),
        ("?property_type=CLINIC", {"clinic_rent"}),
        ("?property_type=MEDICAL_CENTER", {"center_rent"}),
        ("?suitable_use=CLINIC", {"clinic_rent", "center_rent"}),
        ("?suitable_use=MEDICAL_CENTER", {"lab_sale", "center_rent"}),
        ("?suitable_use=HOSPITAL", {"land_sale"}),
        ("?suitable_use=GENERAL_MEDICAL_USE", set()),
        ("?min_price=1000000", {"clinic_rent", "lab_sale", "center_rent"}),
        ("?max_price=1000000", {"clinic_rent", "pharmacy_rent"}),
        ("?min_price=600000&max_price=1000000", {"clinic_rent", "pharmacy_rent"}),
        ("?min_area=300", {"lab_sale", "land_sale", "center_rent"}),
        ("?max_area=80", {"clinic_rent", "pharmacy_rent"}),
        ("?min_area=50&max_area=400", {"clinic_rent", "lab_sale"}),
        ("?search=karrada", {"clinic_rent"}),  # title and district
        ("?search=hospital", {"land_sale"}),  # description
        ("?search=ashar", {"lab_sale"}),  # district only
        ("?transaction_type=SALE&suitable_use=MEDICAL_CENTER", {"lab_sale"}),
    ],
)
def test_each_filter_narrows_the_visible_set(catalogue, query, expected):
    resp = _get(query)
    assert resp.status_code == 200
    assert _names(catalogue, resp) == expected


def test_geography_filters(catalogue, baghdad, basra, baghdad_city):
    assert _names(catalogue, _get(f"?governorate={basra.pk}")) == {"lab_sale"}
    assert _names(catalogue, _get(f"?governorate={baghdad.pk}")) == {
        "clinic_rent", "land_sale", "pharmacy_rent", "center_rent",
    }  # fmt: skip
    assert _names(catalogue, _get(f"?city={baghdad_city.pk}")) == {"clinic_rent"}


def test_price_on_request_matches_no_price_range(catalogue):
    assert "land_sale" not in _names(catalogue, _get("?min_price=0"))
    assert "land_sale" not in _names(catalogue, _get("?max_price=999999999999"))


@pytest.mark.parametrize(
    "query",
    [
        "?transaction_type=LEASE",
        "?property_type=CASTLE",
        "?suitable_use=ZOO",
        "?governorate=not-a-uuid",
        "?min_price=abc",
        "?ordering=title",
        "?ordering=seller__account__email",
    ],
)
def test_arbitrary_filter_and_ordering_values_are_rejected(catalogue, query):
    resp = _get(query)
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "validation_error"


def test_filters_cannot_reach_hidden_or_foreign_state(catalogue):
    for param in (
        "publication_status=DRAFT",
        "seller=x",
        "is_public=false",
        "expires_at__lt=2100-01-01",
    ):
        assert _get(f"?{param}").json()["count"] == 5  # unknown parameters are ignored
    assert _get("?search=Hidden").json()["count"] == 0


# ---- ordering and pagination -------------------------------------------------------------------


def test_orderings_are_safe_and_price_on_request_sorts_last(catalogue):
    by = lambda q: [  # noqa: E731
        next(k for k, v in catalogue.items() if str(v.pk) == row["id"])
        for row in _get(q).json()["results"]
    ]
    assert by("?ordering=price") == [
        "pharmacy_rent",
        "clinic_rent",
        "center_rent",
        "lab_sale",
        "land_sale",
    ]
    assert by("?ordering=-price") == [
        "lab_sale",
        "center_rent",
        "clinic_rent",
        "pharmacy_rent",
        "land_sale",
    ]
    assert by("?ordering=area_sqm") == [
        "pharmacy_rent",
        "clinic_rent",
        "lab_sale",
        "center_rent",
        "land_sale",
    ]
    assert by("?ordering=-area_sqm")[0] == "land_sale"
    assert by("") == by("?ordering=-created_at")
    assert by("?ordering=created_at") == list(reversed(by("?ordering=-created_at")))


def test_pagination_is_stable_even_when_the_sort_key_ties(published):
    seller_listing = published()
    for _ in range(24):
        published(seller_listing.seller, price="1000000", area_sqm="100")
    seen: list[str] = []
    for query in ("", "&page=2"):
        for ordering in ("price", "area_sqm"):
            resp = _get(f"?ordering={ordering}{query}")
            assert resp.status_code == 200
    for page in (1, 2):
        seen += [r["id"] for r in _get(f"?ordering=price&page={page}").json()["results"]]
    assert len(seen) == 25 and len(set(seen)) == 25  # no duplicates or gaps across pages
    again = []
    for page in (1, 2):
        again += [r["id"] for r in _get(f"?ordering=price&page={page}").json()["results"]]
    assert seen == again


def test_default_order_is_newest_first_with_an_id_tiebreak(published):
    first = published()
    same_moment = timezone.now()
    ids = [published(first.seller).pk for _ in range(3)]
    PropertyListing.objects.filter(pk__in=ids).update(created_at=same_moment)
    listed = [r["id"] for r in _get().json()["results"]]
    tied = [i for i in listed if uuid.UUID(i) in ids]
    assert tied == sorted(tied)


def test_page_size_is_capped_by_the_shared_pagination(published):
    published()
    assert _get("?page_size=1000").status_code == 200
    assert _get("?page=99").status_code == 404


# ---- queries ------------------------------------------------------------------------------------


def _count_queries(path):
    with CaptureQueriesContext(connection) as ctx:
        assert APIClient().get(path).status_code == 200
    return len(ctx)


def test_list_query_count_does_not_grow_with_the_number_of_listings(published, baghdad_city):
    first = published(city=baghdad_city, uses=["CLINIC", "PHARMACY"])
    few = _count_queries(PUBLIC_LISTINGS)
    for _ in range(12):
        published(first.seller, city=baghdad_city, uses=["CLINIC", "LABORATORY", "HOSPITAL"])
    many = _count_queries(PUBLIC_LISTINGS)
    assert few == many and many <= 4  # count, listings, suitable-use prefetch (+ nothing per row)


def test_detail_query_count_is_bounded(published, baghdad_city):
    listing = published(city=baghdad_city, uses=["CLINIC", "PHARMACY", "HOSPITAL"])
    assert _count_queries(f"{PUBLIC_LISTINGS}/{listing.pk}") <= 3


def test_owner_list_query_count_does_not_grow(listing_factory, seller_factory):
    seller = seller_factory()
    listing_factory(seller)
    client = client_for(seller.account)

    def run():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/api/v1/real-estate/owner/listings").status_code == 200
        return len(ctx)

    few = run()
    for _ in range(10):
        listing_factory(seller, uses=["CLINIC", "PHARMACY"])
    assert run() == few
