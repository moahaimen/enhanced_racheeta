import pytest

from apps.providers.models import ServiceOffering
from apps.providers.services import accept_membership, create_membership
from apps.providers.types import ProviderType, VerificationStatus

pytestmark = pytest.mark.django_db


def url(profile):
    return f"/api/v1/providers/{profile.id}"


def test_detail_shows_public_fields_services_and_related(api_client, provider_factory, cardiology):
    doctor = provider_factory(
        display_name="Dr Public",
        specialties=[cardiology],
        about="About me",
        phone="+9647700000000",
        public_email="dr@example.com",
        website="https://dr.example",
        address="Street 1",
        latitude="33.312800",
        longitude="44.361500",
    )
    ServiceOffering.objects.create(
        provider=doctor, title="Consultation", price="25000.00", specialty=cardiology
    )
    ServiceOffering.objects.create(provider=doctor, title="Old", price="1.00", is_active=False)
    hospital = provider_factory(display_name="City Hospital", provider_type=ProviderType.HOSPITAL)
    hidden_hospital = provider_factory(
        display_name="Hidden", provider_type=ProviderType.HOSPITAL, is_visible=False
    )
    accept_membership(create_membership(initiator=doctor, counterpart=hospital), hospital)
    m2 = create_membership(initiator=doctor, counterpart=hidden_hospital)
    accept_membership(m2, hidden_hospital)

    body = api_client.get(url(doctor)).json()
    assert body["display_name"] == "Dr Public"
    assert body["about"] == "About me"
    assert body["specialties"][0]["slug"] == "cardiology"
    assert [s["title"] for s in body["services"]] == ["Consultation"]
    assert body["services"][0]["specialty"]["slug"] == "cardiology"
    assert [r["display_name"] for r in body["related_providers"]] == ["City Hospital"]
    assert body["latitude"] == "33.312800"
    for secret in ("account", "verification_note", "is_visible", "email", "rating"):
        assert secret not in body
    assert "verified_at" in body


def test_facility_detail_lists_active_public_practitioners(api_client, provider_factory):
    hospital = provider_factory(display_name="Hosp", provider_type=ProviderType.HOSPITAL)
    doc = provider_factory(display_name="Doc")
    pending_doc = provider_factory(display_name="Pending doc")
    accept_membership(create_membership(initiator=hospital, counterpart=doc), doc)
    create_membership(initiator=hospital, counterpart=pending_doc)  # stays PENDING
    body = api_client.get(url(hospital)).json()
    assert [r["display_name"] for r in body["related_providers"]] == ["Doc"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"verification_status": VerificationStatus.UNVERIFIED},
        {"verification_status": VerificationStatus.PENDING},
        {"verification_status": VerificationStatus.SUSPENDED},
        {"is_visible": False},
    ],
)
def test_non_discoverable_detail_is_404(api_client, provider_factory, kwargs):
    profile = provider_factory(**kwargs)
    response = api_client.get(url(profile))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unknown_id_is_404(api_client):
    assert (
        api_client.get("/api/v1/providers/00000000-0000-4000-8000-000000000000").status_code == 404
    )


def test_detail_query_count(
    api_client, provider_factory, cardiology, django_assert_max_num_queries
):
    doctor = provider_factory(specialties=[cardiology])
    for i in range(5):
        ServiceOffering.objects.create(
            provider=doctor, title=f"S{i}", price="10.00", specialty=cardiology
        )
    with django_assert_max_num_queries(6):
        assert api_client.get(url(doctor)).status_code == 200
