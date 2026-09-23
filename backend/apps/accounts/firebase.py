"""Firebase Authentication adapter boundary.

The API endpoint (`POST /api/v1/auth/firebase/exchange`) depends only on the
`FirebaseVerifier` protocol below. Which implementation is used comes from
`settings.RACHEETA["FIREBASE_VERIFIER"]` (env `FIREBASE_VERIFIER`):

* `apps.accounts.firebase.DisabledVerifier` (default) — endpoint answers 503.
* `apps.accounts.firebase.FirebaseAdminVerifier` — real verification with the
  Firebase Admin SDK. Requires `pip install firebase-admin` and
  `FIREBASE_CREDENTIALS_FILE` pointing at a service-account JSON that is
  provided by the platform environment, never committed.

Tests inject a fake verifier through `override_settings`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


@dataclass(frozen=True, slots=True)
class FirebaseIdentity:
    """The subset of verified Firebase claims Racheeta relies on."""

    uid: str
    email: str | None
    email_verified: bool
    phone_number: str | None = None
    name: str | None = None
    sign_in_provider: str | None = None


class FirebaseTokenInvalid(Exception):
    """Raised by verifiers when the ID token is not valid for this project."""


class FirebaseNotConfigured(Exception):
    """Raised when no real verifier is configured."""


class FirebaseVerifier(Protocol):
    def verify(self, id_token: str) -> FirebaseIdentity: ...


class DisabledVerifier:
    def verify(self, id_token: str) -> FirebaseIdentity:
        raise FirebaseNotConfigured("Firebase sign-in is not enabled on this server.")


class FirebaseAdminVerifier:
    """Verifies ID tokens with the Firebase Admin SDK (server-side, never trusts claims)."""

    def __init__(self) -> None:
        try:
            import firebase_admin  # type: ignore[import-not-found]
            from firebase_admin import auth as firebase_auth  # type: ignore[import-not-found]
            from firebase_admin import credentials  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise ImproperlyConfigured(
                "FirebaseAdminVerifier needs the 'firebase-admin' package "
                "(pip install firebase-admin)."
            ) from exc
        credentials_file = settings.RACHEETA["FIREBASE_CREDENTIALS_FILE"]
        if not credentials_file:  # pragma: no cover
            raise ImproperlyConfigured(
                "FIREBASE_CREDENTIALS_FILE is required for FirebaseAdminVerifier."
            )
        if not firebase_admin._apps:  # pragma: no cover
            firebase_admin.initialize_app(credentials.Certificate(credentials_file))
        self._auth = firebase_auth

    def verify(self, id_token: str) -> FirebaseIdentity:  # pragma: no cover - needs credentials
        try:
            claims = self._auth.verify_id_token(id_token, check_revoked=True)
        except Exception as exc:  # noqa: BLE001 - SDK raises several subclasses
            raise FirebaseTokenInvalid(str(exc)) from exc
        firebase_claims = claims.get("firebase", {})
        return FirebaseIdentity(
            uid=claims["uid"],
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
            phone_number=claims.get("phone_number"),
            name=claims.get("name"),
            sign_in_provider=firebase_claims.get("sign_in_provider"),
        )


def get_verifier_class() -> type:
    return import_string(settings.RACHEETA["FIREBASE_VERIFIER"])


def get_verifier() -> FirebaseVerifier:
    return get_verifier_class()()


def is_enabled() -> bool:
    return get_verifier_class() is not DisabledVerifier
