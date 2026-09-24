"""Regression tests for the PR #4 review findings: quota idempotency per
application attempt, serialised active-job slots, restore re-check, featured
expiry, and the analogous invitation/seat rules."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.billing.exceptions import UsageLimitReached
from apps.billing.models import PlanEntitlement, UsageCounter, UsageEvent
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import JobApplication, JobInvitation, JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import InvitationStatus, JobStatus

APPS = "/api/v1/jobs/me/applications"
JOBS = "/api/v1/jobs/employer/jobs"
ADMIN = "/api/v1/admin/recruitment/jobs"


def _seeker_usage(seeker):
    account = services.seeker_entitlements(seeker).billing_account
    used = sum(
        UsageCounter.objects.filter(
            billing_account=account, key=Keys.APPLICATIONS_LIMIT
        ).values_list("used", flat=True)
    )
    events = list(
        UsageEvent.objects.filter(billing_account=account, key=Keys.APPLICATIONS_LIMIT)
        .order_by("created_at")
        .values_list("reference", flat=True)
    )
    return used, events


# ---- 1. application quota idempotency ---------------------------------------


def test_initial_application_consumes_one_unit(seeker_client, seeker, employer, job_factory):
    job = job_factory(employer)
    created = seeker_client.post(f"/api/v1/jobs/{job.id}/apply")
    assert created.status_code == 201
    used, events = _seeker_usage(seeker)
    assert used == 1 and events == [f"apply:{created.json()['id']}"]


def test_duplicate_http_retry_does_not_double_consume(seeker_client, seeker, employer, job_factory):
    job = job_factory(employer)
    assert seeker_client.post(f"/api/v1/jobs/{job.id}/apply").status_code == 201
    retry = seeker_client.post(f"/api/v1/jobs/{job.id}/apply")
    assert retry.status_code == 409 and retry.json()["error"]["code"] == "already_applied"
    used, events = _seeker_usage(seeker)
    assert used == 1 and len(events) == 1


def test_withdraw_then_reapply_consumes_a_new_unit(seeker_client, seeker, employer, job_factory):
    job = job_factory(employer)
    first = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()
    assert seeker_client.post(f"{APPS}/{first['id']}/withdraw").status_code == 200
    second = seeker_client.post(f"/api/v1/jobs/{job.id}/apply")
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    used, events = _seeker_usage(seeker)
    assert used == 2
    assert events == [f"apply:{first['id']}", f"apply:{second.json()['id']}"]
    assert JobApplication.objects.filter(job=job, job_seeker=seeker).count() == 2


def test_reapply_in_a_later_period_uses_a_fresh_usage_event(
    seeker_client, seeker, employer, job_factory
):
    job = job_factory(employer)
    first = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()
    account = services.seeker_entitlements(seeker).billing_account
    # Pretend the first application happened last month.
    previous_period = (timezone.localdate().replace(day=1) - timedelta(days=1)).replace(day=1)
    UsageCounter.objects.filter(billing_account=account, key=Keys.APPLICATIONS_LIMIT).update(
        period_start=previous_period
    )
    seeker_client.post(f"{APPS}/{first['id']}/withdraw")
    second = seeker_client.post(f"/api/v1/jobs/{job.id}/apply")
    assert second.status_code == 201
    counters = dict(
        UsageCounter.objects.filter(
            billing_account=account, key=Keys.APPLICATIONS_LIMIT
        ).values_list("period_start", "used")
    )
    assert counters[previous_period] == 1
    assert sum(v for k, v in counters.items() if k != previous_period) == 1
    assert UsageEvent.objects.filter(billing_account=account).count() == 2


def test_application_limit_counts_attempts_not_jobs(seeker_client, seeker, employer, job_factory):
    PlanEntitlement.objects.filter(plan__code="SEEKER_FREE", key=Keys.APPLICATIONS_LIMIT).update(
        limit=2
    )
    job = job_factory(employer)
    first = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()
    seeker_client.post(f"{APPS}/{first['id']}/withdraw")
    second = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()
    seeker_client.post(f"{APPS}/{second['id']}/withdraw")
    blocked = seeker_client.post(f"/api/v1/jobs/{job.id}/apply")
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "usage_limit_reached"


# ---- 2. concurrent active-job limit -----------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_submissions_cannot_exceed_active_limit(employer_factory, job_factory):
    trial = employer_factory()  # TRIAL: one active job
    owner = owner_of(trial)
    drafts = [job_factory(trial, status=JobStatus.DRAFT) for _ in range(2)]
    barrier = threading.Barrier(2)
    outcomes: dict = {}

    def submit(job):
        try:
            barrier.wait(timeout=10)
            services.submit_job_for_review(job, actor=owner)
            outcomes[job.pk] = "submitted"
        except UsageLimitReached:
            outcomes[job.pk] = "limit"
        except Exception as exc:  # pragma: no cover - surfaced by the assertion below
            outcomes[job.pk] = repr(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=submit, args=(job,)) for job in drafts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes.values()) == ["limit", "submitted"], outcomes
    assert (
        JobPost.objects.filter(employer=trial, status__in=services.ACTIVE_JOB_STATUSES).count() == 1
    )


def test_submission_gate_runs_under_the_employer_row_lock(employer, job_factory, monkeypatch):
    """Deterministic complement to the threaded test: the lock is taken before
    the slot count and both happen inside one transaction."""
    calls: list[str] = []
    real_lock, real_count = services._lock_employer, services._active_job_count
    monkeypatch.setattr(
        services, "_lock_employer", lambda e: (calls.append("lock"), real_lock(e))[1]
    )
    monkeypatch.setattr(
        services,
        "_active_job_count",
        lambda e, **kw: (calls.append("count"), real_count(e, **kw))[1],
    )
    services.submit_job_for_review(
        job_factory(employer, status=JobStatus.DRAFT), actor=owner_of(employer)
    )
    assert calls == ["lock", "count"]


# ---- 3. restore re-checks the active limit ----------------------------------


def test_restore_rechecks_active_limit(api_client, employer_factory, job_factory, admin_client):
    trial = employer_factory()  # limit 1
    suspended = job_factory(trial, status=JobStatus.SUSPENDED)
    other = job_factory(trial, status=JobStatus.PUBLISHED)  # took the freed slot meanwhile
    denied = admin_client.post(f"{ADMIN}/{suspended.id}/restore", {"note": "looks fine"})
    assert denied.status_code == 403, denied.content
    body = denied.json()["error"]
    assert body["code"] == "usage_limit_reached" and body["meta"]["key"] == Keys.JOBS_ACTIVE_LIMIT
    suspended.refresh_from_db()
    assert suspended.status == JobStatus.SUSPENDED
    # Freeing the slot makes the restore succeed and keeps the audit trail.
    api_client.force_authenticate(user=owner_of(trial))
    assert api_client.post(f"{JOBS}/{other.id}/close").status_code == 200
    restored = admin_client.post(f"{ADMIN}/{suspended.id}/restore", {"note": "looks fine"})
    assert restored.status_code == 200 and restored.json()["status"] == "PUBLISHED"
    assert restored.json()["transitions"][-1]["to_status"] == "PUBLISHED"
    audit = admin_client.get("/api/v1/admin/audit", {"action": "jobs.post.restored"}).json()
    assert audit["count"] == 1


# ---- 4. featured expiry -----------------------------------------------------


def _feature(job, *, days=30):
    services.set_featured(job, True, actor=owner_of(job.employer), days=days)
    return job


def test_active_featured_job_is_featured(employer, job_factory, api_client):
    job = _feature(job_factory(employer))
    assert job.is_actively_featured
    card = api_client.get("/api/v1/jobs").json()["results"][0]
    assert card["is_featured"] is True


def test_expired_featured_window_serialises_as_not_featured(employer, job_factory, api_client):
    job = _feature(job_factory(employer))
    JobPost.objects.filter(pk=job.pk).update(featured_until=timezone.now() - timedelta(minutes=1))
    job.refresh_from_db()
    assert job.is_featured is True and not job.is_actively_featured  # stale flag, rule wins
    card = api_client.get("/api/v1/jobs").json()["results"][0]
    assert card["is_featured"] is False
    job.refresh_from_db()
    assert job.is_featured is False and job.featured_until is None  # normalised at read time


def test_ordering_after_featured_expiration(employer, job_factory, api_client):
    now = timezone.now()
    stale = _feature(
        job_factory(employer, title="Stale featured", published_at=now - timedelta(days=3))
    )
    JobPost.objects.filter(pk=stale.pk).update(featured_until=now - timedelta(days=1))
    newer = job_factory(employer, title="Newer plain", published_at=now - timedelta(days=1))
    live = _feature(
        job_factory(employer, title="Live featured", published_at=now - timedelta(days=5))
    )
    titles = [j["title"] for j in api_client.get("/api/v1/jobs").json()["results"]]
    assert titles == [live.title, newer.title, stale.title]


def test_featured_slot_is_reusable_after_expiration(employer, job_factory):
    # PROFESSIONAL: two featured slots.
    first, second, third = (job_factory(employer) for _ in range(3))
    _feature(first)
    _feature(second)
    with pytest.raises(UsageLimitReached):
        _feature(third)
    JobPost.objects.filter(pk=first.pk).update(featured_until=timezone.now() - timedelta(seconds=1))
    _feature(third)  # the expired window no longer occupies a slot
    third.refresh_from_db()
    assert third.is_actively_featured
    first.refresh_from_db()
    assert first.is_featured is False


# ---- analogous rules found in the audit -------------------------------------


def test_reinviting_after_cancellation_consumes_a_new_unit(employer, job_factory, seeker_factory):
    job = job_factory(employer)
    candidate = seeker_factory()
    owner = owner_of(employer)
    first = services.invite_candidate(employer, job, candidate, actor=owner)
    with pytest.raises(services.AlreadyInvited):
        services.invite_candidate(employer, job, candidate, actor=owner)
    services.cancel_invitation(first, actor=owner)
    second = services.invite_candidate(employer, job, candidate, actor=owner)
    assert first.status == InvitationStatus.CANCELLED and second.pk != first.pk
    assert JobInvitation.objects.filter(job=job, job_seeker=candidate).count() == 2
    account = services.employer_entitlements(employer).billing_account
    refs = list(
        UsageEvent.objects.filter(billing_account=account, key=Keys.TALENT_INVITE_LIMIT)
        .order_by("created_at")
        .values_list("reference", flat=True)
    )
    assert refs == [f"invite:{first.pk}", f"invite:{second.pk}"]
    assert services.employer_entitlements(employer).get(Keys.TALENT_INVITE_LIMIT).used == 2
