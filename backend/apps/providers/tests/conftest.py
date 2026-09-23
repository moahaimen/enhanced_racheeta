import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.geography.models import City, Governorate
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus
from apps.specialties.models import Specialty


@pytest.fixture
def baghdad(db) -> Governorate:
    return Governorate.objects.get(slug="baghdad")


@pytest.fixture
def basra(db) -> Governorate:
    return Governorate.objects.get(slug="basra")


@pytest.fixture
def baghdad_city(baghdad) -> City:
    return baghdad.cities.get(slug="baghdad")


@pytest.fixture
def cardiology(db) -> Specialty:
    return Specialty.objects.get(slug="cardiology")


@pytest.fixture
def dentistry(db) -> Specialty:
    return Specialty.objects.get(slug="dentistry")


@pytest.fixture
def provider_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(
        provider_type=ProviderType.DOCTOR,
        verification_status=VerificationStatus.VERIFIED,
        is_visible=True,
        governorate=None,
        city=None,
        specialties=(),
        account=None,
        **overrides,
    ) -> ProviderProfile:
        counter["n"] += 1
        account = account or account_factory(role=AccountRole.PROVIDER)
        profile = ProviderProfile.objects.create(
            account=account,
            provider_type=provider_type,
            display_name=overrides.pop("display_name", f"Provider {counter['n']:03d}"),
            governorate=governorate or baghdad,
            city=city,
            verification_status=verification_status,
            is_visible=is_visible,
            **overrides,
        )
        if specialties:
            profile.specialties.set(specialties)
        return profile

    return _make


@pytest.fixture
def provider_client(api_client, provider_factory):
    """(client authenticated as a verified DOCTOR, its profile)."""
    profile = provider_factory()
    api_client.force_authenticate(user=profile.account)
    return api_client, profile


@pytest.fixture
def admin_client(api_client, db):
    from apps.accounts.models import Account

    admin = Account.objects.create_superuser(
        email="admin@example.com", password="Str0ng-Passw0rd!", full_name="Admin"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    return client
