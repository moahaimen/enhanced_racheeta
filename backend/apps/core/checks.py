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
