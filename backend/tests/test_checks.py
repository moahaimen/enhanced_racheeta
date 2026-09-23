"""Project system checks that guard production configuration."""

from django.core.checks import run_checks
from django.test import override_settings


def _ids(**overrides):
    with override_settings(**overrides):
        return {c.id for c in run_checks()}


def test_console_email_is_an_error_in_production():
    assert "racheeta.E001" in _ids(
        DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
    )
    assert "racheeta.E001" in _ids(
        DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )


def test_console_email_is_fine_in_debug():
    assert "racheeta.E001" not in _ids(
        DEBUG=True, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
    )


def test_smtp_email_is_fine_in_production():
    assert "racheeta.E001" not in _ids(
        DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
    )


def test_locale_middleware_localises_errors(client):
    ar = client.get("/api/v1/me", HTTP_ACCEPT_LANGUAGE="ar").json()["error"]["message"]
    en = client.get("/api/v1/me", HTTP_ACCEPT_LANGUAGE="en").json()["error"]["message"]
    assert ar != en
    assert "credentials" in en.lower()
