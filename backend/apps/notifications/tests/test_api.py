import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.types import NotificationCategory, NotificationEventType

BASE = "/api/v1/notifications/"
PAYLOAD = {
    "reservation_id": "r",
    "service_title": "Consultation",
    "provider_name": "Dr Notify",
    "status": "CONFIRMED",
    "previous_status": "PENDING",
}


def _make(account, **overrides):
    values = {
        "recipient": account,
        "category": NotificationCategory.RESERVATION,
        "event_type": NotificationEventType.RESERVATION_STATUS_CHANGED,
        "resource_type": "RESERVATION",
        "resource_id": uuid.uuid4(),
        "dedupe_key": f"k:{uuid.uuid4()}",
        "payload": PAYLOAD,
    }
    values.update(overrides)
    return Notification.objects.create(**values)


@pytest.fixture
def other(account_factory):
    return account_factory()


# --- security ------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method,suffix",
    [
        ("get", ""),
        ("get", "unread-count/"),
        ("post", "read-all/"),
        ("post", f"{uuid.uuid4()}/read/"),
    ],
)
def test_all_endpoints_require_authentication(api_client, method, suffix):
    assert getattr(api_client, method)(BASE + suffix).status_code == 401


@pytest.mark.django_db
def test_list_only_returns_own_and_newest_first(auth_client, account, other):
    first = _make(account)
    second = _make(account)
    _make(other)

    results = auth_client.get(BASE).json()["results"]
    assert [r["id"] for r in results] == [str(second.pk), str(first.pk)]


@pytest.mark.django_db
def test_list_fields_and_private_data_not_exposed(auth_client, account):
    row = _make(account, payload={**PAYLOAD, "patient_note": "secret", "phone": "0770"})
    item = auth_client.get(BASE).json()["results"][0]
    assert set(item) == {
        "id",
        "category",
        "event_type",
        "title",
        "body",
        "resource_type",
        "resource_id",
        "is_read",
        "read_at",
        "created_at",
    }
    assert item["id"] == str(row.pk) and item["is_read"] is False
    raw = str(auth_client.get(BASE).content)
    for forbidden in ("dedupe", "recipient", "payload", "secret", "0770"):
        assert forbidden not in raw


@pytest.mark.django_db
def test_title_and_body_follow_request_language(auth_client, account):
    _make(account)
    en = auth_client.get(BASE, headers={"Accept-Language": "en"}).json()["results"][0]
    ar = auth_client.get(BASE, headers={"Accept-Language": "ar"}).json()["results"][0]
    assert en["title"] == "Reservation confirmed"
    assert ar["title"] == "تم تأكيد الحجز"
    assert "Consultation" in en["body"] and "Consultation" in ar["body"]


@pytest.mark.django_db
def test_unknown_event_type_row_is_still_listed_safely(auth_client, account):
    _make(account, event_type="FUTURE_EVENT", payload={"x": object.__name__})
    item = auth_client.get(BASE, headers={"Accept-Language": "en"}).json()["results"][0]
    assert item["title"] == "New notification"


@pytest.mark.django_db
def test_pagination_is_twenty_per_page(auth_client, account):
    for _ in range(25):
        _make(account)
    page1 = auth_client.get(BASE).json()
    page2 = auth_client.get(BASE + "?page=2").json()
    assert page1["count"] == 25 and len(page1["results"]) == 20
    assert len(page2["results"]) == 5 and page2["next"] is None


@pytest.mark.django_db
def test_list_has_no_n_plus_one(auth_client, account):
    for _ in range(3):
        _make(account)
    with CaptureQueriesContext(connection) as small:
        auth_client.get(BASE)
    for _ in range(15):
        _make(account)
    with CaptureQueriesContext(connection) as large:
        auth_client.get(BASE)
    assert len(large) == len(small)


# --- unread count ----------------------------------------------------------------


@pytest.mark.django_db
def test_unread_count_is_own_unread_only(auth_client, account, other):
    _make(account)
    _make(account)
    _make(account, read_at=timezone.now())
    _make(other)
    response = auth_client.get(BASE + "unread-count/")
    assert response.status_code == 200
    assert response.json() == {"count": 2}


@pytest.mark.django_db
def test_unread_count_zero_and_single_query(auth_client):
    with CaptureQueriesContext(connection) as ctx:
        response = auth_client.get(BASE + "unread-count/")
    assert response.json() == {"count": 0}
    counts = [q for q in ctx.captured_queries if "COUNT(" in q["sql"]]
    assert len(counts) == 1


# --- mark one read -----------------------------------------------------------------


@pytest.mark.django_db
def test_mark_read_sets_server_timestamp(auth_client, account):
    row = _make(account)
    response = auth_client.post(f"{BASE}{row.pk}/read/")
    assert response.status_code == 200
    body = response.json()
    assert body["is_read"] is True and body["read_at"]
    row.refresh_from_db()
    assert row.read_at is not None


@pytest.mark.django_db
def test_mark_read_is_idempotent_and_keeps_original_timestamp(auth_client, account):
    row = _make(account)
    first = auth_client.post(f"{BASE}{row.pk}/read/").json()
    second = auth_client.post(f"{BASE}{row.pk}/read/", {}, format="json")
    assert second.status_code == 200
    assert second.json()["read_at"] == first["read_at"]


@pytest.mark.django_db
def test_mark_read_foreign_and_unknown_are_plain_404(auth_client, other):
    foreign = _make(other)
    for target in (foreign.pk, uuid.uuid4()):
        response = auth_client.post(f"{BASE}{target}/read/")
        assert response.status_code == 404
    foreign.refresh_from_db()
    assert foreign.read_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [{"read_at": "2000-01-01T00:00:00Z"}, {"anything": 1}, [], [1], "x", "", 0, 1, False, True],
)
def test_mark_read_rejects_client_data(auth_client, account, body):
    row = _make(account)
    response = auth_client.post(f"{BASE}{row.pk}/read/", body, format="json")
    assert response.status_code == 400, body
    assert "field_not_allowed" in response.content.decode()
    row.refresh_from_db()
    assert row.read_at is None


@pytest.mark.django_db
def test_mark_read_accepts_empty_object_and_no_body(auth_client, account):
    row = _make(account)
    assert auth_client.post(f"{BASE}{row.pk}/read/", {}, format="json").status_code == 200
    other_row = _make(account)
    assert auth_client.post(f"{BASE}{other_row.pk}/read/").status_code == 200


# --- read all ------------------------------------------------------------------------


@pytest.mark.django_db
def test_read_all_updates_only_own_unread(auth_client, account, other):
    original = timezone.now() - timezone.timedelta(days=1)
    _make(account)
    _make(account)
    kept = _make(account, read_at=original)
    theirs = _make(other)

    response = auth_client.post(BASE + "read-all/")
    assert response.status_code == 200 and response.json() == {"updated": 2}

    kept.refresh_from_db()
    theirs.refresh_from_db()
    assert kept.read_at == original
    assert theirs.read_at is None
    stamps = set(
        Notification.objects.filter(recipient=account)
        .exclude(pk=kept.pk)
        .values_list("read_at", flat=True)
    )
    assert len(stamps) == 1  # one server timestamp for the whole batch
    assert auth_client.post(BASE + "read-all/").json() == {"updated": 0}


@pytest.mark.django_db
def test_read_all_is_one_update_query(auth_client, account):
    for _ in range(5):
        _make(account)
    with CaptureQueriesContext(connection) as ctx:
        auth_client.post(BASE + "read-all/")
    updates = [q for q in ctx.captured_queries if q["sql"].lstrip().upper().startswith("UPDATE")]
    assert len(updates) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("body", [{"x": 1}, [], "s", 0, False])
def test_read_all_rejects_client_data(auth_client, account, body):
    row = _make(account)
    response = auth_client.post(BASE + "read-all/", body, format="json")
    assert response.status_code == 400
    assert "field_not_allowed" in response.content.decode()
    row.refresh_from_db()
    assert row.read_at is None


# --- no client writes -------------------------------------------------------------------


@pytest.mark.django_db
def test_clients_cannot_create_patch_or_delete(auth_client, account):
    row = _make(account)
    assert auth_client.post(BASE, {"event_type": "X"}, format="json").status_code == 405
    for method in ("patch", "put", "delete"):
        assert getattr(auth_client, method)(f"{BASE}{row.pk}/").status_code in (404, 405)
        assert getattr(auth_client, method)(BASE).status_code == 405
    assert Notification.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("suffix", ["read-all/", "ROW/read/"])
def test_explicit_json_null_body_is_rejected(auth_client, account, suffix):
    row = _make(account)
    url = BASE + suffix.replace("ROW", str(row.pk))
    response = auth_client.generic("POST", url, "null", content_type="application/json")
    assert response.status_code == 400
    assert "field_not_allowed" in response.content.decode()
    row.refresh_from_db()
    assert row.read_at is None
