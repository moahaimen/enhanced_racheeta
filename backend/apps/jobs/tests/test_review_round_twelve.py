"""Regression tests for the twelfth Codex review of PR #4 (commit 0dddd00):
activation refuses retired plans, decision notes fit the transition column,
messages are serialised with application closure, and public job detail
follows the same deadline rule as public search."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.models import PaymentRecord, Plan
from apps.billing.types import Audience, SubjectType, SubscriptionStatus
from apps.jobs import services
from apps.jobs.models import JobApplication, RecruitmentMessage
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus

ADMIN = "/api/v1/admin/recruitment/jobs"
SUBS = "/api/v1/admin/billing/subscriptions"
TODAY = timezone.localdate()


def _race(actions):
    barrier = threading.Barrier(len(actions))
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except (services.JobsError, billing.SubscriptionError) as exc:
            outcomes[name] = getattr(exc, "code", type(exc).__name__)
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


# ---- 1. plan must still be active at activation -----------------------------------


@pytest.fixture
def pending_request(employer_factory):
    org = employer_factory()
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, org.pk, Audience.EMPLOYER
    )
    sub = billing.request_subscription(
        account, Plan.objects.get(code="BASIC"), requested_by=owner_of(org)
    )
    return org, account, sub


def test_pending_request_with_active_plan_activates(admin_client, pending_request):
    _, _, sub = pending_request
    resp = admin_client.post(f"{SUBS}/{sub.id}/activate", {"reference": "TRX-1"}, format="json")
    assert resp.status_code == 200 and resp.json()["status"] == "ACTIVE"


def test_plan_deactivated_after_request_blocks_activation(admin_client, pending_request, admin):
    org, account, sub = pending_request
    Plan.objects.filter(code="BASIC").update(is_active=False)
    resp = admin_client.post(
        f"{SUBS}/{sub.id}/activate",
        {
            "reference": "TRX-2",
            "payment": {"amount": "100000", "method": "CASH", "reference": "TRX-2"},
        },
        format="json",
    )
    assert resp.status_code == 400, resp.content
    assert "no longer available" in resp.json()["error"]["details"]["non_field_errors"][0]
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.PENDING and sub.activated_by is None
    assert not sub.events.filter(to_status=SubscriptionStatus.ACTIVE).exists()
    assert not PaymentRecord.objects.filter(subscription=sub).exists()
    # Entitlements keep ignoring the retired plan and resolve the default.
    ent = billing.EntitlementService(account)
    assert ent.subscription is None and ent.plan.code == "TRIAL"


def test_suspended_subscription_with_retired_plan_cannot_be_reactivated(pending_request, admin):
    _, _, sub = pending_request
    billing.activate_subscription(sub, admin=admin, term_days=30)
    billing.suspend_subscription(sub, admin=admin, reason="late payment")
    Plan.objects.filter(code="BASIC").update(is_active=False)
    with pytest.raises(billing.SubscriptionError):
        billing.activate_subscription(sub, admin=admin, note="paid")
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.SUSPENDED
    assert sub.events.filter(to_status=SubscriptionStatus.ACTIVE).count() == 1  # only the first


def test_entitlements_ignore_an_inactive_subscribed_plan(pending_request, admin):
    _, account, sub = pending_request
    billing.activate_subscription(sub, admin=admin, term_days=30)
    Plan.objects.filter(code="BASIC").update(is_active=False)
    ent = billing.EntitlementService(account)
    assert ent.subscription is not None and ent.plan.code == "TRIAL"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_activation_races_plan_deactivation(employer_factory, admin):
    org = employer_factory()
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, org.pk, Audience.EMPLOYER
    )
    sub = billing.request_subscription(
        account, Plan.objects.get(code="BASIC"), requested_by=owner_of(org)
    )

    def deactivate():
        from django.db import transaction

        with transaction.atomic():
            plan = Plan.objects.select_for_update().get(code="BASIC")
            plan.is_active = False
            plan.save(update_fields=["is_active"])

    outcomes = _race(
        {
            "activate": lambda: billing.activate_subscription(
                billing.Subscription.objects.get(pk=sub.pk), admin=admin, term_days=30
            ),
            "deactivate": deactivate,
        }
    )
    assert outcomes["deactivate"] == "ok", outcomes
    sub.refresh_from_db()
    if outcomes["activate"] == "ok":
        assert sub.status == SubscriptionStatus.ACTIVE  # activated before the plan was retired
    else:
        assert outcomes["activate"] == "SubscriptionError"
        assert sub.status == SubscriptionStatus.PENDING
        assert not sub.events.filter(to_status=SubscriptionStatus.ACTIVE).exists()


# ---- 2. decision notes fit the transition column ------------------------------------


@pytest.mark.parametrize(
    "action,status,field",
    [
        ("approve", JobStatus.PENDING_ADMIN_REVIEW, "note"),
        ("restore", JobStatus.SUSPENDED, "note"),
        ("reject", JobStatus.PENDING_ADMIN_REVIEW, "reason"),
        ("suspend", JobStatus.PUBLISHED, "reason"),
    ],
)
def test_decision_text_is_bounded_by_the_transition_column(
    admin_client, employer, job_factory, action, status, field
):
    job = job_factory(employer, status=status)
    too_long = admin_client.post(f"{ADMIN}/{job.id}/{action}", {field: "x" * 501}, format="json")
    assert too_long.status_code == 400, too_long.content
    assert field in too_long.json()["error"]["details"]
    job.refresh_from_db()
    assert job.status == status and not job.transitions.exists()
    ok = admin_client.post(f"{ADMIN}/{job.id}/{action}", {field: "y" * 500}, format="json")
    assert ok.status_code == 200, ok.content
    assert job.transitions.get().reason == "y" * 500


# ---- 3. messages vs application closure ---------------------------------------------


def _application(seeker_client, employer, job_factory):
    return JobApplication.objects.get(
        pk=seeker_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply").json()["id"]
    )


def test_message_on_open_application_and_after_closure(
    seeker_client, seeker, employer, employer_client, job_factory
):
    application = _application(seeker_client, employer, job_factory)
    url = f"/api/v1/recruitment/applications/{application.id}/messages"
    assert employer_client.post(url, {"body": "hello"}).status_code == 201
    services.transition_application(application, "REJECTED", actor=owner_of(employer))
    closed = seeker_client.post(url, {"body": "one more thing"})
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "application_closed"
    other = _application(seeker_client, employer, job_factory)
    services.withdraw_application(other, actor=seeker.account)
    withdrawn = employer_client.post(
        f"/api/v1/recruitment/applications/{other.id}/messages", {"body": "still there?"}
    )
    assert (
        withdrawn.status_code == 409 and withdrawn.json()["error"]["code"] == "application_closed"
    )
    assert [m.body for m in RecruitmentMessage.objects.filter(application=application)] == ["hello"]
    assert not RecruitmentMessage.objects.filter(application=other).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("closer", ["reject", "withdraw"])
def test_message_races_closure(employer_factory, job_factory, seeker_factory, closer):
    employer = employer_factory(plan_code="PROFESSIONAL")
    owner = owner_of(employer)
    candidate = seeker_factory()
    application = services.apply_to_job(job_factory(employer), candidate)
    stale = JobApplication.objects.get(pk=application.pk)  # SUBMITTED when loaded

    def close():
        target = JobApplication.objects.get(pk=application.pk)
        if closer == "reject":
            services.transition_application(target, "REJECTED", actor=owner)
        else:
            services.withdraw_application(target, actor=candidate.account)

    outcomes = _race(
        {
            "message": lambda: services.send_message(
                stale, sender=owner, side="EMPLOYER", body="are you available?"
            ),
            "close": close,
        }
    )
    assert outcomes["close"] == "ok", outcomes
    application.refresh_from_db()
    assert application.status == ("REJECTED" if closer == "reject" else "WITHDRAWN")
    messages = list(RecruitmentMessage.objects.filter(application=application))
    if outcomes["message"] == "ok":  # sent before the closure committed
        assert len(messages) == 1
    else:
        assert outcomes["message"] == "application_closed", outcomes
        assert messages == []


# ---- 4. public detail follows the deadline rule ------------------------------------


@pytest.mark.parametrize("delta,visible", [(3, True), (0, True), (-1, False)])
def test_public_detail_matches_public_search_on_the_deadline(
    api_client, employer, job_factory, delta, visible
):
    job = job_factory(employer, application_deadline=TODAY + timedelta(days=delta))
    listed = {r["id"] for r in api_client.get("/api/v1/jobs").json()["results"]}
    detail = api_client.get(f"/api/v1/jobs/{job.id}")
    assert (str(job.id) in listed) is visible
    assert (detail.status_code == 200) is visible
    if not visible:
        assert detail.status_code == 404
        assert api_client.post(f"/api/v1/jobs/{job.id}/apply").status_code in (401, 403, 404)


def test_expired_job_stays_readable_for_its_employer_and_administrators(
    api_client, admin_client, employer, employer_client, job_factory
):
    job = job_factory(employer, application_deadline=TODAY - timedelta(days=2))
    for _ in range(3):
        assert api_client.get(f"/api/v1/jobs/{job.id}").status_code == 404
    assert employer_client.get(f"/api/v1/jobs/employer/jobs/{job.id}").status_code == 200
    assert admin_client.get(f"{ADMIN}/{job.id}").status_code == 200
    # Only the listing normalises history, exactly once.
    api_client.get("/api/v1/jobs")
    api_client.get("/api/v1/jobs")
    job.refresh_from_db()
    assert job.status == JobStatus.EXPIRED
    assert list(job.transitions.values_list("to_status", flat=True)) == ["EXPIRED"]
