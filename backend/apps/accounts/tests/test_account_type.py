import pytest

from apps.accounts.models import Account
from apps.accounts.roles import ACCOUNT_TYPE_ROLE, AccountType

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register"
ME = "/api/v1/me"
VALID = {"email": "typed@example.com", "password": "Str0ng-Passw0rd!", "full_name": "Typed Person"}


@pytest.mark.parametrize("account_type", AccountType.values)
def test_account_type_derives_the_role(api_client, account_type):
    response = api_client.post(REGISTER, {**VALID, "account_type": account_type})
    assert response.status_code == 201, response.json()
    account = response.json()["account"]
    assert account["account_type"] == account_type
    assert account["role"] == ACCOUNT_TYPE_ROLE[account_type]


def test_contradicting_role_is_rejected(api_client):
    response = api_client.post(REGISTER, {**VALID, "account_type": "PHARMACY", "role": "PATIENT"})
    assert response.status_code == 400
    assert not Account.objects.filter(email="typed@example.com").exists()


def test_unknown_account_type_and_admin_are_rejected(api_client):
    assert api_client.post(REGISTER, {**VALID, "account_type": "ADMIN"}).status_code == 400


def test_account_type_cannot_be_changed_by_profile_update(api_client):
    api_client.post(REGISTER, {**VALID, "account_type": "PATIENT"})
    account = Account.objects.get(email="typed@example.com")
    api_client.force_authenticate(user=account)
    response = api_client.patch(ME, {"account_type": "PHARMACEUTICAL_COMPANY"}, format="json")
    assert response.status_code == 400
    account.refresh_from_db()
    assert account.account_type == "PATIENT"
