"""Phase A: onboarding types are hints for the NEXT step, never permissions.

* employer / job-seeker registrations are personal accounts (role PATIENT) whose first workspace
  is a setup step pointing at the employer workspace or the résumé, until that workspace exists;
* a dentist / midwife registration is a PROVIDER account (the profile form preselects doctor +
  dentistry / nurse + midwifery; the server validates the profile as for any provider);
* an existing patient becomes a job seeker without a second account.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import ACCOUNT_TYPE_PROVIDER, AccountRole, AccountType
from apps.geography.models import Governorate
from apps.specialties.models import Specialty

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register"
WS = "/api/v1/workspaces"
DASH = "/api/v1/workspaces/dashboard"


def _register(account_type: str) -> Account:
    body = {
        "email": f"{account_type.lower()}@example.com",
        "password": "Str0ng-Passw0rd!",
        "full_name": f"{account_type} person",
        "account_type": account_type,
    }
    assert APIClient().post(REGISTER, body).status_code == 201
    return Account.objects.get(email=body["email"])


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.mark.parametrize(
    "account_type,role",
    [
        ("DENTIST", AccountRole.PROVIDER),
        ("MIDWIFE", AccountRole.PROVIDER),
        ("EMPLOYER", AccountRole.PATIENT),
        ("JOB_SEEKER", AccountRole.PATIENT),
    ],
)
def test_new_onboarding_types_derive_the_role(account_type, role):
    account = _register(account_type)
    assert account.role == role and account.account_type == account_type


def test_dentist_and_midwife_preset_existing_specialties():
    slugs = set(Specialty.objects.values_list("slug", flat=True))
    assert ACCOUNT_TYPE_PROVIDER[AccountType.DENTIST] == ("DOCTOR", "dentistry")
    assert ACCOUNT_TYPE_PROVIDER[AccountType.MIDWIFE] == ("NURSE", "midwifery")
    assert {"dentistry", "midwifery"} <= slugs
    midwifery = Specialty.objects.get(slug="midwifery")
    assert midwifery.parent.slug == "nursing" and midwifery.name_ar == "القبالة"


def test_employer_registration_lands_on_hiring_setup_then_on_the_employer_workspace():
    account = _register("EMPLOYER")
    client = _client(account)
    workspaces = client.get(WS).json()
    assert workspaces[0]["kind"] == "setup" and workspaces[0]["path"] == "/employer"
    dash = client.get(DASH).json()
    assert dash["workspace"]["kind"] == "setup"
    setup = next(m for m in dash["modules"] if m["key"] == "setup")
    assert setup["variant"] == "employer" and setup["link"] == "/employer"
    created = client.post(
        "/api/v1/jobs/employer",
        {
            "name": "Demo Software House",
            "organization_type": "HEALTHCARE_INSTITUTION",
            "governorate": str(Governorate.objects.get(slug="baghdad").pk),
        },
        format="json",
    )
    assert created.status_code == 201, created.json()
    workspaces = client.get(WS).json()
    assert all(w["kind"] != "setup" for w in workspaces)
    assert client.get(DASH).json()["workspace"]["kind"] == "employer"


def test_job_seeker_registration_lands_on_the_resume_setup():
    account = _register("JOB_SEEKER")
    client = _client(account)
    dash = client.get(DASH).json()
    assert dash["workspace"]["kind"] == "setup"
    setup = next(m for m in dash["modules"] if m["key"] == "setup")
    assert setup["variant"] == "job_seeker" and setup["link"] == "/jobs/profile"


def test_a_patient_becomes_a_job_seeker_without_a_second_account(account_factory):
    patient = account_factory(role=AccountRole.PATIENT)
    client = _client(patient)
    body = {
        "profession": "ACCOUNTANT",
        "professional_title": "Accountant (demo)",
        "degree": "BACHELOR",
        "governorate": str(Governorate.objects.get(slug="baghdad").pk),
    }
    response = client.put("/api/v1/jobs/me/profile", body, format="json")
    if response.status_code == 405:
        response = client.post("/api/v1/jobs/me/profile", body, format="json")
    assert response.status_code in (200, 201), response.json()
    kinds = {w["kind"] for w in client.get(WS).json()}
    assert {"patient", "job_seeker"} <= kinds
    assert Account.objects.filter(pk=patient.pk).count() == 1


def test_the_account_type_never_grants_access(account_factory):
    """A personal account that SAYS it is an employer still has no employer workspace, staff
    rights or seller tools until it creates (and an admin verifies) its organization."""
    account = _register("EMPLOYER")
    client = _client(account)
    assert client.get("/api/v1/jobs/employer").status_code in (403, 404)
    assert client.get("/api/v1/merchant/orders").status_code == 403
    assert client.get("/api/v1/admin/recruitment/employers").status_code == 403
