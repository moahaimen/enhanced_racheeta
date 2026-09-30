"""Database-level integrity and immutability."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.real_estate.models import ListingSuitableUse, PropertyListing
from apps.real_estate.types import PublicationStatus

pytestmark = pytest.mark.django_db


def _violates(listing_factory, name, **fields):
    listing = listing_factory()
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        PropertyListing.objects.filter(pk=listing.pk).update(**fields)
    assert name in str(exc.value)


@pytest.mark.parametrize(
    "constraint,fields",
    [
        ("real_estate_listing_price_non_negative", {"price": Decimal("-1")}),
        ("real_estate_listing_area_positive", {"area_sqm": Decimal("0")}),
        ("real_estate_listing_area_positive", {"area_sqm": Decimal("-3")}),
        ("real_estate_listing_latitude_range", {"latitude": Decimal("90.5"), "longitude": 1}),
        ("real_estate_listing_latitude_range", {"latitude": Decimal("-91"), "longitude": 1}),
        ("real_estate_listing_longitude_range", {"latitude": 1, "longitude": Decimal("180.1")}),
        ("real_estate_listing_coordinate_pair", {"latitude": Decimal("10"), "longitude": None}),
        ("real_estate_listing_coordinate_pair", {"latitude": None, "longitude": Decimal("10")}),
        (
            "real_estate_listing_published_complete",
            {"publication_status": PublicationStatus.PUBLISHED, "expires_at": None},
        ),
        (
            "real_estate_listing_published_complete",
            {"publication_status": PublicationStatus.PUBLISHED, "area_sqm": None},
        ),
    ],
)
def test_the_database_enforces_the_listing_rules(listing_factory, constraint, fields):
    _violates(listing_factory, constraint, **fields)


def test_boundary_values_are_accepted(listing_factory):
    listing = listing_factory(
        price=Decimal("0"),
        latitude=Decimal("90"),
        longitude=Decimal("-180"),
        area_sqm=Decimal("0.01"),
    )
    assert PropertyListing.objects.get(pk=listing.pk).price == 0


def test_a_draft_may_be_incomplete_at_the_database_level(listing_factory):
    listing = listing_factory(area_sqm=None, expires_at=None, price=None)
    assert listing.publication_status == PublicationStatus.DRAFT


def test_a_listing_cannot_suit_the_same_use_twice(listing_factory):
    listing = listing_factory(uses=("CLINIC",))
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        ListingSuitableUse.objects.create(listing=listing, use="CLINIC")
    assert "real_estate_listing_use_unique" in str(exc.value)
    ListingSuitableUse.objects.create(listing=listing, use="PHARMACY")  # another use is fine


def test_one_seller_profile_per_account(seller_factory):
    seller = seller_factory()
    with pytest.raises(IntegrityError), transaction.atomic():
        seller_factory(account=seller.account)


def test_suitable_use_codes_come_back_in_a_fixed_order(listing_factory):
    listing = listing_factory(uses=("MEDICAL_INVESTMENT", "CLINIC", "HOSPITAL"))
    assert PropertyListing.objects.get(pk=listing.pk).suitable_use_codes == [
        "CLINIC",
        "HOSPITAL",
        "MEDICAL_INVESTMENT",
    ]


def test_a_seller_profile_cannot_be_moved_to_another_account(seller_factory, account_factory):
    seller = seller_factory()
    other = account_factory(role=AccountRole.REAL_ESTATE_SELLER)
    loaded = type(seller).objects.get(pk=seller.pk)
    loaded.account = other
    with pytest.raises(ValueError, match="account_id"):
        loaded.save()
    loaded.refresh_from_db()  # untouched
    assert loaded.account_id == seller.account_id
    loaded = type(seller).objects.get(pk=seller.pk)
    loaded.display_name = "Renamed"
    loaded.save()  # ordinary edits still work


def test_a_listing_cannot_be_moved_to_another_seller(listing_factory, seller_factory):
    listing = listing_factory()
    loaded = PropertyListing.objects.get(pk=listing.pk)
    loaded.seller = seller_factory()
    with pytest.raises(ValueError, match="seller_id"):
        loaded.save()
    assert PropertyListing.objects.get(pk=listing.pk).seller_id == listing.seller_id


def test_public_visibility_queryset_uses_the_supplied_clock(published):
    listing = published(expires_at=timezone.now() + timedelta(days=1))
    assert PropertyListing.objects.publicly_visible().filter(pk=listing.pk).exists()
    later = timezone.now() + timedelta(days=2)
    assert not PropertyListing.objects.publicly_visible(later).filter(pk=listing.pk).exists()
