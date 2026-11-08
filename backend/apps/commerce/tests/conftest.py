# ruff: noqa: F811  (fixtures re-exported from the marketplace suite)
"""Store/quote fixtures. Reuses the marketplace fixtures (company, provider, category, product)."""

import uuid
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
            "idempotency_key": uuid.uuid4().hex,
        }
        body.update(overrides)
        return body

    return _make


def _staff(account_factory):
    """A Racheeta staff (ADMIN role, staff flag) account that is NOT a superuser. The manager
    refuses to create staff through create_user, so the flags are set the way an operator would
    set them in the Django admin."""
    user = account_factory(role=AccountRole.PATIENT)
    type(user).objects.filter(pk=user.pk).update(role=AccountRole.ADMIN, is_staff=True)
    return type(user).objects.get(pk=user.pk)


@pytest.fixture
def finance(account_factory):
    """A Racheeta finance operator: staff WITH the finance permission (not a superuser)."""
    from django.contrib.auth.models import Permission

    user = _staff(account_factory)
    user.user_permissions.add(Permission.objects.get(codename="change_settlementbatch"))
    return type(user).objects.get(pk=user.pk)  # fresh instance: no stale permission cache


@pytest.fixture
def support_staff(account_factory):
    """Racheeta staff WITHOUT the finance permission."""
    return _staff(account_factory)
