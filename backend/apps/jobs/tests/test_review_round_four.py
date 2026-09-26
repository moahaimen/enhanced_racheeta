"""Regression tests for the fourth Codex review of PR #4 (commit 53698f6):
identity lock after verification, withdrawal during INTERVIEW, interview
answers on closed applications, and job row locks."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.jobs import services
from apps.jobs.models import Employer, JobApplication, JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import ApplicationStatus, InterviewStatus, JobStatus, VerificationStatus

ME = "/api/v1/jobs/employer"
APPS = "/api/v1/jobs/me/applications"
JOBS = "/api/v1/jobs/employer/jobs"
ADMIN = "/api/v1/admin/recruitment/jobs"


# ---- 1. identity lock --------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("organization_type", "RECRUITMENT_AGENCY"),
        ("is_recruitment_agency", True),
        ("name", "Totally Different Hospital"),
    ],
)
def test_verified_organisation_cannot_change_identity_fields(
    employer_client, employer, field, value
):
    before = Employer.objects.get(pk=employer.pk)
    resp = employer_client.patch(ME, {field: value}, format="json")
    assert resp.status_code == 400, resp.content
    assert resp.json()["error"]["codes"][field] == ["identity_locked"]
    after = Employer.objects.get(pk=employer.pk)
    assert getattr(after, field) == getattr(before, field)
    assert after.verification_status == VerificationStatus.VERIFIED  # badge untouched


def test_verified_organisation_cannot_swap_provider_profile(
    api_client, provider_factory, baghdad, admin
):
    facility = provider_factory(provider_type="HOSPITAL")
    api_client.force_authenticate(user=facility.account)
    created = api_client.post(
        ME,
        {
            "name": "Facility Org",
            "organization_type": "HOSPITAL",
            "governorate": str(baghdad.id),
            "provider_profile": str(facility.id),
        },
    )
    assert created.status_code == 201, created.content
    employer = Employer.objects.get(pk=created.json()["id"])
    services.set_employer_verification(employer, VerificationStatus.VERIFIED, admin=admin)
    # Unlink (and by symmetry relink) is an identity change once verified.
    resp = api_client.patch(ME, {"provider_profile": None}, format="json")
    assert resp.status_code == 400 and resp.json()["error"]["codes"]["provider_profile"] == [
        "identity_locked"
    ]
    employer.refresh_from_db()
    assert employer.provider_profile_id == facility.id


def test_same_value_and_presentation_edits_still_work_when_verified(
    employer_client, employer, baghdad
):
    ok = employer_client.patch(
        ME,
        {
            "organization_type": employer.organization_type,  # unchanged value is fine
            "description": "We are hiring for the new wing.",
            "is_discoverable": False,
            "city": None,
        },
        format="json",
    )
    assert ok.status_code == 200, ok.content
    assert ok.json()["description"] == "We are hiring for the new wing."
    assert ok.json()["is_discoverable"] is False


def test_identity_is_locked_while_under_review_and_free_before(api_client, employer_factory, admin):
    org = employer_factory(verified=False)
    api_client.force_authenticate(user=owner_of(org))
    assert api_client.patch(ME, {"organization_type": "CLINIC"}, format="json").status_code == 200
    services.request_employer_verification(org, actor=owner_of(org))
    locked = api_client.patch(ME, {"organization_type": "PHARMACY"}, format="json")
    assert locked.status_code == 400 and "organization_type" in locked.json()["error"]["codes"]
    services.set_employer_verification(org, VerificationStatus.REJECTED, admin=admin)
    assert api_client.patch(ME, {"organization_type": "PHARMACY"}, format="json").status_code == 200


def test_admin_verification_path_and_job_gate_still_work(
    api_client, employer_factory, admin_client, baghdad
):
    org = employer_factory(verified=False)
    api_client.force_authenticate(user=owner_of(org))
    from apps.jobs.tests.test_jobs_lifecycle import draft_payload

    job = api_client.post(JOBS, draft_payload(baghdad)).json()
    assert api_client.post(f"{JOBS}/{job['id']}/submit").status_code == 403  # not verified
    decided = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{org.id}/verification", {"status": "VERIFIED"}
    )
    assert decided.status_code == 200 and decided.json()["verification_status"] == "VERIFIED"
    assert api_client.post(f"{JOBS}/{job['id']}/submit").status_code == 200
    suspended = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{org.id}/verification",
        {"status": "SUSPENDED", "note": "documents expired"},
    )
    assert suspended.json()["verification_status"] == "SUSPENDED"
    second = api_client.post(JOBS, draft_payload(baghdad, title="Second")).json()
    assert api_client.post(f"{JOBS}/{second['id']}/submit").status_code == 403


# ---- 2. withdrawal during INTERVIEW --------------------------------------------


def _interview_stage(seeker_client, employer, job_factory):
    job = job_factory(employer)
    application = JobApplication.objects.get(
        pk=seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    )
    owner = owner_of(employer)
    services.transition_application(application, "SHORTLISTED", actor=owner)
    interview = services.request_interview(
        application, actor=owner, proposed_at=timezone.now() + timedelta(days=3), mode="ONLINE"
    )
    application.refresh_from_db()
    assert application.status == ApplicationStatus.INTERVIEW
    return application, interview


def test_seeker_can_withdraw_during_interview_and_open_interview_is_cancelled(
    seeker_client, employer, job_factory
):
    application, interview = _interview_stage(seeker_client, employer, job_factory)
    resp = seeker_client.post(f"{APPS}/{application.id}/withdraw", {"reason": "changed plans"})
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "WITHDRAWN"
    assert [t["to_status"] for t in body["transitions"]] == [
        "SUBMITTED",
        "SHORTLISTED",
        "INTERVIEW",
        "WITHDRAWN",
    ]
    assert body["transitions"][-1]["reason"] == "changed plans"
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.CANCELLED and interview.responded_at is not None


@pytest.mark.parametrize("terminal", ["ACCEPTED", "REJECTED"])
def test_terminal_states_stay_non_withdrawable(seeker_client, employer, job_factory, terminal):
    application, _ = _interview_stage(seeker_client, employer, job_factory)
    services.transition_application(application, terminal, actor=owner_of(employer))
    resp = seeker_client.post(f"{APPS}/{application.id}/withdraw")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_transition"
    withdrawn = seeker_client.post(f"{APPS}/{application.id}/withdraw")
    assert withdrawn.status_code == 400


# ---- 3. interview answers on closed applications ---------------------------------


@pytest.mark.parametrize("closer", ["REJECTED", "ACCEPTED", "WITHDRAWN"])
def test_interview_response_rejected_once_application_is_terminal(
    seeker_client, seeker, employer, job_factory, closer
):
    application, interview = _interview_stage(seeker_client, employer, job_factory)
    # Simulate a stale interview row that stayed PROPOSED (bypassing the policy),
    # then close the application through a raw update so only the guard is tested.
    JobApplication.objects.filter(pk=application.pk).update(status=closer)
    resp = seeker_client.post(
        f"/api/v1/jobs/me/interviews/{interview.id}/respond", {"accept": True}
    )
    assert resp.status_code == 409, resp.content
    assert resp.json()["error"]["code"] == "application_closed"
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.PROPOSED


def test_closing_the_application_cancels_proposed_interviews(seeker_client, employer, job_factory):
    application, interview = _interview_stage(seeker_client, employer, job_factory)
    services.transition_application(application, "REJECTED", actor=owner_of(employer))
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.CANCELLED
    resp = seeker_client.post(
        f"/api/v1/jobs/me/interviews/{interview.id}/respond", {"accept": True}
    )
    assert resp.status_code == 409


def test_interview_answers_work_while_the_application_is_open(seeker_client, employer, job_factory):
    application, interview = _interview_stage(seeker_client, employer, job_factory)
    resp = seeker_client.post(
        f"/api/v1/jobs/me/interviews/{interview.id}/respond",
        {"accept": False, "response": "not available that day"},
    )
    assert resp.status_code == 200 and resp.json()["status"] == "DECLINED"
    application.refresh_from_db()
    assert application.status == ApplicationStatus.INTERVIEW


# ---- 4. job row locks -----------------------------------------------------------


def _race(actions):
    """Run callables concurrently after a barrier; return their outcomes."""
    barrier = threading.Barrier(len(actions))
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

    threads = [threading.Thread(target=run, args=(n, f)) for n, f in actions.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return outcomes


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_approve_and_reject_have_one_winner(employer_factory, job_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = job_factory(employer, status=JobStatus.PENDING_ADMIN_REVIEW)
    outcomes = _race(
        {
            "approve": lambda: services.approve_job(JobPost.objects.get(pk=job.pk), admin=admin),
            "reject": lambda: services.reject_job(
                JobPost.objects.get(pk=job.pk), admin=admin, reason="no"
            ),
        }
    )
    assert sorted(outcomes.values()) == ["invalid_transition", "ok"], outcomes
    job.refresh_from_db()
    winner = {"approve": JobStatus.PUBLISHED, "reject": JobStatus.REJECTED}[
        next(k for k, v in outcomes.items() if v == "ok")
    ]
    assert job.status == winner
    assert list(job.transitions.order_by("created_at").values_list("to_status", flat=True)) == [
        winner
    ]


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_close_and_suspend_have_one_winner(employer_factory, job_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    job = job_factory(employer, status=JobStatus.PUBLISHED)
    outcomes = _race(
        {
            "close": lambda: services.close_job(JobPost.objects.get(pk=job.pk), actor=owner),
            "suspend": lambda: services.suspend_job(
                JobPost.objects.get(pk=job.pk), admin=admin, reason="review"
            ),
        }
    )
    assert sorted(outcomes.values()) == ["invalid_transition", "ok"], outcomes
    job.refresh_from_db()
    winner = {"close": JobStatus.CLOSED, "suspend": JobStatus.SUSPENDED}[
        next(k for k, v in outcomes.items() if v == "ok")
    ]
    assert job.status == winner
    assert list(job.transitions.values_list("to_status", flat=True)) == [winner]


def test_stale_job_instance_gets_a_typed_error_and_sequential_flow_works(
    employer, job_factory, admin
):
    owner = owner_of(employer)
    job = job_factory(employer, status=JobStatus.DRAFT)
    stale = JobPost.objects.get(pk=job.pk)
    services.submit_job_for_review(job, actor=owner)
    services.approve_job(job, admin=admin)
    with pytest.raises(services.JobsError) as excinfo:
        services.submit_job_for_review(stale, actor=owner)  # stale instance still says DRAFT
    assert excinfo.value.code == "invalid_transition"
    assert stale.status == JobStatus.PUBLISHED  # refreshed under the lock
    services.suspend_job(job, admin=admin, reason="check")
    services.restore_job(job, admin=admin)
    services.close_job(job, actor=owner)
    services.archive_job(job, actor=owner)
    job.refresh_from_db()
    assert job.status == JobStatus.ARCHIVED
    assert list(job.transitions.order_by("created_at").values_list("to_status", flat=True)) == [
        "PENDING_ADMIN_REVIEW",
        "PUBLISHED",
        "SUSPENDED",
        "PUBLISHED",
        "CLOSED",
        "ARCHIVED",
    ]


def test_submit_pre_check_is_re_run_under_the_lock(employer, job_factory):
    """The unlocked pre-check in submit_job_for_review is only an early exit; the
    locked check inside _submit_job is authoritative."""
    owner = owner_of(employer)
    job = job_factory(employer, status=JobStatus.DRAFT)
    JobPost.objects.filter(pk=job.pk).update(status=JobStatus.ARCHIVED)  # changed underneath
    with pytest.raises(services.JobsError):
        services.submit_job_for_review(job, actor=owner)
    job.refresh_from_db()
    assert job.status == JobStatus.ARCHIVED and not job.transitions.exists()
