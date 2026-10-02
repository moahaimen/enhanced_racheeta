import uuid

import pytest

from apps.chat import services
from apps.chat.models import Conversation, ConversationParticipant, Message

from .helpers import make_reservation_world

BASE = "/api/v1/chat/"


def _open(api_client, account, reservation_id, body=None):
    api_client.force_authenticate(user=account)
    if body is None:
        return api_client.post(f"{BASE}reservations/{reservation_id}/conversation")
    return api_client.post(
        f"{BASE}reservations/{reservation_id}/conversation",
        body,
        format="json",
    )


@pytest.mark.django_db
def test_chat_endpoints_require_authentication(api_client):
    assert api_client.get(BASE + "conversations/").status_code == 401
    assert api_client.get(BASE + "unread-count/").status_code == 401
    assert api_client.post(
        f"{BASE}reservations/{uuid.uuid4()}/conversation"
    ).status_code == 401
    assert api_client.get(
        f"{BASE}conversations/{uuid.uuid4()}/messages/"
    ).status_code == 401


@pytest.mark.django_db
def test_reservation_open_derives_exact_participants_and_is_idempotent(api_client, account_factory):
    provider, patient, outsider, reservation = make_reservation_world(account_factory)

    first = _open(api_client, patient, reservation.pk)
    second = _open(api_client, provider, reservation.pk)

    assert first.status_code == 201, first.content
    assert second.status_code == 200, second.content
    assert first.json()["id"] == second.json()["id"]
    conversation = Conversation.objects.get()
    assert conversation.context_id == reservation.pk
    assert set(
        ConversationParticipant.objects.filter(conversation=conversation).values_list(
            "account_id", flat=True
        )
    ) == {patient.pk, provider.pk}
    assert outsider.pk not in set(
        ConversationParticipant.objects.values_list("account_id", flat=True)
    )


@pytest.mark.django_db
def test_clients_cannot_choose_participants(api_client, account_factory):
    provider, patient, outsider, reservation = make_reservation_world(account_factory)
    response = _open(
        api_client,
        patient,
        reservation.pk,
        {"account_id": str(outsider.pk)},
    )
    assert response.status_code == 400
    assert "field_not_allowed" in response.content.decode()
    assert Conversation.objects.count() == 0


@pytest.mark.django_db
def test_foreign_reservation_and_missing_reservation_are_same_404(api_client, account_factory):
    _, patient, outsider, reservation = make_reservation_world(account_factory)
    api_client.force_authenticate(user=outsider)

    foreign = api_client.post(f"{BASE}reservations/{reservation.pk}/conversation")
    missing = api_client.post(f"{BASE}reservations/{uuid.uuid4()}/conversation")

    assert foreign.status_code == missing.status_code == 404
    assert Conversation.objects.count() == 0


@pytest.mark.django_db
def test_message_thread_is_participant_scoped_and_hides_contact_fields(api_client, account_factory):
    provider, patient, outsider, reservation = make_reservation_world(account_factory)
    opened = _open(api_client, patient, reservation.pk)
    conversation_id = opened.json()["id"]

    sent = api_client.post(
        f"{BASE}conversations/{conversation_id}/messages/",
        {"body": "  Hello doctor  "},
        format="json",
    )
    assert sent.status_code == 201, sent.content
    assert sent.json()["body"] == "Hello doctor"
    assert sent.json()["sequence"] == 1
    assert sent.json()["is_mine"] is True
    assert set(sent.json()["sender"]) == {"id", "full_name", "role"}
    assert "email" not in sent.content.decode() and "phone" not in sent.content.decode()

    api_client.force_authenticate(user=provider)
    received = api_client.get(f"{BASE}conversations/{conversation_id}/messages/")
    assert received.status_code == 200
    assert received.json()["results"][0]["body"] == "Hello doctor"
    assert received.json()["results"][0]["is_mine"] is False

    api_client.force_authenticate(user=outsider)
    assert api_client.get(
        f"{BASE}conversations/{conversation_id}/messages/"
    ).status_code == 404
    assert api_client.post(
        f"{BASE}conversations/{conversation_id}/messages/",
        {"body": "intrusion"},
        format="json",
    ).status_code == 404
    assert Message.objects.count() == 1


@pytest.mark.django_db
def test_message_body_is_required_and_bounded(api_client, account_factory):
    _, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    for body in ("", "   ", "x" * 2001):
        response = api_client.post(
            f"{BASE}conversations/{conversation_id}/messages/",
            {"body": body},
            format="json",
        )
        assert response.status_code == 400
    assert Message.objects.count() == 0


@pytest.mark.django_db
def test_unread_count_and_sequence_cursor(api_client, account_factory):
    provider, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    api_client.force_authenticate(user=provider)
    assert api_client.post(
        f"{BASE}conversations/{conversation_id}/messages/",
        {"body": "one"},
        format="json",
    ).status_code == 201
    assert api_client.post(
        f"{BASE}conversations/{conversation_id}/messages/",
        {"body": "two"},
        format="json",
    ).status_code == 201
    assert api_client.get(BASE + "unread-count/").json() == {"count": 0}

    api_client.force_authenticate(user=patient)
    assert api_client.get(BASE + "unread-count/").json() == {"count": 2}
    listing = api_client.get(BASE + "conversations/").json()
    assert listing["results"][0]["unread_count"] == 2

    read = api_client.post(
        f"{BASE}conversations/{conversation_id}/read/",
        {"through_sequence": 2},
        format="json",
    )
    assert read.status_code == 200
    assert read.json() == {"last_read_sequence": 2}
    assert api_client.get(BASE + "unread-count/").json() == {"count": 0}

    api_client.force_authenticate(user=provider)
    api_client.post(
        f"{BASE}conversations/{conversation_id}/messages/",
        {"body": "three"},
        format="json",
    )
    api_client.force_authenticate(user=patient)
    assert api_client.get(BASE + "unread-count/").json() == {"count": 1}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [{}, {"through_sequence": -1}, {"through_sequence": "not-an-integer"}, [], "x", 0, False],
)
def test_mark_read_requires_a_valid_observed_sequence(api_client, account_factory, body):
    _, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]
    response = api_client.post(
        f"{BASE}conversations/{conversation_id}/read/",
        body,
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_mark_read_rejects_cursor_beyond_current_conversation(api_client, account_factory):
    _, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    response = api_client.post(
        f"{BASE}conversations/{conversation_id}/read/",
        {"through_sequence": 99},
        format="json",
    )

    assert response.status_code == 400
    assert "invalid_read_cursor" in response.content.decode()


@pytest.mark.django_db
def test_mark_read_foreign_and_missing_are_same_404(api_client, account_factory):
    _, patient, outsider, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]
    api_client.force_authenticate(user=outsider)

    foreign = api_client.post(
        f"{BASE}conversations/{conversation_id}/read/",
        {"through_sequence": 0},
        format="json",
    )
    missing = api_client.post(
        f"{BASE}conversations/{uuid.uuid4()}/read/",
        {"through_sequence": 0},
        format="json",
    )
    assert foreign.status_code == missing.status_code == 404


@pytest.mark.django_db
def test_message_rejects_client_owned_sender(api_client, account_factory):
    provider, patient, outsider, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    response = api_client.post(
        f"{BASE}conversations/{conversation_id}/messages/",
        {"body": "hello", "sender": str(outsider.pk)},
        format="json",
    )

    assert response.status_code == 400
    assert "field_not_allowed" in response.content.decode()
    assert Message.objects.count() == 0


@pytest.mark.django_db
def test_read_cursor_does_not_swallow_message_arriving_after_render(api_client, account_factory):
    provider, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]
    conversation_uuid = uuid.UUID(conversation_id)

    services.send_message(conversation_uuid, sender=provider, body="observed")
    # The patient rendered sequence 1. Another provider message arrives before
    # the read receipt is submitted.
    services.send_message(conversation_uuid, sender=provider, body="arrived later")

    api_client.force_authenticate(user=patient)
    read = api_client.post(
        f"{BASE}conversations/{conversation_id}/read/",
        {"through_sequence": 1},
        format="json",
    )

    assert read.status_code == 200
    assert read.json() == {"last_read_sequence": 1}
    assert api_client.get(BASE + "unread-count/").json() == {"count": 1}


@pytest.mark.django_db
def test_messages_page_one_is_latest_slice_but_chronological_inside_page(
    api_client, account_factory
):
    provider, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    for i in range(25):
        sender = patient if i % 2 == 0 else provider
        services.send_message(uuid.UUID(conversation_id), sender=sender, body=f"m{i + 1}")

    api_client.force_authenticate(user=patient)
    first = api_client.get(f"{BASE}conversations/{conversation_id}/messages/").json()
    second = api_client.get(
        f"{BASE}conversations/{conversation_id}/messages/?page=2"
    ).json()

    assert [row["sequence"] for row in first["results"]] == list(range(6, 26))
    assert [row["sequence"] for row in second["results"]] == list(range(1, 6))


@pytest.mark.django_db
def test_conversation_list_is_own_only(api_client, account_factory):
    _, patient, outsider, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    api_client.force_authenticate(user=patient)
    own = api_client.get(BASE + "conversations/").json()
    assert [row["id"] for row in own["results"]] == [conversation_id]

    api_client.force_authenticate(user=outsider)
    assert api_client.get(BASE + "conversations/").json()["results"] == []


@pytest.mark.django_db
def test_no_public_client_update_delete_or_arbitrary_conversation_create(
    api_client, account_factory
):
    _, patient, _, reservation = make_reservation_world(account_factory)
    conversation_id = _open(api_client, patient, reservation.pk).json()["id"]

    assert api_client.post(
        BASE + "conversations/",
        {"participant": str(uuid.uuid4())},
        format="json",
    ).status_code == 405
    for method in ("patch", "put", "delete"):
        assert getattr(api_client, method)(
            f"{BASE}conversations/{conversation_id}/messages/"
        ).status_code == 405
    assert Conversation.objects.count() == 1
