import pytest

from apps.jobs.models import Employer
from apps.jobs.tests.conftest import owner_of

pytestmark = pytest.mark.django_db

ME = "/api/v1/jobs/employer"


def test_create_organisation_becomes_owner(api_client, account_factory, baghdad):
    account = account_factory(role="PROVIDER")
    api_client.force_authenticate(user=account)
    response = api_client.post(
        ME,
        {
            "name": "Al Noor Hospital",
            "organization_type": "HOSPITAL",
            "governorate": str(baghdad.id),
            "description": "General hospital",
        },
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert (
        body["verification_status"] == "UNVERIFIED"
        and body["my_role"] == "OWNER"
        and body["is_verified"] is False
    )
    assert (
        api_client.post(
            ME, {"name": "Second", "organization_type": "CLINIC", "governorate": str(baghdad.id)}
        ).status_code
        == 409
    )


def test_admin_fields_rejected_on_create_and_update(
    api_client, account_factory, baghdad, employer_client
):
    api_client.force_authenticate(user=account_factory())
    response = api_client.post(
        ME,
        {
            "name": "X",
            "organization_type": "CLINIC",
            "governorate": str(baghdad.id),
            "verification_status": "VERIFIED",
        },
    )
    assert (
        response.status_code == 400 and "verification_status" in response.json()["error"]["details"]
    )
    response = employer_client.patch(ME, {"recruitment_status": "ACTIVE", "name": "Renamed"})
    assert (
        response.status_code == 400 and "recruitment_status" in response.json()["error"]["details"]
    )


def test_contact_info_rejected_in_description(api_client, account_factory, baghdad):
    api_client.force_authenticate(user=account_factory())
    response = api_client.post(
        ME,
        {
            "name": "X",
            "organization_type": "CLINIC",
            "governorate": str(baghdad.id),
            "description": "call 07701234567",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["codes"]["description"] == ["contact_information_not_allowed"]


def test_link_provider_profile_must_be_own_facility(api_client, provider_factory, baghdad):
    hospital_profile = provider_factory(provider_type="HOSPITAL")
    api_client.force_authenticate(user=hospital_profile.account)
    ok = api_client.post(
        ME,
        {
            "name": "Linked",
            "organization_type": "HOSPITAL",
            "governorate": str(baghdad.id),
            "provider_profile": str(hospital_profile.id),
        },
    )
    assert ok.status_code == 201 and ok.json()["provider_profile_id"] == str(hospital_profile.id)
    doctor_profile = provider_factory(provider_type="DOCTOR")
    api_client.force_authenticate(user=doctor_profile.account)
    bad = api_client.post(
        ME,
        {
            "name": "Bad",
            "organization_type": "CLINIC",
            "governorate": str(baghdad.id),
            "provider_profile": str(hospital_profile.id),
        },
    )
    assert bad.status_code == 400 and "provider_profile" in bad.json()["error"]["details"]


def test_verification_request_and_admin_decision(api_client, employer_factory, admin_client):
    employer = employer_factory(verified=False)
    api_client.force_authenticate(user=owner_of(employer))
    assert api_client.post(f"{ME}/verification/request").json()["verification_status"] == "PENDING"
    assert api_client.post(f"{ME}/verification/request").status_code == 400
    listed = admin_client.get(
        "/api/v1/admin/recruitment/employers", {"verification_status": "PENDING"}
    ).json()
    assert listed["count"] == 1 and listed["results"][0]["created_by_email"]
    decided = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{employer.id}/verification",
        {"status": "VERIFIED", "note": "docs checked"},
    )
    assert decided.status_code == 200 and decided.json()["verification_status"] == "VERIFIED"
    employer.refresh_from_db()
    assert employer.verified_at is not None
    # a normal owner cannot self-verify
    assert (
        api_client.post(
            f"/api/v1/admin/recruitment/employers/{employer.id}/verification",
            {"status": "VERIFIED"},
        ).status_code
        == 403
    )
    suspended = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{employer.id}/recruitment/SUSPENDED",
        {"reason": "abuse"},
    )
    assert suspended.json()["recruitment_status"] == "SUSPENDED"
    assert Employer.objects.get(pk=employer.pk).can_recruit is False


def test_members_seats_and_roles(employer_client, employer, account_factory, api_client):
    recruiter = account_factory()
    viewer = account_factory()
    assert (
        employer_client.post(
            f"{ME}/members", {"email": recruiter.email.upper(), "role": "RECRUITER"}
        ).status_code
        == 201
    )
    assert (
        employer_client.post(f"{ME}/members", {"email": viewer.email, "role": "VIEWER"}).status_code
        == 201
    )
    assert (
        employer_client.post(
            f"{ME}/members", {"email": recruiter.email, "role": "RECRUITER"}
        ).status_code
        == 409
    )  # already member
    assert (
        employer_client.post(
            f"{ME}/members", {"email": account_factory().email, "role": "OWNER"}
        ).status_code
        == 400
    )
    members = employer_client.get(f"{ME}/members").json()
    assert {m["role"] for m in members} == {"OWNER", "RECRUITER", "VIEWER"}
    assert all("email" not in m for m in members)
    # viewer cannot add members or create jobs
    api_client.force_authenticate(user=viewer)
    assert (
        api_client.post(
            f"{ME}/members", {"email": account_factory().email, "role": "VIEWER"}
        ).status_code
        == 403
    )
    assert api_client.post(f"{ME}/jobs", {}).status_code == 403


def test_seat_limit_enforced(api_client, employer_factory, account_factory):
    trial = employer_factory()  # TRIAL: 1 seat (the owner)
    api_client.force_authenticate(user=owner_of(trial))
    response = api_client.post(
        f"{ME}/members", {"email": account_factory().email, "role": "RECRUITER"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "usage_limit_reached"
    assert response.json()["error"]["meta"]["key"] == "recruiter.seats"


def test_billing_summary_and_plan_request(employer_client, employer_factory, api_client):
    body = employer_client.get(f"{ME}/billing").json()
    assert body["plan"]["code"] == "PROFESSIONAL" and body["subscription"]["status"] == "ACTIVE"
    keys = {e["key"]: e for e in body["entitlements"]}
    assert (
        keys["jobs.active_limit"]["limit"] == 10 and keys["talent.search_limit"]["remaining"] == 100
    )
    assert all(p["code"] != "TRIAL" for p in body["requestable_plans"])
    trial = employer_factory()
    api_client.force_authenticate(user=owner_of(trial))
    assert api_client.get(f"{ME}/billing").json()["plan"]["code"] == "TRIAL"
    req = api_client.post(
        f"{ME}/billing/request", {"plan": "BASIC", "note": "will pay by transfer"}
    )
    assert req.status_code == 201 and req.json()["status"] == "PENDING"
    assert api_client.post(f"{ME}/billing/request", {"plan": "BASIC"}).status_code == 400
    assert (
        api_client.post(f"{ME}/billing/request", {"plan": "TRIAL"}).status_code == 400
    )  # not public
    # the requester cannot activate anything
    assert (
        api_client.post(
            "/api/v1/admin/billing/subscriptions/00000000-0000-4000-8000-000000000000/activate"
        ).status_code
        == 403
    )
    assert api_client.get(f"{ME}/billing").json()["plan"]["code"] == "TRIAL"


def test_public_employer_page_hides_internal_fields(api_client, employer, employer_factory):
    body = api_client.get(f"/api/v1/employers/{employer.id}").json()
    assert body["is_verified"] is True
    for hidden in ("verification_note", "recruitment_status", "created_by_email", "email"):
        assert hidden not in body
    assert (
        api_client.get(f"/api/v1/employers/{employer_factory(verified=False).id}").status_code
        == 404
    )
