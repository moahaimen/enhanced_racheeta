"""In-process stand-ins for Firebase. Nothing here touches the network.

* `RecordingSender` replaces the whole sender (selected via settings.RACHEETA["PUSH_SENDER"]).
* `FakeMessaging` / `fake_sdk()` replace the Firebase Admin SDK handles, so the real
  `FirebaseAdminPushSender` adapter code (multicast call, per-token mapping, deadline runner)
  is exercised end to end. The SDK shapes mirror firebase-admin 7.7.0 (`MulticastMessage`,
  `BatchResponse.responses[i].success/.exception`).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from apps.notifications.push import (
    BoundedCallRunner,
    FirebaseAdminPushSender,
    FirebaseSdk,
    PushMessage,
    PushResult,
    classify_firebase_error,
)


class RecordingSender:
    """Whole-sender fake. `outcomes[token]` is a PushResult, or an Exception instance that is
    classified exactly like an SDK per-token error. `batch_error` fails the whole batch."""

    batches: list[tuple[tuple[str, ...], PushMessage]] = []
    calls: list[tuple[str, PushMessage]] = []  # flat: one entry per token attempted
    outcomes: dict[str, object] = {}
    batch_error: Exception | None = None

    @classmethod
    def reset(cls) -> None:
        cls.batches = []
        cls.calls = []
        cls.outcomes = {}
        cls.batch_error = None

    def send_batch(self, tokens, message: PushMessage) -> dict[str, PushResult]:
        cls = type(self)
        cls.batches.append((tuple(tokens), message))
        if cls.batch_error is not None:
            raise cls.batch_error
        results: dict[str, PushResult] = {}
        for token in tokens:
            cls.calls.append((token, message))
            outcome = cls.outcomes.get(token, PushResult.SENT)
            if isinstance(outcome, Exception):
                outcome = classify_firebase_error(outcome)
            results[token] = outcome  # type: ignore[assignment]
        return results


# --- fake Firebase Admin SDK -------------------------------------------------------------


@dataclass
class FakeNotification:
    title: str
    body: str


@dataclass
class FakeMulticastMessage:
    tokens: list[str]
    notification: FakeNotification
    data: dict[str, str]


@dataclass
class FakeSendResponse:
    success: bool
    exception: Exception | None = None


@dataclass
class FakeBatchResponse:
    responses: list[FakeSendResponse] = field(default_factory=list)


# Same class names as firebase_admin.messaging / firebase_admin.exceptions; the production
# classifier works on class names so it is independent of the SDK import.
class UnregisteredError(Exception): ...


class SenderIdMismatchError(Exception): ...


class QuotaExceededError(Exception): ...


class UnavailableError(Exception): ...


class InvalidArgumentError(Exception): ...


class FakeMessaging:
    """Stands in for the `firebase_admin.messaging` module.

    `responder(message)` returns the `FakeBatchResponse` (default: everything succeeds).
    `release` lets a test hold `send_each_for_multicast` open to simulate a hung Firebase.
    Per-token APIs are forbidden: calling them is the N x blocking-sends regression.
    """

    Notification = FakeNotification
    MulticastMessage = FakeMulticastMessage

    def __init__(self, responder=None, hang: threading.Event | None = None) -> None:
        self.multicast_calls: list[tuple[FakeMulticastMessage, Any]] = []
        self.responder = responder
        self.hang = hang  # when set, the call blocks until this event is set

    def send_each_for_multicast(self, message: FakeMulticastMessage, app=None):
        self.multicast_calls.append((message, app))
        if self.hang is not None:
            self.hang.wait(timeout=20)  # safety net so a failing test cannot hang the suite
        if self.responder is not None:
            return self.responder(message)
        return FakeBatchResponse([FakeSendResponse(True) for _ in message.tokens])

    def send(self, *args, **kwargs):  # noqa: ARG002
        raise AssertionError("per-token messaging.send is forbidden: use one multicast call")

    send_each = send
    send_all = send
    send_multicast = send


def fake_sdk(messaging: FakeMessaging | None = None) -> FirebaseSdk:
    return FirebaseSdk(messaging=messaging or FakeMessaging(), app="fake-app")


class FakeSdkFirebaseSender(FirebaseAdminPushSender):
    """The real adapter over a fake SDK (whose multicast call can be held open or scripted).

    `get_sender()` constructs the sender with no arguments, so the fake SDK and the shared
    runner (the bulkhead state must survive across deliveries) live on the class.
    """

    messaging: FakeMessaging = FakeMessaging()
    runner: BoundedCallRunner | None = None

    def __init__(self) -> None:
        super().__init__(sdk=fake_sdk(type(self).messaging), runner=type(self).runner)
