"""Phase 9C latency contract.

`transaction.on_commit` is a hook, not asynchronous execution: push delivery runs inside the
request that caused it. These tests lock the properties that keep that cost constant:

* one sender operation per delivery, never one blocking send per device;
* a hard caller-side deadline, a bulkhead and a fail-fast window around the SDK call;
* per-token results, so only permanent rejections deactivate a device.

No test contacts Firebase: the SDK is a fake with the same shape as firebase-admin 7.7.0.
"""

import threading
import time
import uuid

import pytest
from rest_framework.test import APIClient

from apps.chat import services as chat_services
from apps.chat.models import Message
from apps.chat.tests.helpers import make_reservation_world
from apps.notifications import push, push_service, services
from apps.notifications.models import Notification, PushDevice
from apps.notifications.push import (
    BoundedCallRunner,
    PushBusy,
    PushDeadlineExceeded,
    PushPaused,
    PushResult,
)
from apps.notifications.tests import fakes
from apps.notifications.tests.fakes import RecordingSender
from apps.notifications.tests.helpers import book, make_booking_world

DEADLINE = 0.3
SENDER = "apps.notifications.tests.fakes.RecordingSender"
FAKE_SDK_SENDER = "apps.notifications.tests.fakes.FakeSdkFirebaseSender"


def use_sender(settings, path):
    settings.RACHEETA = {**settings.RACHEETA, "PUSH_SENDER": path}


@pytest.fixture(autouse=True)
def recording_sender(settings):
    RecordingSender.reset()
    use_sender(settings, SENDER)
    yield RecordingSender
    RecordingSender.reset()


def register(account, count, prefix="dev"):
    tokens = [f"{prefix}-{i}-" + "x" * 30 for i in range(count)]
    for token in tokens:
        push_service.register_device(account, token=token, platform="WEB")
    return tokens


def message():
    return push.PushMessage("title", "body", {"type": "t"})


def build(language):
    return message()


class SlowBatchSender:
    """Every sender call costs 0.15 s, like one network round trip."""

    def send_batch(self, tokens, msg):
        time.sleep(0.15)
        return {token: PushResult.SENT for token in tokens}


# --- one operation per delivery ---------------------------------------------------------


def public_callables(cls):
    return {n for n, v in vars(cls).items() if callable(v) and not n.startswith("_")}


def test_sender_contract_has_no_per_token_send():
    assert public_callables(push.PushSender) == {"send_batch"}
    for cls in (push.DisabledPushSender, push.FirebaseAdminPushSender, RecordingSender):
        assert hasattr(cls, "send_batch")
        assert not hasattr(cls, "send"), f"{cls.__name__} must not offer a per-token send"


@pytest.mark.django_db
@pytest.mark.parametrize("count", [1, 3, push_service.MAX_ACTIVE_DEVICES])
def test_delivery_is_one_sender_call_for_any_number_of_devices(account, count):
    tokens = register(account, count)
    assert push_service.deliver(account.pk, build) == count
    assert len(RecordingSender.batches) == 1
    assert set(RecordingSender.batches[0][0]) == set(tokens)


@pytest.mark.django_db
def test_delivery_latency_does_not_scale_with_the_number_of_devices(account, settings):
    use_sender(settings, "apps.notifications.tests.test_push_delivery_bounds.SlowBatchSender")
    register(account, push_service.MAX_ACTIVE_DEVICES)
    started = time.monotonic()
    assert push_service.deliver(account.pk, build) == push_service.MAX_ACTIVE_DEVICES
    elapsed = time.monotonic() - started
    # One 0.15 s operation. A per-device loop would cost 10 x 0.15 = 1.5 s.
    assert elapsed < 0.15 * 4, elapsed


@pytest.mark.django_db
def test_only_active_devices_of_the_recipient_are_targeted(account, account_factory):
    other = account_factory()
    active = register(account, 2, "mine")
    gone = register(account, 1, "gone")
    push_service.unregister_device(account, token=gone[0])
    register(other, 2, "theirs")
    push_service.deliver(account.pk, build)
    assert set(RecordingSender.batches[0][0]) == set(active)


# --- per-token results ------------------------------------------------------------------


@pytest.mark.django_db
def test_mixed_results_deactivate_only_permanent_rejections_and_touch_nothing_else(account):
    t_ok, t_unreg, t_transient, t_sender, t_quota = register(account, 5)
    before = {
        d.token: (d.platform, d.account_id, d.last_registered_at) for d in PushDevice.objects.all()
    }
    RecordingSender.outcomes = {
        t_unreg: fakes.UnregisteredError("gone"),
        t_transient: fakes.UnavailableError("later"),
        t_sender: fakes.SenderIdMismatchError("other project"),
        t_quota: PushResult.TRANSIENT_FAILURE,
    }
    assert push_service.deliver(account.pk, build) == 1

    state = {d.token: d.is_active for d in PushDevice.objects.all()}
    assert state == {
        t_ok: True,
        t_unreg: False,
        t_transient: True,
        t_sender: False,
        t_quota: True,
    }
    after = {
        d.token: (d.platform, d.account_id, d.last_registered_at) for d in PushDevice.objects.all()
    }
    assert after == before  # no other registration data changed

    RecordingSender.batches.clear()
    push_service.deliver(account.pk, build)
    assert set(RecordingSender.batches[0][0]) == {
        t_ok,
        t_transient,
        t_quota,
    }  # dead ones not retried


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure",
    [RuntimeError("auth"), push.PushDeadlineExceeded(), push.PushBusy(), push.PushPaused()],
    ids=lambda failure: type(failure).__name__,
)
def test_a_failed_or_refused_batch_keeps_every_registration(account, failure):
    register(account, 3)
    RecordingSender.batch_error = failure
    assert push_service.deliver(account.pk, build) == 0
    assert PushDevice.objects.filter(is_active=True).count() == 3


@pytest.mark.django_db
def test_a_result_missing_for_a_token_is_transient(account, settings):
    class PartialSender:
        def send_batch(self, tokens, msg):
            return {tokens[0]: PushResult.SENT}  # says nothing about the others

    PartialSender.__module__ = __name__
    globals()["PartialSender"] = PartialSender
    use_sender(settings, f"{__name__}.PartialSender")
    register(account, 3)
    assert push_service.deliver(account.pk, build) == 1
    assert PushDevice.objects.filter(is_active=True).count() == 3


# --- the Firebase adapter over a fake SDK ---------------------------------------------


def adapter(messaging=None, runner=None):
    return push.FirebaseAdminPushSender(sdk=fakes.fake_sdk(messaging), runner=runner)


def test_adapter_makes_one_multicast_call_for_all_tokens_with_private_content():
    messaging = fakes.FakeMessaging()
    tokens = [f"t{i}" for i in range(10)]
    results = adapter(messaging).send_batch(tokens, message())

    assert len(messaging.multicast_calls) == 1  # never one send per token
    sent, app = messaging.multicast_calls[0]
    assert sent.tokens == tokens and app == "fake-app"
    assert (sent.notification.title, sent.notification.body) == ("title", "body")
    assert sent.data == {"type": "t"}
    assert results == {token: PushResult.SENT for token in tokens}


def test_adapter_maps_mixed_per_token_results():
    def responder(msg):
        return fakes.FakeBatchResponse(
            [
                fakes.FakeSendResponse(True),
                fakes.FakeSendResponse(False, fakes.UnregisteredError("x")),
                fakes.FakeSendResponse(False, fakes.UnavailableError("x")),
                fakes.FakeSendResponse(False, fakes.SenderIdMismatchError("x")),
                fakes.FakeSendResponse(False, fakes.QuotaExceededError("x")),
                fakes.FakeSendResponse(False, fakes.InvalidArgumentError("x")),
                fakes.FakeSendResponse(False, None),
            ]
        )

    tokens = [f"t{i}" for i in range(7)]
    results = adapter(fakes.FakeMessaging(responder)).send_batch(tokens, message())
    assert [results[t] for t in tokens] == [
        PushResult.SENT,
        PushResult.INVALID_TOKEN,
        PushResult.TRANSIENT_FAILURE,
        PushResult.INVALID_TOKEN,
        PushResult.TRANSIENT_FAILURE,
        PushResult.TRANSIENT_FAILURE,
        PushResult.TRANSIENT_FAILURE,
    ]


def test_adapter_never_guesses_from_a_misaligned_response():
    def responder(msg):  # one answer for three tokens: cannot be attributed
        return fakes.FakeBatchResponse(
            [fakes.FakeSendResponse(False, fakes.UnregisteredError("x"))]
        )

    results = adapter(fakes.FakeMessaging(responder)).send_batch(["a", "b", "c"], message())
    assert set(results.values()) == {PushResult.TRANSIENT_FAILURE}


def test_adapter_with_no_tokens_makes_no_call():
    messaging = fakes.FakeMessaging()
    assert adapter(messaging).send_batch([], message()) == {}
    assert messaging.multicast_calls == []


@pytest.mark.django_db
def test_mixed_results_through_the_adapter_update_the_registry(account, settings):
    t_ok, t_unreg, t_quota, t_sender = register(account, 4)
    answers = {
        t_ok: fakes.FakeSendResponse(True),
        t_unreg: fakes.FakeSendResponse(False, fakes.UnregisteredError("x")),
        t_quota: fakes.FakeSendResponse(False, fakes.QuotaExceededError("x")),
        t_sender: fakes.FakeSendResponse(False, fakes.SenderIdMismatchError("x")),
    }

    def responder(msg):  # responses[i] answers msg.tokens[i], whatever order the sender chose
        return fakes.FakeBatchResponse([answers[token] for token in msg.tokens])

    use_sender(settings, FAKE_SDK_SENDER)
    previous = (fakes.FakeSdkFirebaseSender.messaging, fakes.FakeSdkFirebaseSender.runner)
    messaging = fakes.FakeMessaging(responder)
    fakes.FakeSdkFirebaseSender.messaging = messaging
    fakes.FakeSdkFirebaseSender.runner = BoundedCallRunner(
        max_inflight=2, deadline=DEADLINE * 5, cooldown=0, name="mixed"
    )
    try:
        assert push_service.deliver(account.pk, build) == 1
    finally:
        fakes.FakeSdkFirebaseSender.runner.shutdown()
        fakes.FakeSdkFirebaseSender.messaging, fakes.FakeSdkFirebaseSender.runner = previous
    assert len(messaging.multicast_calls) == 1
    assert set(messaging.multicast_calls[0][0].tokens) == {t_ok, t_unreg, t_quota, t_sender}
    state = {d.token: d.is_active for d in PushDevice.objects.all()}
    assert state == {t_ok: True, t_unreg: False, t_quota: True, t_sender: False}


# --- the bounded runner -----------------------------------------------------------------


def make_runner(**overrides):
    options = {
        "max_inflight": 2,
        "deadline": 0.2,
        "cooldown": 0,
        "name": f"t-{uuid.uuid4().hex[:8]}",
    }
    options.update(overrides)
    return BoundedCallRunner(**options)


def hung_call(release):
    return lambda: release.wait(timeout=20)


@pytest.fixture
def release():
    event = threading.Event()
    yield event
    event.set()


def test_runner_returns_the_value_and_reraises_the_callables_own_errors():
    runner = make_runner()
    try:
        assert runner.run(lambda: 42) == 42
        with pytest.raises(ValueError, match="boom"):
            runner.run(lambda: (_ for _ in ()).throw(ValueError("boom")))

        # A TimeoutError raised *by the call* is its own failure, not a missed deadline.
        def socket_timeout():
            raise TimeoutError("socket")

        with pytest.raises(TimeoutError) as caught:
            runner.run(socket_timeout)
        assert not isinstance(caught.value, PushDeadlineExceeded)
    finally:
        runner.shutdown()


def test_runner_enforces_a_hard_deadline_on_a_hung_call(release):
    runner = make_runner(deadline=0.2)
    try:
        started = time.monotonic()
        with pytest.raises(PushDeadlineExceeded):
            runner.run(hung_call(release))
        assert time.monotonic() - started < 2.0  # the call itself would block for 20 s
    finally:
        release.set()
        runner.shutdown()


def test_runner_bulkhead_refuses_instantly_when_slots_are_held_and_recovers(release):
    runner = make_runner(max_inflight=2, deadline=0.1, cooldown=0)
    invoked = []
    try:
        for _ in range(2):
            with pytest.raises(PushDeadlineExceeded):
                runner.run(hung_call(release))  # abandoned, still holding its slot
        started = time.monotonic()
        with pytest.raises(PushBusy):
            runner.run(lambda: invoked.append("ran"))
        assert time.monotonic() - started < 0.1 and invoked == []

        release.set()  # the abandoned calls finish and give their slots back
        deadline = time.monotonic() + 5
        while True:
            try:
                assert runner.run(lambda: "ok") == "ok"
                break
            except PushBusy:
                assert time.monotonic() < deadline, "slots were never released"
                time.sleep(0.02)
    finally:
        release.set()
        runner.shutdown()


def test_runner_never_uses_more_threads_than_its_bulkhead(release):
    name = f"bounded-{uuid.uuid4().hex[:8]}"
    runner = make_runner(max_inflight=3, deadline=0.05, cooldown=0, name=name)
    try:
        for _ in range(25):
            with pytest.raises((PushDeadlineExceeded, PushBusy)):
                runner.run(hung_call(release))
        workers = [t for t in threading.enumerate() if t.name.startswith(name)]
        assert 0 < len(workers) <= 3
    finally:
        release.set()
        runner.shutdown()


def test_runner_fails_fast_after_a_missed_deadline_then_probes_again(release):
    now = [100.0]
    runner = make_runner(max_inflight=4, deadline=0.1, cooldown=10, clock=lambda: now[0])
    invoked = []
    try:
        with pytest.raises(PushDeadlineExceeded):
            runner.run(hung_call(release))
        started = time.monotonic()
        with pytest.raises(PushPaused):  # a free slot exists, but the window is open
            runner.run(lambda: invoked.append("ran"))
        assert time.monotonic() - started < 0.1 and invoked == []

        now[0] += 10.1  # window over: the next delivery is allowed to probe
        assert runner.run(lambda: "probe") == "probe"
    finally:
        release.set()
        runner.shutdown()


# --- end to end: a hung Firebase cannot hold the request -------------------------------


@pytest.fixture
def hung_firebase(settings, release):
    """The real adapter over a fake SDK whose multicast call never returns."""
    messaging = fakes.FakeMessaging(hang=release)
    runner = make_runner(max_inflight=2, deadline=DEADLINE, cooldown=5)
    use_sender(settings, FAKE_SDK_SENDER)
    previous = (fakes.FakeSdkFirebaseSender.messaging, fakes.FakeSdkFirebaseSender.runner)
    fakes.FakeSdkFirebaseSender.messaging = messaging
    fakes.FakeSdkFirebaseSender.runner = runner
    yield messaging
    release.set()
    runner.shutdown()
    fakes.FakeSdkFirebaseSender.messaging, fakes.FakeSdkFirebaseSender.runner = previous


def client_for(account):
    client = APIClient()
    client.force_authenticate(account)
    return client


@pytest.mark.django_db
def test_hung_firebase_cannot_block_a_chat_request_beyond_the_deadline(
    account_factory, django_capture_on_commit_callbacks, hung_firebase
):
    provider_account, patient, _, reservation = make_reservation_world(account_factory)
    conversation, _ = chat_services.get_or_create_reservation_conversation(
        reservation.pk, actor=patient
    )
    tokens = register(provider_account, push_service.MAX_ACTIVE_DEVICES)

    started = time.monotonic()
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(patient).post(
            f"/api/v1/chat/conversations/{conversation.pk}/messages/", {"body": "hello"}
        )
    elapsed = time.monotonic() - started

    assert response.status_code == 201
    assert elapsed < DEADLINE + 2.0, elapsed  # 10 devices must not multiply the wait
    assert len(hung_firebase.multicast_calls) == 1  # one SDK operation for 10 devices
    assert set(hung_firebase.multicast_calls[0][0].tokens) == set(tokens)
    # Authoritative state is untouched by the push outage.
    assert Message.objects.count() == 1
    assert chat_services.unread_count(provider_account) == 1
    assert PushDevice.objects.filter(is_active=True).count() == len(tokens)


@pytest.mark.django_db
def test_hung_firebase_cannot_block_a_notification_producing_request(
    account_factory, django_capture_on_commit_callbacks, hung_firebase
):
    provider, provider_account, patient, service, slot = make_booking_world(account_factory)
    tokens = register(provider_account, push_service.MAX_ACTIVE_DEVICES)

    started = time.monotonic()
    with django_capture_on_commit_callbacks(execute=True):
        book(patient, slot)
    elapsed = time.monotonic() - started

    assert elapsed < DEADLINE + 2.0, elapsed
    assert len(hung_firebase.multicast_calls) == 1
    assert Notification.objects.filter(recipient=provider_account).count() == 1
    assert PushDevice.objects.filter(is_active=True).count() == len(tokens)


@pytest.mark.django_db
def test_a_request_with_two_recipients_pays_one_deadline_not_two(
    account_factory, django_capture_on_commit_callbacks, hung_firebase
):
    first, second = account_factory(), account_factory()
    register(first, 3, "first")
    register(second, 3, "second")

    started = time.monotonic()
    with django_capture_on_commit_callbacks(execute=True):
        services.notify_reservation_created(
            recipient_id=first.pk, reservation_id=uuid.uuid4(), payload={}
        )
        services.notify_reservation_created(
            recipient_id=second.pk, reservation_id=uuid.uuid4(), payload={}
        )
    elapsed = time.monotonic() - started

    assert elapsed < DEADLINE * 2, elapsed  # the second delivery is refused instantly
    assert len(hung_firebase.multicast_calls) == 1
    assert Notification.objects.count() == 2


@pytest.mark.django_db
def test_notification_and_message_survive_a_failing_whole_batch(
    account_factory, django_capture_on_commit_callbacks
):
    provider_account, patient, _, reservation = make_reservation_world(account_factory)
    conversation, _ = chat_services.get_or_create_reservation_conversation(
        reservation.pk, actor=patient
    )
    register(provider_account, 2)
    RecordingSender.batch_error = RuntimeError("fcm unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        notified = services.notify_reservation_created(
            recipient_id=provider_account.pk, reservation_id=reservation.pk, payload={}
        )
        response = client_for(patient).post(
            f"/api/v1/chat/conversations/{conversation.pk}/messages/", {"body": "hi"}
        )

    assert notified is True and response.status_code == 201
    assert (
        Notification.objects.filter(recipient=provider_account, read_at__isnull=True).count() == 1
    )
    assert Message.objects.count() == 1
    assert PushDevice.objects.filter(is_active=True).count() == 2
