"""Regression tests for the fifth Codex review of PR #4 (commit 750ef64):
locked job edits, identity edits serialised with verification decisions, and
entitlement checks on the saved-candidate and other paid read endpoints."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.types import Audience, SubjectType
from apps.jobs import services
from apps.jobs.models import Employer, JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus, VerificationStatus

ME = "/api/v1/jobs/employer"
JOBS = "/api/v1/jobs/employer/jobs"
TALENT = "/api/v1/talent"


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


# ---- 1. job edits vs lifecycle -----------------------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_patch_and_submit_serialise(employer_factory, job_factory):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    job = job_factory(employer, status=JobStatus.DRAFT, title="Original")
    outcomes = _race(
        {
            "patch": lambda: services.edit_job(
                JobPost.objects.get(pk=job.pk), {"title": "Edited"}, actor=owner
            ),
            "submit": lambda: services.submit_job_for_review(
                JobPost.objects.get(pk=job.pk), actor=owner
            ),
        }
    )
    job.refresh_from_db()
    assert outcomes["submit"] == "ok", outcomes
    assert job.status == JobStatus.PENDING_ADMIN_REVIEW  # never reverted to DRAFT
    assert outcomes["patch"] in ("ok", "job_locked"), outcomes
    if outcomes["patch"] == "ok":  # the edit landed before the submission
        assert job.title == "Edited"
    else:  # the submission won: the reviewed content is untouched
        assert job.title == "Original"
    assert list(job.transitions.values_list("to_status", flat=True)) == ["PENDING_ADMIN_REVIEW"]


def test_stale_patch_cannot_revert_or_change_a_submitted_job(
    employer_client, employer, job_factory
):
    owner = owner_of(employer)
    job = job_factory(employer, status=JobStatus.DRAFT, title="Original")
    stale = JobPost.objects.get(pk=job.pk)  # loaded as DRAFT
    services.submit_job_for_review(job, actor=owner)
    with pytest.raises(services.JobsError) as excinfo:
        services.edit_job(stale, {"title": "Sneaky"}, actor=owner)
    assert excinfo.value.code == "job_locked"
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING_ADMIN_REVIEW and job.title == "Original"
    assert job.submitted_at is not None  # lifecycle columns never overwritten
    resp = employer_client.patch(f"{JOBS}/{job.id}", {"title": "Sneaky"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "job_locked"


def test_sequential_draft_edits_write_only_the_edited_fields(
    employer_client, employer, job_factory
):
    job = job_factory(employer, status=JobStatus.DRAFT, title="Draft")
    first = employer_client.patch(f"{JOBS}/{job.id}", {"title": "Draft v2"})
    assert first.status_code == 200 and first.json()["title"] == "Draft v2"
    second = employer_client.patch(f"{JOBS}/{job.id}", {"minimum_experience_years": 4})
    assert second.status_code == 200 and second.json()["minimum_experience_years"] == 4
    job.refresh_from_db()
    assert job.title == "Draft v2" and job.status == JobStatus.DRAFT
    assert not job.transitions.exists()  # edits are not transitions


# ---- 2. identity edits vs verification decisions ----------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_identity_patch_racing_admin_verify_never_verifies_unreviewed_identity(
    employer_factory, admin
):
    org = employer_factory(verified=False, organization_type="CLINIC")
    owner = owner_of(org)
    outcomes = _race(
        {
            "patch": lambda: services.update_employer(
                Employer.objects.get(pk=org.pk), {"organization_type": "PHARMACY"}, actor=owner
            ),
            "verify": lambda: services.set_employer_verification(
                Employer.objects.get(pk=org.pk), VerificationStatus.VERIFIED, admin=admin
            ),
        }
    )
    org.refresh_from_db()
    assert outcomes["verify"] == "ok", outcomes
    assert org.verification_status == VerificationStatus.VERIFIED
    if outcomes["patch"] == "ok":  # edit committed first: the decision reviewed PHARMACY
        assert org.organization_type == "PHARMACY"
    else:  # decision committed first: the edit was refused by the lock
        assert outcomes["patch"] == "identity_locked" and org.organization_type == "CLINIC"


def test_patch_after_verification_is_locked_and_presentation_edits_pass(
    api_client, employer_factory, admin
):
    org = employer_factory(verified=False, organization_type="CLINIC")
    api_client.force_authenticate(user=owner_of(org))
    services.set_employer_verification(org, VerificationStatus.VERIFIED, admin=admin)
    stale_resp = api_client.patch(ME, {"organization_type": "PHARMACY"}, format="json")
    assert stale_resp.status_code == 400
    assert stale_resp.json()["error"]["codes"]["organization_type"] == ["identity_locked"]
    ok = api_client.patch(ME, {"description": "New wing opening soon."}, format="json")
    assert ok.status_code == 200 and ok.json()["description"] == "New wing opening soon."


def test_service_identity_lock_uses_the_locked_row_not_the_instance(employer_factory, admin):
    org = employer_factory(verified=False, organization_type="CLINIC")
    stale = Employer.objects.get(pk=org.pk)  # still thinks UNVERIFIED
    services.set_employer_verification(org, VerificationStatus.VERIFIED, admin=admin)
    with pytest.raises(services.IdentityLocked) as excinfo:
        services.update_employer(stale, {"organization_type": "PHARMACY"}, actor=owner_of(org))
    assert excinfo.value.fields == ["organization_type"]
    org.refresh_from_db()
    assert org.organization_type == "CLINIC" and org.verification_status == "VERIFIED"


def test_admin_decisions_refresh_the_row_before_writing(employer_factory, admin):
    org = employer_factory(verified=False)
    stale = Employer.objects.get(pk=org.pk)
    services.request_employer_verification(org, actor=owner_of(org))
    services.set_employer_recruitment_status(stale, "SUSPENDED", admin=admin, reason="x")
    org.refresh_from_db()
    assert org.verification_status == "PENDING"  # not clobbered by the stale instance
    assert org.recruitment_status == "SUSPENDED"
    with pytest.raises(services.JobsError):
        services.request_employer_verification(stale, actor=owner_of(org))  # already PENDING


# ---- 3. saved candidates and other paid reads --------------------------------------


def _account(employer):
    return billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )


@pytest.fixture
def basic_with_saved(employer_factory, seeker_factory, admin):
    employer = employer_factory(plan_code="BASIC")
    candidate = seeker_factory()
    services.save_candidate(employer, candidate, actor=owner_of(employer), note="strong")
    return employer, candidate


def test_entitled_employer_lists_saved_candidates(api_client, basic_with_saved):
    employer, candidate = basic_with_saved
    api_client.force_authenticate(user=owner_of(employer))
    listed = api_client.get(f"{TALENT}/saved")
    assert listed.status_code == 200 and [
        r["candidate"]["id"] for r in listed.json()["results"]
    ] == [str(candidate.id)]


def test_expired_subscription_cannot_list_saved_candidates(api_client, basic_with_saved, admin):
    employer, _ = basic_with_saved
    sub = _account(employer).subscriptions.get(status="ACTIVE")
    sub.starts_at = timezone.now() - timedelta(days=60)
    sub.ends_at = timezone.now() - timedelta(days=30)
    sub.save(update_fields=["starts_at", "ends_at"])
    api_client.force_authenticate(user=owner_of(employer))
    denied = api_client.get(f"{TALENT}/saved")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "entitlement_required"
    assert denied.json()["error"]["meta"]["key"] == "talent.save_candidate"


def test_suspended_subscription_cannot_list_saved_candidates(api_client, basic_with_saved, admin):
    employer, _ = basic_with_saved
    sub = _account(employer).subscriptions.get(status="ACTIVE")
    billing.suspend_subscription(sub, admin=admin, reason="late payment")
    api_client.force_authenticate(user=owner_of(employer))
    denied = api_client.get(f"{TALENT}/saved")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "entitlement_required"


def test_recruitment_suspended_organisation_cannot_list_saved_candidates(
    api_client, basic_with_saved, admin
):
    employer, _ = basic_with_saved
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="audit")
    api_client.force_authenticate(user=owner_of(employer))
    denied = api_client.get(f"{TALENT}/saved")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "organization_not_verified"


def test_plan_without_entitlement_cannot_list_but_post_behaviour_is_unchanged(
    api_client, employer_factory, seeker_factory
):
    trial = employer_factory()  # TRIAL: no talent.save_candidate
    api_client.force_authenticate(user=owner_of(trial))
    denied = api_client.get(f"{TALENT}/saved")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "entitlement_required"
    post = api_client.post(f"{TALENT}/saved", {"job_seeker": str(seeker_factory().id)})
    assert post.status_code == 403 and post.json()["error"]["code"] == "entitlement_required"


def test_saved_candidates_stay_isolated_between_organisations(
    api_client, basic_with_saved, employer_factory
):
    other = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(other))
    assert api_client.get(f"{TALENT}/saved").json()["results"] == []


def test_talent_detail_and_sent_invitations_need_recruitment_access(
    api_client, employer_factory, seeker_factory, job_factory, admin
):
    employer = employer_factory(plan_code="BASIC")
    candidate = seeker_factory()
    owner = owner_of(employer)
    services.invite_candidate(employer, job_factory(employer), candidate, actor=owner)
    api_client.force_authenticate(user=owner)
    assert api_client.get(f"{TALENT}/{candidate.id}").status_code == 200
    assert api_client.get(f"{TALENT}/invitations").json()["count"] == 1
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="audit")
    for url in (f"{TALENT}/{candidate.id}", f"{TALENT}/invitations"):
        resp = api_client.get(url)
        assert resp.status_code == 403, url
        assert resp.json()["error"]["code"] == "organization_not_verified", url
