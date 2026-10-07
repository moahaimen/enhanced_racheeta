"""Project-level system checks (run by `manage.py check` and at startup)."""

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


@register(Tags.security)
def check_frontend_url(app_configs, **kwargs):
    url = settings.RACHEETA["FRONTEND_URL"]
    if not settings.DEBUG and not url.startswith("https://"):
        return [
            Warning(
                f"RACHEETA['FRONTEND_URL'] is {url!r}; email links should use https in production.",
                id="racheeta.W001",
            )
        ]
    return []


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
    secret = settings.SECRET_KEY
    if len(secret) < 50 or secret.startswith(("change-me", "build-time-placeholder")):
        errors.append(
            Warning(
                "SECRET_KEY looks weak or like a placeholder; use 64+ random characters "
                "(it signs JWTs, password-reset tokens and sessions).",
                id="racheeta.W002",
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
