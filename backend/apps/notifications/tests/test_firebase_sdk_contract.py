"""Contract tests against the REAL firebase-admin SDK. Nothing here contacts Firebase.

`firebase-admin` is a production-only dependency (requirements/production.txt), so this module
is skipped where it is not installed (the default CI image). Run it with the SDK on the path:

    pip install firebase-admin==7.7.0   # or PYTHONPATH=<dir with the SDK>
    pytest apps/notifications/tests/test_firebase_sdk_contract.py

A loopback HTTP server plays fcm.googleapis.com. It lets the tests prove the claims the
delivery design rests on, against the real SDK code path:

* `send_each_for_multicast` sends all tokens concurrently in one operation;
* per-token failures arrive as typed exceptions that map to permanent / transient;
* the SDK's own timeout + retry policy is NOT a strict bound, so the runner's hard deadline is.
"""

import json
import socket
import threading
import time
import uuid

import pytest

firebase_admin = pytest.importorskip("firebase_admin")

import google.auth.credentials  # noqa: E402
import requests  # noqa: E402
from firebase_admin import _http_client, credentials, messaging  # noqa: E402

from apps.notifications import push  # noqa: E402
from apps.notifications.push import BoundedCallRunner, PushResult  # noqa: E402


class _FakeCredential(credentials.Base):
    def get_credential(self):
        return google.auth.credentials.AnonymousCredentials()


class _FakeFcm:
    """Loopback stand-in for the FCM v1 endpoint; `behaviour(token)` scripts each request."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.requests = 0
        self._stop = threading.Event()
        self._server = socket.socket()
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(64)
        self.port = self._server.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self):
        self._stop.set()
        self._server.close()

    def _accept(self):
        self._server.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except (TimeoutError, OSError):
                continue
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            token = json.loads(self._read_body(conn))["message"]["token"]
            self.requests += 1
            outcome = self.behaviour(token)
            if outcome is None:  # hang: accept, read, never answer
                time.sleep(30)
                return
            status, payload = outcome
            body = json.dumps(payload).encode()
            head = (
                f"HTTP/1.1 {status} X\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
            )
            conn.sendall(head.encode() + body)
        except OSError:
            pass
        finally:
            conn.close()

    @staticmethod
    def _read_body(conn):
        conn.settimeout(10)
        data = b""
        while b"\r\n\r\n" not in data:
            data += conn.recv(65536)
        head, _, body = data.partition(b"\r\n\r\n")
        length = next(
            int(line.split(b":")[1])
            for line in head.split(b"\r\n")
            if line.lower().startswith(b"content-length:")
        )
        while len(body) < length:
            body += conn.recv(65536)
        return body


def _error(status, http_status, code):
    detail = {
        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
        "errorCode": code,
    }
    return status, {
        "error": {"code": status, "status": http_status, "message": "x", "details": [detail]}
    }


OK = (200, {"name": "projects/demo/messages/1"})


@pytest.fixture
def fcm_sdk():
    """Factory: real SDK app pointed at a scripted loopback FCM."""
    created = []

    def make(behaviour, *, http_timeout=2, sdk_retries=False):
        fake = _FakeFcm(behaviour)
        app = firebase_admin.initialize_app(
            _FakeCredential(),
            options={"projectId": "demo", "httpTimeout": http_timeout},
            name=f"contract-{uuid.uuid4().hex[:8]}",
        )
        service = messaging._get_messaging_service(app)
        service._fcm_url = f"http://127.0.0.1:{fake.port}/v1/projects/demo/messages:send"
        retries = _http_client.DEFAULT_RETRY_CONFIG if sdk_retries else 0
        service._client.session.mount(
            "http://127.0.0.1",
            requests.adapters.HTTPAdapter(
                pool_connections=100, pool_maxsize=100, max_retries=retries
            ),
        )
        created.append((app, fake))
        return push.FirebaseSdk(messaging=messaging, app=app), fake

    yield make
    for app, fake in created:
        fake.close()
        firebase_admin.delete_app(app)


def _runner(**overrides):
    options = {"max_inflight": 2, "deadline": 5.0, "cooldown": 0, "name": "contract"}
    options.update(overrides)
    return BoundedCallRunner(**options)


def test_the_sdk_offers_the_multicast_api_the_sender_uses():
    assert callable(messaging.send_each_for_multicast)
    assert hasattr(messaging, "MulticastMessage") and hasattr(messaging, "Notification")


def test_multicast_sends_every_token_concurrently_in_one_operation(fcm_sdk):
    def slow(token):
        time.sleep(0.4)
        return OK

    sdk, fake = fcm_sdk(slow)
    runner = _runner()
    try:
        tokens = [f"tok{i}" for i in range(10)]
        started = time.monotonic()
        results = push.FirebaseAdminPushSender(sdk=sdk, runner=runner).send_batch(
            tokens, push.PushMessage("t", "b", {"type": "x"})
        )
        elapsed = time.monotonic() - started
    finally:
        runner.shutdown()
    assert fake.requests == 10
    assert results == {token: PushResult.SENT for token in tokens}
    assert elapsed < 2.0, elapsed  # sequential sends would take 10 x 0.4 = 4 s


def test_real_per_token_errors_map_to_permanent_and_transient(fcm_sdk):
    script = {
        "ok": OK,
        "unregistered": _error(404, "NOT_FOUND", "UNREGISTERED"),
        "mismatch": _error(403, "PERMISSION_DENIED", "SENDER_ID_MISMATCH"),
        "quota": _error(429, "RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED"),
        "unavailable": _error(503, "UNAVAILABLE", "UNAVAILABLE"),
        "invalid": (400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "x"}}),
    }
    sdk, _ = fcm_sdk(script.__getitem__)
    runner = _runner()
    try:
        results = push.FirebaseAdminPushSender(sdk=sdk, runner=runner).send_batch(
            list(script), push.PushMessage("t", "b")
        )
    finally:
        runner.shutdown()
    assert results == {
        "ok": PushResult.SENT,
        "unregistered": PushResult.INVALID_TOKEN,
        "mismatch": PushResult.INVALID_TOKEN,
        "quota": PushResult.TRANSIENT_FAILURE,
        "unavailable": PushResult.TRANSIENT_FAILURE,
        "invalid": PushResult.TRANSIENT_FAILURE,
    }


def test_the_sdks_own_retry_policy_is_not_a_bound_but_the_deadline_is(fcm_sdk):
    # Production retry policy on a server that never answers: the SDK alone needs ~2 x timeout.
    sdk, _ = fcm_sdk(lambda token: None, http_timeout=1, sdk_retries=True)
    runner = _runner(deadline=0.4)
    sender = push.FirebaseAdminPushSender(sdk=sdk, runner=runner)
    try:
        started = time.monotonic()
        with pytest.raises(push.PushDeadlineExceeded):
            sender.send_batch([f"tok{i}" for i in range(10)], push.PushMessage("t", "b"))
        assert time.monotonic() - started < 1.5  # 10 devices, still one deadline
    finally:
        runner.shutdown()  # joins the abandoned call (bounded by the SDK timeouts)
