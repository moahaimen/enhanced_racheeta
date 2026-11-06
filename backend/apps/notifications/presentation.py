"""Localised title/body for a notification, computed at read time.

No prose is stored in the database. `render(event_type, payload, language)` is the
single mapping used by the REST API (request language) and, later, by any push
delivery (recipient.preferred_language). It never raises: unknown events and
malformed payloads fall back to a generic, safe message.
"""

from __future__ import annotations

import logging
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


def _created(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    # The appointment time is intentionally NOT rendered here. `starts_at` is a UTC instant
    # and Phase 9A has no canonical recipient timezone, so any clock text in this prose
    # would be wrong for someone. The reservation pages localise the real timestamp on the
    # client. A timezone-aware push presentation may revisit this in Phase 9C.
    service = _text(payload, "service_title")
    if lang == "ar":
        body = "تم استلام حجز جديد"
        if service:
            body += f" لخدمة «{service}»"
        return "حجز جديد", body + "."
    body = "A new reservation was requested"
    if service:
        body += f' for "{service}"'
    return "New reservation", body + "."


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


ORDER_STATUS = {
    "ar": {
        "PLACED": "تم استلام الطلب",
        "CONFIRMED": "تم تأكيد الطلب",
        "SHIPPED": "تم شحن الطلب",
        "DELIVERED": "تم تسليم الطلب",
        "COMPLETED": "اكتمل الطلب",
        "CANCELLED": "تم إلغاء الطلب",
        "PAID": "تم التحقق من الدفع",
        "REFUND_PENDING": "استرداد قيد المعالجة",
        "PARTIALLY_REFUNDED": "تم استرداد جزء من المبلغ",
        "REFUNDED": "تم استرداد المبلغ",
        "RETURN_REQUESTED": "طلب إرجاع جديد",
    },
    "en": {
        "PLACED": "Order received",
        "CONFIRMED": "Order confirmed",
        "SHIPPED": "Order shipped",
        "DELIVERED": "Order delivered",
        "COMPLETED": "Order completed",
        "CANCELLED": "Order cancelled",
        "PAID": "Payment verified",
        "REFUND_PENDING": "Refund pending",
        "PARTIALLY_REFUNDED": "Partial refund issued",
        "REFUNDED": "Refund issued",
        "RETURN_REQUESTED": "New return request",
    },
}
QUOTE_STATUS = {
    "ar": {
        "QUOTED": "وصل عرض سعر",
        "ACCEPTED": "تم قبول عرض السعر",
        "DECLINED": "تم رفض طلب التسعير",
        "WITHDRAWN": "تم سحب طلب التسعير",
    },
    "en": {
        "QUOTED": "Price quote received",
        "ACCEPTED": "Quote accepted",
        "DECLINED": "Quote request declined",
        "WITHDRAWN": "Quote request withdrawn",
    },
}
SPONSORED = {"ar": "إعلان ممول", "en": "Sponsored"}


def _pick(text: str, lang: str) -> str:
    """Demo/business names may be stored as "Arabic | English": show the reader's half."""
    parts = text.split(" | ")
    if len(parts) != 2:
        return text
    arabic = any("\u0600" <= ch <= "\u06ff" for ch in parts[0])
    return (parts[0] if arabic == (lang == "ar") else parts[1]).strip()


def _order(lang: str, payload: dict[str, Any]) -> tuple[str, str] | None:
    status = _text(payload, "status")
    number = _text(payload, "order_number")
    if status not in ORDER_STATUS[lang]:
        return None
    if lang == "ar":
        return ORDER_STATUS[lang][status], f"الطلب {number}".strip() + "."
    return ORDER_STATUS[lang][status], f"Order {number}".strip() + "."


def _quote_requested(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    product = _pick(_text(payload, "product_title"), lang)
    quantity = _text(payload, "quantity")
    if lang == "ar":
        return "طلب تسعير جديد", f"طلب سعر لـ «{product}» — الكمية {quantity}."
    return "New quote request", f'A price was requested for "{product}" (quantity {quantity}).'


def _quote_updated(lang: str, payload: dict[str, Any]) -> tuple[str, str] | None:
    status = _text(payload, "status")
    if status not in QUOTE_STATUS[lang]:
        return None
    product = _pick(_text(payload, "product_title"), lang)
    if lang == "ar":
        return QUOTE_STATUS[lang][status], f"طلب التسعير لـ «{product}»."
    return QUOTE_STATUS[lang][status], f'Quote request for "{product}".'


def _sponsored(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    product = _pick(_text(payload, "product_title"), lang)
    company = _pick(_text(payload, "company_name"), lang)
    if lang == "ar":
        return f"{SPONSORED[lang]} · منتج في مجالك", f"«{product}» من {company}."
    return f"{SPONSORED[lang]} · A product for your field", f'"{product}" by {company}.'


def _promotion(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    listing = _pick(_text(payload, "listing_title"), lang)
    if lang == "ar":
        return f"{SPONSORED[lang]} · عقار طبي", f"«{listing}» — لأنك فعّلت عروض العقارات."
    return (
        f"{SPONSORED[lang]} · Medical property",
        f'"{listing}" — you opted in to property offers.',
    )


def _stock_low(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    product = _pick(_text(payload, "product_title"), lang)
    left = _text(payload, "quantity")
    if lang == "ar":
        return "المخزون منخفض", f"تبقّى {left} من «{product}»."
    return "Low stock", f'{left} left of "{product}".'


def _settlement_paid(lang: str, payload: dict[str, Any]) -> tuple[str, str]:
    amount = _text(payload, "amount")
    if lang == "ar":
        return "تم تسجيل دفعة مستحقاتك", f"{amount} د.ع (محاكاة — لا أموال حقيقية)."
    return "Payout recorded", f"{amount} IQD (simulated — no real money)."


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
        if event_type in (
            NotificationEventType.ORDER_PLACED,
            NotificationEventType.ORDER_STATUS_CHANGED,
        ):
            rendered = _order(lang, data)
            if rendered is not None:
                return rendered
        if event_type == NotificationEventType.QUOTE_REQUESTED:
            return _quote_requested(lang, data)
        if event_type == NotificationEventType.QUOTE_UPDATED:
            rendered = _quote_updated(lang, data)
            if rendered is not None:
                return rendered
        if event_type == NotificationEventType.SPONSORED_PRODUCT:
            return _sponsored(lang, data)
        if event_type == NotificationEventType.PROPERTY_PROMOTION:
            return _promotion(lang, data)
        if event_type == NotificationEventType.STOCK_LOW:
            return _stock_low(lang, data)
        if event_type == NotificationEventType.SETTLEMENT_PAID:
            return _settlement_paid(lang, data)
    except Exception:  # noqa: BLE001 — presentation must never break a read
        logger.exception("notification presentation failed for %s", event_type)
    return FALLBACK[lang]
