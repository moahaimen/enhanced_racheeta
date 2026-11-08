import pytest

from apps.jobs.types import PROFESSION_GROUPS, Profession

pytestmark = pytest.mark.django_db


def test_profession_groups_endpoint_is_public_and_healthcare_first(api_client):
    response = api_client.get("/api/v1/jobs/professions")
    assert response.status_code == 200
    groups = response.json()
    assert groups[0]["group"] == "HEALTHCARE"
    flat = [p for g in groups for p in g["professions"]]
    assert sorted(flat) == sorted(Profession.values)
    for expected in (
        "SOFTWARE_DEVELOPER",
        "CYBERSECURITY",
        "ACCOUNTANT",
        "MARKETING",
        "BIOMEDICAL_ENGINEER",
    ):
        assert expected in flat


def test_every_profession_has_exactly_one_group():
    flat = [p for members in PROFESSION_GROUPS.values() for p in members]
    assert len(flat) == len(set(flat)) == len(Profession.values)
