"""Push-token ownership is decided by the client's sequence, never by arrival or commit order.

Every test applies requests deliberately in the WRONG order (a stale register after a newer one,
the newer one first, a register after the unregister that followed it, ...) and asserts the final
owner / active state of the single token row.
"""

import threading
import time

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.notifications import push_service
from apps.notifications.models import PushDevice
from apps.notifications.push_service import StaleOwnership

DEVICES = "/api/v1/notifications/push-devices/"
UNREGISTER = "/api/v1/notifications/push-devices/unregister/"
TOKEN = "orderToken-" + "t" * 60


@pytest.fixture
def a(account_factory):
    return account_factory()


@pytest.fixture
def b(account_factory):
    return account_factory()


def client_for(account):
    client = APIClient()
    client.force_authenticate(account)
    return client


def register(account, seq, token=TOKEN, platform="ANDROID"):
    return push_service.register_device(account, token=token, platform=platform, ownership_seq=seq)


def unregister(account, seq, token=TOKEN):
    return push_service.unregister_device(account, token=token, ownership_seq=seq)


def row(token=TOKEN):
    return PushDevice.objects.get(token=token)


# --- register ordering -----------------------------------------------------------------


@pytest.mark.django_db
def test_stale_register_of_a_after_b_changes_nothing(a, b):
    register(a, 10)
    register(b, 20)
    with pytest.raises(StaleOwnership):
        register(a, 10)  # the late request of A, arriving after B's
    device = row()
    assert device.account_id == b.pk and device.is_active
    assert device.ownership_seq == 20


@pytest.mark.django_db
def test_network_order_inversion_larger_sequence_wins(a, b):
    register(b, 20)  # processed first although it was issued second
    with pytest.raises(StaleOwnership):
        register(a, 10)
    device = row()
    assert device.account_id == b.pk and device.is_active and device.ownership_seq == 20


@pytest.mark.django_db
def test_a_stale_register_modifies_no_field_at_all(a, b):
    register(b, 20, platform="IOS")
    before = row()
    with pytest.raises(StaleOwnership):
        register(a, 10, platform="ANDROID")
    after = row()
    for field in ("account_id", "platform", "is_active", "last_registered_at", "ownership_seq"):
        assert getattr(after, field) == getattr(before, field), field
    assert after.updated_at == before.updated_at


@pytest.mark.django_db
def test_exact_replay_by_the_owner_is_idempotent(a):
    first = register(a, 10)
    before = row()
    again = register(a, 10)
    after = row()
    assert again.pk == first.pk
    assert after.last_registered_at == before.last_registered_at
    assert after.updated_at == before.updated_at
    assert after.ownership_seq == 10 and after.is_active


@pytest.mark.django_db
def test_equal_sequence_from_another_account_is_stale(a, b):
    register(a, 10)
    with pytest.raises(StaleOwnership):
        register(b, 10)
    assert row().account_id == a.pk


@pytest.mark.django_db
def test_newer_register_by_the_same_account_refreshes(a):
    register(a, 10)
    before = row().last_registered_at
    register(a, 11)
    device = row()
    assert device.ownership_seq == 11 and device.last_registered_at >= before


# --- unregister ordering ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_late_register_cannot_resurrect_a_logged_out_account(a):
    register(a, 10)
    assert unregister(a, 20) is True
    assert row().is_active is False and row().ownership_seq == 20
    with pytest.raises(StaleOwnership):
        register(a, 10)  # the register that was delayed in the network
    device = row()
    assert device.is_active is False and device.ownership_seq == 20


@pytest.mark.django_db
def test_switch_ordering_b_owns_after_a_logout_whatever_arrives_late(a, b):
    register(a, 10)
    unregister(a, 20)
    register(b, 30)
    with pytest.raises(StaleOwnership):
        register(a, 10)
    assert unregister(a, 20) is False  # a late replay of A's unregister
    assert unregister(a, 15) is False
    device = row()
    assert device.account_id == b.pk and device.is_active and device.ownership_seq == 30


@pytest.mark.django_db
def test_an_unregister_that_arrives_before_its_register_leaves_a_marker(a):
    assert unregister(a, 20) is False  # unknown token: nothing to deactivate...
    marker = row()
    assert marker.is_active is False and marker.ownership_seq == 20  # ...but order is recorded
    with pytest.raises(StaleOwnership):
        register(a, 10)
    assert row().is_active is False


@pytest.mark.django_db
def test_a_marker_never_blocks_a_genuinely_newer_registration(a, b):
    unregister(a, 20)
    register(b, 30)
    device = row()
    assert device.account_id == b.pk and device.is_active


@pytest.mark.django_db
def test_stale_unregister_does_not_deactivate_a_newer_registration(a):
    register(a, 20)
    assert unregister(a, 10) is False
    assert row().is_active is True and row().ownership_seq == 20


@pytest.mark.django_db
def test_unregister_by_a_non_owner_changes_nothing_and_records_no_sequence(a, b):
    register(a, 10)
    assert unregister(b, 99) is False
    device = row()
    assert device.account_id == a.pk and device.is_active and device.ownership_seq == 10


@pytest.mark.django_db
def test_replayed_unregister_is_idempotent(a):
    register(a, 10)
    assert unregister(a, 20) is True
    before = row()
    assert unregister(a, 20) is False
    after = row()
    assert after.updated_at == before.updated_at and after.ownership_seq == 20


@pytest.mark.django_db
def test_markers_are_bounded_per_account(a):
    for i in range(1, 60):
        unregister(a, i, token=f"marker-{i:03d}-" + "m" * 40)
    inactive = PushDevice.objects.filter(account=a, is_active=False).count()
    assert inactive <= push_service.MAX_INACTIVE_DEVICES
    # the newest marker always survives
    assert PushDevice.objects.filter(token__startswith="marker-059-").exists()


# --- legacy (unsequenced) requests -----------------------------------------------------


@pytest.mark.django_db
def test_a_never_sequenced_row_keeps_the_legacy_behaviour(a, b):
    push_service.register_device(a, token=TOKEN, platform="WEB")
    push_service.register_device(b, token=TOKEN, platform="WEB")  # legacy transfer still works
    assert row().account_id == b.pk and row().ownership_seq is None
    assert push_service.unregister_device(b, token=TOKEN) is True
    assert row().is_active is False


@pytest.mark.django_db
def test_an_unsequenced_request_cannot_supersede_a_sequenced_row(a, b):
    register(a, 10)
    with pytest.raises(StaleOwnership):
        push_service.register_device(b, token=TOKEN, platform="WEB")  # legacy register
    assert push_service.unregister_device(a, token=TOKEN) is False  # legacy unregister
    device = row()
    assert device.account_id == a.pk and device.is_active and device.ownership_seq == 10


@pytest.mark.django_db
def test_a_legacy_row_becomes_sequenced_by_the_first_sequenced_request(a, b):
    push_service.register_device(a, token=TOKEN, platform="WEB")
    register(b, 5)
    assert row().ownership_seq == 5
    with pytest.raises(StaleOwnership):
        push_service.register_device(a, token=TOKEN, platform="WEB")


@pytest.mark.django_db
def test_an_unsequenced_unregister_of_an_unknown_token_creates_nothing(a):
    assert push_service.unregister_device(a, token=TOKEN) is False
    assert not PushDevice.objects.filter(token=TOKEN).exists()


# --- API -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_stale_register_is_a_typed_409_that_leaks_nothing(a, b):
    assert (
        client_for(a)
        .post(DEVICES, {"token": TOKEN, "platform": "ANDROID", "ownership_seq": 10})
        .status_code
        == 200
    )
    assert (
        client_for(b)
        .post(DEVICES, {"token": TOKEN, "platform": "ANDROID", "ownership_seq": 20})
        .status_code
        == 200
    )
    late = client_for(a).post(DEVICES, {"token": TOKEN, "platform": "ANDROID", "ownership_seq": 10})
    assert late.status_code == 409
    body = late.json()
    assert body["error"]["code"] == "stale_ownership"
    assert TOKEN not in late.content.decode() and str(b.pk) not in late.content.decode()
    assert row().account_id == b.pk


@pytest.mark.django_db
def test_api_unregister_answers_204_for_applied_stale_and_unknown(a, b):
    client = client_for(a)
    client.post(DEVICES, {"token": TOKEN, "platform": "ANDROID", "ownership_seq": 10})
    applied = client.post(UNREGISTER, {"token": TOKEN, "ownership_seq": 20})
    stale = client.post(UNREGISTER, {"token": TOKEN, "ownership_seq": 15})
    foreign = client_for(b).post(UNREGISTER, {"token": TOKEN, "ownership_seq": 99})
    unknown = client.post(UNREGISTER, {"token": "nope-" + "z" * 40})
    assert {applied.status_code, stale.status_code, foreign.status_code, unknown.status_code} == {
        204
    }
    assert applied.content == stale.content == foreign.content == unknown.content
    assert row().is_active is False and row().ownership_seq == 20


@pytest.mark.django_db
@pytest.mark.parametrize("seq", [0, -5, 2**63, "abc", 1.5, None])
def test_api_rejects_invalid_sequences_on_both_endpoints(a, seq):
    client = client_for(a)
    assert (
        client.post(
            DEVICES, {"token": TOKEN, "platform": "ANDROID", "ownership_seq": seq}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.post(UNREGISTER, {"token": TOKEN, "ownership_seq": seq}, format="json").status_code
        == 400
    )


@pytest.mark.django_db
def test_api_largest_sequence_is_accepted_and_the_response_never_returns_it(a):
    response = client_for(a).post(
        DEVICES, {"token": TOKEN, "platform": "ANDROID", "ownership_seq": 2**63 - 1}
    )
    assert response.status_code == 200
    assert "ownership_seq" not in response.json()
    assert row().ownership_seq == 2**63 - 1


@pytest.mark.django_db
def test_api_legacy_requests_still_work_on_new_tokens(a):
    assert client_for(a).post(DEVICES, {"token": TOKEN, "platform": "ANDROID"}).status_code == 200
    assert client_for(a).post(UNREGISTER, {"token": TOKEN}).status_code == 204
    assert row().is_active is False


# --- concurrency -----------------------------------------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("delay_older", [False, True])
def test_concurrent_registers_the_larger_sequence_wins_regardless_of_arrival(
    account_factory, delay_older
):
    a, b = account_factory(), account_factory()
    outcomes = {}

    def run(name, account, seq, delay):
        try:
            time.sleep(delay)
            register(account, seq)
            outcomes[name] = "applied"
        except StaleOwnership:
            outcomes[name] = "stale"
        finally:
            connection.close()

    older_delay, newer_delay = (0.15, 0.0) if delay_older else (0.0, 0.15)
    threads = [
        threading.Thread(target=run, args=("old", a, 10, older_delay)),
        threading.Thread(target=run, args=("new", b, 20, newer_delay)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    device = row()
    assert device.account_id == b.pk and device.is_active and device.ownership_seq == 20
    assert outcomes["new"] == "applied"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_register_and_unregister_are_ordered_by_sequence(account_factory):
    a = account_factory()

    def reg():
        try:
            register(a, 10)
        except StaleOwnership:
            pass
        finally:
            connection.close()

    def unreg():
        try:
            unregister(a, 20)
        finally:
            connection.close()

    for _ in range(5):
        PushDevice.objects.all().delete()
        threads = [threading.Thread(target=unreg), threading.Thread(target=reg)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        device = row()
        assert device.is_active is False and device.ownership_seq == 20
