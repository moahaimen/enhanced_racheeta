import pytest
from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole

PASSWORD = "Str0ng-Passw0rd!"

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"

VALID = {
    "email": "New.Person@Example.com",
    "password": PASSWORD,
    "full_name": "New Person",
}


# ---- register ---------------------------------------------------------------


def test_register_creates_account_and_returns_tokens(api_client):
    response = api_client.post(REGISTER, VALID)
    assert response.status_code == 201, response.content
    body = response.json()
    assert set(body) == {"account", "tokens"}
    assert body["account"]["email"] == "new.person@example.com"
    assert body["account"]["role"] == "PATIENT"
    assert body["account"]["is_staff"] is False
    assert isinstance(body["account"]["permissions"], list)
    assert "password" not in body["account"]
    assert set(body["tokens"]) == {"access", "refresh"}
    assert Account.objects.get(email="new.person@example.com").check_password(PASSWORD)


def test_register_response_never_contains_password_hash(api_client):
    response = api_client.post(REGISTER, VALID)
    assert "pbkdf2" not in response.content.decode()
    assert "md5$" not in response.content.decode()


@pytest.mark.parametrize("role", ["PROVIDER", "MEDICAL_COMPANY", "REAL_ESTATE_SELLER"])
def test_register_allows_self_service_roles(api_client, role):
    response = api_client.post(REGISTER, {**VALID, "role": role})
    assert response.status_code == 201
    assert response.json()["account"]["role"] == role


def test_register_rejects_admin_role(api_client):
    response = api_client.post(REGISTER, {**VALID, "role": "ADMIN"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "role" in body["error"]["details"]
    assert not Account.objects.filter(email="new.person@example.com").exists()


@pytest.mark.parametrize("field", ["is_staff", "is_superuser", "permissions", "groups"])
def test_register_rejects_privilege_fields(api_client, field):
    response = api_client.post(REGISTER, {**VALID, field: True})
    assert response.status_code == 400
    assert field in response.json()["error"]["details"]
    assert not Account.objects.exists()


def test_register_rejects_weak_password(api_client):
    response = api_client.post(REGISTER, {**VALID, "password": "password"})
    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]


def test_register_rejects_duplicate_email_case_insensitively(api_client, account_factory):
    account_factory(email="taken@example.com")
    response = api_client.post(REGISTER, {**VALID, "email": "TAKEN@example.com"})
    assert response.status_code == 400
    assert "email" in response.json()["error"]["details"]


def test_register_validation_error_envelope(api_client):
    response = api_client.post(REGISTER, {})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"]
    assert {"email", "password", "full_name"} <= set(body["error"]["details"])


# ---- login ------------------------------------------------------------------


def test_login_returns_token_pair(api_client, account):
    response = api_client.post(LOGIN, {"email": account.email, "password": PASSWORD})
    assert response.status_code == 200, response.content
    assert set(response.json()) == {"access", "refresh"}


def test_login_is_case_insensitive_on_email(api_client, account):
    response = api_client.post(LOGIN, {"email": account.email.upper(), "password": PASSWORD})
    assert response.status_code == 200


def test_login_wrong_password_returns_401_envelope(api_client, account):
    response = api_client.post(LOGIN, {"email": account.email, "password": "nope-nope-nope"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "no_active_account"


def test_login_inactive_account_rejected(api_client, account_factory):
    inactive = account_factory(is_active=False)
    response = api_client.post(LOGIN, {"email": inactive.email, "password": PASSWORD})
    assert response.status_code == 401


def test_login_updates_last_login(api_client, account):
    assert account.last_login is None
    api_client.post(LOGIN, {"email": account.email, "password": PASSWORD})
    account.refresh_from_db()
    assert account.last_login is not None


# ---- refresh / logout -------------------------------------------------------


def _login(api_client, account) -> dict:
    return api_client.post(LOGIN, {"email": account.email, "password": PASSWORD}).json()


def test_refresh_rotates_and_blacklists_old_token(api_client, account):
    tokens = _login(api_client, account)
    first = api_client.post(REFRESH, {"refresh": tokens["refresh"]})
    assert first.status_code == 200
    assert set(first.json()) == {"access", "refresh"}
    assert first.json()["refresh"] != tokens["refresh"]

    reused = api_client.post(REFRESH, {"refresh": tokens["refresh"]})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "token_not_valid"


def test_access_token_grants_access_to_me(api_client, account):
    tokens = _login(api_client, account)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    response = api_client.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json()["id"] == str(account.id)


def test_logout_blacklists_refresh_token(api_client, account):
    tokens = _login(api_client, account)
    response = api_client.post(LOGOUT, {"refresh": tokens["refresh"]})
    assert response.status_code == 204
    reused = api_client.post(REFRESH, {"refresh": tokens["refresh"]})
    assert reused.status_code == 401


def test_logout_with_garbage_token_is_400(api_client):
    response = api_client.post(LOGOUT, {"refresh": "not-a-token"})
    assert response.status_code == 400
    assert "refresh" in response.json()["error"]["details"]


# ---- throttling -------------------------------------------------------------


def test_auth_endpoints_are_throttled(api_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "auth", "2/min")
    cache.clear()
    try:
        bad = {"email": "x@example.com", "password": "wrong-wrong"}
        assert api_client.post(LOGIN, bad).status_code == 401
        assert api_client.post(LOGIN, bad).status_code == 401
        third = api_client.post(LOGIN, bad)
        assert third.status_code == 429
        assert third.json()["error"]["code"] == "throttled"
    finally:
        cache.clear()


def test_role_choice_labels_exclude_admin():
    from apps.accounts.serializers import RegisterSerializer

    choices = dict(RegisterSerializer().fields["role"].choices)
    assert AccountRole.ADMIN not in choices


def test_self_registration_choices_match_settings(settings):
    from apps.accounts.roles import SELF_REGISTRATION_ROLE_CHOICES

    assert [c[0] for c in SELF_REGISTRATION_ROLE_CHOICES] == list(
        settings.RACHEETA["SELF_REGISTRATION_ROLES"]
    )


def test_access_token_is_not_accepted_as_refresh_token(api_client, account):
    tokens = _login(api_client, account)
    response = api_client.post(REFRESH, {"refresh": tokens["access"]})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_not_valid"


def test_logout_with_already_revoked_token_is_400_without_leaking(api_client, account):
    tokens = _login(api_client, account)
    assert api_client.post(LOGOUT, {"refresh": tokens["refresh"]}).status_code == 204
    again = api_client.post(LOGOUT, {"refresh": tokens["refresh"]})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "validation_error"
    assert account.email not in again.content.decode()


def test_refresh_for_deleted_account_is_401_not_500(api_client, account):
    tokens = _login(api_client, account)
    account.delete()
    response = api_client.post(REFRESH, {"refresh": tokens["refresh"]})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_not_valid"


def test_refresh_for_deactivated_account_is_401(api_client, account):
    tokens = _login(api_client, account)
    Account.objects.filter(pk=account.pk).update(is_active=False)
    response = api_client.post(REFRESH, {"refresh": tokens["refresh"]})
    assert response.status_code == 401
