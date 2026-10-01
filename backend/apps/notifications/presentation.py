"""Localised title/body for a notification, computed at read time.

No prose is stored in the database. `render(event_type, payload, language)` is the
single mapping used by the REST API (request language) and, later, by any push
delivery (recipient.preferred_language). It never raises: unknown events and
malformed payloads fall back to a generic, safe message.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .types import NotificationEventType

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "ar"
SUPPORTED = ("ar", "en")

FALLBACK = {
    "ar": ("إشعار جديد", ""),
    "en": ("New notification", ""),
}

STATUS_LABEL = {
    "ar": {
        "PENDING": "قيد الانتظار",
        "CONFIRMED": "مؤكد",
        "COMPLETED": "مكتمل",
        "REJECTED": "مرفوض",
        "CANCELLED": "ملغى",
        "NO_SHOW": "لم يحضر",
    },
    "en": {
        "PENDING": "pending",
        "CONFIRMED": "confirmed",
        "COMPLETED": "completed",
        "REJECTED": "rejected",
        "CANCELLED": "cancelled",
        "NO_SHOW": "no-show",
    },
}

STATUS_TITLE = {
    "ar": {
        "PENDING": "الحجز قيد الانتظار",
        "CONFIRMED": "تم تأكيد الحجز",
        "COMPLETED": "اكتمل الحجز",
        "REJECTED": "تم رفض الحجز",
        "CANCELLED": "تم إلغاء الحجز",
        "NO_SHOW": "تم تسجيل عدم الحضور",
    },
    "en": {
        "PENDING": "Reservation pending",
        "CONFIRMED": "Reservation confirmed",
        "COMPLETED": "Reservation completed",
        "REJECTED": "Reservation rejected",
        "CANCELLED": "Reservation cancelled",
        "NO_SHOW": "Marked as no-show",
    },
}


def normalize_language(language: str | None) -> str:
    code = (language or "").lower().split("-")[0]
    return code if code in SUPPORTED else DEFAULT_LANGUAGE


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _when(payload: dict[str, Any]) -> str:
    raw = _text(payload, "starts_at")
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ""


def _created(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    service, when = _text(payload, "service_title"), _when(payload)
    if lang == "ar":
        title = "حجز جديد"
        body = "تم استلام حجز جديد"
        if service:
            body += f" لخدمة «{service}»"
        if when:
            body += f" بتاريخ {when}"
        return title, body + "."
    title = "New reservation"
    body = "A new reservation was requested"
    if service:
        body += f' for "{service}"'
    if when:
        body += f" on {when}"
    return title, body + "."


def _status_changed(lang: str, payload: dict[str, Any]) -> tuple[str, str] | None:
    status = _text(payload, "status")
    if status not in STATUS_TITLE[lang]:
        return None
    title = STATUS_TITLE[lang][status]
    service, provider = _text(payload, "service_title"), _text(payload, "provider_name")
    label = STATUS_LABEL[lang][status]
    if lang == "ar":
        body = "الحجز"
        if service:
            body += f" لخدمة «{service}»"
        if provider:
            body += f" لدى {provider}"
        return title, f"{body} — الحالة الآن: {label}."
    body = "The reservation"
    if service:
        body += f' for "{service}"'
    if provider:
        body += f" with {provider}"
    return title, f"{body} is now {label}."


def render(event_type: str, payload: Any, language: str | None) -> tuple[str, str]:
    """Return (title, body) for the event in `language`. Never raises."""
    lang = normalize_language(language)
    data = payload if isinstance(payload, dict) else {}
    try:
        if event_type == NotificationEventType.RESERVATION_CREATED:
            return _created(lang, data)
        if event_type == NotificationEventType.RESERVATION_STATUS_CHANGED:
            rendered = _status_changed(lang, data)
            if rendered is not None:
                return rendered
    except Exception:  # noqa: BLE001 — presentation must never break a read
        logger.exception("notification presentation failed for %s", event_type)
    return FALLBACK[lang]
