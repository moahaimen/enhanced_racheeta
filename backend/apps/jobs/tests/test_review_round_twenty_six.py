"""Twenty-sixth Codex review of PR #4 (commit fe963f0): every employer-side
write re-reads the actor's membership under lock at commit time, and every
paid write resolves its entitlement on the locked billing account, which the
subscription lifecycle locks as well."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing import services as billing
from apps.billing.exceptions import EntitlementError, UsageLimitReached
from apps.billing.models import PlanEntitlement, Subscription, UsageEvent
from apps.billing.types import Audience, Keys, SubjectType, SubscriptionStatus
from apps.jobs import services
from apps.jobs.models import EmployerMembership, JobInvitation, JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import ApplicationStatus, JobStatus, MemberRole, MemberStatus, MessageSide

pytestmark = pytest.mark.django_db
JOBS = "/api/v1/jobs/employer/jobs"


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.fixture
def recruiter(employer, account_factory):
    acct = account_factory(role="PROVIDER")
    services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    return acct


@pytest.fixture
def viewer(employer, account_factory):
    acct = account_factory(role="PROVIDER")
    services.add_member(employer, acct, MemberRole.VIEWER, actor=owner_of(employer))
    return acct


def _end(employer, account):
    m = EmployerMembership.objects.get(
        employer=employer, account=account, status=MemberStatus.ACTIVE
    )
    services.end_membership(m, actor=owner_of(employer))


def _draft(employer, actor):
    return services.create_job(
        employer,
        {
            "title": "Nurse",
            "profession": "NURSE",
            "description": "Role",
            "governorate": employer.governorate,
            "employment_type": "FULL_TIME",
        },
        actor=actor,
    )


# ---- 2. membership revocation is authoritative at commit time ---------------------------


def _mutations(employer, job_factory, seeker_factory, actor):
    """Every employer-side write, prepared so that only the membership guard can refuse it."""
    published = job_factory(employer)
    draft = job_factory(employer, status=JobStatus.DRAFT)
    to_close = job_factory(employer)
    to_archive = job_factory(employer, status=JobStatus.CLOSED)
    candidate, invited = seeker_factory(), seeker_factory()
    application = services.apply_to_job(published, seeker_factory())
    invitation = services.invite_candidate(employer, published, invited, actor=owner_of(employer))
    future = timezone.now() + timedelta(days=2)
    return {
        "create_job": lambda: _draft(employer, actor),
        "edit_job": lambda: services.edit_job(draft, {"title": "Edited"}, actor=actor),
        "submit_job": lambda: services.submit_job_for_review(draft, actor=actor),
        "close_job": lambda: services.close_job(to_close, actor=actor),
        "archive_job": lambda: services.archive_job(to_archive, actor=actor),
        "feature_job": lambda: services.set_featured(published, True, actor=actor),
        "transition": lambda: services.transition_application(
            application, ApplicationStatus.REVIEWING, actor=actor
        ),
        "interview": lambda: services.request_interview(
            services.transition_application(
                application, ApplicationStatus.SHORTLISTED, actor=owner_of(employer)
            ),
            actor=actor,
            proposed_at=future,
            mode="ONLINE",
        ),
        "message": lambda: services.send_message(
            application, sender=actor, side=MessageSide.EMPLOYER, body="Hello"
        ),
        "invite": lambda: services.invite_candidate(employer, published, candidate, actor=actor),
        "save_candidate": lambda: services.save_candidate(employer, candidate, actor=actor),
        "cancel_invitation": lambda: services.cancel_invitation(invitation, actor=actor),
    }


MUTATIONS = [
    "create_job",
    "edit_job",
    "submit_job",
    "close_job",
    "archive_job",
    "feature_job",
    "transition",
    "interview",
    "message",
    "invite",
    "save_candidate",
    "cancel_invitation",
]


@pytest.mark.parametrize("name", MUTATIONS)
def test_an_active_recruiter_and_owner_can_perform_every_write(
    employer, recruiter, job_factory, seeker_factory, name
):
    _mutations(employer, job_factory, seeker_factory, recruiter)[name]()
    _mutations(employer, job_factory, seeker_factory, owner_of(employer))[name]()


@pytest.mark.parametrize("name", MUTATIONS)
def test_a_committed_revocation_refuses_every_write_with_a_typed_error(
    employer, recruiter, job_factory, seeker_factory, name
):
    """The recruiter's request read an ACTIVE membership; the owner ended it and
    committed before the write took its locks."""
    mutation = _mutations(employer, job_factory, seeker_factory, recruiter)[name]
    before = (JobPost.objects.count(), JobInvitation.objects.count())
    _end(employer, recruiter)
    with pytest.raises(services.MembershipInactive) as exc:
        mutation()
    assert exc.value.code == "membership_inactive"
    assert (JobPost.objects.count(), JobInvitation.objects.count()) == before


@pytest.mark.parametrize("name", ["create_job", "transition", "invite"])
def test_a_viewer_and_a_non_member_are_refused_at_the_guard(
    employer, viewer, account_factory, job_factory, seeker_factory, name
):
    for actor in (viewer, account_factory()):
        with pytest.raises(services.MembershipInactive):
            _mutations(employer, job_factory, seeker_factory, actor)[name]()


def test_the_api_refuses_a_stale_permission_membership(employer, recruiter, monkeypatch):
    """The permission layer still holds the ACTIVE membership object it loaded;
    the ended row in the database wins at commit time: typed 403, no job."""
    stale = EmployerMembership.objects.select_related("employer").get(
        employer=employer, account=recruiter
    )
    _end(employer, recruiter)
    # The permission class binds `membership_for` at import time: patch the name
    # it actually calls (and the services one), so the pre-check passes on the
    # stale object and only the service-level guard can refuse.
    from apps.jobs import permissions

    fake = lambda account: stale if account == recruiter else None  # noqa: E731
    monkeypatch.setattr(permissions, "membership_for", fake)
    monkeypatch.setattr(services, "membership_for", fake)
    resp = _client(recruiter).post(
        JOBS,
        {
            "title": "Nurse",
            "profession": "NURSE",
            "description": "Role",
            "governorate": str(employer.governorate_id),
            "employment_type": "FULL_TIME",
        },
        format="json",
    )
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "membership_inactive"
    assert not JobPost.objects.filter(title="Nurse", employer=employer).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_revocation_racing_a_write_never_commits_after_it(
    employer_factory, account_factory, job_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    recruiter = account_factory(role="PROVIDER")
    services.add_member(employer, recruiter, MemberRole.RECRUITER, actor=owner_of(employer))
    barrier = threading.Barrier(2)
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

    threads = [
        threading.Thread(target=run, args=("create", lambda: _draft(employer, recruiter))),
        threading.Thread(target=run, args=("revoke", lambda: _end(employer, recruiter))),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["revoke"] == "ok"
    assert outcomes["create"] in ("ok", "membership_inactive"), outcomes
    assert JobPost.objects.filter(employer=employer, created_by=recruiter).exists() == (
        outcomes["create"] == "ok"
    )
    assert (
        EmployerMembership.objects.get(employer=employer, account=recruiter).status
        == MemberStatus.ENDED
    )


# ---- 3. entitlement revocation is authoritative at commit time ---------------------------


def _billing(employer):
    return billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )


def _active_sub(employer):
    return Subscription.objects.get(
        billing_account=_billing(employer), status=SubscriptionStatus.ACTIVE
    )


def _invites_used(employer):
    return UsageEvent.objects.filter(
        billing_account=_billing(employer), key=Keys.TALENT_INVITE_LIMIT
    ).count()


def test_entitled_plan_invites_and_consumes_exactly_once(employer, job_factory, seeker_factory):
    services.invite_candidate(
        employer, job_factory(employer), seeker_factory(), actor=owner_of(employer)
    )
    assert _invites_used(employer) == 1


@pytest.mark.parametrize("how", ["suspend", "cancel", "trial"])
def test_a_revoked_or_unentitled_plan_cannot_invite(
    employer_factory, job_factory, seeker_factory, admin, how
):
    employer = employer_factory(plan_code=None if how == "trial" else "PROFESSIONAL")
    if how == "suspend":
        billing.suspend_subscription(_active_sub(employer), admin=admin, reason="late")
    elif how == "cancel":
        billing.cancel_subscription(_active_sub(employer), admin=admin, reason="closed")
    with pytest.raises(EntitlementError):
        services.invite_candidate(
            employer, job_factory(employer), seeker_factory(), actor=owner_of(employer)
        )
    assert not JobInvitation.objects.exists() and _invites_used(employer) == 0


def test_quota_exceeded_and_duplicates_are_unchanged(employer, job_factory, seeker_factory):
    PlanEntitlement.objects.filter(plan__code="PROFESSIONAL", key=Keys.TALENT_INVITE_LIMIT).update(
        limit=1
    )
    job, first = job_factory(employer), seeker_factory()
    services.invite_candidate(employer, job, first, actor=owner_of(employer))
    with pytest.raises(services.AlreadyInvited):
        services.invite_candidate(employer, job, first, actor=owner_of(employer))
    with pytest.raises(UsageLimitReached):
        services.invite_candidate(employer, job, seeker_factory(), actor=owner_of(employer))
    assert JobInvitation.objects.count() == 1 and _invites_used(employer) == 1


def test_a_pre_transaction_entitlement_observation_is_never_trusted(
    employer, job_factory, seeker_factory, admin
):
    observed = services.employer_entitlements(employer)
    assert observed.get(Keys.TALENT_INVITE).enabled is True  # what a request would have seen
    billing.suspend_subscription(
        _active_sub(employer), admin=admin, reason="late"
    )  # committed meanwhile
    with pytest.raises(EntitlementError):
        services.invite_candidate(
            employer, job_factory(employer), seeker_factory(), actor=owner_of(employer)
        )
    assert not JobInvitation.objects.exists() and _invites_used(employer) == 0


def test_an_invitation_that_took_the_billing_lock_first_completes_and_revocation_follows(
    employer, job_factory, seeker_factory, admin
):
    inv = services.invite_candidate(
        employer, job_factory(employer), seeker_factory(), actor=owner_of(employer)
    )
    billing.suspend_subscription(_active_sub(employer), admin=admin, reason="late")
    assert (
        Subscription.objects.get(pk=_billing(employer).subscriptions.first().pk).status
        == SubscriptionStatus.SUSPENDED
    )
    assert JobInvitation.objects.filter(pk=inv.pk).exists() and _invites_used(employer) == 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_suspension_racing_an_invitation_never_commits_after_it(
    employer_factory, job_factory, seeker_factory, admin
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job, candidate = job_factory(employer), seeker_factory()
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except EntitlementError:
            outcomes[name] = "entitlement"
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=run,
            args=(
                "invite",
                lambda: services.invite_candidate(
                    employer, job, candidate, actor=owner_of(employer)
                ),
            ),
        ),
        threading.Thread(
            target=run,
            args=(
                "suspend",
                lambda: billing.suspend_subscription(
                    _active_sub(employer), admin=admin, reason="late"
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["suspend"] == "ok" and outcomes["invite"] in ("ok", "entitlement"), outcomes
    created = JobInvitation.objects.filter(job=job, job_seeker=candidate).exists()
    assert created == (outcomes["invite"] == "ok")
    assert _invites_used(employer) == (1 if created else 0)
    assert (
        Subscription.objects.get(billing_account=_billing(employer)).status
        == SubscriptionStatus.SUSPENDED
    )
