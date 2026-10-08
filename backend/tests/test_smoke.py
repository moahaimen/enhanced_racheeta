"""Smoke tests: the project boots, routes resolve, contracts are wired."""

from io import StringIO

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command


def test_settings_are_production_safe_in_tests():
    assert settings.DEBUG is False
    assert settings.AUTH_USER_MODEL == "accounts.Account"
    assert "rest_framework_simplejwt.token_blacklist" in settings.INSTALLED_APPS


@pytest.mark.django_db
def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


def test_openapi_schema_is_generated():
    """The committed contract is generated from code (CI diffs it); the HTTP endpoints are
    development-only (see tests/test_phase12a_hardening.py)."""
    out = StringIO()
    call_command("spectacular", stdout=out, verbosity=0)
    schema = yaml.safe_load(out.getvalue())
    assert schema["openapi"].startswith("3.")
    paths = set(schema["paths"])
    for expected in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/me",
    ):
        assert expected in paths
