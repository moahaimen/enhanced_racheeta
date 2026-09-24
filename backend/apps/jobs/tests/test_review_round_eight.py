"""Regression tests for the eighth Codex review of PR #4 (commit ec62133):
agency hiring fields validated on resulting state, invitation acceptance
validated against locked job/employer state, and saves gated on recruiting."""

import threading

import pytest
from django.db import connection

from apps.billing import services as billing
from apps.billing.types import Audience, SubjectType
from apps.jobs import services
from apps.jobs.models import JobInvitation, JobPost, SavedCandidate
from apps.jobs.tests.conftest import owner_of
from apps.jobs.tests.test_jobs_lifecycle import draft_payload
from apps.jobs.types import InvitationStatus, JobStatus, VerificationStatus

JOBS = "/api/v1/jobs/employer/jobs"
TALENT = "/api/v1/talent"
INVITES = "/api/v1/jobs/me/invitations"


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


# ---- 1. hiring fields for non-agencies ------------------------------------------


@pytest.fixture
def agency_with_drafts(api_client, employer_factory, employer, baghdad):
    agency = employer_factory(
        verified=False, is_recruitment_agency=True, organization_type="RECRUITMENT_AGENCY"
    )
    api_client.force_authenticate(user=owner_of(agency))
    by_fk = api_client.post(JOBS, draft_payload(baghdad, hiring_employer=str(employer.id)))
    by_name = api_client.post(
        JOBS, draft_payload(baghdad, hiring_organization_name="Karrada clinic")
    )
    assert by_fk.status_code == 201 and by_name.status_code == 201
    return (
        agency,
        JobPost.objects.get(pk=by_fk.json()["id"]),
        JobPost.objects.get(pk=by_name.json()["id"]),
    )


def test_agency_can_create_both_kinds_of_hiring_jobs(agency_with_drafts):
    agency, by_fk, by_name = agency_with_drafts
    assert by_fk.hiring_employer_id and by_name.hiring_organization_name == "Karrada clinic"


def test_retained_hiring_fields_block_edit_and_submit_after_losing_agency_status(
    api_client, agency_with_drafts, admin
):
    agency, by_fk, by_name = agency_with_drafts
    # Still UNVERIFIED, so the owner may change the flag; both drafts keep their hiring fields.
    assert (
        api_client.patch(
            "/api/v1/jobs/employer", {"is_recruitment_agency": False}, format="json"
        ).status_code
        == 200
    )
    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    owner = owner_of(agency)
    # An unrelated PATCH is refused because the RESULTING job would still claim to hire for others.
    for job, field in ((by_fk, "hiring_employer"), (by_name, "hiring_organization_name")):
        resp = api_client.patch(f"{JOBS}/{job.id}", {"title": "Renamed"}, format="json")
        assert resp.status_code == 400, resp.content
        assert resp.json()["error"]["codes"][field] == ["not_an_agency"]
        job.refresh_from_db()
        assert job.title != "Renamed"
        # Submit is refused too, on the locked/refreshed employer + job state.
        with pytest.raises(services.HiringFieldsNotAllowed):
            services.submit_job_for_review(job, actor=owner)
        submitted = api_client.post(f"{JOBS}/{job.id}/submit")
        assert submitted.status_code == 400 and submitted.json()["error"]["code"] == "not_an_agency"
        job.refresh_from_db()
        assert job.status == JobStatus.DRAFT and not job.transitions.exists()
    # Clearing the fields makes both editable and submittable again.
    cleared = api_client.patch(
        f"{JOBS}/{by_fk.id}", {"hiring_employer": None, "title": "Renamed"}, format="json"
    )
    assert cleared.status_code == 200 and cleared.json()["title"] == "Renamed"
    assert (
        api_client.patch(
            f"{JOBS}/{by_name.id}", {"hiring_organization_name": ""}, format="json"
        ).status_code
        == 200
    )
    assert api_client.post(f"{JOBS}/{by_fk.id}/submit").status_code == 200


def test_stale_agency_flag_cannot_bypass_the_invariant_at_submit(agency_with_drafts, admin):
    agency, by_fk, _ = agency_with_drafts
    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    stale_job = JobPost.objects.select_related("employer").get(pk=by_fk.pk)  # flagged as agency
    # An administrator-side correction of the flag (bypasses the owner identity lock).
    services.Employer.objects.filter(pk=agency.pk).update(is_recruitment_agency=False)
    assert stale_job.employer.is_recruitment_agency and stale_job.employer.can_recruit
    with pytest.raises(services.HiringFieldsNotAllowed):
        services.submit_job_for_review(stale_job, actor=owner_of(agency))


def test_plain_non_agency_jobs_still_work(employer_client, baghdad):
    created = employer_client.post(JOBS, draft_payload(baghdad))
    assert created.status_code == 201
    assert (
        employer_client.patch(f"{JOBS}/{created.json()['id']}", {"title": "Plain"}).status_code
        == 200
    )
    assert employer_client.post(f"{JOBS}/{created.json()['id']}/submit").status_code == 200


# ---- 2. accepting an invitation --------------------------------------------------


def _invited(employer, job_factory, seeker_factory, **job_fields):
    job = job_factory(employer, **job_fields)
    candidate = seeker_factory()
    inv = services.invite_candidate(employer, job, candidate, actor=owner_of(employer))
    return job, candidate, inv


def test_live_invitation_on_open_job_is_accepted(api_client, employer, job_factory, seeker_factory):
    job, candidate, inv = _invited(employer, job_factory, seeker_factory)
    api_client.force_authenticate(user=candidate.account)
    resp = api_client.post(f"{INVITES}/{inv.id}/respond", {"accept": True})
    assert resp.status_code == 200 and resp.json()["status"] == "ACCEPTED"


@pytest.mark.parametrize("how", ["closed", "suspended_job", "recruitment", "verification"])
def test_acceptance_refused_when_job_or_employer_is_no_longer_valid(
    api_client, employer_factory, job_factory, seeker_factory, admin, how
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job, candidate, inv = _invited(employer, job_factory, seeker_factory)
    if how == "closed":
        services.close_job(job, actor=owner_of(employer))
    elif how == "suspended_job":
        services.suspend_job(job, admin=admin, reason="review")
    elif how == "recruitment":
        services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    else:
        services.set_employer_verification(employer, VerificationStatus.SUSPENDED, admin=admin)
    api_client.force_authenticate(user=candidate.account)
    resp = api_client.post(f"{INVITES}/{inv.id}/respond", {"accept": True})
    assert resp.status_code == 409, resp.content
    assert resp.json()["error"]["code"] == "invitation_unavailable"
    inv.refresh_from_db()
    assert inv.status == InvitationStatus.PENDING and inv.responded_at is None
    # Declining is still possible.
    declined = api_client.post(f"{INVITES}/{inv.id}/respond", {"accept": False})
    assert declined.status_code == 200 and declined.json()["status"] == "DECLINED"
    assert JobInvitation.objects.filter(pk=inv.pk).count() == 1


def test_expired_invitation_still_expires_instead_of_accepting(
    api_client, employer, job_factory, seeker_factory
):
    from datetime import timedelta

    from django.utils import timezone

    job, candidate, inv = _invited(employer, job_factory, seeker_factory)
    JobInvitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(hours=1))
    api_client.force_authenticate(user=candidate.account)
    resp = api_client.post(f"{INVITES}/{inv.id}/respond", {"accept": True})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "invitation_expired"
    inv.refresh_from_db()
    assert inv.status == InvitationStatus.EXPIRED


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("closer", ["close", "suspend"])
def test_accept_races_close_or_suspend(
    employer_factory, job_factory, seeker_factory, admin, closer
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job, candidate, inv = _invited(employer, job_factory, seeker_factory)

    def accept():
        services.respond_to_invitation(
            JobInvitation.objects.select_related("job", "job__employer").get(pk=inv.pk), accept=True
        )

    def close():
        target = JobPost.objects.get(pk=job.pk)
        if closer == "close":
            services.close_job(target, actor=owner_of(employer))
        else:
            services.suspend_job(target, admin=admin, reason="review")

    outcomes = _race({"accept": accept, "closer": close})
    assert outcomes["closer"] == "ok", outcomes
    inv.refresh_from_db()
    job.refresh_from_db()
    if outcomes["accept"] == "ok":  # accepted before the job changed
        assert inv.status == InvitationStatus.ACCEPTED
    else:
        assert outcomes["accept"] == "invitation_unavailable", outcomes
        assert inv.status == InvitationStatus.PENDING
    assert job.status == (JobStatus.CLOSED if closer == "close" else JobStatus.SUSPENDED)
    assert list(job.transitions.values_list("to_status", flat=True)) == [job.status]


# ---- 3. saving candidates -------------------------------------------------------


def test_entitled_active_employer_can_save(api_client, employer_factory, seeker_factory):
    basic = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(basic))
    resp = api_client.post(f"{TALENT}/saved", {"job_seeker": str(seeker_factory().id)})
    assert resp.status_code == 201


@pytest.mark.parametrize("how", ["recruitment", "verification", "subscription"])
def test_suspended_employer_or_plan_cannot_save(
    api_client, employer_factory, seeker_factory, admin, how
):
    basic = employer_factory(plan_code="BASIC")
    if how == "recruitment":
        services.set_employer_recruitment_status(basic, "SUSPENDED", admin=admin, reason="x")
    elif how == "verification":
        services.set_employer_verification(basic, VerificationStatus.SUSPENDED, admin=admin)
    else:
        account = billing.get_or_create_billing_account(
            SubjectType.ORGANIZATION, basic.pk, Audience.EMPLOYER
        )
        billing.suspend_subscription(account.subscriptions.get(status="ACTIVE"), admin=admin)
    api_client.force_authenticate(user=owner_of(basic))
    resp = api_client.post(f"{TALENT}/saved", {"job_seeker": str(seeker_factory().id)})
    assert resp.status_code == 403, resp.content
    expected = "entitlement_required" if how == "subscription" else "organization_not_verified"
    assert resp.json()["error"]["code"] == expected
    assert not SavedCandidate.objects.filter(employer=basic).exists()


def test_service_level_save_also_refuses_a_suspended_organisation(
    employer_factory, seeker_factory, admin
):
    basic = employer_factory(plan_code="BASIC")
    stale = services.Employer.objects.get(pk=basic.pk)
    services.set_employer_recruitment_status(basic, "SUSPENDED", admin=admin, reason="x")
    with pytest.raises(services.OrganizationNotVerified):
        services.save_candidate(stale, seeker_factory(), actor=owner_of(basic))
    assert not SavedCandidate.objects.exists()


def test_viewer_cannot_save_and_organisations_stay_isolated(
    api_client, employer_factory, seeker_factory, account_factory
):
    basic = employer_factory(plan_code="BASIC")
    viewer = account_factory()
    services.add_member(basic, viewer, "VIEWER", actor=owner_of(basic))
    api_client.force_authenticate(user=viewer)
    assert (
        api_client.post(f"{TALENT}/saved", {"job_seeker": str(seeker_factory().id)}).status_code
        == 403
    )
    other = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(other))
    assert api_client.get(f"{TALENT}/saved").json() == []
    assert not SavedCandidate.objects.exists()
