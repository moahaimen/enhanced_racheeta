"""Twenty-seventh Codex review of PR #4 (commit b7e88bb): talent search and
saved-candidate removal are serialised like writes (employer → membership →
billing account), and a seeker application resolves its effective plan on the
locked seeker billing account."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.billing import services as billing
from apps.billing.exceptions import EntitlementError, UsageLimitReached
from apps.billing.models import Plan, PlanEntitlement, Subscription, UsageEvent
from apps.billing.types import Audience, Keys, SubjectType, SubscriptionStatus
from apps.jobs import permissions, services
from apps.jobs.models import Employer, EmployerMembership, JobApplication, SavedCandidate
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import MemberRole, MemberStatus

pytestmark = pytest.mark.django_db
TALENT = "/api/v1/talent"
SAVED = "/api/v1/talent/saved"


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


def _account(subject_type, subject_id, audience):
    return billing.get_or_create_billing_account(subject_type, subject_id, audience)


def _used(account, key):
    return UsageEvent.objects.filter(billing_account=account, key=key).count()


@pytest.fixture
def recruiter(employer, account_factory):
    acct = account_factory(role="PROVIDER")
    services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    return acct


def _end(employer, account):
    m = EmployerMembership.objects.get(
        employer=employer, account=account, status=MemberStatus.ACTIVE
    )
    services.end_membership(m, actor=owner_of(employer))


def _stale_permission(monkeypatch, employer, account):
    """The permission layer keeps the ACTIVE membership object it loaded."""
    stale = EmployerMembership.objects.select_related("employer").get(
        employer=employer, account=account
    )
    fake = lambda acc: stale if acc == account else None  # noqa: E731
    monkeypatch.setattr(permissions, "membership_for", fake)
    monkeypatch.setattr(services, "membership_for", fake)


# ---- 1. talent search ----------------------------------------------------------------------


def _employer_account(employer):
    return _account(SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER)


def test_active_recruiter_searches_and_is_charged_once(employer, recruiter, seeker_factory):
    seeker_factory()
    client = _client(recruiter)
    assert client.get(TALENT, {"profession": "NURSE"}).json()["count"] == 1
    assert client.get(TALENT, {"profession": "NURSE"}).status_code == 200  # same search, same day
    assert _used(_employer_account(employer), Keys.TALENT_SEARCH_LIMIT) == 1


def test_viewer_is_denied(employer, account_factory):
    viewer = account_factory(role="PROVIDER")
    services.add_member(employer, viewer, MemberRole.VIEWER, actor=owner_of(employer))
    assert _client(viewer).get(TALENT).status_code == 403


def test_revoked_recruiter_gets_no_cards_and_no_charge(
    employer, recruiter, seeker_factory, monkeypatch
):
    seeker_factory()
    _stale_permission(monkeypatch, employer, recruiter)
    _end(employer, recruiter)  # committed before the search takes its locks
    resp = _client(recruiter).get(TALENT, {"profession": "NURSE"})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "membership_inactive"
    assert "results" not in resp.json()
    assert _used(_employer_account(employer), Keys.TALENT_SEARCH_LIMIT) == 0


def test_suspended_employer_is_refused_on_the_locked_row(employer, seeker_factory, admin):
    seeker_factory()
    stale = Employer.objects.get(pk=employer.pk)  # recruiting in memory
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    with pytest.raises(services.OrganizationNotVerified):
        services.record_talent_search(stale, {"profession": "NURSE"}, actor=owner_of(employer))
    assert _used(_employer_account(employer), Keys.TALENT_SEARCH_LIMIT) == 0
    assert _client(owner_of(employer)).get(TALENT).status_code == 403


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_revocation_racing_a_search_never_charges_after_it(
    employer_factory, account_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    recruiter = account_factory(role="PROVIDER")
    services.add_member(employer, recruiter, MemberRole.RECRUITER, actor=owner_of(employer))
    seeker_factory()
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def search():
        try:
            barrier.wait(timeout=10)
            outcomes["search"] = _client(recruiter).get(TALENT, {"profession": "NURSE"}).status_code
        finally:
            connection.close()

    def revoke():
        try:
            barrier.wait(timeout=10)
            _end(employer, recruiter)
            outcomes["revoke"] = "ok"
        finally:
            connection.close()

    threads = [threading.Thread(target=search), threading.Thread(target=revoke)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["revoke"] == "ok" and outcomes["search"] in (200, 403), outcomes
    charged = _used(_employer_account(employer), Keys.TALENT_SEARCH_LIMIT)
    assert charged == (1 if outcomes["search"] == 200 else 0)


# ---- 2. saved-candidate removal ------------------------------------------------------------


@pytest.fixture
def saved(employer, seeker_factory):
    return services.save_candidate(employer, seeker_factory(), actor=owner_of(employer))


def test_active_recruiter_removes_a_saved_candidate(employer, recruiter, saved):
    assert _client(recruiter).delete(f"{SAVED}/{saved.pk}").status_code == 204
    assert not SavedCandidate.objects.filter(pk=saved.pk).exists()


def test_revoked_membership_cannot_remove(employer, recruiter, saved, monkeypatch):
    _stale_permission(monkeypatch, employer, recruiter)
    _end(employer, recruiter)
    resp = _client(recruiter).delete(f"{SAVED}/{saved.pk}")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "membership_inactive"
    assert SavedCandidate.objects.filter(pk=saved.pk).exists()


def test_suspended_employer_cannot_remove(employer, saved, admin):
    stale = Employer.objects.get(pk=employer.pk)
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    with pytest.raises(services.OrganizationNotVerified):
        services.unsave_candidate(stale, saved.pk, actor=owner_of(employer))
    assert _client(owner_of(employer)).delete(f"{SAVED}/{saved.pk}").status_code == 403
    assert SavedCandidate.objects.filter(pk=saved.pk).exists()


@pytest.mark.parametrize("how", ["suspend", "cancel"])
def test_revoked_subscription_applies_the_current_entitlement(employer, saved, admin, how):
    sub = Subscription.objects.get(
        billing_account=_employer_account(employer), status=SubscriptionStatus.ACTIVE
    )
    fn = billing.suspend_subscription if how == "suspend" else billing.cancel_subscription
    fn(sub, admin=admin, reason="late")
    with pytest.raises(EntitlementError):  # the default plan carries no talent.save_candidate
        services.unsave_candidate(employer, saved.pk, actor=owner_of(employer))
    assert SavedCandidate.objects.filter(pk=saved.pk).exists()


def test_unentitled_foreign_and_missing_rows(employer_factory, employer, saved, seeker_factory):
    trial = employer_factory()  # default plan: no talent.save_candidate
    assert _client(owner_of(trial)).delete(f"{SAVED}/{saved.pk}").status_code == 403
    other = employer_factory(plan_code="PROFESSIONAL")
    assert _client(owner_of(other)).delete(f"{SAVED}/{saved.pk}").status_code == 404  # privacy-safe
    assert SavedCandidate.objects.filter(pk=saved.pk).exists()
    assert _client(owner_of(employer)).delete(f"{SAVED}/{saved.pk}").status_code == 204
    assert _client(owner_of(employer)).delete(f"{SAVED}/{saved.pk}").status_code == 404


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_revocation_racing_a_removal_never_deletes_after_it(
    employer_factory, account_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    recruiter = account_factory(role="PROVIDER")
    services.add_member(employer, recruiter, MemberRole.RECRUITER, actor=owner_of(employer))
    saved = services.save_candidate(employer, seeker_factory(), actor=owner_of(employer))
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def remove():
        try:
            barrier.wait(timeout=10)
            outcomes["remove"] = _client(recruiter).delete(f"{SAVED}/{saved.pk}").status_code
        finally:
            connection.close()

    def revoke():
        try:
            barrier.wait(timeout=10)
            _end(employer, recruiter)
            outcomes["revoke"] = "ok"
        finally:
            connection.close()

    threads = [threading.Thread(target=remove), threading.Thread(target=revoke)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["revoke"] == "ok" and outcomes["remove"] in (204, 403), outcomes
    assert SavedCandidate.objects.filter(pk=saved.pk).exists() == (outcomes["remove"] == 403)


# ---- 3. seeker application on the locked seeker billing account ------------------------------


def _seeker_account(profile):
    return _account(SubjectType.ACCOUNT, profile.account_id, Audience.JOB_SEEKER)


def _activate_plus(profile, admin):
    sub = billing.request_subscription(
        _seeker_account(profile), Plan.objects.get(code="SEEKER_PLUS"), requested_by=profile.account
    )
    return billing.activate_subscription(sub, admin=admin)


@pytest.fixture
def plus_seeker(seeker_factory, admin):
    profile = seeker_factory()
    _activate_plus(profile, admin)
    return profile


def _plus_sub(profile):
    return Subscription.objects.get(
        billing_account=_seeker_account(profile), status=SubscriptionStatus.ACTIVE
    )


def _free_limit(n):
    PlanEntitlement.objects.filter(plan__code="SEEKER_FREE", key=Keys.APPLICATIONS_LIMIT).update(
        limit=n
    )


def test_active_plus_seeker_applies_and_consumes_once(employer, job_factory, plus_seeker):
    services.apply_to_job(job_factory(employer), plus_seeker)
    assert _used(_seeker_account(plus_seeker), Keys.APPLICATIONS_LIMIT) == 1
    assert services.seeker_entitlements(plus_seeker).plan.code == "SEEKER_PLUS"


def test_duplicate_application_unchanged(employer, job_factory, plus_seeker):
    job = job_factory(employer)
    services.apply_to_job(job, plus_seeker)
    with pytest.raises(services.AlreadyApplied):
        services.apply_to_job(job, plus_seeker)
    assert _used(_seeker_account(plus_seeker), Keys.APPLICATIONS_LIMIT) == 1


@pytest.mark.parametrize("free_limit,outcome", [(1, "refused"), (2, "created")])
def test_revoked_paid_plan_falls_back_to_the_current_free_quota(
    employer, job_factory, seeker_factory, admin, free_limit, outcome
):
    """One unit was used on the FREE plan this month, then SEEKER_PLUS was
    activated. The request read the paid, unlimited entitlement; the
    suspension committed before its billing lock. The CURRENT plan is FREE and
    its quota decides: exhausted (limit 1) refuses, capacity (limit 2) allows."""
    profile = seeker_factory()
    _free_limit(free_limit)
    services.apply_to_job(job_factory(employer), profile)  # under FREE: bucket used = 1
    _activate_plus(profile, admin)
    observed = services.seeker_entitlements(profile).get(Keys.APPLICATIONS_LIMIT)
    assert observed.unlimited  # what a request read before the lock
    billing.suspend_subscription(
        _plus_sub(profile), admin=admin, reason="late"
    )  # committed meanwhile
    job = job_factory(employer)
    if outcome == "refused":
        with pytest.raises(UsageLimitReached):
            services.apply_to_job(job, profile)
        assert not JobApplication.objects.filter(job=job).exists()
        assert _used(_seeker_account(profile), Keys.APPLICATIONS_LIMIT) == 1
    else:
        services.apply_to_job(job, profile)
        assert JobApplication.objects.filter(job=job).exists()
        assert _used(_seeker_account(profile), Keys.APPLICATIONS_LIMIT) == 2
    assert services.seeker_entitlements(profile).plan.code == "SEEKER_FREE"


def test_application_before_revocation_completes_and_revocation_follows(
    employer, job_factory, plus_seeker, admin
):
    application = services.apply_to_job(job_factory(employer), plus_seeker)
    billing.suspend_subscription(_plus_sub(plus_seeker), admin=admin, reason="late")
    assert JobApplication.objects.filter(pk=application.pk).exists()
    assert (
        Subscription.objects.get(billing_account=_seeker_account(plus_seeker)).status
        == SubscriptionStatus.SUSPENDED
    )


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_suspension_racing_an_application_never_uses_stale_paid_entitlement(
    employer_factory, job_factory, seeker_factory, admin
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    profile = seeker_factory()
    _free_limit(1)
    services.apply_to_job(job_factory(employer), profile)  # FREE quota (1) exhausted
    sub = _activate_plus(profile, admin)
    job = job_factory(employer)
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except UsageLimitReached:
            outcomes[name] = "usage_limit"
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=("apply", lambda: services.apply_to_job(job, profile))),
        threading.Thread(
            target=run,
            args=(
                "suspend",
                lambda: billing.suspend_subscription(
                    Subscription.objects.get(pk=sub.pk), admin=admin, reason="late"
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["suspend"] == "ok" and outcomes["apply"] in ("ok", "usage_limit"), outcomes
    created = JobApplication.objects.filter(job=job, job_seeker=profile).exists()
    assert created == (outcomes["apply"] == "ok")  # under the still-valid paid plan, or refused
    assert _used(_seeker_account(profile), Keys.APPLICATIONS_LIMIT) == (2 if created else 1)
