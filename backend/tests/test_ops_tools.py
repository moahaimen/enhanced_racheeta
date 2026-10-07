"""Safety rails of the operator tools: they must refuse to touch anything but local/test targets."""

import importlib.util
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import Account

REPO = Path(__file__).resolve().parents[2]


def _load(path: str):
    spec = importlib.util.spec_from_file_location("tool", REPO / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.django_db
def test_seed_synthetic_requires_explicit_confirmation():
    with pytest.raises(CommandError, match="confirm-synthetic"):
        call_command("seed_synthetic", providers=1)
    assert not Account.objects.filter(email__endswith="@synthetic.invalid").exists()


@pytest.mark.django_db
def test_seed_synthetic_refuses_a_non_local_database_host(settings, monkeypatch):
    from django.db import connection

    monkeypatch.setitem(connection.settings_dict, "HOST", "db.internal.example")
    with pytest.raises(CommandError, match="not local"):
        call_command("seed_synthetic", confirm_synthetic=True, providers=1)
    assert not Account.objects.filter(email__endswith="@synthetic.invalid").exists()


@pytest.mark.django_db
def test_seed_synthetic_writes_only_obviously_fake_rows():
    call_command("seed_synthetic", confirm_synthetic=True, providers=3, notifications=2)
    emails = list(
        Account.objects.filter(role__in=["PROVIDER", "PATIENT"]).values_list("email", flat=True)
    )
    synthetic = [e for e in emails if e.endswith("@synthetic.invalid")]
    assert len(synthetic) == 4  # 3 providers + 1 notification owner
    assert all(e.endswith("@synthetic.invalid") for e in emails)


@pytest.mark.parametrize(
    "url", ["https://racheeta.example.com", "https://api.railway.app", "http://10.0.0.5:8000"]
)
def test_load_harness_refuses_non_local_targets(url):
    harness = _load("scripts/loadtest/loadtest.py")
    with pytest.raises(SystemExit) as refused:
        harness.check_target(url, None)
    assert "refusing" in str(refused.value)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000", "http://localhost:8000", "https://stack.test", "http://x.invalid"],
)
def test_load_harness_accepts_local_and_reserved_targets(url):
    harness = _load("scripts/loadtest/loadtest.py")
    assert harness.check_target(url, None)


def test_load_harness_allows_a_named_staging_host_only_when_asked():
    harness = _load("scripts/loadtest/loadtest.py")
    assert harness.check_target("https://staging.example.com", "staging.example.com")
    with pytest.raises(SystemExit):
        harness.check_target("https://staging.example.com", "other.example.com")
