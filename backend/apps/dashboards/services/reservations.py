"""Reservation aggregates for the patient (own bookings) and the provider (received bookings).

Lists are `.values()` rows with an explicit allow-list of columns: private fields
(`patient_note`) and anything not named here can never reach a dashboard payload.
"""

from __future__ import annotations

from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus

from .common import RECENT_LIMIT, UPCOMING_LIMIT, status_counts

# A reservation that has not started yet and is still live (not rejected/cancelled/finished).
UPCOMING_STATUSES = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED)

_PATIENT_COLUMNS = (
    "id",
    "provider_name_snapshot",
    "service_title_snapshot",
    "starts_at",
    "ends_at",
    "status",
)


def _upcoming_filter(now) -> Q:
    return Q(status__in=UPCOMING_STATUSES, starts_at__gte=now)


def _counts(queryset: QuerySet, now) -> dict:
    counts = status_counts(
        queryset,
        "status",
        ReservationStatus.values,
        upcoming=Count("pk", filter=_upcoming_filter(now)),
    )
    return {
        "total": counts["total"],
        "by_status": counts["by_status"],
        "upcoming": counts["upcoming"],
    }


def patient_summary(account, *, now=None) -> dict:
    """3 queries: counts, upcoming list, recent list."""
    now = now or timezone.now()
    rows = Reservation.objects.filter(patient=account)
    return {
        "reservations": _counts(rows, now),
        "upcoming": list(
            rows.filter(_upcoming_filter(now))
            .order_by("starts_at", "id")
            .values(*_PATIENT_COLUMNS)[:UPCOMING_LIMIT]
        ),
        "recent": list(
            rows.order_by("-created_at", "-id").values(*_PATIENT_COLUMNS)[:RECENT_LIMIT]
        ),
    }


def provider_summary(profile, *, now=None) -> dict:
    """2 queries: counts, upcoming list. `patient_name` is what the provider's own reservation
    API already shows the provider; the patient's note is never selected."""
    now = now or timezone.now()
    rows = Reservation.objects.filter(provider=profile)
    upcoming = list(
        rows.filter(_upcoming_filter(now))
        .order_by("starts_at", "id")
        .values(*_PATIENT_COLUMNS, patient_name=F("patient__full_name"))[:UPCOMING_LIMIT]
    )
    return {"reservations": _counts(rows, now), "upcoming": upcoming}
