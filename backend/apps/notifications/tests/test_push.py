import threading
import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.chat import services as chat_services
from apps.chat.models import Message
from apps.chat.tests.helpers import make_reservation_world
from apps.notifications import push, push_service, services
from apps.notifications.models import Notification, PushDevice
from apps.notifications.push import PushResult
from apps.notifications.tests.fakes import RecordingSender
from apps.notifications.tests.helpers import book, make_booking_world

DEVICES = "/api/v1/notifications/push-devices/"
UNREGISTER = "/api/v1/notifications/push-devices/unregister/"
TOKEN_A = "tokenA-" + "a" * 60
TOKEN_B = "tokenB-" + "b" * 60


@pytest.fixture(autouse=True)
def fake_push(settings):
    RecordingSender.reset()
    settings.RACHEETA = {
        **settings.RACHEETA,
        "PUSH_SENDER": "apps.notifications.tests.fakes.RecordingSender",
    }
    yield RecordingSender
    RecordingSender.reset()


@pytest.fixture
def other(account_factory):
    return account_factory()


def client_for(account):
    client = APIClient()
    client.force_authenticate(account)
    return client


def sent_tokens():
    return [token for token, _ in RecordingSender.calls]


# --- registration API ------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("method,url", [("post", DEVICES), ("post", UNREGISTER)])
def test_authentication_required(api_client, method, url):
    response = getattr(api_client, method)(url, {"token": TOKEN_A, "platform": "WEB"})
    assert response.status_code == 401


@pytest.mark.django_db
def test_register_binds_to_request_user_and_never_returns_the_token(account, other):
    response = client_for(account).post(DEVICES, {"token": TOKEN_A, "platform": "ANDROID"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "platform", "is_active", "last_registered_at"}
    assert TOKEN_A not in response.content.decode()
    device = PushDevice.objects.get()
    assert device.account_id == account.pk and device.is_active
    assert str(account.pk) not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["account", "account_id", "user", "recipient", "is_active", "id"])
def test_client_cannot_assign_owner_or_other_fields(account, other, field):
    value = str(other.pk) if "id" in field or field in ("account", "user", "recipient") else True
    response = client_for(account).post(
        DEVICES, {"token": TOKEN_A, "platform": "WEB", field: value}
    )
    assert response.status_code == 400
    assert field in response.content.decode()
    assert PushDevice.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("platform", ["", "windows", "android", "FUCHSIA", None, 1])
def test_unsupported_platform_rejected(account, platform):
    response = client_for(account).post(DEVICES, {"token": TOKEN_A, "platform": platform})
    assert response.status_code == 400
    assert PushDevice.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("token", ["", "   ", "x" * 1025, None])
def test_invalid_token_values_rejected(account, token):
    response = client_for(account).post(DEVICES, {"token": token, "platform": "WEB"})
    assert response.status_code == 400
    assert PushDevice.objects.count() == 0


@pytest.mark.django_db
def test_registration_is_idempotent(account):
    client = client_for(account)
    first = client.post(DEVICES, {"token": TOKEN_A, "platform": "WEB"}).json()
    second = client.post(DEVICES, {"token": TOKEN_A, "platform": "WEB"}).json()
    assert first["id"] == second["id"]
    assert PushDevice.objects.filter(is_active=True).count() == 1


@pytest.mark.django_db
def test_re_registration_reactivates_an_unregistered_device(account):
    client = client_for(account)
    client.post(DEVICES, {"token": TOKEN_A, "platform": "WEB"})
    assert client.post(UNREGISTER, {"token": TOKEN_A}).status_code == 204
    assert PushDevice.objects.get().is_active is False
    client.post(DEVICES, {"token": TOKEN_A, "platform": "WEB"})
    assert PushDevice.objects.get().is_active is True


@pytest.mark.django_db
def test_database_enforces_single_owner_per_token(account, other):
    PushDevice.objects.create(account=account, token=TOKEN_A, platform="WEB")
    with pytest.raises(IntegrityError), transaction.atomic():
        PushDevice.objects.create(account=other, token=TOKEN_A, platform="WEB")
    with pytest.raises(IntegrityError), transaction.atomic():
        PushDevice.objects.create(account=account, token="", platform="WEB")


@pytest.mark.django_db
def test_account_switch_transfers_the_token_and_stops_old_owner_pushes(account, other):
    client_for(account).post(DEVICES, {"token": TOKEN_A, "platform": "WEB"})
    client_for(other).post(DEVICES, {"token": TOKEN_A, "platform": "WEB"})

    device = PushDevice.objects.get()
    assert device.account_id == other.pk and device.is_active
    build = lambda lang: push.PushMessage("t", "b")  # noqa: E731
    assert push_service.deliver(account.pk, build) == 0
    assert sent_tokens() == []
    assert push_service.deliver(other.pk, build) == 1
    assert sent_tokens() == [TOKEN_A]
    assert AuditEvent.objects.filter(action="push_device.transferred").count() == 1


@pytest.mark.django_db
def test_unregister_only_affects_own_device_and_answers_identically(account, other):
    client_for(account).post(DEVICES, {"token": TOKEN_A, "platform": "WEB"})
    foreign = client_for(other).post(UNREGISTER, {"token": TOKEN_A})
    missing = client_for(other).post(UNREGISTER, {"token": "nope-" + "z" * 40})
    assert foreign.status_code == missing.status_code == 204
    assert foreign.content == missing.content
    assert PushDevice.objects.get().is_active is True
    assert client_for(account).post(UNREGISTER, {"token": TOKEN_A}).status_code == 204
    assert PushDevice.objects.get().is_active is False


@pytest.mark.django_db
def test_unregister_rejects_extra_fields_and_has_no_bulk_form(account, other):
    PushDevice.objects.create(account=account, token=TOKEN_A, platform="WEB")
    client = client_for(other)
    assert (
        client.post(UNREGISTER, {"token": TOKEN_A, "account": str(account.pk)}).status_code == 400
    )
    assert client.post(UNREGISTER, {}).status_code == 400
    assert PushDevice.objects.get().is_active is True
    for method in ("get", "put", "patch", "delete"):
        assert getattr(client, method)(DEVICES).status_code == 405


@pytest.mark.django_db
def test_registration_does_not_leak_tokens_into_audit(account):
    client_for(account).post(DEVICES, {"token": TOKEN_A, "platform": "WEB"})
    client_for(account).post(UNREGISTER, {"token": TOKEN_A})
    blob = " ".join(f"{e.summary} {e.data} {e.target_id}" for e in AuditEvent.objects.all())
    assert TOKEN_A not in blob and "tokenA" not in blob


@pytest.mark.django_db
def test_active_devices_are_capped_per_account(account):
    for i in range(push_service.MAX_ACTIVE_DEVICES + 3):
        push_service.register_device(account, token=f"tok-{i}-" + "x" * 30, platform="WEB")
    assert (
        PushDevice.objects.filter(account=account, is_active=True).count()
        == push_service.MAX_ACTIVE_DEVICES
    )
    newest = PushDevice.objects.get(token=f"tok-{push_service.MAX_ACTIVE_DEVICES + 2}-" + "x" * 30)
    assert newest.is_active


# --- delivery --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fan_out_to_all_active_devices_and_one_failure_does_not_block_others(account):
    for token in ("t1-" + "a" * 30, "t2-" + "b" * 30, "t3-" + "c" * 30):
        push_service.register_device(account, token=token, platform="ANDROID")
    RecordingSender.outcomes["t2-" + "b" * 30] = RuntimeError("boom")
    sent = push_service.deliver(account.pk, lambda lang: push.PushMessage("t", "b"))
    assert sent == 2
    assert len(RecordingSender.batches) == 1  # one operation for all three devices
    assert len(RecordingSender.calls) == 3
    assert PushDevice.objects.filter(is_active=True).count() == 3  # transient: nothing deactivated


@pytest.mark.django_db
def test_invalid_token_is_deactivated_and_not_retried(account):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    push_service.register_device(account, token=TOKEN_B, platform="WEB")
    RecordingSender.outcomes[TOKEN_A] = PushResult.INVALID_TOKEN
    build = lambda lang: push.PushMessage("t", "b")  # noqa: E731
    assert push_service.deliver(account.pk, build) == 1
    assert PushDevice.objects.get(token=TOKEN_A).is_active is False
    assert PushDevice.objects.get(token=TOKEN_B).is_active is True
    RecordingSender.calls.clear()
    push_service.deliver(account.pk, build)
    assert sent_tokens() == [TOKEN_B]


@pytest.mark.django_db
def test_transient_failures_never_deactivate(account):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    for outcome in (PushResult.TRANSIENT_FAILURE, ConnectionError("net"), TimeoutError()):
        RecordingSender.outcomes[TOKEN_A] = outcome
        push_service.deliver(account.pk, lambda lang: push.PushMessage("t", "b"))
    assert PushDevice.objects.get().is_active is True


def test_firebase_error_classification():
    class UnregisteredError(Exception): ...

    class SenderIdMismatchError(Exception): ...

    class UnavailableError(Exception): ...

    class Sub(UnregisteredError): ...

    assert push.classify_firebase_error(UnregisteredError()) is PushResult.INVALID_TOKEN
    assert push.classify_firebase_error(Sub()) is PushResult.INVALID_TOKEN
    assert push.classify_firebase_error(SenderIdMismatchError()) is PushResult.INVALID_TOKEN
    assert push.classify_firebase_error(UnavailableError()) is PushResult.TRANSIENT_FAILURE
    assert push.classify_firebase_error(ConnectionError()) is PushResult.TRANSIENT_FAILURE


@pytest.mark.django_db
def test_disabled_sender_sends_nothing_and_never_raises(account, settings):
    settings.RACHEETA = {
        **settings.RACHEETA,
        "PUSH_SENDER": "apps.notifications.push.DisabledPushSender",
    }
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    assert push_service.deliver(account.pk, lambda lang: push.PushMessage("t", "b")) == 0
    assert RecordingSender.calls == []


@pytest.mark.django_db
def test_broken_sender_configuration_never_raises(account, settings):
    settings.RACHEETA = {**settings.RACHEETA, "PUSH_SENDER": "no.such.Sender"}
    assert push_service.deliver(account.pk, lambda lang: push.PushMessage("t", "b")) == 0


@pytest.mark.django_db
def test_inactive_account_receives_nothing(account):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    account.is_active = False
    account.save(update_fields=["is_active"])
    assert push_service.deliver(account.pk, lambda lang: push.PushMessage("t", "b")) == 0


# --- persistent notification push ------------------------------------------------------


def _notify(account, reservation_id=None):
    return services.notify_reservation_created(
        recipient_id=account.pk,
        reservation_id=reservation_id or uuid.uuid4(),
        payload={"service_title": "Secret Oncology", "provider_name": "Dr X"},
    )


@pytest.mark.django_db
def test_notification_pushes_after_commit_only(account, django_capture_on_commit_callbacks):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks() as callbacks:
        with transaction.atomic():
            assert _notify(account) is True
            assert RecordingSender.calls == []  # not before commit
        assert RecordingSender.calls == []
    assert len(callbacks) == 1
    callbacks[0]()
    assert sent_tokens() == [TOKEN_A]


@pytest.mark.django_db
def test_rollback_produces_no_push(account, django_capture_on_commit_callbacks):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            _notify(account)
            raise RuntimeError("rollback")
    assert RecordingSender.calls == []
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_notification_push_content_is_private_and_carries_only_ids(
    account, django_capture_on_commit_callbacks
):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks(execute=True):
        _notify(account)
    ((_, message),) = RecordingSender.calls
    row = Notification.objects.get()
    text = f"{message.title} {message.body}"
    assert "Secret Oncology" not in text and "Dr X" not in text
    assert message.data == {
        "type": "notification",
        "notification_id": str(row.pk),
        "event_type": "RESERVATION_CREATED",
    }
    assert TOKEN_A not in str(message)


@pytest.mark.django_db
def test_push_is_localised_to_the_recipient(account, django_capture_on_commit_callbacks):
    account.preferred_language = "en"
    account.save(update_fields=["preferred_language"])
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks(execute=True):
        _notify(account)
    assert RecordingSender.calls[0][1].title == "New reservation"


@pytest.mark.django_db
def test_notification_survives_push_failure_and_replay_does_not_repush(
    account, django_capture_on_commit_callbacks
):
    push_service.register_device(account, token=TOKEN_A, platform="WEB")
    RecordingSender.outcomes[TOKEN_A] = RuntimeError("fcm down")
    reservation_id = uuid.uuid4()
    with django_capture_on_commit_callbacks(execute=True):
        assert _notify(account, reservation_id) is True
    row = Notification.objects.get()
    assert row.read_at is None
    assert client_for(account).get("/api/v1/notifications/unread-count/").json() == {"count": 1}
    RecordingSender.calls.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert _notify(account, reservation_id) is False  # replay
    assert RecordingSender.calls == []
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_reservation_event_pushes_provider_not_patient(
    account_factory, django_capture_on_commit_callbacks
):
    provider, provider_account, patient, service, slot = make_booking_world(account_factory)
    push_service.register_device(provider_account, token=TOKEN_A, platform="ANDROID")
    push_service.register_device(patient, token=TOKEN_B, platform="IOS")
    with django_capture_on_commit_callbacks(execute=True):
        book(patient, slot, note="very private note")
    assert sent_tokens() == [TOKEN_A]
    assert "very private note" not in str(RecordingSender.calls)


# --- chat push -------------------------------------------------------------------------


def _open_conversation(account_factory):
    provider_account, patient, outsider, reservation = make_reservation_world(account_factory)
    conversation, _ = chat_services.get_or_create_reservation_conversation(
        reservation.pk, actor=patient
    )
    return provider_account, patient, outsider, conversation


@pytest.mark.django_db
def test_chat_message_pushes_other_participant_only(
    account_factory, django_capture_on_commit_callbacks
):
    provider_account, patient, outsider, conversation = _open_conversation(account_factory)
    push_service.register_device(provider_account, token=TOKEN_A, platform="WEB")
    push_service.register_device(patient, token=TOKEN_B, platform="WEB")
    push_service.register_device(outsider, token="out-" + "o" * 40, platform="WEB")
    with django_capture_on_commit_callbacks(execute=True):
        chat_services.send_message(conversation.pk, sender=patient, body="secret medical text")

    assert sent_tokens() == [TOKEN_A]  # not the sender, not the outsider
    ((_, message),) = RecordingSender.calls
    assert "secret medical text" not in f"{message.title} {message.body} {message.data}"
    assert message.data == {"type": "chat_message", "conversation_id": str(conversation.pk)}


@pytest.mark.django_db
def test_chat_push_does_not_touch_read_cursors_or_messages(
    account_factory, django_capture_on_commit_callbacks
):
    provider_account, patient, _, conversation = _open_conversation(account_factory)
    push_service.register_device(provider_account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks(execute=True):
        chat_services.send_message(conversation.pk, sender=patient, body="hi")
    cursors = {p.account_id: p.last_read_sequence for p in conversation.participants.all()}
    assert set(cursors.values()) == {0}
    assert chat_services.unread_count(provider_account) == 1


@pytest.mark.django_db
def test_chat_message_survives_push_failure(account_factory, django_capture_on_commit_callbacks):
    provider_account, patient, _, conversation = _open_conversation(account_factory)
    push_service.register_device(provider_account, token=TOKEN_A, platform="WEB")
    RecordingSender.outcomes[TOKEN_A] = RuntimeError("fcm down")
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(patient).post(
            f"/api/v1/chat/conversations/{conversation.pk}/messages/", {"body": "hello"}
        )
    assert response.status_code == 201
    assert Message.objects.count() == 1
    assert chat_services.unread_count(provider_account) == 1


@pytest.mark.django_db
def test_rolled_back_chat_message_pushes_nothing(
    account_factory, django_capture_on_commit_callbacks
):
    provider_account, patient, _, conversation = _open_conversation(account_factory)
    push_service.register_device(provider_account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            chat_services.send_message(conversation.pk, sender=patient, body="never")
            raise RuntimeError("rollback")
    assert RecordingSender.calls == []
    assert Message.objects.count() == 0


@pytest.mark.django_db
def test_chat_push_not_sent_before_commit(account_factory, django_capture_on_commit_callbacks):
    provider_account, patient, _, conversation = _open_conversation(account_factory)
    push_service.register_device(provider_account, token=TOKEN_A, platform="WEB")
    with django_capture_on_commit_callbacks() as callbacks:
        chat_services.send_message(conversation.pk, sender=patient, body="x")
        assert RecordingSender.calls == []
    for callback in callbacks:
        callback()
    assert sent_tokens() == [TOKEN_A]


# --- concurrency -----------------------------------------------------------------------


def _run_threads(target, count):
    threads = [threading.Thread(target=target, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_registration_of_one_token_by_two_accounts_keeps_one_owner(
    account_factory,
):
    a, b = account_factory(), account_factory()
    errors = []

    def run(i):
        try:
            push_service.register_device((a, b)[i % 2], token=TOKEN_A, platform="WEB")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    _run_threads(run, 8)
    assert errors == []
    device = PushDevice.objects.get()  # exactly one row for the token
    assert device.account_id in {a.pk, b.pk} and device.is_active


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_same_account_registration_is_idempotent(account):
    def run(i):
        try:
            push_service.register_device(account, token=TOKEN_A, platform="WEB")
        finally:
            connection.close()

    _run_threads(run, 8)
    assert PushDevice.objects.count() == 1


# --- admin / settings ------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_is_inspection_only_and_masks_tokens(client, account_factory):
    from apps.accounts.models import Account

    su = Account.objects.create_superuser(
        email="su@example.com", password="Str0ng-Passw0rd!", full_name="Su"
    )
    client.force_login(su)
    device = PushDevice.objects.create(account=su, token=TOKEN_A, platform="WEB")
    changelist = client.get("/admin/notifications/pushdevice/")
    assert changelist.status_code == 200
    assert TOKEN_A not in changelist.content.decode()
    detail = client.get(f"/admin/notifications/pushdevice/{device.pk}/change/")
    assert detail.status_code == 200 and TOKEN_A not in detail.content.decode()
    assert client.get("/admin/notifications/pushdevice/add/").status_code == 403
    assert (
        client.post(f"/admin/notifications/pushdevice/{device.pk}/change/", {}).status_code == 403
    )
    assert (
        client.post(
            f"/admin/notifications/pushdevice/{device.pk}/delete/", {"post": "yes"}
        ).status_code
        == 403
    )


def test_push_sender_system_check(settings):
    from apps.core.checks import check_push_sender

    base = settings.RACHEETA
    settings.DEBUG = False
    settings.RACHEETA = {**base, "PUSH_SENDER": "apps.notifications.push.DisabledPushSender"}
    assert [m.id for m in check_push_sender(None)] == ["racheeta.W001"]
    settings.RACHEETA = {
        **base,
        "PUSH_SENDER": "apps.notifications.push.FirebaseAdminPushSender",
        "FIREBASE_CREDENTIALS_FILE": "",
    }
    assert [m.id for m in check_push_sender(None)] == ["racheeta.E004"]
    settings.RACHEETA = {**base, "PUSH_SENDER": "no.such.Thing"}
    assert [m.id for m in check_push_sender(None)] == ["racheeta.E003"]
    settings.RACHEETA = {**base, "PUSH_SENDER": "apps.notifications.tests.fakes.RecordingSender"}
    assert check_push_sender(None) == []
