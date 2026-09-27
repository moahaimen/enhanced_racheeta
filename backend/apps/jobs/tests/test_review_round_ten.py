"""Regression tests for the tenth Codex review of PR #4 (commit 8fa90f8):
restore uses the full submission eligibility gate, and administrators see the
linked facility profile when reviewing an organisation."""

import threading

import pytest
from django.db import connection

from apps.billing.models import PlanEntitlement
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import JobPost
from apps.jobs.types import JobStatus, VerificationStatus

ADMIN = "/api/v1/admin/recruitment/jobs"
EMPLOYERS = "/api/v1/admin/recruitment/employers"


def _suspended_job(employer, job_factory):
    return job_factory(employer, status=JobStatus.SUSPENDED)


def test_eligible_employer_restores_with_history(admin_client, employer, job_factory):
    job = _suspended_job(employer, job_factory)
    resp = admin_client.post(f"{ADMIN}/{job.id}/restore", {"note": "resolved"})
    assert resp.status_code == 200 and resp.json()["status"] == "PUBLISHED"
    assert list(job.transitions.values_list("to_status", flat=True)) == ["PUBLISHED"]


@pytest.mark.parametrize("how", ["unverified", "recruitment", "verification"])
def test_ineligible_employer_cannot_restore(
    admin_client, employer_factory, job_factory, admin, how
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = _suspended_job(employer, job_factory)
    if how == "unverified":
        services.set_employer_verification(employer, VerificationStatus.UNVERIFIED, admin=admin)
    elif how == "recruitment":
        services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    else:
        services.set_employer_verification(employer, VerificationStatus.SUSPENDED, admin=admin)
    resp = admin_client.post(f"{ADMIN}/{job.id}/restore")
    assert resp.status_code == 403, resp.content
    assert resp.json()["error"]["code"] == "organization_not_verified"
    job.refresh_from_db()
    assert job.status == JobStatus.SUSPENDED and not job.transitions.exists()


def test_former_agency_with_retained_hiring_fields_cannot_restore_until_cleared(
    admin_client, employer_factory, job_factory, admin
):
    agency = employer_factory(
        plan_code="PROFESSIONAL", is_recruitment_agency=True, organization_type="RECRUITMENT_AGENCY"
    )
    job = job_factory(agency, status=JobStatus.SUSPENDED, hiring_organization_name="Karrada clinic")
    services.Employer.objects.filter(pk=agency.pk).update(is_recruitment_agency=False)  # admin-side
    resp = admin_client.post(f"{ADMIN}/{job.id}/restore")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "not_an_agency"
    job.refresh_from_db()
    assert job.status == JobStatus.SUSPENDED and not job.transitions.exists()
    JobPost.objects.filter(pk=job.pk).update(hiring_organization_name="")
    assert admin_client.post(f"{ADMIN}/{job.id}/restore").json()["status"] == "PUBLISHED"


def test_restore_still_enforces_active_capacity(admin_client, employer_factory, job_factory):
    trial = employer_factory()  # one active slot
    suspended = _suspended_job(trial, job_factory)
    job_factory(trial, status=JobStatus.PUBLISHED)
    resp = admin_client.post(f"{ADMIN}/{suspended.id}/restore")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "usage_limit_reached"
    suspended.refresh_from_db()
    assert suspended.status == JobStatus.SUSPENDED and not suspended.transitions.exists()


def test_restore_without_jobs_post_capability_is_refused(
    admin_client, employer_factory, job_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = _suspended_job(employer, job_factory)
    PlanEntitlement.objects.filter(plan__code="PROFESSIONAL", key=Keys.JOBS_POST).update(
        enabled=False
    )
    resp = admin_client.post(f"{ADMIN}/{job.id}/restore")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "entitlement_required"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_restore_races_employer_suspension(employer_factory, job_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = _suspended_job(employer, job_factory)
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except services.JobsError as exc:
            outcomes[name] = exc.code
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=run,
            args=(
                "restore",
                lambda: services.restore_job(JobPost.objects.get(pk=job.pk), admin=admin),
            ),
        ),
        threading.Thread(
            target=run,
            args=(
                "suspend",
                lambda: services.set_employer_recruitment_status(
                    services.Employer.objects.get(pk=employer.pk), "SUSPENDED", admin=admin
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["suspend"] == "ok", outcomes
    job.refresh_from_db()
    if outcomes["restore"] == "ok":
        assert job.status == JobStatus.PUBLISHED
        assert list(job.transitions.values_list("to_status", flat=True)) == ["PUBLISHED"]
    else:
        assert outcomes["restore"] == "organization_not_verified", outcomes
        assert job.status == JobStatus.SUSPENDED and not job.transitions.exists()


# ---- admin sees the linked facility ----------------------------------------------


def test_admin_employer_list_shows_the_linked_provider_reference(
    api_client, admin_client, provider_factory, baghdad
):
    facility = provider_factory(provider_type="HOSPITAL")
    api_client.force_authenticate(user=facility.account)
    created = api_client.post(
        "/api/v1/jobs/employer",
        {
            "name": "Facility Org",
            "organization_type": "HOSPITAL",
            "governorate": str(baghdad.id),
            "provider_profile": str(facility.id),
            "is_recruitment_agency": False,
        },
    )
    assert created.status_code == 201, created.content
    listed = admin_client.get(EMPLOYERS, {"search": "Facility Org"}).json()["results"]
    assert len(listed) == 1
    row = listed[0]
    assert row["is_recruitment_agency"] is False
    assert row["provider_profile"] == {
        "id": str(facility.id),
        "display_name": facility.display_name,
        "provider_type": "HOSPITAL",
        "verification_status": facility.verification_status,
    }
    for hidden in ("email", "phone_number", "account", "full_name"):
        assert hidden not in row["provider_profile"]


def test_admin_employer_list_reports_no_link_as_null(admin_client, employer):
    row = admin_client.get(EMPLOYERS, {"search": employer.name}).json()["results"][0]
    assert row["provider_profile"] is None and "is_recruitment_agency" in row
