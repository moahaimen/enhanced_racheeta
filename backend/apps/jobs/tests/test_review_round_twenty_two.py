"""Twenty-second Codex review of PR #4 (commit cefad96): invitation
eligibility is decided on the locked candidate row, and the talent detail
exposes that eligibility (`can_invite`) so the UI never offers an invitation
the backend refuses."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.jobs import services
from apps.jobs.models import JobInvitation, JobSeekerProfile
from apps.jobs.tests.conftest import owner_of

pytestmark = pytest.mark.django_db
INVITES = "/api/v1/talent/invitations"


def _hide(candidate):
    JobSeekerProfile.objects.filter(pk=candidate.pk).update(discoverable_by_employers=False)


def test_discoverable_candidate_can_be_invited_and_duplicates_still_refused(
    employer, employer_client, job_factory, seeker_factory
):
    job, candidate = job_factory(employer), seeker_factory()
    resp = employer_client.post(
        INVITES, {"job": str(job.pk), "job_seeker": str(candidate.pk)}, format="json"
    )
    assert resp.status_code == 201 and resp.json()["candidate"]["id"] == str(candidate.pk)
    dup = employer_client.post(
        INVITES, {"job": str(job.pk), "job_seeker": str(candidate.pk)}, format="json"
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_invited"


def test_non_discoverable_candidate_cannot_be_invited(
    employer, employer_client, job_factory, seeker_factory
):
    job, candidate = job_factory(employer), seeker_factory(discoverable=False)
    resp = employer_client.post(
        INVITES, {"job": str(job.pk), "job_seeker": str(candidate.pk)}, format="json"
    )
    assert resp.status_code == 404 and "professional_title" not in resp.content.decode()
    assert not JobInvitation.objects.filter(job_seeker=candidate).exists()


def test_prior_application_keeps_detail_readable_but_not_invitable(
    employer, employer_client, job_factory, seeker_factory
):
    job, other_job, candidate = job_factory(employer), job_factory(employer), seeker_factory()
    services.apply_to_job(job, candidate)
    _hide(candidate)
    detail = employer_client.get(f"/api/v1/talent/{candidate.pk}")
    assert detail.status_code == 200 and detail.json()["can_invite"] is False
    resp = employer_client.post(
        INVITES, {"job": str(other_job.pk), "job_seeker": str(candidate.pk)}, format="json"
    )
    assert resp.status_code == 404
    assert not JobInvitation.objects.filter(job_seeker=candidate).exists()


def test_can_invite_reflects_current_discoverability(employer_client, seeker_factory):
    candidate = seeker_factory()
    assert employer_client.get(f"/api/v1/talent/{candidate.pk}").json()["can_invite"] is True
    _hide(candidate)
    assert (
        employer_client.get(f"/api/v1/talent/{candidate.pk}").status_code == 404
    )  # no relationship


def test_stale_profile_instance_is_re_read_under_lock(employer, job_factory, seeker_factory):
    job, candidate = job_factory(employer), seeker_factory()
    stale = JobSeekerProfile.objects.select_related("account").get(pk=candidate.pk)
    _hide(candidate)  # the opt-out commits before the invitation transaction
    assert stale.discoverable_by_employers is True
    with pytest.raises(services.JobsError) as exc:
        services.invite_candidate(employer, job, stale, actor=owner_of(employer))
    assert exc.value.code == "not_found"
    assert stale.discoverable_by_employers is False  # synchronised, not stale
    assert not JobInvitation.objects.filter(job_seeker=candidate).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_opt_out_racing_an_invitation_never_creates_an_invitation_after_it(
    employer_factory, job_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job, candidate = job_factory(employer), seeker_factory()
    stale = JobSeekerProfile.objects.select_related("account").get(pk=candidate.pk)
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def opt_out():
        try:
            barrier.wait(timeout=10)
            client = APIClient()
            client.force_authenticate(user=candidate.account)
            outcomes["opt_out"] = client.patch(
                "/api/v1/jobs/me/profile", {"discoverable_by_employers": False}, format="json"
            ).status_code
        finally:
            connection.close()

    def invite():
        try:
            barrier.wait(timeout=10)
            services.invite_candidate(employer, job, stale, actor=owner_of(employer))
            outcomes["invite"] = "ok"
        except services.JobsError as exc:
            outcomes["invite"] = exc.code
        except Exception as exc:  # pragma: no cover
            outcomes["invite"] = repr(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=opt_out), threading.Thread(target=invite)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["opt_out"] == 200
    assert outcomes["invite"] in ("ok", "not_found"), outcomes
    created = JobInvitation.objects.filter(job=job, job_seeker=candidate).exists()
    assert created == (outcomes["invite"] == "ok")
    assert JobSeekerProfile.objects.get(pk=candidate.pk).discoverable_by_employers is False
