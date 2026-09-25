"""Regression tests for the sixteenth Codex review of PR #4 (commit eca49d0):
re-verification re-validates PUBLISHED jobs against the current identity, and
membership assignment is serialised on the target account row."""

import threading
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, connection

from apps.billing.exceptions import UsageLimitReached
from apps.jobs import services
from apps.jobs.models import EmployerMembership, JobPost, JobPostTransition
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus, MemberRole, MemberStatus, VerificationStatus

pytestmark = pytest.mark.django_db
VERIFY = "/api/v1/admin/recruitment/employers/{}/verification"


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


# ---- P2. employer re-verification re-validates published jobs ---------------------------


@pytest.fixture
def agency(employer_factory):
    return employer_factory(name="Agency", is_recruitment_agency=True, plan_code="PROFESSIONAL")


@pytest.fixture
def hiring_job(agency, employer_factory, job_factory):
    client_org = employer_factory(name="Client hospital")
    return job_factory(agency, title="Nurse via agency", hiring_employer=client_org)


@pytest.fixture
def plain_job(agency, job_factory):
    return job_factory(agency, title="Nurse at the agency itself")


def _unverify_and_drop_agency(agency, admin):
    services.set_employer_verification(agency, VerificationStatus.UNVERIFIED, admin=admin)
    services.update_employer(agency, {"is_recruitment_agency": False}, actor=owner_of(agency))
    agency.refresh_from_db()
    assert agency.is_recruitment_agency is False


def _public_ids(client):
    return {row["id"] for row in client.get("/api/v1/jobs").json()["results"]}


def test_reverification_suspends_the_job_that_no_longer_holds(
    agency, hiring_job, plain_job, admin, admin_client, seeker_client
):
    _unverify_and_drop_agency(agency, admin)
    assert _public_ids(seeker_client) == set()  # unverified: nothing public

    resp = admin_client.post(
        VERIFY.format(agency.pk), {"status": "VERIFIED", "note": "re-checked"}, format="json"
    )
    assert resp.status_code == 200, resp.content

    agency.refresh_from_db()
    hiring_job.refresh_from_db()
    plain_job.refresh_from_db()
    assert agency.verification_status == VerificationStatus.VERIFIED
    assert hiring_job.status == JobStatus.SUSPENDED
    assert "re-verification" in hiring_job.moderation_note
    assert hiring_job.hiring_employer_id is not None  # content untouched
    assert plain_job.status == JobStatus.PUBLISHED
    # public surfaces: the invalid job is hidden, the valid one is back
    assert _public_ids(seeker_client) == {str(plain_job.pk)}
    assert seeker_client.get(f"/api/v1/jobs/{hiring_job.pk}").status_code == 404
    assert seeker_client.get(f"/api/v1/jobs/{plain_job.pk}").status_code == 200
    # normal transition history with the actor and a reason
    t = JobPostTransition.objects.get(job=hiring_job, to_status=JobStatus.SUSPENDED)
    assert t.from_status == JobStatus.PUBLISHED and t.actor_id == admin.pk and t.reason


def test_unchanged_identity_reverifies_without_touching_jobs(agency, hiring_job, admin):
    services.set_employer_verification(agency, VerificationStatus.UNVERIFIED, admin=admin)
    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    hiring_job.refresh_from_db()
    assert hiring_job.status == JobStatus.PUBLISHED
    assert not JobPostTransition.objects.filter(job=hiring_job).exists()


def test_employer_without_jobs_verifies_normally(employer_factory, admin):
    org = employer_factory(verified=False)
    services.set_employer_verification(org, VerificationStatus.VERIFIED, admin=admin)
    org.refresh_from_db()
    assert org.verification_status == VerificationStatus.VERIFIED and org.verified_at


def test_non_published_jobs_are_left_alone(agency, employer_factory, job_factory, admin):
    client_org = employer_factory(name="Other client")
    draft = job_factory(agency, status=JobStatus.DRAFT, hiring_employer=client_org)
    pending = job_factory(agency, status=JobStatus.PENDING_ADMIN_REVIEW, hiring_employer=client_org)
    _unverify_and_drop_agency(agency, admin)
    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    draft.refresh_from_db()
    pending.refresh_from_db()
    assert draft.status == JobStatus.DRAFT and pending.status == JobStatus.PENDING_ADMIN_REVIEW
    # ...and the pending one still cannot be approved with its hiring fields
    with pytest.raises(services.HiringFieldsNotAllowed):
        services.approve_job(pending, admin=admin)


def test_several_invalid_jobs_are_handled_in_one_transaction(
    agency, employer_factory, job_factory, plain_job, admin, monkeypatch
):
    client_org = employer_factory(name="Client B")
    invalid = [job_factory(agency, hiring_employer=client_org) for _ in range(3)]
    _unverify_and_drop_agency(agency, admin)

    # Fail on the second suspension: nothing may commit (jobs, verification).
    real = services.audit.record
    seen = {"n": 0}

    def flaky(**kwargs):
        if kwargs.get("action") == "jobs.post.suspended":
            seen["n"] += 1
            if seen["n"] == 2:
                raise RuntimeError("boom")
        return real(**kwargs)

    monkeypatch.setattr(services.audit, "record", flaky)
    with pytest.raises(RuntimeError):
        services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    monkeypatch.setattr(services.audit, "record", real)
    agency.refresh_from_db()
    assert agency.verification_status == VerificationStatus.UNVERIFIED
    assert set(JobPost.objects.filter(employer=agency).values_list("status", flat=True)) == {
        JobStatus.PUBLISHED
    }
    assert not JobPostTransition.objects.filter(job__employer=agency).exists()

    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    statuses = dict(JobPost.objects.filter(employer=agency).values_list("pk", "status"))
    assert all(statuses[j.pk] == JobStatus.SUSPENDED for j in invalid)
    assert statuses[plain_job.pk] == JobStatus.PUBLISHED
    assert JobPostTransition.objects.filter(job__in=invalid).count() == 3


def test_restore_after_reverification_keeps_the_same_gate(agency, hiring_job, admin):
    _unverify_and_drop_agency(agency, admin)
    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)
    hiring_job.refresh_from_db()
    with pytest.raises(services.HiringFieldsNotAllowed):
        services.restore_job(hiring_job, admin=admin)
    hiring_job.hiring_employer = None
    hiring_job.save(update_fields=["hiring_employer"])
    services.restore_job(hiring_job, admin=admin)
    hiring_job.refresh_from_db()
    assert hiring_job.status == JobStatus.PUBLISHED


# ---- P2. membership assignment is serialised on the target account ----------------------


def test_add_member_still_works(employer, account_factory):
    acct = account_factory()
    m = services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    assert m.status == MemberStatus.ACTIVE and m.role == MemberRole.RECRUITER


@pytest.mark.parametrize("where", ["same", "other"])
def test_existing_membership_is_a_typed_error(employer, employer_factory, account_factory, where):
    acct = account_factory()
    first = employer if where == "same" else employer_factory(plan_code="PROFESSIONAL")
    services.add_member(first, acct, MemberRole.VIEWER, actor=owner_of(first))
    with pytest.raises(services.JobsError) as exc:
        services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    assert exc.value.code == "already_member"
    assert EmployerMembership.objects.filter(account=acct, status=MemberStatus.ACTIVE).count() == 1


def test_members_api_returns_409_not_500(employer_client, employer_factory, account_factory):
    acct = account_factory()
    other = employer_factory(plan_code="PROFESSIONAL")
    services.add_member(other, acct, MemberRole.VIEWER, actor=owner_of(other))
    resp = employer_client.post(
        "/api/v1/jobs/employer/members", {"email": acct.email, "role": "RECRUITER"}, format="json"
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "already_member"


def test_seat_limit_and_role_checks_are_preserved(employer_factory, account_factory):
    basic = employer_factory(plan_code="BASIC")  # 2 seats, the owner holds one
    services.add_member(basic, account_factory(), MemberRole.RECRUITER, actor=owner_of(basic))
    with pytest.raises(UsageLimitReached):
        services.add_member(basic, account_factory(), MemberRole.VIEWER, actor=owner_of(basic))
    with pytest.raises(services.JobsError) as exc:
        services.add_member(basic, account_factory(), MemberRole.OWNER, actor=owner_of(basic))
    assert exc.value.code == "invalid_role"


def test_ended_membership_frees_the_account(employer, employer_factory, account_factory):
    acct = account_factory()
    m = services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    services.end_membership(m, actor=owner_of(employer))
    other = employer_factory(plan_code="PROFESSIONAL")
    again = services.add_member(other, acct, MemberRole.VIEWER, actor=owner_of(other))
    assert again.employer_id == other.pk
    assert EmployerMembership.objects.filter(account=acct, status=MemberStatus.ACTIVE).count() == 1


class _BlindManager:
    """Hides the account's existing membership from the pre-insert check so the
    DB constraint is the one that fires."""

    def __init__(self, real, create=None):
        self._real, self._create = real, create

    def filter(self, **kwargs):
        if "account" in kwargs:
            return self._real.none()
        return self._real.filter(**kwargs)

    def create(self, **kwargs):
        if self._create:
            return self._create(**kwargs)
        return self._real.create(**kwargs)


def test_constraint_violation_maps_to_already_member(
    employer, employer_factory, account_factory, monkeypatch
):
    acct = account_factory()
    other = employer_factory(plan_code="PROFESSIONAL")
    services.add_member(other, acct, MemberRole.VIEWER, actor=owner_of(other))
    monkeypatch.setattr(
        services,
        "EmployerMembership",
        SimpleNamespace(objects=_BlindManager(EmployerMembership.objects)),
    )
    with pytest.raises(services.JobsError) as exc:
        services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    assert exc.value.code == "already_member"
    assert EmployerMembership.objects.filter(account=acct).count() == 1


def test_other_integrity_errors_are_not_swallowed(employer, account_factory, monkeypatch):
    def broken(**kwargs):
        raise IntegrityError("some other constraint")

    monkeypatch.setattr(
        services,
        "EmployerMembership",
        SimpleNamespace(objects=_BlindManager(EmployerMembership.objects, create=broken)),
    )
    with pytest.raises(IntegrityError):
        services.add_member(
            employer, account_factory(), MemberRole.RECRUITER, actor=owner_of(employer)
        )


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_employers_adding_the_same_account_concurrently(employer_factory, account_factory):
    one = employer_factory(plan_code="PROFESSIONAL")
    two = employer_factory(plan_code="PROFESSIONAL")
    acct = account_factory()
    outcomes = _race(
        {
            "one": lambda: services.add_member(
                one, acct, MemberRole.RECRUITER, actor=owner_of(one)
            ),
            "two": lambda: services.add_member(two, acct, MemberRole.VIEWER, actor=owner_of(two)),
        }
    )
    assert sorted(outcomes.values()) == ["already_member", "ok"], outcomes
    live = EmployerMembership.objects.filter(account=acct, status=MemberStatus.ACTIVE)
    assert live.count() == 1
    winner = one if outcomes["one"] == "ok" else two
    loser = two if winner is one else one
    assert live.get().employer_id == winner.pk
    assert not EmployerMembership.objects.filter(account=acct, employer=loser).exists()
    # seat accounting on both sides reflects exactly what committed
    assert (
        EmployerMembership.objects.filter(employer=winner, status=MemberStatus.ACTIVE).count() == 2
    )
    assert (
        EmployerMembership.objects.filter(employer=loser, status=MemberStatus.ACTIVE).count() == 1
    )
