import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.marketplace.models import MedicalCompany, Product, ProductAudience, ProductCategory
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus
from apps.specialties.models import Specialty


@pytest.fixture
def baghdad(db):
    return Governorate.objects.get(slug="baghdad")


@pytest.fixture
def dentistry(db):
    return Specialty.objects.get(slug="dentistry")


@pytest.fixture
def cardiology(db):
    return Specialty.objects.get(slug="cardiology")


def client_for(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


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
def provider_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(
        provider_type=ProviderType.DOCTOR,
        specialties=(),
        verification_status=VerificationStatus.VERIFIED,
        is_visible=True,
    ):
        counter["n"] += 1
        profile = ProviderProfile.objects.create(
            account=account_factory(role=AccountRole.PROVIDER),
            provider_type=provider_type,
            display_name=f"Provider {counter['n']}",
            governorate=baghdad,
            verification_status=verification_status,
            is_visible=is_visible,
        )
        profile.specialties.set(specialties)
        return profile

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
def admin_client(db):
    from apps.accounts.models import Account

    admin = Account.objects.create_superuser(
        email="admin@example.com", password="Str0ng-Passw0rd!", full_name="Admin"
    )
    return client_for(admin)
