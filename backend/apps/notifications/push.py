"""Push transport boundary (Firebase Cloud Messaging).

Everything Firebase-specific lives here. The rest of the application asks
`push_service` to deliver a `PushMessage`; it never touches the SDK. PostgreSQL stays
authoritative: a push is a best-effort *hint* that something can be fetched.

Which sender runs comes from `settings.RACHEETA["PUSH_SENDER"]` (env `PUSH_SENDER`):

* `apps.notifications.push.DisabledPushSender` (default) — nothing is ever sent.
* `apps.notifications.push.FirebaseAdminPushSender` — real FCM delivery through the
  Firebase Admin SDK (`pip install firebase-admin`), using the same
  `FIREBASE_CREDENTIALS_FILE` service account as Firebase sign-in. Never committed.

Tests inject a fake sender; no test contacts Firebase.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

# Firebase error classes that mean "this registration token is dead for good".
# Everything else (quota, unavailable, internal, network, auth) is transient.
PUSH_APP_NAME = "racheeta-push"
PUSH_HTTP_TIMEOUT_SECONDS = 5

PERMANENT_TOKEN_ERRORS = frozenset({"UnregisteredError", "SenderIdMismatchError"})


@dataclass(frozen=True, slots=True)
class PushMessage:
    """Privacy-preserving push content. Text must never carry private data; `data` holds
    only opaque ids the app uses to fetch the authoritative record after authenticating."""

    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


class PushResult(enum.Enum):
    SENT = "sent"
    INVALID_TOKEN = "invalid_token"  # noqa: S105 - permanent: deactivate the local registration
    TRANSIENT_FAILURE = "transient_failure"  # temporary: keep the registration


class PushSender(Protocol):
    def send(self, token: str, message: PushMessage) -> PushResult: ...


class DisabledPushSender:
    """Default. Development, test and unconfigured environments never send."""

    def send(self, token: str, message: PushMessage) -> PushResult:  # pragma: no cover
        raise ImproperlyConfigured("Push delivery is not enabled on this server.")


def classify_firebase_error(exc: BaseException) -> PushResult:
    """Map an SDK exception to a delivery outcome (by class name, so it is SDK-version safe)."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if names & PERMANENT_TOKEN_ERRORS:
        return PushResult.INVALID_TOKEN
    return PushResult.TRANSIENT_FAILURE


class FirebaseAdminPushSender:
    """Sends one FCM message per registration token with the Firebase Admin SDK."""

    def __init__(self) -> None:
        try:
            import firebase_admin  # type: ignore[import-not-found]
            from firebase_admin import credentials, messaging  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise ImproperlyConfigured(
                "FirebaseAdminPushSender needs the 'firebase-admin' package."
            ) from exc
        credentials_file = settings.RACHEETA["FIREBASE_CREDENTIALS_FILE"]
        if not credentials_file:  # pragma: no cover
            raise ImproperlyConfigured("FIREBASE_CREDENTIALS_FILE is required for push delivery.")
        # A dedicated named app (not the sign-in default app) with a short HTTP timeout, so a
        # hanging FCM cannot hold a request thread for the SDK's 120 s default per device.
        try:
            self._app = firebase_admin.get_app(PUSH_APP_NAME)
        except ValueError:  # pragma: no cover - first use in this process
            self._app = firebase_admin.initialize_app(
                credentials.Certificate(credentials_file),
                options={"httpTimeout": PUSH_HTTP_TIMEOUT_SECONDS},
                name=PUSH_APP_NAME,
            )
        self._messaging = messaging

    def send(self, token: str, message: PushMessage) -> PushResult:  # pragma: no cover
        sdk = self._messaging
        try:
            sdk.send(
                sdk.Message(
                    token=token,
                    notification=sdk.Notification(title=message.title, body=message.body),
                    data=dict(message.data),
                ),
                app=self._app,
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises many subclasses
            return classify_firebase_error(exc)
        return PushResult.SENT


def get_sender_class() -> type:
    return import_string(settings.RACHEETA["PUSH_SENDER"])


def is_enabled() -> bool:
    return get_sender_class() is not DisabledPushSender


def get_sender() -> PushSender:
    return get_sender_class()()
