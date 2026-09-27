"""Twenty-third Codex review of PR #4 (commit cb98621): profile PATCHes write
only the submitted fields onto the locked row (a concurrent opt-out is never
reversed), saving a candidate decides on the locked candidate row."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.geography.models import City
from apps.jobs import services
from apps.jobs.models import JobSeekerProfile, SavedCandidate, WorkExperience
from apps.jobs.tests.conftest import owner_of

pytestmark = pytest.mark.django_db
PROFILE = "/api/v1/jobs/me/profile"
SAVED = "/api/v1/talent/saved"


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


# ---- 1. seeker profile PATCH -----------------------------------------------------------


def test_partial_patch_writes_only_the_submitted_fields(seeker):
    client = _client(seeker.account)
    resp = client.patch(PROFILE, {"professional_summary": "ICU nurse, 3 years."}, format="json")
    assert resp.status_code == 200 and resp.json()["professional_summary"] == "ICU nurse, 3 years."
    row = JobSeekerProfile.objects.get(pk=seeker.pk)
    assert (
        row.discoverable_by_employers is True
        and row.professional_title == seeker.professional_title
    )
    resp = client.patch(PROFILE, {"discoverable_by_employers": False}, format="json")
    assert resp.status_code == 200 and resp.json()["discoverable_by_employers"] is False
    row.refresh_from_db()
    assert row.professional_summary == "ICU nurse, 3 years."  # untouched by the second request


def test_stale_instance_cannot_restore_a_committed_opt_out(seeker):
    stale = JobSeekerProfile.objects.get(pk=seeker.pk)  # discoverable=True in memory
    JobSeekerProfile.objects.filter(pk=seeker.pk).update(discoverable_by_employers=False)
    services.update_seeker_profile(stale, {"professional_summary": "Updated"})
    row = JobSeekerProfile.objects.get(pk=seeker.pk)
    assert row.discoverable_by_employers is False and row.professional_summary == "Updated"
    assert stale.discoverable_by_employers is False  # synchronised


def test_existing_validation_and_cross_field_rules_still_run(seeker, baghdad, basra):
    client = _client(seeker.account)
    assert client.patch(PROFILE, {"graduation_year": 1800}, format="json").status_code == 400
    basra_city = City.objects.filter(governorate=basra, is_active=True).first()
    resp = client.patch(PROFILE, {"city": str(basra_city.pk)}, format="json")
    assert resp.status_code == 400 and "city" in resp.json()["error"]["codes"]
    # stale governorate edit against a city set meanwhile is refused on the locked row
    stale = JobSeekerProfile.objects.get(pk=seeker.pk)
    baghdad_city = City.objects.filter(governorate=baghdad, is_active=True).first()
    services.update_seeker_profile(seeker, {"city": baghdad_city})
    with pytest.raises(services.FieldsInvalid):
        services.update_seeker_profile(stale, {"governorate": basra})
    row = JobSeekerProfile.objects.get(pk=seeker.pk)
    assert (row.governorate_id, row.city_id) == (baghdad.pk, baghdad_city.pk)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_unrelated_patch_never_reverses_an_opt_out(seeker_factory):
    seeker = seeker_factory()
    barrier = threading.Barrier(2)
    outcomes: dict[str, int] = {}

    def run(name, payload):
        try:
            barrier.wait(timeout=10)
            outcomes[name] = (
                _client(seeker.account).patch(PROFILE, payload, format="json").status_code
            )
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=("summary", {"professional_summary": "Night shifts."})),
        threading.Thread(target=run, args=("opt_out", {"discoverable_by_employers": False})),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes == {"summary": 200, "opt_out": 200}, outcomes
    row = JobSeekerProfile.objects.get(pk=seeker.pk)
    # whichever order they ran in, each request wrote only its own field
    assert row.discoverable_by_employers is False
    assert row.professional_summary == "Night shifts."


def test_child_row_patch_writes_over_the_committed_row(seeker):
    client = _client(seeker.account)
    xp = client.post(
        "/api/v1/jobs/me/profile/experiences",
        {"title": "Nurse", "organization_name": "Hospital A", "start_date": "2020-01-01"},
        format="json",
    )
    assert xp.status_code == 201, xp.content
    pk = xp.json()["id"]
    WorkExperience.objects.filter(pk=pk).update(
        organization_name="Hospital B"
    )  # committed meanwhile
    resp = client.patch(
        f"/api/v1/jobs/me/profile/experiences/{pk}", {"title": "Senior nurse"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    row = WorkExperience.objects.get(pk=pk)
    assert (row.title, row.organization_name) == ("Senior nurse", "Hospital B")


# ---- 2. save candidate on the locked candidate row ------------------------------------------


def test_discoverable_candidate_can_be_saved_and_duplicates_refused(
    employer, employer_client, seeker_factory
):
    candidate = seeker_factory()
    resp = employer_client.post(SAVED, {"job_seeker": str(candidate.pk)}, format="json")
    assert resp.status_code == 201 and resp.json()["candidate"]["id"] == str(candidate.pk)
    dup = employer_client.post(SAVED, {"job_seeker": str(candidate.pk)}, format="json")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_saved"


def test_non_discoverable_candidate_cannot_be_newly_saved(
    employer, employer_client, seeker_factory
):
    candidate = seeker_factory(discoverable=False)
    resp = employer_client.post(SAVED, {"job_seeker": str(candidate.pk)}, format="json")
    assert resp.status_code == 404 and "professional_title" not in resp.content.decode()
    assert not SavedCandidate.objects.filter(job_seeker=candidate).exists()


def test_prior_applicant_may_still_be_saved_and_existing_saves_survive_an_opt_out(
    employer, employer_client, job_factory, seeker_factory
):
    applicant, saved_earlier = seeker_factory(), seeker_factory()
    services.apply_to_job(job_factory(employer), applicant)
    services.save_candidate(employer, saved_earlier, actor=owner_of(employer))
    for c in (applicant, saved_earlier):
        JobSeekerProfile.objects.filter(pk=c.pk).update(discoverable_by_employers=False)
    # existing policy: an applicant stays saveable; an existing relationship is kept
    assert (
        employer_client.post(SAVED, {"job_seeker": str(applicant.pk)}, format="json").status_code
        == 201
    )
    assert SavedCandidate.objects.filter(employer=employer, job_seeker=saved_earlier).exists()


def test_stale_candidate_instance_is_re_read_under_lock(employer, seeker_factory):
    candidate = seeker_factory()
    stale = JobSeekerProfile.objects.select_related("account").get(pk=candidate.pk)
    JobSeekerProfile.objects.filter(pk=candidate.pk).update(discoverable_by_employers=False)
    with pytest.raises(services.JobsError) as exc:
        services.save_candidate(employer, stale, actor=owner_of(employer))
    assert exc.value.code == "not_found"
    assert stale.discoverable_by_employers is False  # synchronised, nothing stale to render
    assert not SavedCandidate.objects.filter(job_seeker=candidate).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_opt_out_racing_a_save_never_creates_a_relationship_after_it(
    employer_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    candidate = seeker_factory()
    stale = JobSeekerProfile.objects.select_related("account").get(pk=candidate.pk)
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def opt_out():
        try:
            barrier.wait(timeout=10)
            outcomes["opt_out"] = (
                _client(candidate.account)
                .patch(PROFILE, {"discoverable_by_employers": False}, format="json")
                .status_code
            )
        finally:
            connection.close()

    def save():
        try:
            barrier.wait(timeout=10)
            services.save_candidate(employer, stale, actor=owner_of(employer))
            outcomes["save"] = "ok"
        except services.JobsError as exc:
            outcomes["save"] = exc.code
        except Exception as exc:  # pragma: no cover
            outcomes["save"] = repr(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=opt_out), threading.Thread(target=save)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["opt_out"] == 200 and outcomes["save"] in ("ok", "not_found"), outcomes
    assert SavedCandidate.objects.filter(job_seeker=candidate).exists() == (
        outcomes["save"] == "ok"
    )
    assert JobSeekerProfile.objects.get(pk=candidate.pk).discoverable_by_employers is False
