import pytest
from django.core.management import call_command

DEMO_PASSWORD = "Demo-Test-Passw0rd!"


@pytest.fixture(autouse=True)
def _demo_env(monkeypatch):
    monkeypatch.setenv("DEMO_DATA_ENABLED", "true")
    monkeypatch.setenv("DEMO_PASSWORD", DEMO_PASSWORD)


def seed(**options):
    call_command("seed_demo_data", **options)


def clear(**options):
    call_command("clear_demo_data", **options)


@pytest.fixture
def seeded(db):
    seed()
