import pytest

from apps.providers.models import ServiceOffering

pytestmark = pytest.mark.django_db

SERVICES = "/api/v1/providers/me/services"


def test_crud_own_services(provider_client, cardiology):
    client, profile = provider_client
    created = client.post(
        SERVICES,
        {
            "title": "Consultation",
            "price": "25000",
            "specialty": str(cardiology.id),
            "duration_minutes": 30,
        },
    )
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["currency"] == "IQD"
    assert body["price"] == "25000.00"
    sid = body["id"]

    listed = client.get(SERVICES).json()
    assert [s["id"] for s in listed] == [sid]

    updated = client.patch(f"{SERVICES}/{sid}", {"price": "30000", "is_active": False})
    assert updated.status_code == 200
    assert updated.json()["price"] == "30000.00"
    assert updated.json()["is_active"] is False

    assert client.delete(f"{SERVICES}/{sid}").status_code == 204
    assert client.get(SERVICES).json() == []


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"title": "X", "price": "-1"}, "price"),
        ({"title": "X", "price": "10", "duration_minutes": 0}, "duration_minutes"),
        ({"title": "X", "price": "10", "currency": "XXX"}, "currency"),
        ({"price": "10"}, "title"),
        ({"title": "X"}, "price"),
        (
            {"title": "X", "price": "10", "specialty": "00000000-0000-4000-8000-000000000000"},
            "specialty",
        ),
    ],
)
def test_service_validation(provider_client, payload, field):
    client, _ = provider_client
    response = client.post(SERVICES, payload)
    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_duplicate_title_rejected(provider_client):
    client, _ = provider_client
    assert client.post(SERVICES, {"title": "Same", "price": "1"}).status_code == 201
    dup = client.post(SERVICES, {"title": " Same ", "price": "2"})
    assert dup.status_code == 400
    assert "title" in dup.json()["error"]["details"]


def test_cannot_touch_another_providers_service(provider_client, provider_factory):
    client, _ = provider_client
    other = provider_factory()
    foreign = ServiceOffering.objects.create(provider=other, title="Theirs", price="5.00")
    assert client.get(f"{SERVICES}/{foreign.id}").status_code == 404
    assert client.patch(f"{SERVICES}/{foreign.id}", {"title": "Mine"}).status_code == 404
    assert client.delete(f"{SERVICES}/{foreign.id}").status_code == 404
    foreign.refresh_from_db()
    assert foreign.title == "Theirs"


def test_services_require_a_profile(api_client, account_factory):
    api_client.force_authenticate(user=account_factory(role="PROVIDER"))
    response = api_client.get(SERVICES)
    assert response.status_code == 403
    assert "profile" in response.json()["error"]["message"].lower()


def test_services_require_provider_role(api_client, account_factory):
    api_client.force_authenticate(user=account_factory(role="PATIENT"))
    assert api_client.get(SERVICES).status_code == 403
