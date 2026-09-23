"""Firebase exchange is tested against a fake verifier; no credentials needed."""

import pytest
from django.test import override_settings

from apps.accounts.firebase import (
    DisabledVerifier,
    FirebaseIdentity,
    FirebaseTokenInvalid,
    get_verifier,
    is_enabled,
)
from apps.accounts.models import Account

pytestmark = pytest.mark.django_db

EXCHANGE = "/api/v1/auth/firebase/exchange"
ME = "/api/v1/me"

IDENTITIES: dict[str, FirebaseIdentity] = {}


class FakeVerifier:
    def verify(self, id_token: str) -> FirebaseIdentity:
        try:
            return IDENTITIES[id_token]
        except KeyError:
            raise FirebaseTokenInvalid("unknown token") from None


FAKE = f"{__name__}.FakeVerifier"


@pytest.fixture
def fake_firebase(settings):
    IDENTITIES.clear()
    settings.RACHEETA = {**settings.RACHEETA, "FIREBASE_VERIFIER": FAKE}
    yield IDENTITIES
    IDENTITIES.clear()


def test_disabled_by_default(api_client, settings):
    assert isinstance(get_verifier(), DisabledVerifier)
    assert not is_enabled()
    response = api_client.post(EXCHANGE, {"id_token": "anything"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "firebase_not_configured"


def test_invalid_token_is_401(api_client, fake_firebase):
    response = api_client.post(EXCHANGE, {"id_token": "bad"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "firebase_token_invalid"


def test_creates_account_with_unusable_password(api_client, fake_firebase):
    fake_firebase["t1"] = FirebaseIdentity(
        uid="uid-1", email="New.Google@Example.com", email_verified=True, name="Google Person"
    )
    response = api_client.post(EXCHANGE, {"id_token": "t1", "role": "PROVIDER"})
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["created"] is True
    assert body["account"]["email"] == "new.google@example.com"
    assert body["account"]["role"] == "PROVIDER"
    assert body["account"]["email_verified"] is True
    assert body["account"]["has_password"] is False
    assert set(body["tokens"]) == {"access", "refresh"}

    account = Account.objects.get(email="new.google@example.com")
    assert not account.has_usable_password()
    assert account.firebase_uid == "uid-1"
    assert account.full_name == "Google Person"

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}")
    assert api_client.get(ME).status_code == 200


def test_signs_in_existing_linked_account(api_client, fake_firebase, account_factory):
    linked = account_factory(firebase_uid="uid-2")
    fake_firebase["t2"] = FirebaseIdentity(uid="uid-2", email=None, email_verified=False)
    response = api_client.post(EXCHANGE, {"id_token": "t2"})
    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["account"]["id"] == str(linked.id)


def test_links_existing_account_only_when_firebase_verified_email(
    api_client, fake_firebase, account_factory
):
    existing = account_factory(email="victim@example.com")
    fake_firebase["unverified"] = FirebaseIdentity(
        uid="uid-3", email="victim@example.com", email_verified=False
    )
    blocked = api_client.post(EXCHANGE, {"id_token": "unverified"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "email_not_verified"
    existing.refresh_from_db()
    assert existing.firebase_uid == ""

    fake_firebase["verified"] = FirebaseIdentity(
        uid="uid-3", email="VICTIM@example.com", email_verified=True
    )
    ok = api_client.post(EXCHANGE, {"id_token": "verified"})
    assert ok.status_code == 200
    existing.refresh_from_db()
    assert existing.firebase_uid == "uid-3"
    assert existing.email_verified_at is not None
    assert existing.has_usable_password()  # existing password untouched


def test_phone_only_identity_requires_email(api_client, fake_firebase):
    fake_firebase["phone"] = FirebaseIdentity(
        uid="uid-4", email=None, email_verified=False, phone_number="+9647700000001"
    )
    response = api_client.post(EXCHANGE, {"id_token": "phone"})
    assert response.status_code == 400
    assert "id_token" in response.json()["error"]["details"]
    assert not Account.objects.filter(firebase_uid="uid-4").exists()


def test_admin_role_cannot_be_requested(api_client, fake_firebase):
    fake_firebase["t5"] = FirebaseIdentity(uid="uid-5", email="a@example.com", email_verified=True)
    response = api_client.post(EXCHANGE, {"id_token": "t5", "role": "ADMIN"})
    assert response.status_code == 400
    assert "role" in response.json()["error"]["details"]


def test_inactive_linked_account_rejected(api_client, fake_firebase, account_factory):
    account_factory(firebase_uid="uid-6", is_active=False)
    fake_firebase["t6"] = FirebaseIdentity(uid="uid-6", email=None, email_verified=False)
    response = api_client.post(EXCHANGE, {"id_token": "t6"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "no_active_account"


def test_duplicate_phone_is_not_stolen(api_client, fake_firebase, account_factory):
    account_factory(phone_number="+9647700000009")
    fake_firebase["t7"] = FirebaseIdentity(
        uid="uid-7", email="p@example.com", email_verified=True, phone_number="+9647700000009"
    )
    response = api_client.post(EXCHANGE, {"id_token": "t7"})
    assert response.status_code == 201
    assert Account.objects.get(firebase_uid="uid-7").phone_number == ""


def test_unloadable_verifier_fails_system_check():
    from django.core.checks import run_checks

    with override_settings(RACHEETA={"FIREBASE_VERIFIER": "nope.Missing", "FRONTEND_URL": "x"}):
        errors = [e for e in run_checks() if e.id == "racheeta.E002"]
    assert errors
