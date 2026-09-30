from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.advertising import services
from apps.advertising.models import AdvertisingCampaign, AdvertisingRate
from apps.geography.models import Governorate
from apps.marketplace.models import (
    MedicalCompany,
    Product,
    ProductAudience,
    ProductCategory,
)
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus
from apps.specialties.models import Specialty

COMPANY = "/api/v1/advertising/company"
CAMPAIGNS = f"{COMPANY}/campaigns"
SPONSORED = "/api/v1/advertising/marketplace"
ADMIN = "/api/v1/admin/advertising/campaigns"


def client_for(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


def today():
    return timezone.localdate()


@pytest.fixture
def baghdad(db):
    return Governorate.objects.get(slug="baghdad")


@pytest.fixture
def basra(db):
    return Governorate.objects.get(slug="basra")


@pytest.fixture
def dentistry(db):
    return Specialty.objects.get(slug="dentistry")


@pytest.fixture
def cardiology(db):
    return Specialty.objects.get(slug="cardiology")


@pytest.fixture
def company_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(status=CompanyVerificationStatus.VERIFIED, **fields):
        counter["n"] += 1
        account = fields.pop("account", None) or account_factory(role=AccountRole.MEDICAL_COMPANY)
        return MedicalCompany.objects.create(
            account=account,
            name=fields.pop("name", f"Company {counter['n']}"),
            governorate=baghdad,
            verification_status=status,
            **fields,
        )

    return _make


@pytest.fixture
def category_factory(db):
    counter = {"n": 0}

    def _make(rules=(), is_active=True, **fields):
        """`rules`: iterable of (provider_type or "", specialty or None)."""
        counter["n"] += 1
        category = ProductCategory.objects.create(
            slug=fields.pop("slug", f"category-{counter['n']}"),
            name_ar=f"فئة {counter['n']}",
            name_en=f"Category {counter['n']}",
            is_active=is_active,
            **fields,
        )
        for provider_type, specialty in rules:
            ProductAudience.objects.create(
                category=category, provider_type=provider_type, specialty=specialty
            )
        return category

    return _make


@pytest.fixture
def open_category(category_factory):
    """A category open to every provider type (rule: doctors, laboratories, ...)."""
    return category_factory(
        rules=[
            (t, None) for t in (ProviderType.DOCTOR, ProviderType.LABORATORY, ProviderType.PHARMACY)
        ]
    )


@pytest.fixture
def product_factory(db):
    counter = {"n": 0}

    def _make(company, category, is_active=True, **fields):
        counter["n"] += 1
        return Product.objects.create(
            company=company,
            category=category,
            title=fields.pop("title", f"Product {counter['n']}"),
            is_active=is_active,
            **fields,
        )

    return _make


@pytest.fixture
def provider_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(
        provider_type=ProviderType.DOCTOR,
        specialties=(),
        verification_status=VerificationStatus.VERIFIED,
        governorate=None,
        **fields,
    ):
        counter["n"] += 1
        account = fields.pop("account", None) or account_factory(role=AccountRole.PROVIDER)
        profile = ProviderProfile.objects.create(
            account=account,
            provider_type=provider_type,
            display_name=f"Provider {counter['n']:03d}",
            governorate=governorate or baghdad,
            verification_status=verification_status,
            **fields,
        )
        if specialties:
            profile.specialties.set(specialties)
        return profile

    return _make


@pytest.fixture
def rate(db):
    """An active rate of 1000 IQD/day. (Never seeded by a migration: tests create it.)"""
    return AdvertisingRate.objects.create(
        code="standard",
        name_ar="السعر القياسي",
        name_en="Standard",
        price_per_day=Decimal("1000.00"),
        currency="IQD",
        is_active=True,
    )


@pytest.fixture
def ready(company_factory, open_category, product_factory):
    """(company, product) — a verified company with an exposable product."""
    company = company_factory()
    return company, product_factory(company, open_category)


@pytest.fixture
def campaign_factory(db):
    counter = {"n": 0}

    def _make(company, product, **fields):
        counter["n"] += 1
        if (
            fields.get("status", "DRAFT") != "DRAFT"
        ):  # a submitted campaign always carries its quote
            fields.setdefault("quoted_days", 10)
            fields.setdefault("quoted_daily_rate", Decimal("1000.00"))
            fields.setdefault("quoted_amount", Decimal("10000.00"))
            fields.setdefault("quoted_currency", "IQD")
            fields.setdefault("quoted_at", timezone.now())
        return AdvertisingCampaign.objects.create(
            company=company,
            product=product,
            name=fields.pop("name", f"Campaign {counter['n']}"),
            starts_on=fields.pop("starts_on", today()),
            ends_on=fields.pop("ends_on", today() + timedelta(days=9)),
            **fields,
        )

    return _make


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import Account

    return Account.objects.create_superuser(
        email="admin@example.com", password="Str0ng-Passw0rd!", full_name="Admin"
    )


@pytest.fixture
def admin_client(admin_user):
    return client_for(admin_user)


@pytest.fixture
def live_campaign(ready, rate, campaign_factory, admin_user):
    """An ACTIVE, verified-payment campaign that is date-live today, no narrowing."""
    company, product = ready
    campaign = campaign_factory(company, product)
    services.submit_campaign(company, campaign.pk)
    services.verify_campaign_payment(
        campaign.pk, method="BANK_TRANSFER", reference="REF-1", verified_by=admin_user
    )
    return AdvertisingCampaign.objects.get(pk=campaign.pk)


def draft_payload(product, **overrides):
    payload = {
        "name": "Spring push",
        "product": str(product.pk),
        "starts_on": str(today() + timedelta(days=1)),
        "ends_on": str(today() + timedelta(days=10)),
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def make_live(db):
    """Turn a draft into an ACTIVE campaign with a VERIFIED payment directly (fast
    setup for visibility tests; the real transitions are covered elsewhere)."""
    from apps.advertising.models import CampaignPayment

    def _make(campaign, **payment_fields):
        AdvertisingCampaign.objects.filter(pk=campaign.pk).update(
            status="ACTIVE",
            quoted_days=10,
            quoted_daily_rate=Decimal("1000.00"),
            quoted_amount=Decimal("10000.00"),
            quoted_currency="IQD",
            quoted_at=timezone.now(),
        )
        fields = {
            "amount": Decimal("10000.00"),
            "currency": "IQD",
            "status": "VERIFIED",
            "method": "CASH",
            "verified_at": timezone.now(),
        }
        fields.update(payment_fields)
        CampaignPayment.objects.create(campaign=campaign, **fields)
        return AdvertisingCampaign.objects.get(pk=campaign.pk)

    return _make
