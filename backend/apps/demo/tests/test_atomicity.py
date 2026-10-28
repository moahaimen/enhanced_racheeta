"""An interrupted seed never leaves unregistered demo rows (review P2-1).

Invariant checked after every interruption: every row that exists now but did not exist before the
seed started is owned by a `DemoRecord`. Each phase commits its rows, the rows its deferred
`on_commit` hooks create (notifications, ...) and their registry rows in ONE transaction, so a
failure anywhere inside a phase — including while the registry is written — rolls the whole phase
back, and the phases before it stay registered and clearable.
"""

from collections import defaultdict

import pytest
from django.apps import apps
from django.db import DatabaseError, connection

from apps.accounts.models import Account
from apps.demo.models import DemoRecord
from apps.demo.registry import EXCLUDED_APP_LABELS, Registry
from apps.demo.seeder import DemoSeeder
from apps.demo.tests.conftest import clear, seed
from apps.marketplace.models import MedicalCompany, Product
from apps.notifications.models import Notification
from apps.reservations import hooks as reservation_hooks
from apps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


def _crash(self):
    raise RuntimeError("process interrupted before this phase")


TRACKED = [
    m
    for m in apps.get_models()
    if m._meta.app_label not in EXCLUDED_APP_LABELS and not m._meta.auto_created
]


def _rows() -> dict[str, set[str]]:
    return {
        m._meta.label: {str(pk) for pk in m._base_manager.values_list("pk", flat=True)}
        for m in TRACKED
    }


def _unregistered_new_rows(before: dict[str, set[str]]) -> dict[str, int]:
    """Rows added since `before` that no DemoRecord owns (must always be empty)."""
    owned: dict[str, set[str]] = defaultdict(set)
    for label, pk in DemoRecord.objects.values_list("model_label", "object_pk"):
        owned[label].add(pk)
    now = _rows()
    missing = {}
    for label, pks in now.items():
        orphans = (pks - before[label]) - owned[label]
        if orphans:
            missing[label] = len(orphans)
    return missing


def _registered(label: str) -> int:
    return DemoRecord.objects.filter(model_label=label).count()


@pytest.fixture
def full_counts(db):
    """Registry counts of one complete, uninterrupted seed (the reference for retries)."""
    seed()
    counts = dict(DemoSeeder(password="x" * 12).summary())
    clear(yes=True)
    assert DemoRecord.objects.count() == 0
    return counts


# ---- A. the registry write itself fails ---------------------------------------------------------


def test_a_failing_registry_write_rolls_back_the_whole_phase(monkeypatch, full_counts):
    before = _rows()
    real_flush = Registry.flush
    calls = {"n": 0}

    def flaky_flush(self):
        calls["n"] += 1
        if calls["n"] == 2:  # phase 2: availability, reservations, reviews, offers, chat
            raise DatabaseError("connection lost while writing the registry")
        return real_flush(self)

    monkeypatch.setattr(Registry, "flush", flaky_flush)
    with pytest.raises(DatabaseError):
        seed()

    # nothing committed without its ownership record — neither rows nor their side effects
    assert _unregistered_new_rows(before) == {}
    assert _registered("accounts.Account") > 0  # phase 1 committed, fully registered
    assert Reservation.objects.count() == len(before["reservations.Reservation"])
    assert Notification.objects.count() == len(before["notifications.Notification"])
    assert _registered("reservations.Reservation") == 0

    # the operator retries: same password, completes, same result as an uninterrupted seed
    monkeypatch.setattr(Registry, "flush", real_flush)
    seed()
    assert _unregistered_new_rows(before) == {}
    assert dict(DemoSeeder(password="x" * 12).summary()) == full_counts

    # and cleanup still removes exactly what was added
    clear(yes=True)
    assert _rows() == before


# ---- B. a phase is interrupted after it already inserted rows -----------------------------------


def test_an_interrupted_phase_leaves_earlier_phases_registered_and_clearable(
    monkeypatch, full_counts
):
    before = _rows()
    real_phase = DemoSeeder.phase_marketplace

    def crashing_phase(self):
        real_phase(self)  # companies and products are inserted ...
        raise RuntimeError("process interrupted in the middle of the marketplace phase")

    monkeypatch.setattr(DemoSeeder, "phase_marketplace", crashing_phase)
    with pytest.raises(RuntimeError):
        seed()

    assert _unregistered_new_rows(before) == {}
    # phases 1-2 are committed and owned; the failed phase left nothing behind
    assert _registered("providers.ProviderProfile") > 0
    assert _registered("reservations.Reservation") > 0
    assert MedicalCompany.objects.count() == len(before["marketplace.MedicalCompany"])
    assert Product.objects.count() == len(before["marketplace.Product"])
    assert _registered("marketplace.Product") == 0

    # the committed part is clearable on its own ...
    clear(yes=True)
    assert _rows() == before
    # ... and a later full seed works from scratch
    monkeypatch.setattr(DemoSeeder, "phase_marketplace", real_phase)
    seed()
    assert _unregistered_new_rows(before) == {}
    assert dict(DemoSeeder(password="x" * 12).summary()) == full_counts


def test_a_retry_after_an_interruption_completes_the_seed(monkeypatch, full_counts):
    before = _rows()
    real_phase = DemoSeeder.phase_jobs
    monkeypatch.setattr(DemoSeeder, "phase_jobs", _crash)
    with pytest.raises(RuntimeError):
        seed()
    monkeypatch.setattr(DemoSeeder, "phase_jobs", real_phase)
    seed()  # reuses the registered phases (unique e-mails do not collide) and adds the rest
    assert _unregistered_new_rows(before) == {}
    assert dict(DemoSeeder(password="x" * 12).summary()) == full_counts


# ---- C. side effects created by the product's own deferred hooks --------------------------------


def test_side_effect_rows_are_registered_and_removed_by_cleanup(db):
    before = _rows()
    assert connection.run_on_commit == []
    seed()
    # notifications come from the reservation on_commit hooks; they are all owned
    created = Notification.objects.count() - len(before["notifications.Notification"])
    assert created > 0
    assert _registered("notifications.Notification") == created
    assert _unregistered_new_rows(before) == {}
    # no deferred hook of the seed is left waiting for a commit that would run it unrecorded
    assert connection.run_on_commit == []
    clear(yes=True)
    assert _rows() == before


def test_a_failing_deferred_hook_rolls_back_its_phase(monkeypatch, db):
    before = _rows()

    def broken_send(*args, **kwargs):
        raise DatabaseError("connection lost while running a deferred hook")

    monkeypatch.setattr(reservation_hooks.reservation_created, "send", broken_send)
    with pytest.raises(DatabaseError):
        seed()
    # reservations were inserted before the hook ran, but they rolled back with it
    assert Reservation.objects.count() == len(before["reservations.Reservation"])
    assert _unregistered_new_rows(before) == {}
    assert _registered("accounts.Account") > 0  # the phase before is intact
    clear(yes=True)
    assert _rows() == before


# ---- D. lifecycle --------------------------------------------------------------------------------


def test_seed_seed_clear_seed_clear_is_stable(db):
    before = _rows()
    seed()
    first_counts = dict(DemoSeeder(password="x" * 12).summary())
    first_rows = {label: len(pks) for label, pks in _rows().items()}
    seed()  # idempotent
    assert dict(DemoSeeder(password="x" * 12).summary()) == first_counts
    assert {label: len(pks) for label, pks in _rows().items()} == first_rows
    clear(yes=True)
    assert _rows() == before and DemoRecord.objects.count() == 0
    seed()
    assert dict(DemoSeeder(password="x" * 12).summary()) == first_counts
    assert {label: len(pks) for label, pks in _rows().items()} == first_rows
    assert _unregistered_new_rows(before) == {}
    clear(yes=True)
    assert _rows() == before and DemoRecord.objects.count() == 0
    assert not Account.objects.filter(email__endswith="@demo.racheeta.invalid").exists()
