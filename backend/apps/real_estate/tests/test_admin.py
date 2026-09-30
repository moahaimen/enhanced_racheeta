"""Django admin only inspects sellers, listings and uses: it can never become a
second path for ownership or publication."""

import pytest
from django.conf import settings
from django.test import Client

from apps.accounts.models import Account
from apps.real_estate.models import ListingSuitableUse, PropertyListing, RealEstateSeller
from apps.real_estate.types import PublicationStatus

pytestmark = pytest.mark.django_db
BASE = f"/{settings.ADMIN_URL_PATH}real_estate/"


@pytest.fixture
def staff():
    client = Client()
    client.force_login(
        Account.objects.create_superuser(
            email="staff@example.com", password="Str0ng-Passw0rd!", full_name="Staff"
        )
    )
    return client


@pytest.mark.parametrize("model", ["realestateseller", "propertylisting", "listingsuitableuse"])
def test_changelists_are_inspectable_but_not_addable(staff, listing_factory, model):
    listing_factory()
    assert staff.get(f"{BASE}{model}/").status_code == 200
    assert staff.get(f"{BASE}{model}/add/").status_code == 403


def test_a_listing_change_form_is_read_only_and_posts_change_nothing(
    staff, published, account_factory, basra
):
    listing = published()
    url = f"{BASE}propertylisting/{listing.pk}/change/"
    html = staff.get(url).content.decode()
    for field in ("seller", "publication_status", "published_at", "expires_at", "title"):
        assert f'name="{field}"' not in html, field
    resp = staff.post(url, {"title": "Hijacked", "publication_status": "DRAFT"})
    assert resp.status_code == 403
    assert staff.post(f"{url.rsplit('change/', 1)[0]}delete/", {"post": "yes"}).status_code == 403
    fresh = PropertyListing.objects.get(pk=listing.pk)
    assert fresh.title == listing.title and fresh.publication_status == PublicationStatus.PUBLISHED


def test_a_seller_cannot_be_transferred_through_the_admin(staff, seller_factory, account_factory):
    seller = seller_factory()
    other = account_factory()
    url = f"{BASE}realestateseller/{seller.pk}/change/"
    assert 'name="account"' not in staff.get(url).content.decode()
    assert staff.post(url, {"account": str(other.pk), "display_name": "X"}).status_code == 403
    assert RealEstateSeller.objects.get(pk=seller.pk).account_id == seller.account_id


def test_suitable_use_rows_cannot_be_edited_or_removed_in_the_admin(staff, listing_factory):
    row = ListingSuitableUse.objects.get(listing=listing_factory(uses=("CLINIC",)))
    url = f"{BASE}listingsuitableuse/{row.pk}/change/"
    assert staff.post(url, {"use": "PHARMACY"}).status_code == 403
    assert (
        staff.post(f"{BASE}listingsuitableuse/{row.pk}/delete/", {"post": "yes"}).status_code == 403
    )
    assert ListingSuitableUse.objects.get(pk=row.pk).use == "CLINIC"
