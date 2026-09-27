"""Regression tests for the sixth Codex review of PR #4 (commit 06e30b6):
suspended employers cannot run applicant workflows, applications and
invitations validate against locked job/employer state, and job submission
re-checks recruiting status under the employer lock."""

import threading

import pytest
from django.db import connection

from apps.billing.models import UsageEvent
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import JobApplication, JobInvitation, JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus, VerificationStatus

JOBS = "/api/v1/jobs/employer/jobs"


def _race(actions):
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


# ---- 1. suspended employers and applicant workflows -------------------------------


@pytest.fixture
def applicant_case(seeker_client, employer_factory, job_factory):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    return employer, job, app_id


def _routes(job, app_id):
    return {
        "list": ("get", f"{JOBS}/{job.id}/applications", None),
        "detail": ("get", f"/api/v1/jobs/employer/applications/{app_id}", None),
        "transition": (
            "post",
            f"/api/v1/jobs/employer/applications/{app_id}/transition",
            {"status": "SHORTLISTED"},
        ),
        "interview": (
            "post",
            f"/api/v1/jobs/employer/applications/{app_id}/interviews",
            {"proposed_at": "2030-01-01T10:00:00Z", "mode": "IN_PERSON"},
        ),
        "messages": (
            "post",
            f"/api/v1/recruitment/applications/{app_id}/messages",
            {"body": "hello"},
        ),
    }


def test_verified_active_entitled_employer_runs_the_workflow(api_client, applicant_case):
    employer, job, app_id = applicant_case
    api_client.force_authenticate(user=owner_of(employer))
    for name, (method, url, body) in _routes(job, app_id).items():
        resp = getattr(api_client, method)(url, body, format="json")
        assert resp.status_code in (200, 201), (name, resp.status_code, resp.content)


@pytest.mark.parametrize("how", ["recruitment", "verification"])
def test_suspended_employer_is_blocked_from_every_applicant_route(
    api_client, applicant_case, admin, seeker_client, how
):
    employer, job, app_id = applicant_case
    if how == "recruitment":
        services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    else:
        services.set_employer_verification(employer, VerificationStatus.SUSPENDED, admin=admin)
    api_client.force_authenticate(user=owner_of(employer))
    for name, (method, url, body) in _routes(job, app_id).items():
        resp = getattr(api_client, method)(url, body, format="json")
        assert resp.status_code == 403, (name, resp.status_code, resp.content)
        assert resp.json()["error"]["code"] == "organization_not_verified", name
    application = JobApplication.objects.get(pk=app_id)
    assert application.status == "SUBMITTED" and not application.interviews.exists()
    # The seeker still sees and controls their own application.
    mine = seeker_client.get(f"/api/v1/jobs/me/applications/{app_id}")
    assert mine.status_code == 200 and mine.json()["status"] == "SUBMITTED"
    assert seeker_client.post(f"/api/v1/jobs/me/applications/{app_id}/withdraw").status_code == 200


def test_unrelated_organisation_keeps_isolation(api_client, applicant_case, employer_factory):
    _, job, app_id = applicant_case
    other = employer_factory(plan_code="PROFESSIONAL")
    api_client.force_authenticate(user=owner_of(other))
    for name, (method, url, body) in _routes(job, app_id).items():
        assert getattr(api_client, method)(url, body, format="json").status_code == 404, name


# ---- 2. applying against locked job state -------------------------------------------


def _usage(profile):
    account = services.seeker_entitlements(profile).billing_account
    return UsageEvent.objects.filter(billing_account=account, key=Keys.APPLICATIONS_LIMIT).count()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("closer", ["close", "suspend"])
def test_apply_races_a_close_or_suspension(
    employer_factory, job_factory, seeker_factory, admin, closer
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    job = job_factory(employer)
    candidate = seeker_factory()
    stale = JobPost.objects.select_related("employer").get(pk=job.pk)  # PUBLISHED when loaded

    def close():
        target = JobPost.objects.get(pk=job.pk)
        if closer == "close":
            services.close_job(target, actor=owner)
        else:
            services.suspend_job(target, admin=admin, reason="review")

    outcomes = _race({"apply": lambda: services.apply_to_job(stale, candidate), "closer": close})
    assert outcomes["closer"] == "ok", outcomes
    job.refresh_from_db()
    assert job.status == (JobStatus.CLOSED if closer == "close" else JobStatus.SUSPENDED)
    created = JobApplication.objects.filter(job=job, job_seeker=candidate).exists()
    if outcomes["apply"] == "ok":  # the application committed before the close/suspension
        assert created and _usage(candidate) == 1
    else:  # the close/suspension won: nothing created, nothing charged
        assert outcomes["apply"] == "job_not_open", outcomes
        assert not created and _usage(candidate) == 0


def test_stale_open_job_instance_cannot_apply_after_closure(employer, job_factory, seeker_factory):
    job = job_factory(employer)
    stale = JobPost.objects.select_related("employer").get(pk=job.pk)
    services.close_job(job, actor=owner_of(employer))
    candidate = seeker_factory()
    assert stale.is_open  # what the view would have believed
    with pytest.raises(services.NotOpen):
        services.apply_to_job(stale, candidate)
    assert not JobApplication.objects.filter(job=job).exists() and _usage(candidate) == 0


def test_stale_job_instance_cannot_apply_after_employer_suspension(
    employer_factory, job_factory, seeker_factory, admin
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = job_factory(employer)
    stale = JobPost.objects.select_related("employer").get(pk=job.pk)
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    candidate = seeker_factory()
    with pytest.raises(services.NotOpen):
        services.apply_to_job(stale, candidate)
    assert _usage(candidate) == 0


def test_sequential_apply_and_duplicate_rules_still_hold(employer, job_factory, seeker_factory):
    job = job_factory(employer)
    candidate = seeker_factory()
    first = services.apply_to_job(job, candidate)
    assert first.status == "SUBMITTED" and _usage(candidate) == 1
    with pytest.raises(services.AlreadyApplied):
        services.apply_to_job(job, candidate)
    services.withdraw_application(first, actor=candidate.account)
    second = services.apply_to_job(job, candidate)
    assert second.pk != first.pk and _usage(candidate) == 2


def test_invite_uses_locked_job_state(employer_factory, job_factory, seeker_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = job_factory(employer)
    stale = JobPost.objects.select_related("employer").get(pk=job.pk)
    services.suspend_job(job, admin=admin, reason="review")
    with pytest.raises(services.NotOpen):
        services.invite_candidate(employer, stale, seeker_factory(), actor=owner_of(employer))
    assert not JobInvitation.objects.filter(job=job).exists()


# ---- 3. submit re-checks recruiting under the employer lock ---------------------------


def test_submit_ok_for_active_employer_and_blocked_for_suspended(
    employer_factory, job_factory, admin
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    ok = services.submit_job_for_review(job_factory(employer, status=JobStatus.DRAFT), actor=owner)
    assert ok.status == JobStatus.PENDING_ADMIN_REVIEW
    draft = job_factory(employer, status=JobStatus.DRAFT)
    stale_employer_job = JobPost.objects.select_related("employer").get(pk=draft.pk)
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    assert stale_employer_job.employer.can_recruit  # the unlocked pre-check would pass
    with pytest.raises(services.OrganizationNotVerified):
        services._submit_job(stale_employer_job, actor=owner)  # the locked re-check refuses
    draft.refresh_from_db()
    assert draft.status == JobStatus.DRAFT and not draft.transitions.exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_submit_races_employer_suspension(employer_factory, job_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    draft = job_factory(employer, status=JobStatus.DRAFT)
    outcomes = _race(
        {
            "submit": lambda: services.submit_job_for_review(
                JobPost.objects.select_related("employer").get(pk=draft.pk), actor=owner
            ),
            "suspend": lambda: services.set_employer_recruitment_status(
                services.Employer.objects.get(pk=employer.pk), "SUSPENDED", admin=admin
            ),
        }
    )
    assert outcomes["suspend"] == "ok", outcomes
    draft.refresh_from_db()
    if outcomes["submit"] == "ok":  # submission committed before the suspension
        assert draft.status == JobStatus.PENDING_ADMIN_REVIEW
        assert list(draft.transitions.values_list("to_status", flat=True)) == [
            "PENDING_ADMIN_REVIEW"
        ]
    else:
        assert outcomes["submit"] == "organization_not_verified", outcomes
        assert draft.status == JobStatus.DRAFT and not draft.transitions.exists()


def test_blocked_submit_is_a_typed_403_over_http(api_client, employer_factory, job_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    draft = job_factory(employer, status=JobStatus.DRAFT)
    services.set_employer_verification(employer, VerificationStatus.SUSPENDED, admin=admin)
    api_client.force_authenticate(user=owner_of(employer))
    resp = api_client.post(f"{JOBS}/{draft.id}/submit")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "organization_not_verified"
    assert not JobPost.objects.get(pk=draft.pk).transitions.exists()
