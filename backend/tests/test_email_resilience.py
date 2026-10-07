"""A mail outage must neither leak account existence nor leak a token."""

import logging
import smtplib

import pytest
from rest_framework.test import APIClient

RESET = "/api/v1/auth/password-reset/request"
VERIFY = "/api/v1/auth/email-verification/request"


@pytest.fixture
def failing_mail(monkeypatch):
    def boom(*_args, **_kwargs):
        raise smtplib.SMTPServerDisconnected("smtp.internal:587 refused password=hunter2")

    monkeypatch.setattr("apps.accounts.emails.send_mail", boom)


@pytest.mark.django_db
@pytest.mark.parametrize("error", [smtplib.SMTPException, TimeoutError, OSError])
def test_password_reset_answers_identically_when_mail_fails(account, monkeypatch, caplog, error):
    def boom(*_a, **_k):
        raise error("provider down")

    monkeypatch.setattr("apps.accounts.emails.send_mail", boom)
    client = APIClient()
    with caplog.at_level(logging.ERROR):
        known = client.post(RESET, {"email": account.email})
    unknown = client.post(RESET, {"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "delivery failed" in log and str(account.pk) in log
    assert "/reset-password" not in log and "token" not in log.lower()


@pytest.mark.django_db
def test_failed_reset_mail_leaks_nothing_to_the_client(account, failing_mail):
    response = APIClient().post(RESET, {"email": account.email})
    body = response.content.decode()
    assert response.status_code == 202
    for secret in ("smtp.internal", "hunter2", "SMTPServerDisconnected", "Traceback"):
        assert secret not in body


@pytest.mark.django_db
def test_verification_request_is_a_typed_503_when_mail_fails(account, failing_mail):
    client = APIClient()
    client.force_authenticate(account)
    response = client.post(VERIFY, {})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "email_unavailable"
    body = response.content.decode()
    for secret in ("smtp.internal", "hunter2", "SMTPServerDisconnected", "Traceback"):
        assert secret not in body
    account.refresh_from_db()
    assert not account.email_verified
