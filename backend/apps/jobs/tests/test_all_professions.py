"""Phase C: jobs for every profession, healthcare first.

* the taxonomy covers healthcare, health business, technology, business, education and other
  fields, and stays backward compatible (every pre-existing code is unchanged);
* a non-healthcare business (organization type BUSINESS) is admin-verified like any employer
  and may only post / submit / search NON-clinical roles; its type is frozen once verified;
* a candidate who applied stays visible to that employer even when the profession is clinical
  and the employer could not search for it; other employers never see them.
"""

import pytest
from rest_framework.test import APIClient

from apps.jobs import services
from apps.jobs.models import JobPost
from apps.jobs.types import CLINICAL_PROFESSIONS, PROFESSION_GROUPS, JobStatus, Profession

from .conftest import owner_of

pytestmark = pytest.mark.django_db

JOBS = "/api/v1/jobs/employer/jobs"
TALENT = "/api/v1/talent"

LEGACY_CODES = {
    "DOCTOR", "DENTIST", "PHARMACIST", "NURSE", "MIDWIFE", "LAB_TECHNICIAN",
    "RADIOLOGY_TECHNICIAN", "ANESTHESIA_TECHNICIAN", "PHYSIOTHERAPIST", "NUTRITIONIST",
    "PSYCHOLOGIST", "MEDICAL_ASSISTANT", "ADMINISTRATIVE", "OTHER", "SOFTWARE_DEVELOPER",
    "ACCOUNTANT", "SALES", "HUMAN_RESOURCES", "BIOMEDICAL_ENGINEER", "CYBERSECURITY",
}  # fmt: skip


def _payload(baghdad, profession, title="Role"):
    return {
        "title": title,
        "profession": profession,
        "description": "A demo role description.",
        "governorate": str(baghdad.id),
        "employment_type": "FULL_TIME",
    }


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.fixture
def business(employer_factory):
    return employer_factory(
        name="Demo Software House", organization_type="BUSINESS", plan_code="PROFESSIONAL"
    )


def test_taxonomy_is_backward_compatible_and_covers_every_field():
    assert LEGACY_CODES <= set(Profession.values)
    assert list(PROFESSION_GROUPS)[0] == "HEALTHCARE"
    assert {"HEALTHCARE", "HEALTH_BUSINESS", "TECHNOLOGY", "BUSINESS", "EDUCATION",
            "OTHER_FIELDS"} == set(PROFESSION_GROUPS)  # fmt: skip
    for code in ("MANAGER", "OPERATIONS", "TEACHER", "OTHER_PROFESSION", "DATA_ANALYST",
                 "CUSTOMER_SERVICE", "MARKETING", "NETWORK_ENGINEER"):  # fmt: skip
        assert code in Profession.values
    # Biomedical engineers are health business, not clinical: a business may hire them.
    assert "BIOMEDICAL_ENGINEER" not in CLINICAL_PROFESSIONS
    assert {"DOCTOR", "NURSE", "DENTIST", "MIDWIFE", "PHARMACIST"} <= CLINICAL_PROFESSIONS


def test_public_profession_endpoint_lists_the_new_groups(api_client):
    body = api_client.get("/api/v1/jobs/professions").json()
    groups = {g["group"]: g["professions"] for g in body}
    assert groups["EDUCATION"] == ["TEACHER"] and groups["OTHER_FIELDS"] == ["OTHER_PROFESSION"]
    assert {"MANAGER", "OPERATIONS"} <= set(groups["BUSINESS"])


@pytest.mark.parametrize(
    "profession",
    [
        "SOFTWARE_DEVELOPER",
        "ACCOUNTANT",
        "SALES",
        "HUMAN_RESOURCES",
        "BIOMEDICAL_ENGINEER",
        "TEACHER",
        "OPERATIONS",
    ],  # fmt: skip
)
def test_business_employer_posts_and_submits_non_clinical_roles(
    business, baghdad, admin_client, profession
):
    client = _client(owner_of(business))
    created = client.post(JOBS, _payload(baghdad, profession, f"{profession} role"))
    assert created.status_code == 201, created.json()
    submitted = client.post(f"{JOBS}/{created.json()['id']}/submit")
    assert submitted.status_code == 200, submitted.json()
    assert submitted.json()["status"] == "PENDING_ADMIN_REVIEW"


@pytest.mark.parametrize("profession", ["DOCTOR", "NURSE", "DENTIST", "MIDWIFE", "PHARMACIST"])
def test_business_employer_cannot_post_clinical_roles(business, baghdad, profession):
    client = _client(owner_of(business))
    refused = client.post(JOBS, _payload(baghdad, profession))
    assert refused.status_code == 400
    assert "profession" in refused.json()["error"]["details"]
    assert not JobPost.objects.filter(employer=business).exists()


def test_business_employer_cannot_edit_a_draft_into_a_clinical_role(business, baghdad):
    client = _client(owner_of(business))
    job = client.post(JOBS, _payload(baghdad, "ACCOUNTANT")).json()
    refused = client.patch(f"{JOBS}/{job['id']}", {"profession": "DOCTOR"}, format="json")
    assert refused.status_code == 400
    assert JobPost.objects.get(pk=job["id"]).profession == "ACCOUNTANT"


def test_a_clinical_draft_that_slipped_in_is_refused_at_submit(business, job_factory):
    """Defence in depth: a row written outside the API (e.g. a data fix) is re-checked on the
    locked rows when the employer submits it."""
    job = job_factory(business, status=JobStatus.DRAFT, profession="NURSE")
    refused = _client(owner_of(business)).post(f"{JOBS}/{job.id}/submit")
    assert refused.status_code == 400
    job.refresh_from_db()
    assert job.status == JobStatus.DRAFT


def test_healthcare_employer_posts_clinical_and_non_clinical_roles(employer, baghdad):
    client = _client(owner_of(employer))
    for profession in ("DOCTOR", "NURSE", "BIOMEDICAL_ENGINEER", "SOFTWARE_DEVELOPER"):
        assert client.post(JOBS, _payload(baghdad, profession)).status_code == 201


def test_unverified_business_employer_cannot_publish(employer_factory, baghdad):
    pending = employer_factory(verified=False, organization_type="BUSINESS")
    client = _client(owner_of(pending))
    job = client.post(JOBS, _payload(baghdad, "SOFTWARE_DEVELOPER"))
    assert job.status_code == 201  # drafting is allowed
    refused = client.post(f"{JOBS}/{job.json()['id']}/submit")
    assert refused.status_code == 403


def test_business_type_is_frozen_after_verification(business):
    """A verified business cannot relabel itself a hospital to reach clinical candidates."""
    refused = _client(owner_of(business)).patch(
        "/api/v1/jobs/employer", {"organization_type": "HOSPITAL"}, format="json"
    )
    assert refused.status_code in (400, 409)
    business.refresh_from_db()
    assert business.organization_type == "BUSINESS"


def test_talent_search_is_scoped_for_a_business_employer(business, employer, seeker_factory):
    doctor = seeker_factory(profession="DOCTOR", professional_title="Physician")
    nurse = seeker_factory(profession="NURSE")
    biomed = seeker_factory(profession="BIOMEDICAL_ENGINEER")
    developer = seeker_factory(profession="SOFTWARE_DEVELOPER")
    accountant = seeker_factory(profession="ACCOUNTANT")
    sales = seeker_factory(profession="SALES")

    def ids(account, **params):
        return {r["id"] for r in _client(account).get(TALENT, params).json()["results"]}

    non_clinical = {str(p.id) for p in (biomed, developer, accountant, sales)}
    assert ids(owner_of(business)) == non_clinical
    assert ids(owner_of(business), profession="DOCTOR") == set()
    assert ids(owner_of(business), profession="ACCOUNTANT") == {str(accountant.id)}
    # Clinical profiles are invisible by direct id too.
    assert _client(owner_of(business)).get(f"{TALENT}/{doctor.id}").status_code == 404
    # A healthcare employer still sees everyone, healthcare included.
    assert ids(owner_of(employer)) == non_clinical | {str(doctor.id), str(nurse.id)}


def test_an_applicant_stays_visible_to_that_employer_only(
    business, employer_factory, seeker_factory, job_factory
):
    """A nurse moving into operations applies to the business: that employer sees the
    application's candidate; another business does not."""
    nurse = seeker_factory(profession="NURSE", discoverable=False)
    job = job_factory(business, profession="OPERATIONS", title="Operations coordinator")
    services.apply_to_job(job, nurse)
    assert _client(owner_of(business)).get(f"{TALENT}/{nurse.id}").status_code == 200
    other = employer_factory(organization_type="BUSINESS", plan_code="PROFESSIONAL")
    assert _client(owner_of(other)).get(f"{TALENT}/{nurse.id}").status_code == 404


def test_public_job_search_filters_new_professions(api_client, business, job_factory):
    teacher = job_factory(business, profession="TEACHER", title="Clinical skills teacher")
    job_factory(business, profession="ACCOUNTANT", title="Accountant")
    found = api_client.get("/api/v1/jobs", {"profession": "TEACHER"}).json()["results"]
    assert [j["id"] for j in found] == [str(teacher.id)]
