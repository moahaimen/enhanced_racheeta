"""Regression tests for the third Codex review of PR #4 (commit d221abf):
withdrawal-reason leaks, invitation expiry before duplicate checks, safe
reactivation next to a pending request, and serialised application transitions."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.billing import services as billing
from apps.billing.models import Plan, Subscription, UsageEvent
from apps.billing.types import Audience, Keys, SubjectType, SubscriptionStatus
from apps.jobs import services
from apps.jobs.models import JobApplication, JobInvitation
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import ApplicationStatus, InvitationStatus

APPS = "/api/v1/jobs/me/applications"
LEAKS = [
    "person@example.com",
    "07701234567",
    "+964 770 123 4567",
    "https://example.com/me",
    "whatsapp 0770 123 45 67",
    "telegram @nurse_sara",
]


# ---- 1. withdrawal reasons ----------------------------------------------------


@pytest.mark.parametrize("leak", LEAKS)
def test_withdrawal_reason_rejects_contact_info(seeker_client, employer, job_factory, leak):
    app_id = seeker_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply").json()["id"]
    resp = seeker_client.post(f"{APPS}/{app_id}/withdraw", {"reason": f"found another job, {leak}"})
    assert resp.status_code == 400
    assert resp.json()["error"]["codes"]["reason"] == ["contact_information_not_allowed"]
    application = JobApplication.objects.get(pk=app_id)
    assert application.status == ApplicationStatus.SUBMITTED
    assert application.transitions.count() == 1  # nothing was recorded


def test_withdrawal_reason_accepts_ordinary_text_and_service_boundary_guards(
    seeker_client, seeker, employer, employer_client, job_factory
):
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    ok = seeker_client.post(f"{APPS}/{app_id}/withdraw", {"reason": "accepted an offer elsewhere"})
    assert ok.status_code == 200 and ok.json()["status"] == "WITHDRAWN"
    history = employer_client.get(f"/api/v1/jobs/employer/applications/{app_id}").json()[
        "transitions"
    ]
    assert [t["reason"] for t in history] == ["", "accepted an offer elsewhere"]
    # The service refuses leaks too, even when called without the serializer.
    other = JobApplication.objects.get(
        pk=seeker_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply").json()["id"]
    )
    with pytest.raises(services.ContactLeak):
        services.withdraw_application(other, actor=seeker.account, reason="call 07701234567")
    with pytest.raises(services.ContactLeak):
        services.transition_application(
            other, "REVIEWING", actor=owner_of(employer), reason="mail me a@b.io"
        )
    other.refresh_from_db()
    assert other.status == ApplicationStatus.SUBMITTED and other.transitions.count() == 1


def test_employer_transition_reason_rejects_contact_info(
    seeker_client, employer, employer_client, job_factory
):
    app_id = seeker_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply").json()["id"]
    resp = employer_client.post(
        f"/api/v1/jobs/employer/applications/{app_id}/transition",
        {"status": "REJECTED", "reason": "contact hr@example.com"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["codes"]["reason"] == ["contact_information_not_allowed"]


# ---- 2. invitation expiry ----------------------------------------------------


def _invite(employer, job, candidate):
    return services.invite_candidate(employer, job, candidate, actor=owner_of(employer))


def test_live_pending_invitation_blocks_duplicate(employer, job_factory, seeker_factory):
    job, candidate = job_factory(employer), seeker_factory()
    _invite(employer, job, candidate)
    with pytest.raises(services.AlreadyInvited):
        _invite(employer, job, candidate)


def test_expired_pending_invitation_is_normalised_and_reinvite_succeeds(
    employer, job_factory, seeker_factory
):
    job, candidate = job_factory(employer), seeker_factory()
    old = _invite(employer, job, candidate)
    JobInvitation.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(days=1))
    new = _invite(employer, job, candidate)
    old.refresh_from_db()
    assert old.status == InvitationStatus.EXPIRED and new.status == InvitationStatus.PENDING
    assert new.pk != old.pk
    assert JobInvitation.objects.filter(job=job, job_seeker=candidate).count() == 2  # history kept
    account = services.employer_entitlements(employer).billing_account
    refs = set(
        UsageEvent.objects.filter(
            billing_account=account, key=Keys.TALENT_INVITE_LIMIT
        ).values_list("reference", flat=True)
    )
    assert refs == {f"invite:{old.pk}", f"invite:{new.pk}"}  # fresh usage reference


def test_invitation_lists_normalise_expired_rows(api_client, employer, job_factory, seeker_factory):
    job, candidate = job_factory(employer), seeker_factory()
    inv = _invite(employer, job, candidate)
    JobInvitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(hours=1))
    api_client.force_authenticate(user=candidate.account)
    listed = api_client.get("/api/v1/jobs/me/invitations").json()["results"]
    assert [i["status"] for i in listed] == ["EXPIRED"]
    api_client.force_authenticate(user=owner_of(employer))
    assert [
        i["status"] for i in api_client.get("/api/v1/talent/invitations").json()["results"]
    ] == ["EXPIRED"]


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_invitations_cannot_create_two_live_rows(
    employer_factory, job_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job, candidate = job_factory(employer), seeker_factory()
    stale = _invite(employer, job, candidate)
    JobInvitation.objects.filter(pk=stale.pk).update(expires_at=timezone.now() - timedelta(days=1))
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt():
        try:
            barrier.wait(timeout=10)
            _invite(employer, job, candidate)
            outcomes.append("created")
        except services.AlreadyInvited:
            outcomes.append("duplicate")
        except Exception as exc:  # pragma: no cover
            outcomes.append(repr(exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == ["created", "duplicate"], outcomes
    live = JobInvitation.objects.filter(
        job=job, job_seeker=candidate, status=InvitationStatus.PENDING
    )
    assert live.count() == 1
    assert (
        services.employer_entitlements(employer).get(Keys.TALENT_INVITE_LIMIT).used == 2
    )  # stale + new, not three


# ---- 3. reactivation next to a pending request --------------------------------


@pytest.fixture
def trial_employer(employer_factory):
    return employer_factory()  # TRIAL: no subscription yet


@pytest.fixture
def billing_account(trial_employer):
    return billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, trial_employer.pk, Audience.EMPLOYER
    )


def _suspended(billing_account, admin, owner, code="BASIC"):
    sub = billing.request_subscription(
        billing_account, Plan.objects.get(code=code), requested_by=owner
    )
    billing.activate_subscription(sub, admin=admin, term_days=30)
    billing.suspend_subscription(sub, admin=admin, reason="late payment")
    return sub


def test_reactivate_suspended_only(trial_employer, billing_account, admin):
    sub = _suspended(billing_account, admin, owner_of(trial_employer))
    billing.activate_subscription(sub, admin=admin, note="paid")
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.ACTIVE


def test_reactivating_suspended_cancels_the_pending_request_deterministically(
    trial_employer, billing_account, admin, admin_client
):
    owner = owner_of(trial_employer)
    suspended = _suspended(billing_account, admin, owner)
    pending = billing.request_subscription(
        billing_account, Plan.objects.get(code="PROFESSIONAL"), requested_by=owner
    )
    resp = admin_client.post(
        f"/api/v1/admin/billing/subscriptions/{suspended.id}/activate", {"note": "settled"}
    )
    assert resp.status_code == 200, resp.content  # never a 500
    suspended.refresh_from_db()
    pending.refresh_from_db()
    assert suspended.status == SubscriptionStatus.ACTIVE
    assert pending.status == SubscriptionStatus.CANCELLED
    assert (
        Subscription.objects.filter(
            billing_account=billing_account,
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING],
        ).count()
        == 1
    )
    assert pending.events.filter(to_status=SubscriptionStatus.CANCELLED).exists()
    cancelled = AuditEvent.objects.filter(
        action="billing.subscription.cancelled", target_id=str(pending.pk)
    ).first()
    assert cancelled is not None and "superseded" in cancelled.summary
    assert AuditEvent.objects.filter(
        action="billing.subscription.activated", target_id=str(suspended.pk)
    ).exists()


def test_activation_of_a_row_that_is_no_longer_activatable_is_a_typed_error(
    trial_employer, billing_account, admin, admin_client
):
    sub = _suspended(billing_account, admin, owner_of(trial_employer))
    billing.cancel_subscription(sub, admin=admin, reason="closed")
    resp = admin_client.post(f"/api/v1/admin/billing/subscriptions/{sub.id}/activate")
    assert resp.status_code == 400
    assert "Cannot activate" in resp.json()["error"]["details"]["non_field_errors"][0]


# ---- 4. serialised application transitions ------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_accept_and_reject_cannot_both_win(
    employer_factory, job_factory, seeker_factory, account_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    recruiter = account_factory()
    services.add_member(employer, recruiter, "RECRUITER", actor=owner)
    job = job_factory(employer)
    application = services.apply_to_job(job, seeker_factory())
    services.transition_application(application, "SHORTLISTED", actor=owner)
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def act(to_status, actor):
        try:
            barrier.wait(timeout=10)
            fresh = JobApplication.objects.get(
                pk=application.pk
            )  # each side reads the same old state
            services.transition_application(fresh, to_status, actor=actor)
            outcomes[to_status] = "ok"
        except services.JobsError as exc:
            outcomes[to_status] = exc.code
        except Exception as exc:  # pragma: no cover
            outcomes[to_status] = repr(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=act, args=("ACCEPTED", owner)),
        threading.Thread(target=act, args=("REJECTED", recruiter)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes.values()) == ["invalid_transition", "ok"], outcomes
    application.refresh_from_db()
    winner = next(k for k, v in outcomes.items() if v == "ok")
    assert application.status == winner
    history = list(
        application.transitions.order_by("created_at").values_list("to_status", flat=True)
    )
    assert history == ["SUBMITTED", "SHORTLISTED", winner]  # exactly one final transition


def test_stale_transition_gets_a_typed_error_and_sequential_flow_still_works(
    employer, job_factory, seeker_factory
):
    owner = owner_of(employer)
    application = services.apply_to_job(job_factory(employer), seeker_factory())
    stale = JobApplication.objects.get(pk=application.pk)
    services.transition_application(application, "REVIEWING", actor=owner)
    services.transition_application(application, "SHORTLISTED", actor=owner)
    with pytest.raises(services.JobsError) as excinfo:
        services.transition_application(stale, "REVIEWING", actor=owner)  # thinks it is SUBMITTED
    assert excinfo.value.code == "invalid_transition"
    assert stale.status == "SHORTLISTED"  # refreshed under the lock, not overwritten
    services.transition_application(application, "ACCEPTED", actor=owner)
    application.refresh_from_db()
    assert application.status == "ACCEPTED"
    assert list(
        application.transitions.order_by("created_at").values_list("to_status", flat=True)
    ) == [
        "SUBMITTED",
        "REVIEWING",
        "SHORTLISTED",
        "ACCEPTED",
    ]


def test_interview_request_sees_the_committed_status(employer, job_factory, seeker_factory):
    owner = owner_of(employer)
    application = services.apply_to_job(job_factory(employer), seeker_factory())
    stale = JobApplication.objects.get(pk=application.pk)
    services.transition_application(application, "SHORTLISTED", actor=owner)
    services.transition_application(application, "REJECTED", actor=owner)
    with pytest.raises(services.JobsError):
        services.request_interview(
            stale,
            actor=owner,
            proposed_at=timezone.now() + timedelta(days=2),
            mode="IN_PERSON",
        )
    assert not application.interviews.exists()
