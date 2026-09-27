"""Phase 3 production-closure audit (2026-09-25): regression tests for the
visibility defects found while preparing the launch review."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.jobs import services
from apps.jobs.models import Employer, JobInvitation, JobPost, JobSeekerProfile, SavedCandidate
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import InvitationStatus, JobStatus, MemberRole

pytestmark = pytest.mark.django_db


def _suspend(employer, admin):
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")


# ---- invitation cancel: visibility rule + recruiting gate ---------------------------------


def test_cancel_returns_no_candidate_card_once_the_candidate_is_hidden(
    employer, employer_client, job_factory, seeker_factory
):
    candidate = seeker_factory()
    inv = services.invite_candidate(
        employer, job_factory(employer), candidate, actor=owner_of(employer)
    )
    candidate.discoverable_by_employers = False
    candidate.save(update_fields=["discoverable_by_employers"])
    assert employer_client.get("/api/v1/talent/invitations").json()["count"] == 0
    resp = employer_client.post(f"/api/v1/talent/invitations/{inv.pk}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED" and resp.json()["candidate"] is None
    assert JobInvitation.objects.get(pk=inv.pk).status == InvitationStatus.CANCELLED


def test_cancel_still_renders_a_visible_candidate(
    employer, employer_client, job_factory, seeker_factory
):
    candidate = seeker_factory()
    inv = services.invite_candidate(
        employer, job_factory(employer), candidate, actor=owner_of(employer)
    )
    body = employer_client.post(f"/api/v1/talent/invitations/{inv.pk}/cancel").json()
    assert body["candidate"]["id"] == str(candidate.pk)


def test_suspended_organisation_cannot_cancel_or_unsave(
    employer, employer_client, job_factory, seeker_factory, admin
):
    candidate = seeker_factory()
    inv = services.invite_candidate(
        employer, job_factory(employer), candidate, actor=owner_of(employer)
    )
    saved = services.save_candidate(employer, candidate, actor=owner_of(employer))
    _suspend(employer, admin)
    assert employer_client.post(f"/api/v1/talent/invitations/{inv.pk}/cancel").status_code == 403
    assert employer_client.delete(f"/api/v1/talent/saved/{saved.pk}").status_code == 403
    assert JobInvitation.objects.get(pk=inv.pk).status == InvitationStatus.PENDING
    assert SavedCandidate.objects.filter(pk=saved.pk).exists()


# ---- deactivated candidates ---------------------------------------------------------------


def test_deactivated_candidates_cannot_be_saved_or_invited(employer, job_factory, seeker_factory):
    candidate = seeker_factory()
    candidate.account.is_active = False
    candidate.account.save(update_fields=["is_active"])
    with pytest.raises(services.JobsError) as exc:
        services.save_candidate(employer, candidate, actor=owner_of(employer))
    assert exc.value.code == "not_found"
    with pytest.raises(services.JobsError) as exc:
        services.invite_candidate(
            employer, job_factory(employer), candidate, actor=owner_of(employer)
        )
    assert exc.value.code == "not_found"


# ---- public presence ----------------------------------------------------------------------


def test_suspended_employer_has_no_public_page(api_client, employer, admin):
    assert api_client.get(f"/api/v1/employers/{employer.pk}").status_code == 200
    _suspend(employer, admin)
    assert api_client.get(f"/api/v1/employers/{employer.pk}").status_code == 404


def test_hidden_organisation_is_not_published_through_an_agency_job(
    api_client, employer_factory, job_factory, employer_client
):
    agency = employer_factory(is_recruitment_agency=True, name="Agency")
    hidden = employer_factory(name="Hidden clinic", is_discoverable=False, description="internal")
    shown = employer_factory(name="Shown clinic")
    # write-time: a hidden organisation cannot be named
    client = APIClient()
    client.force_authenticate(user=owner_of(agency))
    payload = {
        "title": "Nurse",
        "profession": "NURSE",
        "description": "Role",
        "governorate": str(agency.governorate_id),
        "employment_type": "FULL_TIME",
        "hiring_employer": str(hidden.pk),
    }
    resp = client.post("/api/v1/jobs/employer/jobs", payload, format="json")
    assert resp.status_code == 400 and "hiring_employer" in resp.json()["error"]["codes"]
    # read-time: an organisation that hides itself after publication disappears from public cards
    job = job_factory(agency, hiring_employer=shown)
    assert api_client.get(f"/api/v1/jobs/{job.pk}").json()["hiring_employer"]["id"] == str(shown.pk)
    Employer.objects.filter(pk=shown.pk).update(is_discoverable=False)
    assert api_client.get(f"/api/v1/jobs/{job.pk}").json()["hiring_employer"] is None
    cards = {row["id"]: row for row in api_client.get("/api/v1/jobs").json()["results"]}
    assert cards[str(job.pk)]["hiring_employer"] is None
    assert "internal" not in api_client.get(f"/api/v1/jobs/{job.pk}").content.decode()
    # the agency itself still sees whom it hires for
    assert client.get(f"/api/v1/jobs/employer/jobs/{job.pk}").json()["hiring_employer"][
        "id"
    ] == str(shown.pk)


# ---- concurrency / lifecycle blockers ----------------------------------------------------

TODAY = timezone.localdate()


def _elapsed_featured(job):
    JobPost.objects.filter(pk=job.pk).update(
        is_featured=True, featured_until=timezone.now() - timedelta(hours=1)
    )


def test_featured_sweep_under_the_employer_lock_touches_only_own_jobs(
    employer_factory, job_factory
):
    mine = employer_factory(plan_code="PROFESSIONAL")
    other = employer_factory(plan_code="PROFESSIONAL")
    my_job, other_job = job_factory(mine), job_factory(other)
    _elapsed_featured(other_job)
    services.set_featured(my_job, True, actor=owner_of(mine))
    other_job.refresh_from_db()
    assert other_job.is_featured is True  # another organisation's rows are not locked here
    assert services.expire_featured_jobs() == 1  # the unscoped listing sweep still normalises
    other_job.refresh_from_db()
    assert other_job.is_featured is False


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_featuring_across_organisations_never_deadlocks(employer_factory, job_factory):
    orgs = [employer_factory(plan_code="PROFESSIONAL") for _ in range(2)]
    jobs = [job_factory(org) for org in orgs]
    for job in jobs:
        _elapsed_featured(job)
    barrier = threading.Barrier(2)
    outcomes: dict[int, str] = {}

    def run(i):
        try:
            barrier.wait(timeout=10)
            services.set_featured(JobPost.objects.get(pk=jobs[i].pk), True, actor=owner_of(orgs[i]))
            outcomes[i] = "ok"
        except Exception as exc:  # pragma: no cover
            outcomes[i] = repr(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes == {0: "ok", 1: "ok"}, outcomes
    assert all(JobPost.objects.get(pk=j.pk).featured_until > timezone.now() for j in jobs)


def test_suspending_a_job_past_its_deadline_expires_it_instead(employer, job_factory, admin):
    job = job_factory(employer, application_deadline=TODAY - timedelta(days=1))
    with pytest.raises(services.JobsError, match="Only published"):
        services.suspend_job(job, admin=admin, reason="x")
    job.refresh_from_db()
    assert job.status == JobStatus.EXPIRED
    assert list(job.transitions.values_list("to_status", flat=True)) == ["EXPIRED"]


def test_restoring_a_suspended_job_whose_deadline_elapsed_normalises_it(
    employer, job_factory, admin
):
    job = job_factory(employer, application_deadline=TODAY + timedelta(days=1))
    services.suspend_job(job, admin=admin, reason="check")
    JobPost.objects.filter(pk=job.pk).update(application_deadline=TODAY - timedelta(days=1))
    services.restore_job(job, admin=admin)
    job.refresh_from_db()
    assert job.status == JobStatus.EXPIRED and not job.is_featured
    assert list(job.transitions.values_list("to_status", flat=True)) == ["SUSPENDED", "EXPIRED"]
    services.archive_job(job, actor=owner_of(employer))  # the employer has a way out
    assert JobPost.objects.get(pk=job.pk).status == JobStatus.ARCHIVED


def test_submit_rescans_contact_data_on_the_locked_row(employer, job_factory):
    job = job_factory(employer, status=JobStatus.DRAFT)
    stale = JobPost.objects.get(pk=job.pk)
    JobPost.objects.filter(pk=job.pk).update(description="Call me on 07701234567")
    with pytest.raises(services.ContactLeak):
        services.submit_job_for_review(stale, actor=owner_of(employer))
    assert JobPost.objects.get(pk=job.pk).status == JobStatus.DRAFT


def test_restore_keeps_a_featured_window_the_stale_instance_did_not_know(
    employer, job_factory, admin
):
    job = job_factory(employer)
    stale = JobPost.objects.get(pk=job.pk)  # loaded before featuring
    services.set_featured(job, True, actor=owner_of(employer))
    services.suspend_job(JobPost.objects.get(pk=job.pk), admin=admin, reason="x")
    services.restore_job(stale, admin=admin)
    row = JobPost.objects.get(pk=job.pk)
    assert row.status == JobStatus.PUBLISHED and row.is_featured and row.featured_until


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_double_submitted_profile_creation_is_a_typed_conflict(account_factory, baghdad):
    acct = account_factory(role="PATIENT")
    payload = {
        "professional_title": "Nurse",
        "profession": "NURSE",
        "degree": "BACHELOR",
        "governorate": str(baghdad.pk),
        "years_of_experience": 2,
    }
    barrier = threading.Barrier(2)
    outcomes: list[int] = []

    def run():
        try:
            barrier.wait(timeout=10)
            client = APIClient()
            client.force_authenticate(user=acct)
            outcomes.append(
                client.post("/api/v1/jobs/me/profile", payload, format="json").status_code
            )
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == [201, 400], outcomes
    assert JobSeekerProfile.objects.filter(account=acct).count() == 1


def test_cancelling_an_elapsed_invitation_records_expiry(employer, job_factory, seeker_factory):
    inv = services.invite_candidate(
        employer, job_factory(employer), seeker_factory(), actor=owner_of(employer)
    )
    JobInvitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(days=1))
    with pytest.raises(services.JobsError) as exc:
        services.cancel_invitation(inv, actor=owner_of(employer))
    assert exc.value.code == "invitation_expired"
    assert JobInvitation.objects.get(pk=inv.pk).status == InvitationStatus.EXPIRED


def test_ending_a_membership_twice_is_a_typed_error(employer, account_factory):
    m = services.add_member(
        employer, account_factory(), MemberRole.VIEWER, actor=owner_of(employer)
    )
    services.end_membership(m, actor=owner_of(employer))
    with pytest.raises(services.JobsError) as exc:
        services.end_membership(m, actor=owner_of(employer))
    assert exc.value.code == "invalid_transition"


def test_stale_admin_instance_does_not_erase_verified_at(employer_factory, admin):
    org = employer_factory(verified=False)
    stale = Employer.objects.get(pk=org.pk)
    services.set_employer_verification(org, "VERIFIED", admin=admin)
    services.set_employer_verification(stale, "SUSPENDED", admin=admin, note="complaint")
    row = Employer.objects.get(pk=org.pk)
    assert row.verification_status == "SUSPENDED" and row.verified_at is not None


def test_job_patch_maps_domain_errors_to_their_documented_status(
    employer, job_factory, monkeypatch
):
    """The agency flag flipping between the serializer's check and the locked
    edit raises HiringFieldsNotAllowed from the service: documented 400
    not_an_agency, not a blanket 409."""
    job = job_factory(employer, status=JobStatus.DRAFT)

    def flipped(*args, **kwargs):
        raise services.HiringFieldsNotAllowed("Only recruitment agencies can hire on behalf.")

    monkeypatch.setattr(services, "edit_job", flipped)
    client = APIClient()
    client.force_authenticate(user=owner_of(employer))
    resp = client.patch(f"/api/v1/jobs/employer/jobs/{job.pk}", {"title": "New"}, format="json")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "not_an_agency"
