import pytest

from apps.accounts.roles import AccountRole

pytestmark = pytest.mark.django_db

ME = "/api/v1/me"


def test_me_requires_authentication(api_client):
    response = api_client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_identity_role_and_permissions(auth_client, account):
    response = auth_client.get(ME)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "email",
        "full_name",
        "phone_number",
        "role",
        "preferred_language",
        "email_verified",
        "is_staff",
        "permissions",
        "created_at",
        "last_login",
    }
    assert body["id"] == str(account.id)
    assert body["role"] == "PATIENT"
    assert body["preferred_language"] == "ar"
    assert "accounts.edit_self" in body["permissions"]


def test_me_patch_updates_allowed_fields(auth_client, account):
    response = auth_client.patch(
        ME, {"full_name": "Renamed", "phone_number": "+9647700000000", "preferred_language": "en"}
    )
    assert response.status_code == 200, response.content
    account.refresh_from_db()
    assert account.full_name == "Renamed"
    assert account.phone_number == "+9647700000000"
    assert account.preferred_language == "en"
    assert response.json()["full_name"] == "Renamed"


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "ADMIN"},
        {"is_staff": True},
        {"is_superuser": True},
        {"email": "hijack@example.com"},
        {"password": "new-password-123"},
        {"email_verified": True},
    ],
)
def test_me_patch_rejects_privilege_and_identity_fields(auth_client, account, payload):
    before = (account.role, account.is_staff, account.is_superuser, account.email, account.password)
    response = auth_client.patch(ME, {"full_name": "X", **payload})
    assert response.status_code == 400
    assert set(payload) <= set(response.json()["error"]["details"])
    account.refresh_from_db()
    assert before == (
        account.role,
        account.is_staff,
        account.is_superuser,
        account.email,
        account.password,
    )
    assert account.full_name != "X"  # whole request rejected, nothing partially applied


def test_me_rejects_put_and_delete(auth_client):
    assert auth_client.put(ME, {"full_name": "x"}).status_code == 405
    assert auth_client.delete(ME).status_code == 405


def test_me_for_provider_role(api_client, account_factory):
    provider = account_factory(role=AccountRole.PROVIDER)
    api_client.force_authenticate(user=provider)
    body = api_client.get(ME).json()
    assert body["role"] == "PROVIDER"
    assert "providers.manage_own_profile" in body["permissions"]


def test_me_timestamps_are_utc_iso8601(auth_client):
    body = auth_client.get(ME).json()
    assert body["created_at"].endswith("Z"), body["created_at"]
