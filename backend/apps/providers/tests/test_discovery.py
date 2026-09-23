import pytest

from apps.providers.types import ProviderType, VerificationStatus

pytestmark = pytest.mark.django_db

LIST = "/api/v1/providers"


def test_list_is_public_and_paginated(api_client, provider_factory):
    for _ in range(3):
        provider_factory()
    response = api_client.get(LIST)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 3
    card = body["results"][0]
    assert set(card) == {
        "id",
        "provider_type",
        "kind",
        "display_name",
        "governorate",
        "city",
        "specialties",
        "image_url",
    }
    assert "rating" not in card  # Phase 4: never fabricated


def test_only_verified_visible_active_providers_are_listed(
    api_client, provider_factory, account_factory
):
    visible = provider_factory(display_name="Visible")
    provider_factory(display_name="Unverified", verification_status=VerificationStatus.UNVERIFIED)
    provider_factory(display_name="Pending", verification_status=VerificationStatus.PENDING)
    provider_factory(display_name="Rejected", verification_status=VerificationStatus.REJECTED)
    provider_factory(display_name="Suspended", verification_status=VerificationStatus.SUSPENDED)
    provider_factory(display_name="Hidden", is_visible=False)
    inactive = account_factory(role="PROVIDER", is_active=False)
    provider_factory(display_name="Inactive account", account=inactive)

    names = [r["display_name"] for r in api_client.get(LIST).json()["results"]]
    assert names == [visible.display_name]


def test_filter_by_type_kind_specialty_governorate_city(
    api_client, provider_factory, baghdad, basra, baghdad_city, cardiology, dentistry
):
    doc_bgd = provider_factory(
        display_name="Doc Baghdad", specialties=[cardiology], city=baghdad_city
    )
    provider_factory(display_name="Dentist Basra", specialties=[dentistry], governorate=basra)
    hospital = provider_factory(display_name="Hospital", provider_type=ProviderType.HOSPITAL)

    def names(**params):
        return sorted(r["display_name"] for r in api_client.get(LIST, params).json()["results"])

    assert names(type="DOCTOR") == ["Dentist Basra", "Doc Baghdad"]
    assert names(type="HOSPITAL") == [hospital.display_name]
    assert names(kind="FACILITY") == [hospital.display_name]
    assert names(kind="PRACTITIONER") == ["Dentist Basra", "Doc Baghdad"]
    assert names(specialty="cardiology") == ["Doc Baghdad"]
    assert names(specialty="dentistry") == ["Dentist Basra"]
    assert names(specialty="no-such-specialty") == []
    assert names(governorate=str(basra.id)) == ["Dentist Basra"]
    assert names(city=str(baghdad_city.id)) == [doc_bgd.display_name]
    assert names(governorate=str(baghdad.id), type="DOCTOR") == ["Doc Baghdad"]
    assert names(search="hosp") == [hospital.display_name]


def test_invalid_filter_values_are_400(api_client):
    assert api_client.get(LIST, {"type": "WIZARD"}).status_code == 400
    assert api_client.get(LIST, {"governorate": "not-a-uuid"}).status_code == 400


def test_ordering(api_client, provider_factory):
    provider_factory(display_name="Beta")
    provider_factory(display_name="Alpha")
    names = [
        r["display_name"]
        for r in api_client.get(LIST, {"ordering": "-display_name"}).json()["results"]
    ]
    assert names == ["Beta", "Alpha"]
    assert (
        api_client.get(LIST, {"ordering": "verification_status"}).status_code == 200
    )  # ignored, not leaked


def test_pagination_page_size(api_client, provider_factory):
    for i in range(5):
        provider_factory(display_name=f"P{i}")
    body = api_client.get(LIST, {"page_size": 2, "page": 2}).json()
    assert body["count"] == 5
    assert len(body["results"]) == 2
    assert body["next"] and body["previous"]


def test_list_query_count_is_constant(
    api_client, provider_factory, cardiology, django_assert_max_num_queries
):
    for i in range(8):
        provider_factory(display_name=f"P{i}", specialties=[cardiology])
    # count + rows + specialties prefetch (+ through table) — never per row
    with django_assert_max_num_queries(4):
        response = api_client.get(LIST)
    assert response.json()["count"] == 8


def test_specialty_filter_does_not_duplicate_rows(
    api_client, provider_factory, cardiology, dentistry
):
    provider_factory(display_name="Multi", specialties=[cardiology, dentistry])
    body = api_client.get(LIST, {"specialty": "cardiology"}).json()
    assert body["count"] == 1
