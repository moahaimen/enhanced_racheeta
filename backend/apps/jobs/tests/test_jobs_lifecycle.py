from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.models import Plan
from apps.billing.types import Audience, SubjectType
from apps.jobs.models import JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus

pytestmark = pytest.mark.django_db

JOBS = "/api/v1/jobs/employer/jobs"
ADMIN = "/api/v1/admin/recruitment/jobs"


def draft_payload(baghdad, **over):
    return {
        "title": "ICU Nurse",
        "profession": "NURSE",
        "description": "Care for ICU patients.",
        "governorate": str(baghdad.id),
        "employment_type": "FULL_TIME",
        "salary_min": "1500000",
        "salary_max": "2000000",
        "salary_visible": True,
        **over,
    }


def test_create_draft_submit_approve_publish(employer_client, baghdad, admin_client, api_client):
    created = employer_client.post(JOBS, draft_payload(baghdad))
    assert created.status_code == 201, created.content
    job = created.json()
    assert job["status"] == "DRAFT" and job["applications_count"] == 0
    assert api_client.get("/api/v1/jobs").json()["count"] == 0
    submitted = employer_client.post(f"{JOBS}/{job['id']}/submit")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == "PENDING_ADMIN_REVIEW"
    assert employer_client.patch(f"{JOBS}/{job['id']}", {"title": "x"}).status_code == 409  # locked
    review = admin_client.get(ADMIN, {"status": "PENDING_ADMIN_REVIEW"}).json()
    assert (
        review["count"] == 1
        and review["results"][0]["employer"]["verification_status"] == "VERIFIED"
        and review["results"][0]["contact_findings"] == []
    )
    approved = admin_client.post(f"{ADMIN}/{job['id']}/approve", {"note": "ok"})
    assert approved.status_code == 200 and approved.json()["status"] == "PUBLISHED"
    public = api_client.get("/api/v1/jobs").json()
    assert public["count"] == 1 and public["results"][0]["salary_min"] == "1500000.00"
    transitions = [
        t["to_status"] for t in employer_client.get(f"{JOBS}/{job['id']}").json()["transitions"]
    ]
    assert transitions == ["PENDING_ADMIN_REVIEW", "PUBLISHED"]


def test_admin_fields_and_status_cannot_be_set_by_employer(employer_client, baghdad):
    response = employer_client.post(
        JOBS, draft_payload(baghdad, status="PUBLISHED", is_featured=True)
    )
    assert response.status_code == 400
    assert {"status", "is_featured"} <= set(response.json()["error"]["details"])


def test_reject_with_reason_then_fix_and_resubmit(employer_client, baghdad, admin_client):
    job = employer_client.post(JOBS, draft_payload(baghdad)).json()
    employer_client.post(f"{JOBS}/{job['id']}/submit")
    assert (
        admin_client.post(f"{ADMIN}/{job['id']}/reject", {}).status_code == 400
    )  # reason required
    rejected = admin_client.post(f"{ADMIN}/{job['id']}/reject", {"reason": "Title unclear"})
    assert (
        rejected.json()["status"] == "REJECTED"
        and rejected.json()["moderation_note"] == "Title unclear"
    )
    assert (
        employer_client.patch(f"{JOBS}/{job['id']}", {"title": "ICU Registered Nurse"}).status_code
        == 200
    )
    assert (
        employer_client.post(f"{JOBS}/{job['id']}/submit").json()["status"]
        == "PENDING_ADMIN_REVIEW"
    )


def test_suspend_restore_close_archive(employer_client, baghdad, admin_client, api_client):
    job = employer_client.post(JOBS, draft_payload(baghdad)).json()
    employer_client.post(f"{JOBS}/{job['id']}/submit")
    admin_client.post(f"{ADMIN}/{job['id']}/approve")
    assert (
        admin_client.post(f"{ADMIN}/{job['id']}/suspend", {"reason": "complaint"}).json()["status"]
        == "SUSPENDED"
    )
    assert api_client.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert admin_client.post(f"{ADMIN}/{job['id']}/restore").json()["status"] == "PUBLISHED"
    assert employer_client.post(f"{JOBS}/{job['id']}/close").json()["status"] == "CLOSED"
    assert employer_client.post(f"{JOBS}/{job['id']}/archive").json()["status"] == "ARCHIVED"
    assert employer_client.post(f"{JOBS}/{job['id']}/submit").status_code == 400


def test_contact_leak_blocks_draft_and_submission(employer_client, baghdad, admin_client):
    bad = employer_client.post(
        JOBS,
        draft_payload(baghdad, description="Send CV to hr@hospital.com or WhatsApp 07701234567"),
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["codes"]["description"] == ["contact_information_not_allowed"]
    # a job that slipped in (e.g. created before a rule) is caught at submission and at approval
    job = employer_client.post(JOBS, draft_payload(baghdad)).json()
    JobPost.objects.filter(pk=job["id"]).update(description="contact us at +964 770 123 4567")
    submitted = employer_client.post(f"{JOBS}/{job['id']}/submit")
    assert (
        submitted.status_code == 400
        and submitted.json()["error"]["code"] == "contact_information_not_allowed"
    )
    flags = employer_client.get(f"{JOBS}/{job['id']}").json()["moderation_flags"]
    assert flags[0]["category"] == "PHONE" and flags[0]["field"] == "description"
    JobPost.objects.filter(pk=job["id"]).update(status="PENDING_ADMIN_REVIEW")
    approve = admin_client.post(f"{ADMIN}/{job['id']}/approve")
    assert (
        approve.status_code == 400
        and approve.json()["error"]["code"] == "contact_information_not_allowed"
    )


def test_unverified_employer_cannot_submit(api_client, employer_factory, baghdad):
    employer = employer_factory(verified=False)
    api_client.force_authenticate(user=owner_of(employer))
    job = api_client.post(JOBS, draft_payload(baghdad)).json()
    response = api_client.post(f"{JOBS}/{job['id']}/submit")
    assert (
        response.status_code == 403
        and response.json()["error"]["code"] == "organization_not_verified"
    )


def test_active_job_limit_is_enforced(api_client, employer_factory, baghdad, admin_client):
    trial = employer_factory()  # TRIAL: 1 active job
    api_client.force_authenticate(user=owner_of(trial))
    first = api_client.post(JOBS, draft_payload(baghdad, title="First")).json()
    second = api_client.post(JOBS, draft_payload(baghdad, title="Second")).json()
    assert api_client.post(f"{JOBS}/{first['id']}/submit").status_code == 200
    blocked = api_client.post(f"{JOBS}/{second['id']}/submit")
    assert blocked.status_code == 403
    body = blocked.json()["error"]
    assert body["code"] == "usage_limit_reached" and body["meta"] == {
        "key": "jobs.active_limit",
        "limit": 1,
        "used": 1,
    }
    # closing the first frees the slot
    api_client.post(f"{JOBS}/{first['id']}/close")
    assert api_client.post(f"{JOBS}/{second['id']}/submit").status_code == 200


def test_featured_requires_entitlement(
    employer_client, baghdad, admin_client, api_client, employer_factory
):
    job = employer_client.post(JOBS, draft_payload(baghdad)).json()
    employer_client.post(f"{JOBS}/{job['id']}/submit")
    admin_client.post(f"{ADMIN}/{job['id']}/approve")
    featured = employer_client.post(f"{JOBS}/{job['id']}/feature", {"featured": True})
    assert featured.status_code == 200 and featured.json()["is_featured"] is True
    assert api_client.get("/api/v1/jobs").json()["results"][0]["is_featured"] is True
    basic = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(basic))
    other = api_client.post(JOBS, draft_payload(baghdad)).json()
    api_client.post(f"{JOBS}/{other['id']}/submit")
    admin_client.post(f"{ADMIN}/{other['id']}/approve")
    denied = api_client.post(f"{JOBS}/{other['id']}/feature", {"featured": True})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "entitlement_required"


def test_expired_jobs_disappear_at_read_time(employer, job_factory, api_client, employer_client):
    job = job_factory(employer, application_deadline=timezone.localdate() - timedelta(days=1))
    assert api_client.get("/api/v1/jobs").json()["count"] == 0
    job.refresh_from_db()
    assert job.status == JobStatus.EXPIRED
    assert employer_client.get(JOBS, {"status": "EXPIRED"}).json()["count"] == 1


def test_agency_rules(api_client, employer_factory, baghdad, employer):
    agency = employer_factory(
        is_recruitment_agency=True, organization_type="RECRUITMENT_AGENCY", name="Talent Bridge"
    )
    api_client.force_authenticate(user=owner_of(agency))
    ok = api_client.post(JOBS, draft_payload(baghdad, hiring_employer=str(employer.id)))
    assert ok.status_code == 201 and ok.json()["hiring_employer"]["name"] == employer.name
    ok2 = api_client.post(
        JOBS, draft_payload(baghdad, hiring_organization_name="Private clinic in Karrada")
    )
    assert ok2.status_code == 201
    # a non-agency cannot pretend to hire for others
    api_client.force_authenticate(user=owner_of(employer))
    bad = api_client.post(JOBS, draft_payload(baghdad, hiring_organization_name="Someone else"))
    assert bad.status_code == 400 and "hiring_organization_name" in bad.json()["error"]["details"]


def test_cross_organisation_isolation(api_client, employer_factory, baghdad, job_factory):
    a = employer_factory(plan_code="BASIC")
    b = employer_factory(plan_code="BASIC")
    job_b = job_factory(b, status=JobStatus.DRAFT)
    api_client.force_authenticate(user=owner_of(a))
    assert api_client.get(JOBS).json()["count"] == 0
    assert api_client.get(f"{JOBS}/{job_b.id}").status_code == 404
    assert api_client.patch(f"{JOBS}/{job_b.id}", {"title": "Hijack"}).status_code == 404
    assert api_client.post(f"{JOBS}/{job_b.id}/submit").status_code == 404
    assert api_client.get(f"{JOBS}/{job_b.id}/applications").status_code == 404
    job_b.refresh_from_db()
    assert job_b.title != "Hijack"


def test_validation_rules(employer_client, baghdad, basra):
    yesterday = str(timezone.localdate() - timedelta(days=1))
    deadline = employer_client.post(JOBS, draft_payload(baghdad, application_deadline=yesterday))
    assert deadline.status_code == 400
    assert "application_deadline" in deadline.json()["error"]["details"]
    salary = employer_client.post(
        JOBS, draft_payload(baghdad, salary_min="3000", salary_max="1000")
    )
    assert salary.status_code == 400 and "salary_max" in salary.json()["error"]["details"]
    city = employer_client.post(JOBS, draft_payload(baghdad, city=str(basra.cities.first().id)))
    assert city.status_code == 400 and "city" in city.json()["error"]["details"]


def test_non_admin_cannot_use_admin_job_endpoints(employer_client, employer, job_factory):
    job = job_factory(employer, status=JobStatus.PENDING_ADMIN_REVIEW)
    assert employer_client.get(ADMIN).status_code == 403
    assert employer_client.post(f"{ADMIN}/{job.id}/approve").status_code == 403
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING_ADMIN_REVIEW


def test_seeker_billing_default(seeker):
    acc = billing.get_or_create_billing_account(
        SubjectType.ACCOUNT, seeker.account_id, Audience.JOB_SEEKER
    )
    assert billing.EntitlementService(acc).plan == Plan.objects.get(code="SEEKER_FREE")
