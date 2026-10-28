"""Demo credentials are never rotated or misreported by a re-run (review P2-2)."""

from pathlib import Path

import pytest
from django.contrib.auth.hashers import check_password
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.demo.content import common
from apps.demo.models import DemoRecord
from apps.demo.seeder import DemoSeeder
from apps.demo.tests.conftest import DEMO_PASSWORD, clear, seed

pytestmark = pytest.mark.django_db


def _crash(self):
    raise RuntimeError("process interrupted before this phase")


REPO = Path(__file__).resolve().parents[4]


def _printed_password(out: str) -> str:
    line = next(item for item in out.splitlines() if "Shared demo password" in item)
    return line.rsplit(": ", 1)[1].strip().replace("\x1b[0m", "").replace("\x1b[33;1m", "")


def _hashes() -> set[str]:
    records = DemoRecord.objects.filter(model_label="accounts.Account")
    pks = list(records.values_list("object_pk", flat=True))
    return set(Account.objects.filter(pk__in=pks).values_list("password", flat=True))


def _logs_in(password: str) -> bool:
    body = {"email": common.email("patient-sara"), "password": password}
    response = APIClient().post("/api/v1/auth/login", body, format="json")
    return response.status_code == 200


def test_initial_generated_password_authenticates_a_seeded_account(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_PASSWORD")
    seed(generate_password=True)
    generated = _printed_password(capsys.readouterr().out)
    assert len(generated) >= 12
    assert _logs_in(generated)


def test_generate_password_is_refused_once_demo_accounts_exist(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_PASSWORD")
    seed(generate_password=True)
    original = _printed_password(capsys.readouterr().out)
    hashes, registry = _hashes(), DemoRecord.objects.count()

    with pytest.raises(CommandError, match="only valid for the initial seed"):
        seed(generate_password=True)

    out = capsys.readouterr().out
    assert "Shared demo password" not in out  # no new, unusable credential is printed
    assert _hashes() == hashes and DemoRecord.objects.count() == registry  # nothing changed
    assert _logs_in(original)


def test_generate_password_works_again_after_clear(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_PASSWORD")
    seed(generate_password=True)
    first = _printed_password(capsys.readouterr().out)
    clear(yes=True)
    seed(generate_password=True)
    second = _printed_password(capsys.readouterr().out)
    assert second != first and _logs_in(second) and not _logs_in(first)


def test_idempotent_rerun_with_the_same_demo_password(capsys):
    seed()
    hashes, registry = _hashes(), DemoRecord.objects.count()
    seed()
    assert _hashes() == hashes and DemoRecord.objects.count() == registry
    assert DEMO_PASSWORD not in capsys.readouterr().out
    assert _logs_in(DEMO_PASSWORD)


def test_a_different_demo_password_on_an_existing_seed_is_refused(monkeypatch):
    seed()
    hashes, registry = _hashes(), DemoRecord.objects.count()
    monkeypatch.setenv("DEMO_PASSWORD", "A-Completely-Different-Pass-42")
    with pytest.raises(CommandError, match="does not match"):
        seed()
    assert _hashes() == hashes and DemoRecord.objects.count() == registry
    assert _logs_in(DEMO_PASSWORD)
    assert not _logs_in("A-Completely-Different-Pass-42")


def test_generated_password_survives_a_failure_after_accounts_were_committed(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_PASSWORD")
    real_phase = DemoSeeder.phase_marketplace
    monkeypatch.setattr(DemoSeeder, "phase_marketplace", _crash)
    with pytest.raises(RuntimeError):
        seed(generate_password=True)
    out = capsys.readouterr().out
    assert "seed failed after demo accounts were created" in out
    generated = _printed_password(out)
    assert _logs_in(generated)
    # the documented recovery: retry with that password
    monkeypatch.setattr(DemoSeeder, "phase_marketplace", real_phase)
    monkeypatch.setenv("DEMO_PASSWORD", generated)
    seed()
    assert _logs_in(generated)


def test_no_plaintext_password_is_stored(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_PASSWORD")
    seed(generate_password=True)
    generated = _printed_password(capsys.readouterr().out)
    for values in DemoRecord.objects.values_list("model_label", "object_pk", "key"):
        assert all(generated not in (v or "") for v in values)
    for stored in _hashes():
        assert stored != generated and generated not in stored
        assert check_password(generated, stored)
    # the committed example environment carries no demo password value
    example = (REPO / ".env.example").read_text()
    line = next(item for item in example.splitlines() if "DEMO_PASSWORD=" in item)
    value = line.split("DEMO_PASSWORD=", 1)[1].split("#")[0].strip()
    assert line.lstrip().startswith("#") and value == ""
