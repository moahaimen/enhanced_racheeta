# ruff: noqa: F811  (fixtures re-exported from the marketplace suite)
"""Store/quote fixtures. Reuses the marketplace fixtures (company, provider, category, product)."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.geography.models import City
from apps.marketplace.tests.conftest import (  # noqa: F401  (pytest fixtures)
    admin_client,
    baghdad,
    cardiology,
    category_factory,
    client_for,
    company_factory,
    dentistry,
    product_factory,
    provider_factory,
)
from apps.marketplace.types import BusinessType, SaleChannel


@pytest.fixture
def store_category(category_factory):
    return category_factory(slug="mobility-aids", consumer_allowed=True)


@pytest.fixture
def store(company_factory):
    return company_factory(
        name="Fictional Mobility Store", business_type=BusinessType.ASSISTIVE_DEVICE_STORE
    )


@pytest.fixture
def store_product(store, store_category, product_factory):
    return product_factory(
        store,
        store_category,
        title="Folding wheelchair (demo)",
        price=Decimal("150000.00"),
        sale_channel=SaleChannel.B2C,
        stock_quantity=5,
    )


@pytest.fixture
def buyer(account_factory):
    return account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())


@pytest.fixture
def checkout(baghdad):
    city = City.objects.filter(governorate=baghdad, is_active=True).first()

    def _make(lines, **overrides):
        body = {
            "items": [{"product": str(p.pk), "quantity": q} for p, q in lines],
            "payment_method": "CASH_ON_DELIVERY",
            "governorate": baghdad.pk,
            "city": city.pk if city else None,
            "address": "Street 1, house 2 (demo)",
            "phone": "+964 770 000 0000",
        }
        body.update(overrides)
        return body

    return _make
