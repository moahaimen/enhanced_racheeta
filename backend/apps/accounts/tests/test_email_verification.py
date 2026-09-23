import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.tokens import email_verification_token, encode_uid

pytestmark = pytest.mark.django_db

REQUEST = "/api/v1/auth/email-verification/request"
CONFIRM = "/api/v1/auth/email-verification/confirm"
ME = "/api/v1/me"


def _extract_link(body: str) -> tuple[str, str]:
    match = re.search(r"/verify-email\?uid=([^&\s]+)&token=([^\s]+)", body)
    assert match, body
    return match.group(1), match.group(2)


def test_request_requires_authentication(api_client):
    assert api_client.post(REQUEST).status_code == 401


def test_request_sends_link_and_confirm_verifies(auth_client, account):
    response = auth_client.post(REQUEST)
    assert response.status_code == 202
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [account.email]
    uid, token = _extract_link(mail.outbox[0].body)
    assert uid == encode_uid(account)

    confirm = auth_client.post(CONFIRM, {"uid": uid, "token": token})
    assert confirm.status_code == 200, confirm.content
    account.refresh_from_db()
    assert account.email_verified_at is not None
    me = auth_client.get(ME).json()
    assert me["email_verified"] is True
    assert me["email_verified_at"] is not None


def test_confirm_works_without_authentication(api_client, auth_client, account):
    auth_client.post(REQUEST)
    uid, token = _extract_link(mail.outbox[0].body)
    assert api_client.post(CONFIRM, {"uid": uid, "token": token}).status_code == 200


def test_confirm_is_idempotent_after_success(auth_client, account):
    auth_client.post(REQUEST)
    uid, token = _extract_link(mail.outbox[0].body)
    assert auth_client.post(CONFIRM, {"uid": uid, "token": token}).status_code == 200
    again = auth_client.post(CONFIRM, {"uid": uid, "token": token})
    assert again.status_code == 200  # link already used successfully: harmless


def test_request_rejected_when_already_verified(auth_client, account):
    account.email_verified_at = timezone.now()
    account.save(update_fields=["email_verified_at"])
    response = auth_client.post(REQUEST)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["non_field_errors"]
    assert mail.outbox == []


def test_resend_issues_tokens_that_all_work_until_verified(auth_client, account):
    auth_client.post(REQUEST)
    auth_client.post(REQUEST)
    assert len(mail.outbox) == 2
    _, token1 = _extract_link(mail.outbox[0].body)
    _, token2 = _extract_link(mail.outbox[1].body)
    assert email_verification_token.check_token(account, token1)
    assert email_verification_token.check_token(account, token2)


def test_token_invalid_after_email_change(auth_client, account):
    auth_client.post(REQUEST)
    uid, token = _extract_link(mail.outbox[0].body)
    account.email = "changed@example.com"
    account.save(update_fields=["email"])
    response = auth_client.post(CONFIRM, {"uid": uid, "token": token})
    assert response.status_code == 400
    assert "token" in response.json()["error"]["details"]


def test_token_expires(auth_client, account, settings):
    auth_client.post(REQUEST)
    uid, token = _extract_link(mail.outbox[0].body)
    settings.RACHEETA = {**settings.RACHEETA, "EMAIL_VERIFICATION_TIMEOUT": timedelta(seconds=0)}
    from apps.accounts import tokens as t

    original_now = t.EmailVerificationToken._now
    t.EmailVerificationToken._now = lambda self: original_now(self) + timedelta(hours=1)
    try:
        response = auth_client.post(CONFIRM, {"uid": uid, "token": token})
    finally:
        t.EmailVerificationToken._now = original_now
    assert response.status_code == 400


def test_verification_token_is_not_a_password_reset_token(auth_client, account):
    from apps.accounts.tokens import password_reset_token

    auth_client.post(REQUEST)
    _, token = _extract_link(mail.outbox[0].body)
    assert not password_reset_token.check_token(account, token)


def test_confirm_rejects_garbage(api_client):
    response = api_client.post(CONFIRM, {"uid": "nope", "token": "nope"})
    assert response.status_code == 400


def test_verification_endpoints_are_throttled(auth_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "email_verification", "2/min")
    cache.clear()
    assert auth_client.post(REQUEST).status_code == 202
    assert auth_client.post(REQUEST).status_code == 202
    assert auth_client.post(REQUEST).status_code == 429
