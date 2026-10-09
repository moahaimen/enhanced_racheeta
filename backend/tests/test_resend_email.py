"""EMAIL_PROVIDER=resend: the HTTPS transport, its checks, and the unchanged account flows.

No test talks to the network: the HTTP boundary (`email_backends._opener`) is replaced by a fake
that records the request, except the redirect test which uses a loopback server.
"""

import http.server
import json
import logging
import socket
import threading
import urllib.error
import urllib.request

import pytest
from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from rest_framework.test import APIClient

from apps.core import email_backends
from apps.core.checks import sender_address_problem
from apps.core.email_backends import RESEND_API_URL, ResendEmailBackend, ResendEmailError

from .test_phase12a_hardening import _ids, _manage, _production_env

FAKE_KEY = "re_test_fake_key_do_not_use_0123456789"
SENDER = "Racheeta <no-reply@mail.example.com>"
RESET = "/api/v1/auth/password-reset/request"
VERIFY = "/api/v1/auth/email-verification/request"


class FakeResponse:
    def __init__(self, status=200, body=b'{"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"}'):
        self.status, self._body = status, body

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, outcome=None):
        self.outcome = outcome if outcome is not None else FakeResponse()
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def http_error(code, body=b""):
    import io

    return urllib.error.HTTPError(RESEND_API_URL, code, "x", {}, io.BytesIO(body))


@pytest.fixture
def opener(monkeypatch):
    fake = FakeOpener()
    monkeypatch.setattr(email_backends, "_opener", fake)
    return fake


@pytest.fixture
def backend(settings):
    settings.RESEND_API_KEY = FAKE_KEY
    settings.DEFAULT_FROM_EMAIL = SENDER
    settings.EMAIL_TIMEOUT = 7
    return ResendEmailBackend()


def sent_json(opener):
    return json.loads(opener.calls[-1][0].data)


# ---- the request ------------------------------------------------------------------------------


def test_request_shape_endpoint_auth_from_to_subject_text(backend, opener):
    message = EmailMessage("Hello subject", "plain body", SENDER, ["user@example.org"])
    assert backend.send_messages([message]) == 1
    request, timeout = opener.calls[0]
    assert request.full_url == RESEND_API_URL and RESEND_API_URL.startswith("https://")
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {FAKE_KEY}"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("User-agent").startswith("racheeta-backend/")  # not python-urllib
    assert json.loads(request.data) == {
        "from": SENDER,
        "to": ["user@example.org"],
        "subject": "Hello subject",
        "text": "plain body",
    }
    assert timeout == 7  # bounded by EMAIL_TIMEOUT, never None


def test_default_from_is_used_when_the_message_has_none(backend, opener, settings):
    settings.DEFAULT_FROM_EMAIL = "Racheeta <hello@mail.example.com>"
    send_mail("s", "b", None, ["u@example.org"], connection=ResendEmailBackend())
    assert sent_json(opener)["from"] == "Racheeta <hello@mail.example.com>"


def test_html_alternative_and_html_subtype_are_sent(backend, opener):
    multi = EmailMultiAlternatives("s", "text part", SENDER, ["u@example.org"])
    multi.attach_alternative("<p>html part</p>", "text/html")
    backend.send_messages([multi])
    assert sent_json(opener)["text"] == "text part"
    assert sent_json(opener)["html"] == "<p>html part</p>"

    only_html = EmailMessage("s", "<b>x</b>", SENDER, ["u@example.org"])
    only_html.content_subtype = "html"
    backend.send_messages([only_html])
    payload = sent_json(opener)
    assert payload["html"] == "<b>x</b>" and "text" not in payload


def test_cc_bcc_reply_to_and_multiple_recipients(backend, opener):
    message = EmailMessage(
        "s", "b", SENDER, ["a@example.org", "b@example.org"], cc=["c@example.org"],
        bcc=["d@example.org"], reply_to=["r@example.org"],
    )  # fmt: skip
    backend.send_messages([message])
    payload = sent_json(opener)
    assert payload["to"] == ["a@example.org", "b@example.org"]
    assert payload["cc"] == ["c@example.org"] and payload["bcc"] == ["d@example.org"]
    assert payload["reply_to"] == ["r@example.org"]


def test_send_messages_counts_and_handles_empty(backend, opener):
    ok = EmailMessage("s", "b", SENDER, ["u@example.org"])
    assert backend.send_messages([ok, ok]) == 2 and len(opener.calls) == 2
    assert backend.send_messages([]) == 0


def test_attachments_and_header_injection_are_refused_not_dropped(backend, opener):
    with_file = EmailMessage("s", "b", SENDER, ["u@example.org"])
    with_file.attach("a.txt", "data", "text/plain")
    with pytest.raises(ResendEmailError, match="attachments"):
        backend.send_messages([with_file])
    injected = EmailMessage("s\r\nBcc: evil@example.org", "b", SENDER, ["u@example.org"])
    with pytest.raises(ResendEmailError, match="control characters"):
        backend.send_messages([injected])
    assert opener.calls == []  # nothing left the process


def test_fail_silently_swallows_and_reports_zero(backend, opener):
    opener.outcome = http_error(500)
    quiet = ResendEmailBackend(fail_silently=True)
    assert quiet.send_messages([EmailMessage("s", "b", SENDER, ["u@example.org"])]) == 0


# ---- failures never leak the key or the content -----------------------------------------------


def _assert_clean(text, *extra):
    for secret in (FAKE_KEY, *extra):
        assert secret not in text


def test_http_failure_reports_status_and_error_name_only(backend, opener, caplog):
    body = json.dumps(
        {"name": "validation_error", "message": "u@example.org is not allowed " + FAKE_KEY}
    ).encode()
    opener.outcome = http_error(422, body)
    message = EmailMessage("s", "secret-token-123", SENDER, ["u@example.org"])
    with caplog.at_level(logging.DEBUG), pytest.raises(ResendEmailError) as caught:
        backend.send_messages([message])
    text = str(caught.value)
    assert "HTTP 422" in text and "validation_error" in text
    _assert_clean(text + "".join(r.getMessage() for r in caplog.records), "u@example.org")
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("code", [400, 401, 403, 429, 500, 503])
def test_each_http_error_status_raises(backend, opener, code):
    opener.outcome = http_error(code, b"<html>gateway</html>")  # not JSON: still safe
    with pytest.raises(ResendEmailError, match=f"HTTP {code}"):
        backend.send_messages([EmailMessage("s", "b", SENDER, ["u@example.org"])])


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        urllib.error.URLError(ConnectionRefusedError("refused")),
        urllib.error.URLError(socket.gaierror("no dns")),
        OSError("ssl: certificate verify failed"),
    ],
)
def test_network_failures_and_timeouts_raise_a_safe_error(backend, opener, error):
    opener.outcome = error
    with pytest.raises(ResendEmailError) as caught:
        backend.send_messages([EmailMessage("s", "b", SENDER, ["u@example.org"])])
    _assert_clean(str(caught.value), "u@example.org", RESEND_API_URL)
    assert caught.value.__cause__ is None  # no chained exception carrying request details


@pytest.mark.parametrize(
    "outcome",
    [
        FakeResponse(200, b"not json"),
        FakeResponse(200, b"{}"),
        FakeResponse(200, b'{"id": 5}'),
        FakeResponse(200, b'{"id": ""}'),
        FakeResponse(200, b"[]"),
        FakeResponse(204, b""),
        FakeResponse(302, b""),
    ],
)
def test_unexpected_provider_responses_are_failures(backend, opener, outcome):
    opener.outcome = outcome
    with pytest.raises(ResendEmailError):
        backend.send_messages([EmailMessage("s", "b", SENDER, ["u@example.org"])])


@pytest.mark.parametrize("key", ["", "  ", " re_x", "re_x\n", "re_\x00x"])
def test_missing_or_malformed_api_key_fails_before_any_request(settings, opener, key):
    settings.RESEND_API_KEY = key
    with pytest.raises(ResendEmailError, match="RESEND_API_KEY"):
        ResendEmailBackend().send_messages([EmailMessage("s", "b", SENDER, ["u@example.org"])])
    assert opener.calls == []


def test_redirects_are_never_followed():
    """A 3xx must not resend the Authorization header to another location."""

    class Redirector(http.server.BaseHTTPRequestHandler):
        seen = []

        def do_POST(self):  # noqa: N802
            Redirector.seen.append(self.headers.get("Authorization"))
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/elsewhere")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/emails",
            data=b"{}",
            method="POST",
            headers={"Authorization": "Bearer " + FAKE_KEY},
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            email_backends._opener.open(request, timeout=5)
        assert caught.value.code == 307
        assert len(Redirector.seen) == 1  # the redirect target was never contacted
    finally:
        server.shutdown()
        server.server_close()


# ---- account flows through the Resend transport ----------------------------------------------


@pytest.fixture
def resend_flows(settings, opener):
    settings.EMAIL_BACKEND = "apps.core.email_backends.ResendEmailBackend"
    settings.RESEND_API_KEY = FAKE_KEY
    settings.DEFAULT_FROM_EMAIL = SENDER
    return opener


@pytest.mark.django_db
def test_password_reset_and_verification_emails_go_out_through_resend(
    account, resend_flows, caplog
):
    client = APIClient()
    with caplog.at_level(logging.DEBUG):
        assert client.post(RESET, {"email": account.email}).status_code == 202
        client.force_authenticate(account)
        assert client.post(VERIFY, {}).status_code == 202
    assert len(resend_flows.calls) == 2
    reset, verification = (json.loads(call[0].data) for call in resend_flows.calls)
    assert reset["to"] == verification["to"] == [account.email]
    assert reset["from"] == SENDER
    assert "/reset-password?" in reset["text"] and "token=" in reset["text"]
    assert "/verify-email?" in verification["text"]
    token = reset["text"].split("token=")[1].split()[0]
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert token not in logs and FAKE_KEY not in logs and "/reset-password" not in logs
    assert mail.outbox == []  # the Resend transport replaced locmem for these requests


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure",
    [http_error(500), http_error(422, b'{"name":"validation_error"}'), TimeoutError("t")],
)
def test_reset_anti_enumeration_is_unchanged_when_resend_fails(
    account, resend_flows, caplog, failure
):
    resend_flows.outcome = failure
    client = APIClient()
    with caplog.at_level(logging.ERROR):
        known = client.post(RESET, {"email": account.email})
        unknown = client.post(RESET, {"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    body = known.content.decode()
    for leak in (FAKE_KEY, "Resend", "HTTP 5", "Traceback"):
        assert leak not in body
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "delivery failed" in logs and FAKE_KEY not in logs
    assert len(resend_flows.calls) == 1  # unknown address never reaches the provider


@pytest.mark.django_db
def test_verification_is_a_typed_503_when_resend_fails(account, resend_flows):
    resend_flows.outcome = http_error(503)
    client = APIClient()
    client.force_authenticate(account)
    response = client.post(VERIFY, {})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "email_unavailable"
    for leak in (FAKE_KEY, "Resend", "HTTP 503"):
        assert leak not in response.content.decode()


@pytest.mark.django_db
def test_smtp_flows_still_use_the_django_backend_by_default(account):
    """Under pytest the transport is Django's in-memory backend: the SMTP path is untouched."""
    from django.conf import settings

    assert settings.EMAIL_PROVIDER == "django"
    APIClient().post(RESET, {"email": account.email})
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [account.email]


# ---- configuration and production checks -----------------------------------------------------


def resend_env(**extra):
    env = _production_env(
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY=FAKE_KEY,
        DEFAULT_FROM_EMAIL=SENDER,
    )
    env.pop("EMAIL_URL")  # no SMTP credentials are needed with Resend
    env.update(extra)
    return env


def test_valid_resend_configuration_passes_the_production_checks_without_smtp():
    done = _manage(["check", "--deploy", "--fail-level", "ERROR"], resend_env())
    assert done.returncode == 0, done.stderr[-2000:]
    for check_id in ("E001", "E011", "E012", "E013"):
        assert f"racheeta.{check_id}" not in done.stderr
    from_settings = _manage(
        ["shell", "-c", "from django.conf import settings as s; print(s.EMAIL_BACKEND)"],
        resend_env(),
    )
    assert (
        from_settings.stdout.strip().splitlines()[-1]
        == "apps.core.email_backends.ResendEmailBackend"
    )


def test_provider_name_is_case_and_space_insensitive():
    done = _manage(["check"], resend_env(EMAIL_PROVIDER=" Resend "))
    assert done.returncode == 0, done.stderr[-1500:]


@pytest.mark.parametrize("key", ["", " ", "re_has space", "re_tab\there"])
def test_missing_or_malformed_resend_key_stops_manage_check(key):
    done = _manage(["check"], resend_env(RESEND_API_KEY=key))
    assert done.returncode != 0 and "racheeta.E012" in done.stderr
    assert FAKE_KEY not in done.stderr


@pytest.mark.parametrize(
    "sender",
    [
        "Racheeta <no-reply@racheeta.local>",  # the development default
        "no-reply",
        "Racheeta <no-reply@localhost>",
        "<@mail.example.com>",
        "Racheeta <a@b@mail.example.com>",
        "Racheeta <no-reply@mail.invalid>",
    ],
)
def test_invalid_resend_sender_stops_manage_check(sender):
    done = _manage(["check"], resend_env(DEFAULT_FROM_EMAIL=sender))
    assert done.returncode != 0 and "racheeta.E013" in done.stderr


@pytest.mark.parametrize("provider", ["sendgrid", "smtp", "none", "resend2", "true"])
def test_unknown_provider_fails_closed_in_production_and_development(provider):
    for debug in ("false", "true"):
        done = _manage(["check"], _production_env(EMAIL_PROVIDER=provider, DEBUG=debug))
        assert done.returncode != 0 and "racheeta.E011" in done.stderr, (provider, debug)


def test_smtp_production_rules_are_unchanged():
    # explicit django provider + a real SMTP URL still passes
    ok = _manage(["check"], _production_env(EMAIL_PROVIDER="django"))
    assert ok.returncode == 0, ok.stderr[-1500:]
    # console/locmem are still refused in production, with or without a Resend key lying around
    bad = _manage(["check"], _production_env(EMAIL_URL="consolemail://", RESEND_API_KEY=FAKE_KEY))
    assert bad.returncode != 0 and "racheeta.E001" in bad.stderr
    # a Resend key alone does not switch transports
    assert "racheeta.E012" not in bad.stderr


def test_resend_mode_ignores_a_leftover_console_email_url():
    done = _manage(["check"], resend_env(EMAIL_URL="consolemail://"))
    assert done.returncode == 0, done.stderr[-1500:]


def test_other_production_checks_still_apply_in_resend_mode():
    for overrides, expected in (
        ({"SECRET_KEY": "weak"}, "racheeta.E009"),
        ({"FRONTEND_URL": "http://app.example.test"}, "racheeta.E010"),
        ({"TRUSTED_PROXY_COUNT": "0"}, "racheeta.E005"),
        ({"ALLOWED_HOSTS": "*"}, "racheeta.E006"),
        ({"CSRF_TRUSTED_ORIGINS": "http://app.example.test"}, "racheeta.E007"),
    ):
        done = _manage(["check"], resend_env(**overrides))
        assert done.returncode != 0 and expected in done.stderr, expected


def test_check_functions_in_process():
    from django.test import override_settings

    assert "racheeta.E012" in _ids(DEBUG=False, EMAIL_PROVIDER="resend", RESEND_API_KEY="")
    assert "racheeta.E012" not in _ids(DEBUG=True, EMAIL_PROVIDER="resend", RESEND_API_KEY="")
    with override_settings(
        DEBUG=False,
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY=FAKE_KEY,
        DEFAULT_FROM_EMAIL=SENDER,
        EMAIL_BACKEND="apps.core.email_backends.ResendEmailBackend",
    ):
        ids = _ids()
    assert not ids & {"racheeta.E001", "racheeta.E011", "racheeta.E012", "racheeta.E013"}
    assert sender_address_problem(SENDER) is None
    assert sender_address_problem("onboarding@resend.dev") is None
    assert sender_address_problem("")
