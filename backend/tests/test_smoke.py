"""Smoke tests: the project boots, routes resolve, contracts are wired."""

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse


def test_settings_are_production_safe_in_tests():
    assert settings.DEBUG is False
    assert settings.AUTH_USER_MODEL == "accounts.Account"
    assert "rest_framework_simplejwt.token_blacklist" in settings.INSTALLED_APPS


@pytest.mark.django_db
def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


def test_openapi_schema_is_served(client):
    response = client.get(reverse("openapi-schema"))
    assert response.status_code == 200
    schema = yaml.safe_load(response.content)
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


def test_openapi_docs_page(client):
    response = client.get(reverse("openapi-docs"))
    assert response.status_code == 200


def test_unknown_api_path_returns_json_404(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unknown_non_api_path_is_404_without_spa_build(client):
    assert settings.SPA_DIST_DIR is None
    response = client.get("/some/client/route")
    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_login_page_resolves(client):
    response = client.get(f"/{settings.ADMIN_URL_PATH}login/")
    assert response.status_code == 200
