from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.real_estate.models import ListingSuitableUse, PropertyListing, RealEstateSeller
from apps.real_estate.types import (
    ContactMethod,
    PropertyType,
    PublicationStatus,
    SellerType,
    SuitableUse,
    TransactionType,
)

OWNER = "/api/v1/real-estate/owner"
OWNER_LISTINGS = f"{OWNER}/listings"
PUBLIC_LISTINGS = "/api/v1/real-estate/listings"


def client_for(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.fixture
def baghdad(db):
    return Governorate.objects.get(slug="baghdad")


@pytest.fixture
def basra(db):
    return Governorate.objects.get(slug="basra")


@pytest.fixture
def baghdad_city(baghdad):
    return baghdad.cities.filter(is_active=True).order_by("slug").first()


@pytest.fixture
def basra_city(basra):
    return basra.cities.filter(is_active=True).order_by("slug").first()


@pytest.fixture
def seller_factory(account_factory):
    counter = {"n": 0}

    def _make(**fields):
        counter["n"] += 1
        account = fields.pop("account", None) or account_factory(
            role=AccountRole.REAL_ESTATE_SELLER
        )
        return RealEstateSeller.objects.create(
            account=account,
            seller_type=fields.pop("seller_type", SellerType.OWNER),
            display_name=fields.pop("display_name", f"Seller {counter['n']}"),
            **fields,
        )

    return _make


@pytest.fixture
def listing_factory(seller_factory, baghdad):
    counter = {"n": 0}

    def _make(seller=None, uses=(SuitableUse.CLINIC,), **fields):
        """A complete, publishable listing; DRAFT unless `publication_status` says otherwise."""
        counter["n"] += 1
        seller = seller or seller_factory()
        status = fields.pop("publication_status", PublicationStatus.DRAFT)
        defaults = {
            "title": f"Listing {counter['n']:03d}",
            "description": "Bright ground floor.",
            "property_type": PropertyType.CLINIC,
            "transaction_type": TransactionType.RENT,
            "governorate": baghdad,
            "district": "Karrada",
            "area_sqm": "120.00",
            "price": "1500000.00",
            "currency": "IQD",
            "facilities": "Parking, lift",
            "contact_method": ContactMethod.PHONE,
            "contact_phone": "07700000000",
            "expires_at": timezone.now() + timedelta(days=30),
        }
        defaults.update(fields)
        if status == PublicationStatus.PUBLISHED:
            defaults.setdefault("published_at", timezone.now())
        listing = PropertyListing.objects.create(
            seller=seller, publication_status=status, **defaults
        )
        for use in uses:
            ListingSuitableUse.objects.create(listing=listing, use=use)
        return listing

    return _make


@pytest.fixture
def published(listing_factory):
    def _make(seller=None, **fields):
        return listing_factory(seller, publication_status=PublicationStatus.PUBLISHED, **fields)

    return _make


@pytest.fixture
def admin_client(db):
    from apps.accounts.models import Account

    admin = Account.objects.create_superuser(
        email="admin@example.com", password="Str0ng-Passw0rd!", full_name="Admin"
    )
    return client_for(admin)


def create_payload(baghdad, **overrides):
    """A valid draft-creation payload."""
    payload = {
        "title": "Ground floor clinic",
        "property_type": PropertyType.CLINIC,
        "transaction_type": TransactionType.RENT,
        "governorate": str(baghdad.pk),
    }
    payload.update(overrides)
    return payload


def complete_payload(baghdad, **overrides):
    """A payload that satisfies the publication gate."""
    expires = (timezone.now() + timedelta(days=45)).isoformat()
    return create_payload(
        baghdad,
        district="Mansour",
        area_sqm="95.50",
        price="900000",
        currency="IQD",
        contact_method=ContactMethod.BOTH,
        contact_phone="07711111111",
        contact_email="agent@example.com",
        expires_at=expires,
        suitable_uses=[SuitableUse.CLINIC, SuitableUse.LABORATORY],
        **overrides,
    )
