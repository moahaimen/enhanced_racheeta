"""Non-API pages on the API port: 404 normally, redirect to the web app only in local-demo debug."""

import pytest

pytestmark = pytest.mark.django_db


def test_without_a_build_non_api_pages_are_404(client, settings, monkeypatch):
    settings.SPA_DIST_DIR = None
    settings.DEBUG = False
    monkeypatch.setenv("RACHEETA_LOCAL_DEMO", "1")
    assert client.get("/dashboard").status_code == 404


def test_debug_without_local_demo_flag_stays_404(client, settings, monkeypatch):
    settings.SPA_DIST_DIR = None
    settings.DEBUG = True
    monkeypatch.delenv("RACHEETA_LOCAL_DEMO", raising=False)
    assert client.get("/dashboard").status_code == 404


def test_local_demo_debug_redirects_to_the_web_app(client, settings, monkeypatch):
    settings.SPA_DIST_DIR = None
    settings.DEBUG = True
    settings.RACHEETA = {**settings.RACHEETA, "FRONTEND_URL": "http://127.0.0.1:5180"}
    monkeypatch.setenv("RACHEETA_LOCAL_DEMO", "1")
    response = client.get("/dashboard?ws=personal")
    assert response.status_code == 302
    assert response["Location"] == "http://127.0.0.1:5180/dashboard?ws=personal"
    assert client.get("/api/v1/store/products").status_code == 200  # the API is never redirected
