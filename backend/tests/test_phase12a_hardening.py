"""Phase 12A production-hardening guards: readiness, request ids, CSP, logging, throttling,
production checks, token pruning, API-docs exposure."""

import json
import logging
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.checks import run_checks
from django.core.management import call_command
from django.db import OperationalError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core import middleware
from apps.core.logging import JsonFormatter, redact
from apps.core.throttling import UserWritesThrottle

BACKEND = Path(__file__).resolve().parent.parent


# --- readiness vs liveness --------------------------------------------------------------


@pytest.mark.django_db
def test_ready_checks_the_database(client):
    response = client.get("/ready/")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response["Cache-Control"].startswith("max-age=0")


@pytest.mark.django_db
def test_ready_fails_closed_without_leaking_anything(client, monkeypatch):
    def broken(*_args, **_kwargs):
        raise OperationalError("could not connect to server at db.internal:5432 password=hunter2")

    monkeypatch.setattr("django.db.backends.base.base.BaseDatabaseWrapper.cursor", broken)
    response = client.get("/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    body = response.content.decode()
    for secret in ("db.internal", "hunter2", "5432", "OperationalError", "Traceback"):
        assert secret not in body


def test_liveness_still_ignores_the_database(client, monkeypatch):
    monkeypatch.setattr(
        "django.db.backends.base.base.BaseDatabaseWrapper.cursor",
        lambda *a, **k: pytest.fail("liveness must not touch the database"),
    )
    assert client.get("/health/").status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_ready_rejects_non_get(client, method):
    assert getattr(client, method)("/ready/").status_code == 405


def test_ready_and_health_are_exempt_from_the_ssl_redirect_only_when_proxied():
    env = _production_env()
    out = _run(
        "from django.conf import settings; print(settings.SECURE_REDIRECT_EXEMPT, "
        "'healthcheck.railway.app' in settings.ALLOWED_HOSTS)",
        env,
    )
    assert "^health/$" in out and "^ready/$" in out and out.strip().endswith("True")
    out = _run(
        "from django.conf import settings; print(getattr(settings, 'SECURE_REDIRECT_EXEMPT', []))",
        {**env, "SECURE_PROXY_SSL": "false"},
    )
    assert out.strip() == "[]"


# --- request id -------------------------------------------------------------------------


def test_every_response_carries_a_request_id(client):
    response = client.get("/health/")
    assert len(response["X-Request-ID"]) == 32  # server generated uuid4 hex


def test_a_well_formed_client_request_id_is_kept(client):
    response = client.get("/health/", HTTP_X_REQUEST_ID="trace-abc_123.XYZ")
    assert response["X-Request-ID"] == "trace-abc_123.XYZ"


@pytest.mark.parametrize(
    "bad",
    [
        "short",
        "x" * 65,
        "has space inside",
        "line\r\nInjected: header",
        "<script>alert(1)</script>",
        "",
    ],
)
def test_a_malformed_request_id_is_replaced_not_reflected(client, bad):
    try:
        response = client.get("/health/", HTTP_X_REQUEST_ID=bad)
    except ValueError:  # the test client itself refuses a newline in a header
        return
    assert response["X-Request-ID"] != bad
    assert len(response["X-Request-ID"]) == 32


def test_the_request_id_reaches_log_records(client, caplog):
    seen = {}

    class Capture(logging.Handler):
        def emit(self, record):
            seen["id"] = middleware.current_request_id()

    logger = logging.getLogger("test.request_id")
    logger.addHandler(Capture())
    logger.setLevel(logging.INFO)
    token = middleware.request_id_var.set("rid-1234567")
    try:
        logger.info("hello")
    finally:
        middleware.request_id_var.reset(token)
    assert seen["id"] == "rid-1234567"
    assert middleware.current_request_id() == "-"


# --- security headers ---------------------------------------------------------------------


def test_app_documents_get_a_strict_csp_and_permissions_policy(client):
    response = client.get("/some/spa/route")
    csp = response["Content-Security-Policy"]
    directives = {d.split(" ")[0]: d for d in csp.split("; ")}
    assert directives["default-src"] == "default-src 'self'"
    assert directives["script-src"] == "script-src 'self'"
    assert directives["object-src"] == "object-src 'none'"
    assert directives["base-uri"] == "base-uri 'self'"
    assert directives["frame-ancestors"] == "frame-ancestors 'none'"
    assert directives["form-action"] == "form-action 'self'"
    assert "connect-src 'self'" == directives["connect-src"]
    assert "unsafe-eval" not in csp
    assert "unsafe-inline" not in csp
    assert "https://fonts.googleapis.com" in directives["style-src"]
    assert "https://fonts.gstatic.com" in directives["font-src"]
    assert "upgrade-insecure-requests" not in csp  # only behind TLS (SECURE_PROXY_SSL)
    assert "camera=()" in response["Permissions-Policy"]
    assert "microphone=()" in response["Permissions-Policy"]


def test_api_responses_may_load_nothing(client):
    response = client.get("/api/v1/me")
    assert response["Content-Security-Policy"].startswith("default-src 'none'")
    assert "frame-ancestors 'none'" in response["Content-Security-Policy"]


@pytest.mark.django_db
def test_admin_has_its_own_policy_without_inline_scripts(client):
    response = client.get("/" + settings.ADMIN_URL_PATH + "login/")
    assert response.status_code == 200
    csp = response["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-eval" not in csp
    html = response.content.decode()
    import re

    inline = [m for m in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html)]
    assert inline == [], "the admin policy forbids inline scripts, so none may appear"


def test_existing_security_headers_are_not_duplicated_or_weakened(client):
    response = client.get("/health/")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "no-referrer"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers.get("Content-Security-Policy") is not None


def test_a_view_defined_csp_is_never_overwritten(rf):
    from django.http import HttpResponse

    handler = middleware.SecurityHeadersMiddleware(
        lambda r: HttpResponse(headers={"Content-Security-Policy": "default-src 'none'"})
    )
    assert handler(rf.get("/x"))["Content-Security-Policy"] == "default-src 'none'"


def test_csp_is_off_in_debug_and_connect_src_is_extendable(rf):
    from django.http import HttpResponse

    with override_settings(DEBUG=True):
        handler = middleware.SecurityHeadersMiddleware(lambda r: HttpResponse())
        assert "Content-Security-Policy" not in handler(rf.get("/x"))
    with override_settings(
        DEBUG=False, CSP_CONNECT_SRC=["https://api.example.test"], SECURE_PROXY_SSL=True
    ):
        handler = middleware.SecurityHeadersMiddleware(lambda r: HttpResponse())
        csp = handler(rf.get("/x"))["Content-Security-Policy"]
        assert "connect-src 'self' https://api.example.test" in csp
        assert "upgrade-insecure-requests" in csp


# --- the shipped web build is compatible with the policy ------------------------------------


def test_the_web_entry_has_no_inline_script_or_style_blocks():
    index = (BACKEND.parent / "web" / "index.html").read_text()
    import re

    assert re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", index) == []
    assert "<style" not in index
    # the only third-party origins are the two Google Fonts hosts the policy allows
    origins = set(re.findall(r"https://([a-z.]+)/", index))
    assert origins <= {"fonts.googleapis.com", "fonts.gstatic.com"}


# --- logging --------------------------------------------------------------------------------


def _record(msg, **kwargs):
    return logging.LogRecord("racheeta.test", logging.INFO, __file__, 1, msg, (), None, **kwargs)


def test_json_log_line_shape_and_request_id():
    token = middleware.request_id_var.set("rid-abcdefgh")
    try:
        line = JsonFormatter().format(_record("hello world"))
    finally:
        middleware.request_id_var.reset(token)
    entry = json.loads(line)
    assert set(entry) == {"ts", "level", "logger", "msg", "request_id"}
    assert entry["msg"] == "hello world" and entry["request_id"] == "rid-abcdefgh"
    assert "\n" not in line


def test_json_logging_redacts_credentials_and_cannot_leak_extras():
    secret_jwt = "eyJhbGciOi.eyJzdWIiOjF9.c2lnbmF0dXJl"
    record = _record(
        f"auth Bearer {secret_jwt} token=abc123 password: hunter2 user a.b@example.com ok"
    )
    record.password = "from-extra"  # a stray extra= value must never be emitted
    record.request_body = "private message"
    line = JsonFormatter().format(record)
    for leaked in (
        secret_jwt,
        "abc123",
        "hunter2",
        "a.b@example.com",
        "from-extra",
        "private message",
    ):
        assert leaked not in line
    assert "[redacted" in line


def test_exception_text_is_redacted_in_the_log_line():
    try:
        raise RuntimeError("failed with refresh=eyJaaa.bbb.ccc")
    except RuntimeError:
        import sys as _sys

        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", (), _sys.exc_info())
    entry = json.loads(JsonFormatter().format(record))
    assert "eyJaaa" not in entry["exc"] and "RuntimeError" in entry["exc"]


def test_redact_is_idempotent_and_harmless_on_clean_text():
    assert redact("GET /api/v1/jobs 200 12ms") == "GET /api/v1/jobs 200 12ms"
    assert redact(redact("password=x")) == redact("password=x")


def test_5xx_do_not_leak_internals_to_the_client(client, monkeypatch):
    def explode(*_a, **_k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("apps.core.views.health", explode, raising=False)
    from django.test import Client

    quiet = Client(raise_request_exception=False)
    monkeypatch.setattr("django.db.backends.base.base.BaseDatabaseWrapper.cursor", explode)
    response = quiet.get("/api/v1/geo/governorates")
    assert response.status_code == 500
    assert b"secret internal detail" not in response.content
    assert b"Traceback" not in response.content


# --- throttling -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_state_changing_requests_are_throttled_per_account_but_reads_are_not(
    account_factory, monkeypatch
):
    monkeypatch.setitem(UserWritesThrottle.THROTTLE_RATES, "user_writes", "3/hour")
    a, b = account_factory(), account_factory()

    def client_for(user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    ca, cb = client_for(a), client_for(b)
    statuses = [ca.post("/api/v1/notifications/read-all/", {}).status_code for _ in range(5)]
    assert statuses[:3] == [200, 200, 200] and statuses[3:] == [429, 429]
    # reads are never counted
    assert all(ca.get("/api/v1/notifications/unread-count/").status_code == 200 for _ in range(6))
    # another account has its own bucket
    assert cb.post("/api/v1/notifications/read-all/", {}).status_code == 200


@pytest.mark.django_db
def test_anonymous_and_scoped_endpoints_are_untouched_by_the_write_throttle(client, monkeypatch):
    monkeypatch.setitem(UserWritesThrottle.THROTTLE_RATES, "user_writes", "1/hour")
    for _ in range(3):
        assert client.post(
            "/api/v1/auth/login",
            {"email": "x@example.com", "password": "nope"},
            content_type="application/json",
        ).status_code in (400, 401)


def test_the_default_rate_is_set_and_proxy_count_is_configurable():
    assert "user_writes" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert "NUM_PROXIES" in settings.REST_FRAMEWORK


# --- production checks ------------------------------------------------------------------------


def _ids(**overrides):
    with override_settings(**overrides):
        return {c.id for c in run_checks()}


def test_proxy_without_a_trusted_count_is_an_error():
    rest = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    assert "racheeta.E005" in _ids(DEBUG=False, SECURE_PROXY_SSL=True, REST_FRAMEWORK=rest)
    rest = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    assert "racheeta.E005" not in _ids(DEBUG=False, SECURE_PROXY_SSL=True, REST_FRAMEWORK=rest)
    assert "racheeta.E005" not in _ids(DEBUG=False, SECURE_PROXY_SSL=False)


def test_wildcard_or_empty_hosts_are_an_error_in_production():
    assert "racheeta.E006" in _ids(DEBUG=False, ALLOWED_HOSTS=["*"])
    assert "racheeta.E006" in _ids(DEBUG=False, ALLOWED_HOSTS=[])
    assert "racheeta.E006" not in _ids(DEBUG=False, ALLOWED_HOSTS=["app.example.test"])


def test_non_https_csrf_origins_are_an_error_in_production():
    assert "racheeta.E007" in _ids(DEBUG=False, CSRF_TRUSTED_ORIGINS=["http://app.example.test"])
    assert "racheeta.E007" not in _ids(
        DEBUG=False, CSRF_TRUSTED_ORIGINS=["https://app.example.test"]
    )


def test_missing_email_timeout_is_an_error_and_the_default_is_finite():
    assert settings.EMAIL_TIMEOUT == 10
    assert "racheeta.E008" in _ids(DEBUG=False, EMAIL_TIMEOUT=None)


def test_weak_secret_key_and_public_docs_are_flagged():
    assert "racheeta.W002" in _ids(DEBUG=False, SECRET_KEY="change-me-" + "x" * 60)
    assert "racheeta.W002" in _ids(DEBUG=False, SECRET_KEY="short")
    assert "racheeta.W003" in _ids(DEBUG=False, API_DOCS_ENABLED=True)
    assert "racheeta.W003" not in _ids(DEBUG=False, API_DOCS_ENABLED=False)


def _production_env(**extra):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", ""),
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "SECRET_KEY": "fake-production-key-" + "k" * 60,
        "DEBUG": "false",
        "ALLOWED_HOSTS": "app.example.test",
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL", "postgres://racheeta:racheeta@localhost:5432/racheeta"
        ),
        "SECURE_PROXY_SSL": "true",
        "TRUSTED_PROXY_COUNT": "1",
        "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
        "FRONTEND_URL": "https://app.example.test",
        "EMAIL_URL": "smtp://user:pw@smtp.example.test:587?tls=True",
    }
    env.update(extra)
    return env


def _run(code, env):
    done = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [sys.executable, "-c", f"import django;django.setup();{code}"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout


def _manage(args, env):
    return subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [sys.executable, "manage.py", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_manage_check_deploy_passes_with_safe_fake_production_values():
    done = _manage(["check", "--deploy", "--fail-level", "ERROR"], _production_env())
    assert done.returncode == 0, done.stderr[-3000:]
    # the only deploy warnings left are the three accepted ones (documented in docs/SECURITY.md)
    ids = {
        line.split("(")[1].split(")")[0]
        for line in done.stderr.splitlines()
        if "(" in line and ")" in line and ": (" in line
    }
    assert ids <= {
        "racheeta.W001",  # push delivery disabled until configured
        "drf_spectacular.W001",
        "drf_spectacular.W002",
    }, ids
    # HSTS rollout settings are present and conservative
    out = _run(
        "from django.conf import settings as s; "
        "print(s.SECURE_HSTS_SECONDS, s.SECURE_HSTS_PRELOAD, "
        "s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_SSL_REDIRECT, s.DEBUG)",
        _production_env(),
    )
    assert out.split() == ["2592000", "False", "True", "True", "True", "False"]


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"ALLOWED_HOSTS": "*"}, "racheeta.E006"),
        ({"TRUSTED_PROXY_COUNT": "0"}, "racheeta.E005"),
        ({"CSRF_TRUSTED_ORIGINS": "http://app.example.test"}, "racheeta.E007"),
        ({"EMAIL_URL": "consolemail://"}, "racheeta.E001"),
    ],
)
def test_manage_check_rejects_obviously_unsafe_production_settings(overrides, expected):
    done = _manage(["check"], _production_env(**overrides))
    assert done.returncode != 0
    assert expected in done.stderr


def test_api_docs_are_off_in_production_and_on_only_when_enabled():
    off = _run(
        "from django.urls import resolve, Resolver404\n"
        "try:\n resolve('/api/docs/'); print('served')\nexcept Resolver404:\n print('absent')",
        _production_env(),
    )
    # '/api/docs/' falls into the reserved 'api/' space: it is not served in production
    assert off.strip() == "absent" or "served" not in off
    on = _run(
        "from django.urls import resolve; print(resolve('/api/docs/').url_name)",
        _production_env(API_DOCS_ENABLED="true"),
    )
    assert on.strip() == "openapi-docs"


def test_docs_endpoints_are_404_under_the_test_settings(client):
    assert client.get("/api/docs/").status_code == 404
    assert client.get("/api/schema/").status_code == 404


# --- JWT blacklist pruning -----------------------------------------------------------------------


def _token(user, *, expires_in, blacklisted=False, n=0):
    token = OutstandingToken.objects.create(
        user=user,
        jti=f"jti-{user.pk}-{n}-{expires_in.total_seconds()}-{blacklisted}",
        token="x",
        created_at=timezone.now() - timedelta(days=30),
        expires_at=timezone.now() + expires_in,
    )
    if blacklisted:
        BlacklistedToken.objects.create(token=token)
    return token


@pytest.mark.django_db
def test_prune_deletes_only_expired_tokens_and_is_idempotent(account, capsys):
    expired = _token(account, expires_in=timedelta(days=-1), n=1)
    expired_revoked = _token(account, expires_in=timedelta(days=-2), blacklisted=True, n=2)
    live = _token(account, expires_in=timedelta(days=5), n=3)
    live_revoked = _token(account, expires_in=timedelta(days=5), blacklisted=True, n=4)

    call_command("prune_expired_tokens", "--dry-run")
    assert OutstandingToken.objects.count() == 4
    assert "would delete 2" in capsys.readouterr().out

    call_command("prune_expired_tokens", "--batch-size", "1")
    remaining = set(OutstandingToken.objects.values_list("pk", flat=True))
    assert remaining == {live.pk, live_revoked.pk}
    assert not OutstandingToken.objects.filter(pk__in=[expired.pk, expired_revoked.pk]).exists()
    # a revoked-but-unexpired token must stay revoked
    assert BlacklistedToken.objects.filter(token=live_revoked).exists()

    call_command("prune_expired_tokens")  # second run: nothing to do, no error
    assert OutstandingToken.objects.count() == 2
    assert "deleted 0" in capsys.readouterr().out
