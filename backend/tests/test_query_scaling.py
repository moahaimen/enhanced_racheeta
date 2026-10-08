"""Authenticated list endpoints must not issue queries per row (docs/PERFORMANCE.md)."""

import uuid
from datetime import timedelta

import pytest

from apps.chat import services as chat_services
from apps.chat.tests.helpers import make_reservation_world
from apps.notifications.models import Notification
from apps.notifications.types import NotificationCategory, NotificationEventType
from apps.reservations.models import Reservation
from tests.querycount import assert_flat, queries_for


def _more_reservations(reservation: Reservation, n: int) -> list[Reservation]:
    """n further reservations between the same patient and provider on different days."""
    made = []
    for i in range(1, n + 1):
        starts = reservation.starts_at + timedelta(days=i)
        made.append(
            Reservation.objects.create(
                patient=reservation.patient,
                provider=reservation.provider,
                service=reservation.service,
                provider_name_snapshot=reservation.provider_name_snapshot,
                service_title_snapshot=reservation.service_title_snapshot,
                price_snapshot=reservation.price_snapshot,
                currency_snapshot=reservation.currency_snapshot,
                duration_minutes_snapshot=reservation.duration_minutes_snapshot,
                starts_at=starts,
                ends_at=starts + timedelta(minutes=reservation.duration_minutes_snapshot),
                status=reservation.status,
            )
        )
    return made


def _notify(account) -> Notification:
    return Notification.objects.create(
        recipient=account,
        category=NotificationCategory.RESERVATION,
        event_type=NotificationEventType.RESERVATION_STATUS_CHANGED,
        resource_type="RESERVATION",
        resource_id=uuid.uuid4(),
        dedupe_key=f"k:{uuid.uuid4()}",
        payload={"status": "CONFIRMED"},
    )


@pytest.mark.django_db
def test_chat_conversation_list_query_count_does_not_grow_with_rows(api_client, account_factory):
    provider_account, patient, _outsider, first = make_reservation_world(account_factory)
    api_client.force_authenticate(user=patient)

    chat_services.get_or_create_reservation_conversation(first.pk, actor=patient)
    small, body = queries_for(api_client, "/api/v1/chat/conversations/")
    assert body["count"] == 1

    for reservation in _more_reservations(first, 8):
        chat_services.get_or_create_reservation_conversation(reservation.pk, actor=patient)
    large, body = queries_for(api_client, "/api/v1/chat/conversations/")
    assert body["count"] == 9
    assert_flat(small, large, label="GET /api/v1/chat/conversations/")


@pytest.mark.django_db
def test_notification_list_query_count_does_not_grow_with_rows(api_client, account):
    api_client.force_authenticate(user=account)
    for _ in range(3):
        _notify(account)
    small, body = queries_for(api_client, "/api/v1/notifications/")
    assert body["count"] == 3

    for _ in range(12):
        _notify(account)
    large, body = queries_for(api_client, "/api/v1/notifications/")
    assert body["count"] == 15
    assert_flat(small, large, label="GET /api/v1/notifications/")
