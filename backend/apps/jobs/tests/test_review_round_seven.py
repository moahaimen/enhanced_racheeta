"""Regression tests for the seventh Codex review of PR #4 (commit b666379):
locked subscription expiry, expired invitations on apply, and the canonical
billable signature of a talent search."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.models import Plan, Subscription
from apps.billing.types import Audience, Keys, SubjectType, SubscriptionStatus
from apps.jobs import services
from apps.jobs.models import JobInvitation, TalentSearchQuery
from apps.jobs.services import search_signature
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import InvitationStatus

TALENT = "/api/v1/talent"


def _race(actions):
    barrier = threading.Barrier(len(actions))
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except (billing.SubscriptionError, services.JobsError) as exc:
            outcomes[name] = type(exc).__name__
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


# ---- 1. locked subscription expiry ------------------------------------------------


def _elapsed_active(employer, admin):
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )
    sub = billing.request_subscription(
        account, Plan.objects.get(code="BASIC"), requested_by=owner_of(employer)
    )
    billing.activate_subscription(
        sub, admin=admin, starts_at=timezone.now() - timedelta(days=40), term_days=30
    )
    return account, sub


def test_elapsed_active_subscription_expires_once(employer_factory, admin):
    account, sub = _elapsed_active(employer_factory(), admin)
    assert billing.expire_subscription(sub) is True
    assert billing.expire_subscription(sub) is False  # already expired: no second event
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.EXPIRED
    assert sub.events.filter(to_status=SubscriptionStatus.EXPIRED).count() == 1
    ent = billing.EntitlementService(account)
    assert ent.subscription is None and ent.plan.code == "TRIAL"


def test_stale_expiry_never_overwrites_a_newer_admin_decision(employer_factory, admin):
    # Round eighteen: an ELAPSED term can no longer be suspended (it is expired
    # first), so the administrator decides on a live term and the term elapses
    # afterwards; the stale expiry must still not overwrite that decision.
    _, sub = _elapsed_active(employer_factory(), admin)
    Subscription.objects.filter(pk=sub.pk).update(ends_at=timezone.now() + timedelta(days=5))
    stale = Subscription.objects.get(pk=sub.pk)  # loaded while still ACTIVE
    billing.suspend_subscription(sub, admin=admin, reason="late payment")
    Subscription.objects.filter(pk=sub.pk).update(ends_at=timezone.now() - timedelta(days=1))
    assert billing.expire_subscription(stale) is False
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.SUSPENDED
    assert not sub.events.filter(to_status=SubscriptionStatus.EXPIRED).exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("admin_action", ["suspend", "cancel", "expire"])
def test_concurrent_expiry_races(employer_factory, admin, admin_action):
    _, sub = _elapsed_active(employer_factory(), admin)

    def expire():
        billing.expire_subscription(Subscription.objects.get(pk=sub.pk))

    def other():
        row = Subscription.objects.get(pk=sub.pk)
        if admin_action == "suspend":
            billing.suspend_subscription(row, admin=admin, reason="x")
        elif admin_action == "cancel":
            billing.cancel_subscription(row, admin=admin, reason="x")
        else:
            billing.expire_subscription(row)

    outcomes = _race({"expire": expire, "other": other})
    sub.refresh_from_db()
    expected = {
        "suspend": (SubscriptionStatus.SUSPENDED, SubscriptionStatus.EXPIRED),
        "cancel": (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED),
        "expire": (SubscriptionStatus.EXPIRED,),
    }[admin_action]
    assert sub.status in expected, (sub.status, outcomes)
    transitions = list(
        sub.events.exclude(to_status=SubscriptionStatus.PENDING)
        .exclude(to_status=SubscriptionStatus.ACTIVE)
        .values_list("to_status", flat=True)
    )
    assert len(transitions) == 1 and transitions[0] == sub.status  # exactly one final transition
    if admin_action != "expire":
        # Whichever ran second either found the row no longer ACTIVE (no-op) or a typed error.
        assert outcomes["expire"] == "ok"
        assert outcomes["other"] in ("ok", "SubscriptionError")


# ---- 2. invitations when the seeker applies ----------------------------------------


def test_live_invitation_is_accepted_when_the_seeker_applies(employer, job_factory, seeker_factory):
    job, candidate = job_factory(employer), seeker_factory()
    inv = services.invite_candidate(employer, job, candidate, actor=owner_of(employer))
    application = services.apply_to_job(job, candidate)
    inv.refresh_from_db()
    assert application.status == "SUBMITTED"
    assert inv.status == InvitationStatus.ACCEPTED and inv.responded_at is not None


def test_expired_invitation_becomes_expired_not_accepted_when_the_seeker_applies(
    employer, job_factory, seeker_factory
):
    job, candidate = job_factory(employer), seeker_factory()
    inv = services.invite_candidate(employer, job, candidate, actor=owner_of(employer))
    JobInvitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(hours=1))
    application = services.apply_to_job(job, candidate)
    inv.refresh_from_db()
    assert application.status == "SUBMITTED"  # the application itself is fine
    assert inv.status == InvitationStatus.EXPIRED and inv.responded_at is None
    with pytest.raises(services.JobsError):  # explicit response afterwards is refused
        services.respond_to_invitation(inv, accept=True)
    inv.refresh_from_db()
    assert inv.status == InvitationStatus.EXPIRED
    assert JobInvitation.objects.filter(job=job, job_seeker=candidate).count() == 1


def test_already_answered_or_expired_invitations_are_not_touched_by_apply(
    employer, job_factory, seeker_factory
):
    job, candidate = job_factory(employer), seeker_factory()
    inv = services.invite_candidate(employer, job, candidate, actor=owner_of(employer))
    services.respond_to_invitation(inv, accept=False)
    responded_at = inv.responded_at
    services.apply_to_job(job, candidate)
    inv.refresh_from_db()
    assert inv.status == InvitationStatus.DECLINED and inv.responded_at == responded_at


# ---- 3. canonical billable signature ------------------------------------------------


def test_equivalent_filters_share_a_signature_and_different_ones_do_not():
    base = search_signature({"skill": "Nursing"})
    assert search_signature({"skill": "nursing"}) == base
    assert search_signature({"skill": "  Nursing  "}) == base
    assert search_signature({"skill": "NURSING", "page": "3", "ordering": "-x"}) == base
    assert search_signature({"skill": "Nursing", "unknown": "y", "page_size": "50"}) == base
    assert search_signature({"q": " ICU  Nurse "}) == search_signature({"q": "icu nurse"})
    assert search_signature({"language": "English", "language_level": "advanced"}) == (
        search_signature({"language": " english", "language_level": "ADVANCED"})
    )
    assert search_signature({"min_experience": "05"}) == search_signature({"min_experience": "5"})
    assert search_signature({"governorate": "ABCDEF00-0000-4000-8000-000000000000"}) == (
        search_signature({"governorate": "abcdef00-0000-4000-8000-000000000000"})
    )
    assert search_signature({"skill": "nursing"}) != search_signature({"skill": "midwifery"})
    assert search_signature({"q": "icu"}) != search_signature({"q": "icu nurse"})
    assert search_signature({"profession": "NURSE"}) != search_signature({"profession": "DOCTOR"})
    assert search_signature({"min_experience": "5"}) != search_signature({"max_experience": "5"})
    assert search_signature({}) == search_signature({"page": "2"})


def test_equivalent_http_searches_consume_one_unit(api_client, employer_factory, seeker_factory):
    nurse = seeker_factory()
    nurse.skills.create(name="Nursing")
    basic = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(basic))
    ids = set()
    for value in ("Nursing", "nursing", " Nursing ", "NURSING"):
        body = api_client.get(TALENT, {"skill": value}).json()
        ids.add(tuple(r["id"] for r in body["results"]))
    assert ids == {(str(nurse.id),)}  # identical results
    api_client.get(TALENT, {"skill": "nursing", "page": 1})
    assert services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used == 1
    assert TalentSearchQuery.objects.filter(employer=basic).count() == 1
    assert api_client.get(TALENT, {"skill": "nursing", "profession": "WIZARD"}).status_code == 400
    assert services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used == 1
    api_client.get(TALENT, {"skill": "midwifery"})
    assert services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used == 2
