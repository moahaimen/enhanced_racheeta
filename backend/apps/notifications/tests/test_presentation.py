import pytest

from apps.notifications import presentation
from apps.notifications.types import NotificationEventType

STATUSES = ["PENDING", "CONFIRMED", "COMPLETED", "REJECTED", "CANCELLED", "NO_SHOW"]
PAYLOAD = {
    "service_title": "Consultation",
    "provider_name": "Dr Notify",
    "starts_at": "2030-01-02T09:30:00+00:00",
}


@pytest.mark.parametrize("language", ["ar", "en"])
@pytest.mark.parametrize("status", STATUSES)
def test_every_status_has_localised_text(language, status):
    title, body = presentation.render(
        NotificationEventType.RESERVATION_STATUS_CHANGED, {**PAYLOAD, "status": status}, language
    )
    fallback = presentation.FALLBACK[language]
    assert title and body
    assert (title, body) != fallback
    assert "Consultation" in body and "Dr Notify" in body


def test_statuses_are_distinct_per_language():
    for language in ("ar", "en"):
        titles = {
            presentation.render(
                NotificationEventType.RESERVATION_STATUS_CHANGED, {"status": s}, language
            )[0]
            for s in STATUSES
        }
        assert len(titles) == len(STATUSES)


def test_created_prose_is_localised_and_never_renders_the_utc_clock_time():
    # `starts_at` is UTC and there is no recipient timezone in Phase 9A, so the prose must
    # not print a clock value that a UTC+3 reader would see as three hours wrong.
    ar = presentation.render(NotificationEventType.RESERVATION_CREATED, PAYLOAD, "ar")
    en = presentation.render(NotificationEventType.RESERVATION_CREATED, PAYLOAD, "en")
    assert ar != en
    assert ar == ("حجز جديد", "تم استلام حجز جديد لخدمة «Consultation».")
    assert en == ("New reservation", 'A new reservation was requested for "Consultation".')
    for text in (*ar, *en):
        assert "09:30" not in text
        assert "2030" not in text


@pytest.mark.parametrize("language", ["ar", "en"])
@pytest.mark.parametrize("status", STATUSES)
def test_no_prose_renders_the_appointment_time(language, status):
    payload = {**PAYLOAD, "status": status}
    for event_type in (
        NotificationEventType.RESERVATION_CREATED,
        NotificationEventType.RESERVATION_STATUS_CHANGED,
    ):
        title, body = presentation.render(event_type, payload, language)
        assert "09:30" not in title + body
        assert "2030" not in title + body


@pytest.mark.parametrize(
    "event_type,payload",
    [
        ("SOMETHING_NEW", PAYLOAD),
        (NotificationEventType.RESERVATION_STATUS_CHANGED, {"status": "WHO_KNOWS"}),
        (NotificationEventType.RESERVATION_STATUS_CHANGED, {}),
        (NotificationEventType.RESERVATION_STATUS_CHANGED, None),
        (NotificationEventType.RESERVATION_STATUS_CHANGED, "garbage"),
        (NotificationEventType.RESERVATION_STATUS_CHANGED, {"status": ["x"]}),
    ],
)
@pytest.mark.parametrize("language", ["ar", "en"])
def test_unknown_or_malformed_falls_back_safely(event_type, payload, language):
    assert presentation.render(event_type, payload, language) == presentation.FALLBACK[language]


def test_malformed_created_payload_is_safe():
    title, body = presentation.render(
        NotificationEventType.RESERVATION_CREATED,
        {"starts_at": "not-a-date", "service_title": 123},
        "en",
    )
    assert title == "New reservation"
    assert body == "A new reservation was requested."
    assert "not-a-date" not in body


@pytest.mark.parametrize(
    "raw,expected",
    [("en", "en"), ("EN-us", "en"), ("ar", "ar"), ("fr", "ar"), (None, "ar"), ("", "ar")],
)
def test_language_normalisation(raw, expected):
    assert presentation.normalize_language(raw) == expected
