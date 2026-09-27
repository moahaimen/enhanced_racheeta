"""Regression tests for the fifteenth Codex review of PR #4 (commit ed45278):
restore re-validates featured state, featuring refuses elapsed jobs, ACCEPTED
invitations block duplicates."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.billing.exceptions import UsageLimitReached
from apps.billing.models import PlanEntitlement
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import JobInvitation, JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import InvitationStatus, JobStatus

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()
ADMIN = "/api/v1/admin/recruitment/jobs"


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
        except UsageLimitReached:
            outcomes[name] = "usage_limit_reached"
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


def _feature(job, days=30):
    return services.set_featured(job, True, actor=owner_of(job.employer), days=days)


def _suspended_featured(employer, job_factory, admin):
    job = _feature(job_factory(employer))
    services.suspend_job(job, admin=admin, reason="review")
    job.refresh_from_db()
    assert job.status == JobStatus.SUSPENDED and job.is_featured
    return job


# ---- 1. restore re-validates featured state ----------------------------------------


def test_restore_keeps_a_still_valid_featured_state(employer, job_factory, admin):
    job = _suspended_featured(employer, job_factory, admin)  # PROFESSIONAL: 2 slots
    services.restore_job(job, admin=admin)
    job.refresh_from_db()
    assert job.status == JobStatus.PUBLISHED and job.is_actively_featured


def test_restore_drops_featured_state_when_the_last_slot_was_taken(employer, job_factory, admin):
    suspended = _suspended_featured(employer, job_factory, admin)
    _feature(job_factory(employer))
    _feature(job_factory(employer))  # both PROFESSIONAL slots now in use
    services.restore_job(suspended, admin=admin)
    suspended.refresh_from_db()
    assert suspended.status == JobStatus.PUBLISHED
    assert suspended.is_featured is False and suspended.featured_until is None
    assert services._live_featured_count(employer) == 2  # never over quota


@pytest.mark.parametrize("how", ["entitlement", "limit"])
def test_restore_drops_featured_state_after_a_plan_change(employer, job_factory, admin, how):
    suspended = _suspended_featured(employer, job_factory, admin)
    _feature(job_factory(employer))
    if how == "entitlement":
        PlanEntitlement.objects.filter(plan__code="PROFESSIONAL", key=Keys.JOBS_FEATURED).update(
            enabled=False
        )
    else:
        PlanEntitlement.objects.filter(
            plan__code="PROFESSIONAL", key=Keys.JOBS_FEATURED_LIMIT
        ).update(limit=1)
    services.restore_job(suspended, admin=admin)
    suspended.refresh_from_db()
    assert suspended.status == JobStatus.PUBLISHED and not suspended.is_featured
    assert services._live_featured_count(employer) == 1


def test_restore_clears_an_elapsed_featured_window(employer, job_factory, admin):
    suspended = _suspended_featured(employer, job_factory, admin)
    JobPost.objects.filter(pk=suspended.pk).update(
        featured_until=timezone.now() - timedelta(days=1)
    )
    services.restore_job(suspended, admin=admin)
    suspended.refresh_from_db()
    assert suspended.status == JobStatus.PUBLISHED
    assert suspended.is_featured is False and suspended.featured_until is None


def test_plain_restore_and_active_slot_check_are_unchanged(
    admin_client, employer_factory, job_factory
):
    trial = employer_factory()
    plain = job_factory(trial, status=JobStatus.SUSPENDED)
    assert admin_client.post(f"{ADMIN}/{plain.id}/restore").json()["status"] == "PUBLISHED"
    another = job_factory(trial, status=JobStatus.SUSPENDED)
    resp = admin_client.post(f"{ADMIN}/{another.id}/restore")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "usage_limit_reached"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_restore_races_feature_for_the_last_slot(employer_factory, job_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    suspended = _suspended_featured(employer, job_factory, admin)
    _feature(job_factory(employer))  # one slot left
    contender = job_factory(employer)
    outcomes = _race(
        {
            "restore": lambda: services.restore_job(
                JobPost.objects.get(pk=suspended.pk), admin=admin
            ),
            "feature": lambda: _feature(JobPost.objects.get(pk=contender.pk)),
        }
    )
    assert outcomes["restore"] == "ok", outcomes
    suspended.refresh_from_db()
    contender.refresh_from_db()
    assert suspended.status == JobStatus.PUBLISHED
    assert services._live_featured_count(employer) <= 2
    if outcomes["feature"] == "ok":  # contender won the slot: the restored job lost its flag
        assert contender.is_actively_featured and not suspended.is_featured
    else:  # restore kept its slot first: the contender was refused
        assert outcomes["feature"] == "usage_limit_reached", outcomes
        assert suspended.is_actively_featured and not contender.is_featured


# ---- 2. featuring an elapsed job --------------------------------------------------------


@pytest.mark.parametrize("delta,ok", [(5, True), (0, True), (-1, False)])
def test_featuring_follows_the_open_deadline_rule(
    employer_client, employer, job_factory, delta, ok
):
    job = job_factory(employer, application_deadline=TODAY + timedelta(days=delta))
    resp = employer_client.post(f"/api/v1/jobs/employer/jobs/{job.id}/feature", {"featured": True})
    job.refresh_from_db()
    if ok:
        assert resp.status_code == 200 and job.is_actively_featured
    else:
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "deadline_passed"
        assert job.is_featured is False and job.featured_until is None
        assert services._live_featured_count(employer) == 0


def test_expired_row_cannot_be_featured_and_gates_still_apply(employer_factory, job_factory, admin):
    basic = employer_factory(plan_code="BASIC")  # no jobs.featured
    with pytest.raises(services.JobsError):
        _feature(job_factory(basic, status=JobStatus.EXPIRED))
    from apps.billing.exceptions import EntitlementError

    with pytest.raises(EntitlementError):
        _feature(job_factory(basic))


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_feature_races_overdue_normalisation(employer_factory, job_factory):
    employer = employer_factory(plan_code="PROFESSIONAL")
    overdue = job_factory(employer, application_deadline=TODAY - timedelta(days=1))
    outcomes = _race(
        {
            "feature": lambda: _feature(
                JobPost.objects.select_related("employer").get(pk=overdue.pk)
            ),
            "expire": lambda: services.expire_overdue_jobs(employer=employer),
        }
    )
    overdue.refresh_from_db()
    assert outcomes["expire"] == "ok", outcomes
    assert outcomes["feature"] in ("deadline_passed", "invalid_transition"), outcomes
    assert overdue.status == JobStatus.EXPIRED and not overdue.is_featured


# ---- 3. ACCEPTED invitations block duplicates ---------------------------------------


def _invites_used(employer):
    return services.employer_entitlements(employer).get(Keys.TALENT_INVITE_LIMIT).used


@pytest.mark.parametrize(
    "state,blocks",
    [
        ("PENDING", True),
        ("ACCEPTED", True),
        ("DECLINED", False),
        ("EXPIRED", False),
        ("CANCELLED", False),
    ],
)
def test_duplicate_invitation_rule_by_status(employer, job_factory, seeker_factory, state, blocks):
    job, candidate = job_factory(employer), seeker_factory()
    owner = owner_of(employer)
    first = services.invite_candidate(employer, job, candidate, actor=owner)
    if state == "ACCEPTED":
        services.respond_to_invitation(first, accept=True)
    elif state == "DECLINED":
        services.respond_to_invitation(first, accept=False)
    elif state == "CANCELLED":
        services.cancel_invitation(first, actor=owner)
    elif state == "EXPIRED":
        JobInvitation.objects.filter(pk=first.pk).update(
            expires_at=timezone.now() - timedelta(hours=1)
        )
    used_before = _invites_used(employer)
    if blocks:
        with pytest.raises(services.AlreadyInvited):
            services.invite_candidate(employer, job, candidate, actor=owner)
        assert _invites_used(employer) == used_before  # refused duplicate charges nothing
        assert JobInvitation.objects.filter(job=job, job_seeker=candidate).count() == 1
        assert not services.JobApplication.objects.filter(job=job, job_seeker=candidate).exists()
    else:
        second = services.invite_candidate(employer, job, candidate, actor=owner)
        assert second.pk != first.pk and second.status == InvitationStatus.PENDING
        assert _invites_used(employer) == used_before + 1


def test_existing_application_still_blocks_an_invitation(employer, job_factory, seeker_factory):
    job, candidate = job_factory(employer), seeker_factory()
    services.apply_to_job(job, candidate)
    with pytest.raises(services.AlreadyApplied):
        services.invite_candidate(employer, job, candidate, actor=owner_of(employer))


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_invites_after_acceptance_create_no_second_live_invitation(
    employer_factory, job_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    job, candidate = job_factory(employer), seeker_factory()
    accepted = services.invite_candidate(employer, job, candidate, actor=owner)
    services.respond_to_invitation(accepted, accept=True)
    outcomes = _race(
        {
            f"invite{i}": (lambda: services.invite_candidate(employer, job, candidate, actor=owner))
            for i in range(2)
        }
    )
    assert set(outcomes.values()) == {"already_invited"}, outcomes
    assert JobInvitation.objects.filter(job=job, job_seeker=candidate).count() == 1
    assert _invites_used(employer) == 1
