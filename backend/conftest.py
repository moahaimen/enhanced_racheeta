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
