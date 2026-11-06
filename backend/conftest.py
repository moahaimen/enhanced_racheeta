"""Shared pytest fixtures for the whole backend test suite."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Account

DEFAULT_PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache; isolate every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def account_factory(db):
    counter = {"n": 0}

    def _make(**overrides) -> Account:
        counter["n"] += 1
        data = {
            "email": f"user{counter['n']}@example.com",
            "password": DEFAULT_PASSWORD,
            "full_name": f"Test User {counter['n']}",
        }
        data.update(overrides)
        return Account.objects.create_user(**data)

    return _make


@pytest.fixture
def account(account_factory) -> Account:
    return account_factory()


@pytest.fixture
def auth_client(api_client, account) -> APIClient:
    api_client.force_authenticate(user=account)
    return api_client


LEDGER_TABLES = ("ledger_line", "ledger_entry", "ledger_recovery", "ledger_commission_policy")


def _empty_ledger_tables(using="default"):
    from django.db import connections, transaction

    with transaction.atomic(using=using), connections[using].cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        for table in LEDGER_TABLES:
            cursor.execute(f'ALTER TABLE "{table}" DISABLE TRIGGER USER')  # noqa: S608
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")  # no deferred FK checks left pending
        for table in LEDGER_TABLES:
            cursor.execute(f'DELETE FROM "{table}"')  # noqa: S608 (fixed table names)
        for table in LEDGER_TABLES:
            cursor.execute(f'ALTER TABLE "{table}" ENABLE TRIGGER USER')  # noqa: S608


@pytest.fixture(autouse=True, scope="session")
def _ledger_aware_test_flush():
    """Transactional tests are reset by `flush` (TRUNCATE), which the ledger refuses while it
    holds rows (apps/ledger/migrations/0004). For the TEST database only — the test user owns
    it — empty the ledger tables with the row triggers disabled, inside one transaction, right
    before Django's own flush. Production code has no equivalent path."""
    from django.core.management.commands import flush

    original = flush.Command.handle

    def handle(self, **options):
        _empty_ledger_tables(options.get("database", "default"))
        return original(self, **options)

    flush.Command.handle = handle
    yield
    flush.Command.handle = original
