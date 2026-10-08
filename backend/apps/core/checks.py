"""Project-level system checks (run by `manage.py check` and at startup)."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security)
def check_email_backend_in_production(app_configs, **kwargs):
    """Console/locmem email backends print reset tokens to logs. Never in prod."""
    backend = settings.EMAIL_BACKEND
    if settings.DEBUG:
        return []
    if backend.endswith(("console.EmailBackend", "locmem.EmailBackend", "dummy.EmailBackend")):
        return [
            Error(
                f"EMAIL_BACKEND is {backend!r} while DEBUG is False. Password-reset and "
                "verification tokens would be written to logs. Set EMAIL_URL to a real provider.",
                id="racheeta.E001",
            )
        ]
    return []


@register(Tags.security)
def check_firebase_verifier_importable(app_configs, **kwargs):
    from apps.accounts.firebase import get_verifier_class

    try:
        get_verifier_class()
    except Exception as exc:  # noqa: BLE001 - surface any import/config problem
        return [Error(f"RACHEETA['FIREBASE_VERIFIER'] cannot be loaded: {exc}", id="racheeta.E002")]
    return []


def frontend_url_problem(url: str) -> str | None:
    """Why `url` cannot be the production web origin, or None when it can.

    Password-reset and e-mail-verification pages carry one-time credentials in their query string,
    so the origin used to build those links must be an https origin and nothing else. The value is
    never echoed back (it could contain credentials). The setting is already stripped of trailing
    slashes (`settings.RACHEETA["FRONTEND_URL"]`), so `https://app.example.com/` is accepted.
    """
    if not url or url != url.strip() or any(ch.isspace() for ch in url):
        return "is empty or contains whitespace"
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError on a malformed port
    except ValueError:
        return "is not a valid URL"
    if parts.scheme != "https":
        return "must use https (cleartext http would put one-time links on the wire)"
    if not parts.hostname:
        return "has no host"
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        return "must not contain credentials"
    if parts.query or parts.fragment or "?" in url or "#" in url:
        return "must not contain a query string or fragment"
    if parts.path not in ("", "/"):
        return "must be an origin only, without a path"
    return None


@register(Tags.security)
def check_frontend_url(app_configs, **kwargs):
    """Production e-mail links must be built from a valid https origin (racheeta.E010)."""
    if settings.DEBUG:
        return []
    problem = frontend_url_problem(settings.RACHEETA["FRONTEND_URL"])
    if problem is None:
        return []
    return [
        Error(
            f"FRONTEND_URL {problem}. Set it to the public https origin of the web app, e.g. "
            "https://app.example.com (no path, query or credentials).",
            id="racheeta.E010",
        )
    ]


@register(Tags.security)
def check_push_sender(app_configs, **kwargs):
    """Push is optional: when unconfigured nothing is sent (safe). A selected Firebase
    sender without credentials, or an unloadable sender, is a configuration error."""
    from apps.notifications.push import FirebaseAdminPushSender, get_sender_class

    try:
        sender_class = get_sender_class()
    except Exception as exc:  # noqa: BLE001
        return [Error(f"RACHEETA['PUSH_SENDER'] cannot be loaded: {exc}", id="racheeta.E003")]
    if (
        sender_class is FirebaseAdminPushSender
        and not settings.RACHEETA["FIREBASE_CREDENTIALS_FILE"]
    ):
        return [
            Error(
                "PUSH_SENDER is FirebaseAdminPushSender but FIREBASE_CREDENTIALS_FILE is empty.",
                id="racheeta.E004",
            )
        ]
    if not settings.DEBUG and sender_class.__name__ == "DisabledPushSender":
        return [
            Warning(
                "Push delivery is disabled (PUSH_SENDER). Notifications and chat still work; "
                "devices receive no push until a sender is configured.",
                id="racheeta.W001",
            )
        ]
    return []


@register(Tags.security)
def check_proxy_trust(app_configs, **kwargs):
    """Behind a TLS-terminating proxy the client address comes from X-Forwarded-For.

    DRF keys anonymous throttles on that address. With `NUM_PROXIES = 0` it uses REMOTE_ADDR,
    i.e. the proxy itself: every visitor would share one login/password-reset bucket. Without a
    trusted count it would instead believe the whole header, which a client can rotate to dodge
    the throttle.
    """
    if settings.DEBUG or not getattr(settings, "SECURE_PROXY_SSL", False):
        return []
    proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES")
    if not proxies:
        return [
            Error(
                "SECURE_PROXY_SSL is true (a reverse proxy is in front) but TRUSTED_PROXY_COUNT is "
                "0: throttles would key on the proxy address. Set TRUSTED_PROXY_COUNT to the "
                "number of proxies in front of gunicorn (Railway: 1; verify in staging, "
                "docs/RAILWAY.md).",
                id="racheeta.E005",
            )
        ]
    return []


MIN_SECRET_KEY_LENGTH = 50
PLACEHOLDER_SECRET_PREFIXES = ("change-me", "build-time-placeholder", "django-insecure-")


def secret_key_problem(secret: str) -> str | None:
    """Why `secret` is unfit to sign production credentials, or None. Never echoes the value."""
    if not secret or len(secret) < MIN_SECRET_KEY_LENGTH:
        return f"is shorter than {MIN_SECRET_KEY_LENGTH} characters"
    if secret.lower().startswith(PLACEHOLDER_SECRET_PREFIXES):
        return "looks like a placeholder (change-me / build-time-placeholder / django-insecure-)"
    if len(set(secret)) < 5:
        return "has almost no variety of characters"
    return None


@register(Tags.security)
def check_production_hosts_and_secret(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    errors = []
    if "*" in settings.ALLOWED_HOSTS or not settings.ALLOWED_HOSTS:
        errors.append(
            Error(
                "ALLOWED_HOSTS is empty or contains '*' while DEBUG is False.",
                id="racheeta.E006",
            )
        )
    problem = secret_key_problem(settings.SECRET_KEY)
    if problem:
        errors.append(
            Error(
                f"SECRET_KEY {problem}. It is SimpleJWT's HMAC signing key and also signs "
                "password-reset tokens and sessions, so a guessable value lets anyone forge "
                "logins. Generate one: "
                'python3 -c "import secrets; print(secrets.token_urlsafe(64))"',
                id="racheeta.E009",
            )
        )
    return errors


@register(Tags.security)
def check_csrf_origins_https(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    insecure = [o for o in settings.CSRF_TRUSTED_ORIGINS if not o.startswith("https://")]
    if insecure:
        return [
            Error(
                "CSRF_TRUSTED_ORIGINS must be https:// origins in production "
                f"(found {len(insecure)} that are not).",
                id="racheeta.E007",
            )
        ]
    return []


@register(Tags.security)
def check_email_timeout(app_configs, **kwargs):
    if not settings.DEBUG and not settings.EMAIL_TIMEOUT:
        return [
            Error(
                "EMAIL_TIMEOUT is not set: a stalled SMTP server would hold a worker indefinitely.",
                id="racheeta.E008",
            )
        ]
    return []


@register(Tags.security)
def check_api_docs_exposure(app_configs, **kwargs):
    if not settings.DEBUG and getattr(settings, "API_DOCS_ENABLED", False):
        return [
            Warning(
                "API_DOCS_ENABLED is true in production: /api/docs/ and /api/schema/ are public "
                "and served without a Content-Security-Policy.",
                id="racheeta.W003",
            )
        ]
    return []
