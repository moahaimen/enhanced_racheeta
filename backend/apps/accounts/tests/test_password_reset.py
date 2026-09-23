import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import Account
from apps.accounts.tokens import encode_uid, password_reset_token

pytestmark = pytest.mark.django_db

REQUEST = "/api/v1/auth/password-reset/request"
CONFIRM = "/api/v1/auth/password-reset/confirm"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
PASSWORD = "Str0ng-Passw0rd!"
NEW_PASSWORD = "An0ther-Str0ng-One!"


def _extract_link(body: str) -> tuple[str, str]:
    match = re.search(r"/reset-password\?uid=([^&\s]+)&token=([^\s]+)", body)
    assert match, body
    return match.group(1), match.group(2)


# ---- request -----------------------------------------------------------------


def test_request_sends_email_with_link_to_frontend(api_client, account, settings):
    settings.RACHEETA = {**settings.RACHEETA, "FRONTEND_URL": "https://app.example"}
    response = api_client.post(REQUEST, {"email": account.email.upper()})
    assert response.status_code == 202
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [account.email]
    assert "https://app.example/reset-password?uid=" in message.body
    uid, token = _extract_link(message.body)
    assert password_reset_token.check_token(account, token)
    assert uid == encode_uid(account)


def test_request_is_enumeration_safe(api_client, account):
    known = api_client.post(REQUEST, {"email": account.email})
    unknown = api_client.post(REQUEST, {"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mail.outbox) == 1  # only the real account got an email


def test_request_ignores_inactive_accounts(api_client, account_factory):
    inactive = account_factory(is_active=False)
    response = api_client.post(REQUEST, {"email": inactive.email})
    assert response.status_code == 202
    assert mail.outbox == []


def test_request_validates_email_format(api_client):
    response = api_client.post(REQUEST, {"email": "not-an-email"})
    assert response.status_code == 400
    assert "email" in response.json()["error"]["details"]


def test_request_email_uses_account_language(api_client, account_factory):
    en = account_factory(preferred_language="en")
    api_client.post(REQUEST, {"email": en.email})
    assert "Reset your Racheeta password" in mail.outbox[0].subject
    ar = account_factory(preferred_language="ar")
    api_client.post(REQUEST, {"email": ar.email})
    assert "رشيتة" in mail.outbox[1].subject


def test_email_body_never_contains_password_or_hash(api_client, account):
    api_client.post(REQUEST, {"email": account.email})
    body = mail.outbox[0].body
    assert PASSWORD not in body
    assert account.password not in body


# ---- confirm -----------------------------------------------------------------


def _reset_link(api_client, account) -> tuple[str, str]:
    api_client.post(REQUEST, {"email": account.email})
    return _extract_link(mail.outbox[-1].body)


def test_confirm_sets_password_and_revokes_refresh_tokens(api_client, account):
    login = api_client.post(LOGIN, {"email": account.email, "password": PASSWORD}).json()
    uid, token = _reset_link(api_client, account)

    response = api_client.post(CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 200, response.content

    account.refresh_from_db()
    assert account.check_password(NEW_PASSWORD)
    assert account.email_verified_at is not None  # mailbox control proven
    # old refresh token is dead
    reused = api_client.post(REFRESH, {"refresh": login["refresh"]})
    assert reused.status_code == 401
    # new password works, old does not
    new_login = api_client.post(LOGIN, {"email": account.email, "password": NEW_PASSWORD})
    old_login = api_client.post(LOGIN, {"email": account.email, "password": PASSWORD})
    assert new_login.status_code == 200
    assert old_login.status_code == 401


def test_confirm_token_is_single_use(api_client, account):
    uid, token = _reset_link(api_client, account)
    first = api_client.post(CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD})
    assert first.status_code == 200
    second = api_client.post(
        CONFIRM, {"uid": uid, "token": token, "new_password": "Yet-An0ther-1!"}
    )
    assert second.status_code == 400
    assert "token" in second.json()["error"]["details"]


def test_confirm_rejects_expired_token(api_client, account, settings):
    uid, token = _reset_link(api_client, account)
    settings.PASSWORD_RESET_TIMEOUT = 0
    # Django compares elapsed seconds > timeout; force the clock forward.
    from django.contrib.auth import tokens as django_tokens

    original_now = django_tokens.PasswordResetTokenGenerator._now
    django_tokens.PasswordResetTokenGenerator._now = lambda self: (
        original_now(self) + timedelta(minutes=5)
    )
    try:
        response = api_client.post(
            CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD}
        )
    finally:
        django_tokens.PasswordResetTokenGenerator._now = original_now
    assert response.status_code == 400
    assert "token" in response.json()["error"]["details"]


@pytest.mark.parametrize(
    "payload",
    [
        {"uid": "bogus", "token": "bogus"},
        {"uid": "", "token": ""},
        {"uid": "MDAwMDAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAw", "token": "abc-def"},
    ],
)
def test_confirm_rejects_garbage(api_client, payload):
    response = api_client.post(CONFIRM, {**payload, "new_password": NEW_PASSWORD})
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "validation_error"


def test_confirm_token_for_one_account_does_not_work_for_another(api_client, account_factory):
    victim = account_factory()
    attacker = account_factory()
    uid_a, token_a = _reset_link(api_client, attacker)
    response = api_client.post(
        CONFIRM, {"uid": encode_uid(victim), "token": token_a, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400
    victim.refresh_from_db()
    assert victim.check_password(PASSWORD)
    assert uid_a != encode_uid(victim)


def test_confirm_enforces_password_rules(api_client, account):
    uid, token = _reset_link(api_client, account)
    response = api_client.post(CONFIRM, {"uid": uid, "token": token, "new_password": "password"})
    assert response.status_code == 400
    assert "new_password" in response.json()["error"]["details"]
    # token still valid: user can retry with a proper password
    retry = api_client.post(CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD})
    assert retry.status_code == 200


def test_confirm_rejects_inactive_account(api_client, account):
    uid, token = _reset_link(api_client, account)
    Account.objects.filter(pk=account.pk).update(is_active=False)
    response = api_client.post(CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 400


def test_reset_endpoints_are_throttled(api_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "password_reset", "2/min")
    cache.clear()
    payload = {"email": "nobody@example.com"}
    assert api_client.post(REQUEST, payload).status_code == 202
    assert api_client.post(REQUEST, payload).status_code == 202
    third = api_client.post(REQUEST, payload)
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "throttled"


def test_reset_flow_does_not_log_token(api_client, account, caplog):
    import logging

    with caplog.at_level(logging.DEBUG):
        uid, token = _reset_link(api_client, account)
        api_client.post(CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD})
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert token not in logged
    assert NEW_PASSWORD not in logged
    assert PASSWORD not in logged
