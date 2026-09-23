import pytest

from apps.geography.models import City, Country, Governorate

pytestmark = pytest.mark.django_db


def test_iraq_is_seeded():
    iraq = Country.objects.get(code="IQ")
    assert Governorate.objects.filter(country=iraq).count() == 19
    assert City.objects.filter(governorate__country=iraq).count() >= 40
    assert Governorate.objects.get(slug="baghdad").name_ar == "بغداد"


def test_reference_endpoints_are_public_and_unpaginated(api_client):
    countries = api_client.get("/api/v1/geo/countries").json()
    assert isinstance(countries, list) and countries[0]["code"] == "IQ"
    govs = api_client.get("/api/v1/geo/governorates", {"country": countries[0]["id"]}).json()
    assert len(govs) == 19
    assert {"id", "country", "slug", "name_ar", "name_en"} == set(govs[0])
    bgd = next(g for g in govs if g["slug"] == "baghdad")
    cities = api_client.get("/api/v1/geo/cities", {"governorate": bgd["id"]}).json()
    assert [c["slug"] for c in cities][0] == "baghdad"
    assert all(c["governorate"] == bgd["id"] for c in cities)


def test_inactive_entries_are_hidden(api_client):
    gov = Governorate.objects.get(slug="halabja")
    gov.is_active = False
    gov.save()
    slugs = [g["slug"] for g in api_client.get("/api/v1/geo/governorates").json()]
    assert "halabja" not in slugs
    assert api_client.get("/api/v1/geo/cities", {"governorate": str(gov.id)}).json() == []
