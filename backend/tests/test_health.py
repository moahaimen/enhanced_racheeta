import pytest
from django.urls import reverse


def test_health_returns_ok(client):
    response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Cache-Control"].startswith("max-age=0")


def test_health_requires_no_auth_and_no_database(client):
    # No django_db marker: any DB access would fail loudly.
    response = client.get("/health/")
    assert response.status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_health_rejects_non_get(client, method):
    response = getattr(client, method)("/health/")
    assert response.status_code == 405
