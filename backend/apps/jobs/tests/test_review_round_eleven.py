"""Regression tests for the eleventh Codex review of PR #4 (commit fe0e3ee):
approval shares the publication gate, deadline rule, authoritative active-slot
capacity, and eager-loaded job-card relations."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.exceptions import UsageLimitReached
from apps.billing.models import PlanEntitlement
from apps.billing.types import Audience, Keys, SubjectType
from apps.jobs import services
from apps.jobs.models import JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus, VerificationStatus

ADMIN = "/api/v1/admin/recruitment/jobs"
JOBS = "/api/v1/jobs/employer/jobs"
TODAY = timezone.localdate()


def _pending(employer, job_factory, **fields):
    return job_factory(employer, status=JobStatus.PENDING_ADMIN_REVIEW, **fields)


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


# ---- 1. approval re-runs the publication gate ------------------------------------


def test_eligible_pending_job_is_approved(admin_client, employer, job_factory):
    job = _pending(employer, job_factory)
    resp = admin_client.post(f"{ADMIN}/{job.id}/approve", {"note": "ok"})
    assert resp.status_code == 200 and resp.json()["status"] == "PUBLISHED"
    assert list(job.transitions.values_list("to_status", flat=True)) == ["PUBLISHED"]


@pytest.mark.parametrize(
    "how,code",
    [
        ("recruitment", "organization_not_verified"),
        ("verification", "organization_not_verified"),
        ("unverified", "organization_not_verified"),
        ("plan_lapsed", "entitlement_required"),
        ("no_jobs_post", "entitlement_required"),
        ("limit_reduced", "usage_limit_reached"),
        ("former_agency", "not_an_agency"),
    ],
)
def test_approval_refused_when_the_organisation_is_no_longer_eligible(
    admin_client, employer_factory, job_factory, admin, how, code
):
    org = employer_factory(
        plan_code="PROFESSIONAL",
        is_recruitment_agency=(how == "former_agency"),
        organization_type="RECRUITMENT_AGENCY" if how == "former_agency" else "HOSPITAL",
    )
    job = _pending(
        org,
        job_factory,
        hiring_organization_name="Karrada clinic" if how == "former_agency" else "",
    )
    if how == "recruitment":
        services.set_employer_recruitment_status(org, "SUSPENDED", admin=admin, reason="x")
    elif how == "verification":
        services.set_employer_verification(org, VerificationStatus.SUSPENDED, admin=admin)
    elif how == "unverified":
        services.set_employer_verification(org, VerificationStatus.UNVERIFIED, admin=admin)
    elif how == "plan_lapsed":
        account = billing.get_or_create_billing_account(
            SubjectType.ORGANIZATION, org.pk, Audience.EMPLOYER
        )
        sub = account.subscriptions.get(status="ACTIVE")
        sub.ends_at = timezone.now() - timedelta(days=1)
        sub.save(update_fields=["ends_at"])
        PlanEntitlement.objects.filter(plan__code="TRIAL", key=Keys.JOBS_POST).update(enabled=False)
    elif how == "no_jobs_post":
        PlanEntitlement.objects.filter(plan__code="PROFESSIONAL", key=Keys.JOBS_POST).update(
            enabled=False
        )
    elif how == "limit_reduced":
        job_factory(org, status=JobStatus.PUBLISHED)
        PlanEntitlement.objects.filter(
            plan__code="PROFESSIONAL", key=Keys.JOBS_ACTIVE_LIMIT
        ).update(limit=1)
    else:
        services.Employer.objects.filter(pk=org.pk).update(is_recruitment_agency=False)
    resp = admin_client.post(f"{ADMIN}/{job.id}/approve")
    assert resp.status_code in (400, 403), (how, resp.content)
    assert resp.json()["error"]["code"] == code, how
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING_ADMIN_REVIEW and job.published_at is None
    assert not job.transitions.filter(to_status=JobStatus.PUBLISHED).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_approve_races_employer_suspension(employer_factory, job_factory, admin):
    org = employer_factory(plan_code="PROFESSIONAL")
    job = _pending(org, job_factory)
    outcomes = _race(
        {
            "approve": lambda: services.approve_job(JobPost.objects.get(pk=job.pk), admin=admin),
            "suspend": lambda: services.set_employer_recruitment_status(
                services.Employer.objects.get(pk=org.pk), "SUSPENDED", admin=admin
            ),
        }
    )
    assert outcomes["suspend"] == "ok", outcomes
    job.refresh_from_db()
    if outcomes["approve"] == "ok":
        assert job.status == JobStatus.PUBLISHED
        assert list(job.transitions.values_list("to_status", flat=True)) == ["PUBLISHED"]
    else:
        assert outcomes["approve"] == "organization_not_verified", outcomes
        assert job.status == JobStatus.PENDING_ADMIN_REVIEW and not job.transitions.exists()


# ---- 2. deadline rule --------------------------------------------------------------


@pytest.mark.parametrize("delta,ok", [(7, True), (0, True), (-1, False)])
def test_approval_and_the_deadline_boundary(admin_client, employer, job_factory, delta, ok):
    job = _pending(employer, job_factory, application_deadline=TODAY + timedelta(days=delta))
    resp = admin_client.post(f"{ADMIN}/{job.id}/approve")
    job.refresh_from_db()
    if ok:
        assert resp.status_code == 200 and job.status == JobStatus.PUBLISHED
    else:
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "deadline_passed"
        assert job.status == JobStatus.PENDING_ADMIN_REVIEW
        assert not job.transitions.filter(to_status=JobStatus.PUBLISHED).exists()
        assert job.application_deadline == TODAY - timedelta(days=1)  # never rewritten


def test_restore_and_submit_refuse_a_passed_deadline(
    admin_client, employer_client, employer, job_factory
):
    suspended = job_factory(
        employer, status=JobStatus.SUSPENDED, application_deadline=TODAY - timedelta(days=1)
    )
    resp = admin_client.post(f"{ADMIN}/{suspended.id}/restore")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "deadline_passed"
    draft = job_factory(
        employer, status=JobStatus.DRAFT, application_deadline=TODAY - timedelta(days=1)
    )
    resp = employer_client.post(f"{JOBS}/{draft.id}/submit")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "deadline_passed"
    for job in (suspended, draft):
        job.refresh_from_db()
        assert not job.transitions.exists()
    # Fixing the deadline (write validation still requires >= today) unblocks the draft.
    fixed = employer_client.patch(
        f"{JOBS}/{draft.id}", {"application_deadline": str(TODAY + timedelta(days=3))}
    )
    assert fixed.status_code == 200
    assert employer_client.post(f"{JOBS}/{draft.id}/submit").status_code == 200


# ---- 3. authoritative active-slot capacity -------------------------------------------


def test_overdue_published_job_does_not_consume_capacity(
    employer_factory, job_factory, employer_client
):
    trial = employer_factory()  # one slot
    overdue = job_factory(
        trial, status=JobStatus.PUBLISHED, application_deadline=TODAY - timedelta(days=2)
    )
    assert overdue.status == JobStatus.PUBLISHED  # no listing has run
    draft = job_factory(trial, status=JobStatus.DRAFT)
    submitted = services.submit_job_for_review(draft, actor=owner_of(trial))
    assert submitted.status == JobStatus.PENDING_ADMIN_REVIEW
    overdue.refresh_from_db()
    assert overdue.status == JobStatus.EXPIRED  # normalised under the employer lock
    assert list(overdue.transitions.values_list("to_status", flat=True)) == ["EXPIRED"]


def test_fresh_published_job_still_consumes_a_slot(employer_factory, job_factory):
    trial = employer_factory()
    job_factory(trial, status=JobStatus.PUBLISHED, application_deadline=TODAY + timedelta(days=5))
    with pytest.raises(UsageLimitReached):
        services.submit_job_for_review(
            job_factory(trial, status=JobStatus.DRAFT), actor=owner_of(trial)
        )


def test_approve_and_restore_use_the_same_capacity_semantics(
    admin_client, employer_factory, job_factory
):
    trial = employer_factory()
    overdue = job_factory(
        trial, status=JobStatus.PUBLISHED, application_deadline=TODAY - timedelta(days=1)
    )
    pending = _pending(trial, job_factory)
    assert admin_client.post(f"{ADMIN}/{pending.id}/approve").status_code == 200
    overdue.refresh_from_db()
    assert overdue.status == JobStatus.EXPIRED
    # The approved job now really occupies the slot: a restore of another job is refused.
    other = job_factory(trial, status=JobStatus.SUSPENDED)
    resp = admin_client.post(f"{ADMIN}/{other.id}/restore")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "usage_limit_reached"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_capacity_checks_expire_an_overdue_job_once(employer_factory, job_factory):
    org = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(org)
    overdue = job_factory(
        org, status=JobStatus.PUBLISHED, application_deadline=TODAY - timedelta(days=1)
    )
    drafts = [job_factory(org, status=JobStatus.DRAFT) for _ in range(2)]

    def submit(draft):
        return lambda: services.submit_job_for_review(JobPost.objects.get(pk=draft.pk), actor=owner)

    outcomes = _race({"submit0": submit(drafts[0]), "submit1": submit(drafts[1])})
    assert set(outcomes.values()) == {"ok"}, outcomes
    overdue.refresh_from_db()
    assert overdue.status == JobStatus.EXPIRED
    assert list(overdue.transitions.values_list("to_status", flat=True)) == ["EXPIRED"]


# ---- 4. eager-loaded job cards -----------------------------------------------------


def test_job_cards_with_facilities_and_agency_jobs_have_bounded_queries(
    api_client, employer_factory, provider_factory, job_factory, django_assert_max_num_queries
):
    facility = provider_factory(provider_type="HOSPITAL")
    hospital = employer_factory(plan_code="PROFESSIONAL", provider_profile=facility)
    agency = employer_factory(
        plan_code="PROFESSIONAL", is_recruitment_agency=True, organization_type="RECRUITMENT_AGENCY"
    )
    for i in range(10):
        job_factory(hospital, title=f"Hospital job {i}")
        job_factory(agency, title=f"Agency job {i}", hiring_employer=hospital)
    with django_assert_max_num_queries(4):
        page = api_client.get("/api/v1/jobs", {"page_size": 20}).json()
    assert page["count"] == 20
    assert {
        r["hiring_employer"]["provider_profile_id"] for r in page["results"] if r["hiring_employer"]
    } == {str(facility.id)}


def test_query_count_does_not_grow_with_page_size(
    api_client, employer_factory, provider_factory, job_factory, django_assert_num_queries
):
    facility = provider_factory(provider_type="HOSPITAL")
    hospital = employer_factory(plan_code="BUSINESS", provider_profile=facility)
    for i in range(30):
        job_factory(hospital, title=f"Job {i}")

    def queries_for(size):
        from django.db import connection as conn
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(conn) as ctx:
            assert api_client.get("/api/v1/jobs", {"page_size": size}).status_code == 200
        return len(ctx.captured_queries)

    assert queries_for(5) == queries_for(30)
    assert queries_for(30) <= 4
