import pytest

from apps.specialties.models import Specialty

pytestmark = pytest.mark.django_db


def test_specialties_seeded_with_hierarchy():
    dentistry = Specialty.objects.get(slug="dentistry")
    ortho = Specialty.objects.get(slug="orthodontics")
    assert ortho.parent == dentistry
    assert dentistry.name_ar == "طب الأسنان"


def test_specialties_endpoint_public_unpaginated_and_bilingual(api_client):
    body = api_client.get("/api/v1/specialties").json()
    assert isinstance(body, list)
    assert len(body) >= 25
    item = next(s for s in body if s["slug"] == "orthodontics")
    assert set(item) == {"id", "slug", "name_ar", "name_en", "parent"}
    assert item["parent"] == str(Specialty.objects.get(slug="dentistry").id)


def test_inactive_specialty_hidden(api_client):
    Specialty.objects.filter(slug="pharmacy").update(is_active=False)
    assert "pharmacy" not in [s["slug"] for s in api_client.get("/api/v1/specialties").json()]
