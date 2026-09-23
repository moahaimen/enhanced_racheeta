import pytest
from django.db import IntegrityError

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole, capabilities_for

pytestmark = pytest.mark.django_db


def test_create_user_normalises_email_and_hashes_password():
    account = Account.objects.create_user(
        email="  Someone@Example.COM ", password="Str0ng-Passw0rd!", full_name="Someone"
    )
    assert account.email == "someone@example.com"
    assert account.password != "Str0ng-Passw0rd!"
    assert account.check_password("Str0ng-Passw0rd!")
    assert account.role == AccountRole.PATIENT
    assert account.is_active and not account.is_staff and not account.is_superuser
    assert str(account) == "someone@example.com"


def test_create_user_without_password_has_unusable_password():
    account = Account.objects.create_user(email="fb@example.com", full_name="Firebase User")
    assert not account.has_usable_password()


def test_email_is_required():
    with pytest.raises(ValueError):
        Account.objects.create_user(email="", password="x", full_name="x")


def test_email_uniqueness_is_case_insensitive():
    Account.objects.create_user(email="dup@example.com", password="Str0ng-Passw0rd!", full_name="A")
    with pytest.raises(IntegrityError):
        Account.objects.create(email="DUP@example.com", full_name="B")


def test_phone_number_unique_only_when_set(account_factory):
    account_factory(phone_number="")
    account_factory(phone_number="")  # multiple blanks are fine
    account_factory(phone_number="+9647701234567")
    with pytest.raises(IntegrityError):
        Account.objects.create(email="x@example.com", full_name="X", phone_number="+9647701234567")


def test_create_user_cannot_grant_privileges():
    with pytest.raises(ValueError):
        Account.objects.create_user(
            email="a@example.com", password="x", full_name="A", is_staff=True
        )
    with pytest.raises(ValueError):
        Account.objects.create_user(
            email="b@example.com", password="x", full_name="B", role=AccountRole.ADMIN
        )


def test_create_superuser_sets_admin_role_and_flags():
    admin = Account.objects.create_superuser(
        email="admin@example.com", password="Str0ng-Passw0rd!", full_name="Admin"
    )
    assert admin.role == AccountRole.ADMIN
    assert admin.is_staff and admin.is_superuser
    assert "admin.manage_accounts" in admin.capabilities


def test_admin_role_requires_staff_at_database_level():
    with pytest.raises(IntegrityError):
        Account.objects.create(email="c@example.com", full_name="C", role=AccountRole.ADMIN)


def test_capabilities_for_each_role(account_factory):
    patient = account_factory(role=AccountRole.PATIENT)
    provider = account_factory(role=AccountRole.PROVIDER)
    assert "reservations.create_own" in capabilities_for(patient)
    assert "providers.manage_own_profile" not in capabilities_for(patient)
    assert "providers.manage_own_profile" in capabilities_for(provider)
    assert capabilities_for(patient) == sorted(capabilities_for(patient))
