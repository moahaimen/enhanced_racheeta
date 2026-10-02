"""Push transport boundary (Firebase Cloud Messaging).

Everything Firebase-specific lives here. The rest of the application asks
`push_service` to deliver a `PushMessage`; it never touches the SDK. PostgreSQL stays
authoritative: a push is a best-effort *hint* that something can be fetched.

Which sender runs comes from `settings.RACHEETA["PUSH_SENDER"]` (env `PUSH_SENDER`):

* `apps.notifications.push.DisabledPushSender` (default) — nothing is ever sent.
* `apps.notifications.push.FirebaseAdminPushSender` — real FCM delivery through the
  Firebase Admin SDK (`pip install firebase-admin`), using the same
  `FIREBASE_CREDENTIALS_FILE` service account as Firebase sign-in. Never committed.

Latency contract
----------------
Delivery runs synchronously after the originating transaction commits (there is no worker),
so its latency is added to the request that caused it. A sender therefore exposes ONE
operation, `send_batch(tokens, message)`, for *all* of a recipient's devices — never a
per-token send that a caller could loop over. `FirebaseAdminPushSender` makes it strictly
bounded in three layers:

1. one `messaging.send_each_for_multicast` call: the pinned SDK (firebase-admin 7.7.0)
   sends every token concurrently in one round, so latency does not grow with the number
   of devices (measured: 10 tokens at 0.5 s per request finish in ~0.5 s, not 5 s);
2. a hard caller-side deadline (`PUSH_BATCH_DEADLINE_SECONDS`). The SDK's own timeout is
   per socket operation and its retry policy is not configurable (a hung server cost 2×
   the timeout and a 503 storm ~7 s in measurement), so only a deadline in our code gives a
   real bound;
3. a bulkhead and a fail-fast window (`BoundedCallRunner`) so a hung Firebase can neither
   accumulate threads nor charge every request its own deadline.

Tests inject a fake sender or a fake SDK; no test contacts Firebase.
"""

from __future__ import annotations

import concurrent.futures
import enum
import logging
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

T = TypeVar("T")

PUSH_APP_NAME = "racheeta-push"
# Per-request socket timeout handed to the SDK. It is NOT the latency bound (see the module
# docstring); it limits how long abandoned background work can linger after a missed deadline.
PUSH_HTTP_TIMEOUT_SECONDS = 2
# Hard wall-clock bound on the whole fan-out as seen by the originating request.
PUSH_BATCH_DEADLINE_SECONDS = 3.0
# Max batches in flight per process; each holds a slot until it really finishes.
PUSH_MAX_INFLIGHT_BATCHES = 4
# After a missed deadline, refuse further batches instantly for this long (outage fail-fast).
PUSH_COOLDOWN_SECONDS = 10.0

# Firebase error classes that mean "this registration token is dead for good".
# Everything else (quota, unavailable, internal, network, auth) is transient.
PERMANENT_TOKEN_ERRORS = frozenset({"UnregisteredError", "SenderIdMismatchError"})


@dataclass(frozen=True, slots=True)
class PushMessage:
    """Privacy-preserving push content. Text must never carry private data; `data` holds
    only opaque ids the app uses to fetch the authoritative record after authenticating."""

    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


class PushResult(enum.Enum):
    SENT = "sent"
    INVALID_TOKEN = "invalid_token"  # noqa: S105 - permanent: deactivate the local registration
    TRANSIENT_FAILURE = "transient_failure"  # temporary: keep the registration


class PushDeliveryUnavailable(Exception):
    """The batch was refused or did not finish inside this call. It says nothing about any
    individual token, so callers must keep every registration unchanged."""


class PushBusy(PushDeliveryUnavailable):
    """All in-flight slots are held by earlier batches that have not finished yet."""


class PushPaused(PushDeliveryUnavailable):
    """Inside the fail-fast window that follows a missed deadline."""


class PushDeadlineExceeded(PushDeliveryUnavailable):
    """The batch did not finish within the hard deadline (it is abandoned, not cancelled)."""


class PushSender(Protocol):
    """One bounded operation per recipient. There is deliberately no per-token `send`.

    `send_batch` returns a result for each token it attempted (tokens missing from the mapping
    are treated as transient by the caller). Per-token failures are reported in the mapping, not
    raised. It may raise for a failure of the whole batch (including `PushDeliveryUnavailable`);
    the caller then keeps every registration. Implementations must return or raise within a
    time that does not depend on `len(tokens)`.
    """

    def send_batch(
        self, tokens: Sequence[str], message: PushMessage
    ) -> Mapping[str, PushResult]: ...


class DisabledPushSender:
    """Default. Development, test and unconfigured environments never send."""

    def send_batch(  # pragma: no cover - `push_service.deliver` never calls a disabled sender
        self, tokens: Sequence[str], message: PushMessage
    ) -> Mapping[str, PushResult]:
        raise ImproperlyConfigured("Push delivery is not enabled on this server.")


class BoundedCallRunner:
    """Run one blocking call under a hard caller-side deadline.

    * **Hard deadline:** `run` returns or raises within `deadline` seconds whatever the callable
      does. A running call cannot be interrupted, so after the deadline it is *abandoned*: it
      finishes in the background and its result is discarded.
    * **Bulkhead:** at most `max_inflight` calls are in flight per process, on a fixed pool of
      that many threads. A call keeps its slot until it has really finished, so a hung upstream
      can never accumulate threads or memory; surplus calls are refused at once (`PushBusy`).
    * **Fail-fast window:** after a missed deadline further calls are refused at once
      (`PushPaused`) for `cooldown` seconds, so an outage costs one deadline per window, not one
      per notification. `cooldown=0` disables the window.

    The callable runs on a pool thread: it must not use the database or any request state. It
    receives nothing and captures only plain data (tokens, message).
    """

    def __init__(
        self,
        *,
        max_inflight: int,
        deadline: float,
        cooldown: float,
        clock: Callable[[], float] = time.monotonic,
        name: str = "racheeta-push",
    ) -> None:
        self._max_inflight = max_inflight
        self._deadline = deadline
        self._cooldown = cooldown
        self._clock = clock
        self._name = name
        self._slots = threading.BoundedSemaphore(max_inflight)
        self._lock = threading.Lock()
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._paused_until = 0.0

    def run(self, call: Callable[[], T]) -> T:
        with self._lock:
            if self._clock() < self._paused_until:
                raise PushPaused("push delivery is paused after a missed deadline")
        if not self._slots.acquire(blocking=False):
            raise PushBusy("push delivery capacity is exhausted")
        try:
            future = self._pool().submit(self._execute, call)
        except BaseException:
            self._slots.release()
            raise
        try:
            ok, value = future.result(timeout=self._deadline)
        except concurrent.futures.TimeoutError:
            with self._lock:
                self._paused_until = self._clock() + self._cooldown
            raise PushDeadlineExceeded(
                f"push batch did not finish within {self._deadline:g}s"
            ) from None
        if ok:
            return value
        raise value

    def _execute(self, call: Callable[[], T]) -> tuple[bool, Any]:
        # Never raises: an exception raised by `call` itself (even a TimeoutError) is returned
        # as a value, so the only way `future.result` times out is the deadline.
        try:
            try:
                return True, call()
            except Exception as exc:  # noqa: BLE001
                return False, exc
        finally:
            self._slots.release()

    def _pool(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self._max_inflight, thread_name_prefix=self._name
                )
            return self._executor

    def shutdown(self, *, wait: bool = True) -> None:
        """Join the pool (tests, interpreter shutdown). Calls in flight are not interrupted."""
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=wait)


def classify_firebase_error(exc: BaseException) -> PushResult:
    """Map an SDK exception to a delivery outcome (by class name, so it is SDK-version safe)."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if names & PERMANENT_TOKEN_ERRORS:
        return PushResult.INVALID_TOKEN
    return PushResult.TRANSIENT_FAILURE


def results_from_batch(tokens: Sequence[str], response: Any) -> dict[str, PushResult]:
    """Per-token outcomes from an SDK `BatchResponse` (`responses[i]` answers `tokens[i]`).

    Only a one-to-one answer is trusted: if the counts differ nothing can be attributed to a
    token, so every token is transient and no registration is ever deactivated by guesswork.
    """
    responses = list(response.responses)
    if len(responses) != len(tokens):
        return {token: PushResult.TRANSIENT_FAILURE for token in tokens}
    results: dict[str, PushResult] = {}
    for token, item in zip(tokens, responses, strict=True):
        if item.success:
            results[token] = PushResult.SENT
        elif item.exception is not None:
            results[token] = classify_firebase_error(item.exception)
        else:
            results[token] = PushResult.TRANSIENT_FAILURE
    return results


@dataclass(frozen=True, slots=True)
class FirebaseSdk:
    """The two SDK handles the sender needs; tests substitute a fake with the same shape."""

    messaging: Any  # the `firebase_admin.messaging` module
    app: Any  # the named `firebase_admin.App`


_sdk_lock = threading.Lock()
_sdk: FirebaseSdk | None = None


def load_firebase_sdk() -> FirebaseSdk:  # pragma: no cover - needs the package and credentials
    """Import the SDK and initialize the dedicated push app once per process."""
    global _sdk
    with _sdk_lock:
        if _sdk is not None:
            return _sdk
        try:
            import firebase_admin  # type: ignore[import-not-found]
            from firebase_admin import credentials, messaging  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImproperlyConfigured(
                "FirebaseAdminPushSender needs the 'firebase-admin' package."
            ) from exc
        credentials_file = settings.RACHEETA["FIREBASE_CREDENTIALS_FILE"]
        if not credentials_file:
            raise ImproperlyConfigured("FIREBASE_CREDENTIALS_FILE is required for push delivery.")
        # A dedicated named app (not the sign-in default app) so its timeout is ours.
        try:
            app = firebase_admin.get_app(PUSH_APP_NAME)
        except ValueError:
            app = firebase_admin.initialize_app(
                credentials.Certificate(credentials_file),
                options={"httpTimeout": PUSH_HTTP_TIMEOUT_SECONDS},
                name=PUSH_APP_NAME,
            )
        _sdk = FirebaseSdk(messaging=messaging, app=app)
        return _sdk


_default_runner = BoundedCallRunner(
    max_inflight=PUSH_MAX_INFLIGHT_BATCHES,
    deadline=PUSH_BATCH_DEADLINE_SECONDS,
    cooldown=PUSH_COOLDOWN_SECONDS,
)


class FirebaseAdminPushSender:
    """Delivers one recipient's whole fan-out as a single bounded FCM operation.

    SDK API: `firebase_admin.messaging.send_each_for_multicast(MulticastMessage, app=...)`,
    returning a `BatchResponse` whose `responses[i]` (`.success`, `.exception`) answers
    `tokens[i]`. (The HTTP-batch `send_all`/`send_multicast` no longer exist in 7.x; the SDK
    sends the tokens concurrently on its own pool.) `Message.token`/`MulticastMessage.tokens`
    are marked deprecated in 7.7.0 in favour of Firebase Installation IDs but remain
    supported; revisit before upgrading the pinned SDK.
    """

    def __init__(
        self, *, sdk: FirebaseSdk | None = None, runner: BoundedCallRunner | None = None
    ) -> None:
        self._sdk = sdk if sdk is not None else load_firebase_sdk()
        self._runner = runner if runner is not None else _default_runner

    def send_batch(self, tokens: Sequence[str], message: PushMessage) -> Mapping[str, PushResult]:
        tokens = list(tokens)
        if not tokens:
            return {}
        sdk = self._sdk
        multicast = sdk.messaging.MulticastMessage(
            tokens=tokens,
            notification=sdk.messaging.Notification(title=message.title, body=message.body),
            data=dict(message.data),
        )
        response = self._runner.run(
            lambda: sdk.messaging.send_each_for_multicast(multicast, app=sdk.app)
        )
        return results_from_batch(tokens, response)


def get_sender_class() -> type:
    return import_string(settings.RACHEETA["PUSH_SENDER"])


def is_enabled() -> bool:
    return get_sender_class() is not DisabledPushSender


def get_sender() -> PushSender:
    return get_sender_class()()
