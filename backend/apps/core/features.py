"""Server-controlled product switches that the web app reads from `GET /api/v1/platform/features`.

RESERVATIONS_ENABLED (env `RESERVATIONS_ENABLED`, default OFF): online booking is being removed
from the product, reversibly. While OFF, new bookings and new appointment slots are refused with
the typed error `service_disabled`, public availability is empty and the web app hides every booking
entry point. Every table, row and history read stays; existing reservations can still be
cancelled or wound down. Setting the variable to true restores the previous behaviour.
"""

from django.conf import settings


def reservations_enabled() -> bool:
    return bool(settings.RACHEETA.get("RESERVATIONS_ENABLED", False))


def public_features() -> dict:
    """The switches a client may know about (no secrets, no per-user data)."""
    return {"reservations_enabled": reservations_enabled()}
