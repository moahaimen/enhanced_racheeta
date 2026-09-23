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
