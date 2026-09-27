"""Twenty-eighth Codex review of PR #4 (commit 62c36e2): candidate-data reads
(talent detail, saved candidates, sent invitations) decide on committed state
— employer → membership → billing account — and build their response while
those locks are held, so nothing is disclosed after a committed revocation."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.billing import services as billing
from apps.billing.models import Subscription, UsageEvent
from apps.billing.types import Audience, SubjectType, SubscriptionStatus
from apps.jobs import permissions, services, views
from apps.jobs.models import EmployerMembership
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import MemberRole, MemberStatus

pytestmark = pytest.mark.django_db


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
def candidate(employer, job_factory, seeker_factory):
    """A discoverable candidate the organisation has both saved and invited."""
    profile = seeker_factory()
    services.save_candidate(employer, profile, actor=owner_of(employer))
    services.invite_candidate(employer, job_factory(employer), profile, actor=owner_of(employer))
    return profile


ENDPOINTS = {
    "detail": lambda c: f"/api/v1/talent/{c.pk}",
    "saved": lambda c: "/api/v1/talent/saved",
    "invitations": lambda c: "/api/v1/talent/invitations",
}


def _card_ids(name, body):
    if name == "detail":
        return {body["id"]} if "professional_title" in body else set()
    return {row["candidate"]["id"] for row in body.get("results", []) if row.get("candidate")}


def _end(employer, account):
    m = EmployerMembership.objects.get(
        employer=employer, account=account, status=MemberStatus.ACTIVE
    )
    services.end_membership(m, actor=owner_of(employer))


def _stale_permission(monkeypatch, employer, account):
    stale = EmployerMembership.objects.select_related("employer").get(
        employer=employer, account=account
    )
    fake = lambda acc: stale if acc == account else None  # noqa: E731
    monkeypatch.setattr(permissions, "membership_for", fake)
    monkeypatch.setattr(services, "membership_for", fake)


def _events(employer):
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )
    return UsageEvent.objects.filter(billing_account=account).count()


@pytest.mark.parametrize("name", ENDPOINTS)
def test_active_recruiter_reads_the_candidate_and_consumes_nothing(
    employer, recruiter, candidate, name
):
    before = _events(employer)
    resp = _client(recruiter).get(ENDPOINTS[name](candidate))
    assert resp.status_code == 200
    assert _card_ids(name, resp.json()) == {str(candidate.pk)}
    assert _events(employer) == before


@pytest.mark.parametrize("name", ENDPOINTS)
def test_committed_membership_revocation_discloses_nothing(
    employer, recruiter, candidate, name, monkeypatch
):
    _stale_permission(monkeypatch, employer, recruiter)  # the request's pre-check still passes
    _end(employer, recruiter)
    resp = _client(recruiter).get(ENDPOINTS[name](candidate))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "membership_inactive"
    assert "professional_title" not in resp.content.decode() and "results" not in resp.json()


@pytest.mark.parametrize("name", ENDPOINTS)
def test_committed_employer_suspension_discloses_nothing(
    employer, recruiter, candidate, admin, name, monkeypatch
):
    monkeypatch.setattr(
        views, "_require_talent_access", lambda request, key: None
    )  # pre-check already passed
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="x")
    resp = _client(recruiter).get(ENDPOINTS[name](candidate))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "organization_not_verified"
    assert "professional_title" not in resp.content.decode()


@pytest.mark.parametrize("name", ENDPOINTS)
@pytest.mark.parametrize("how", ["suspend", "cancel"])
def test_committed_subscription_revocation_applies_the_current_entitlement(
    employer, recruiter, candidate, admin, name, how, monkeypatch
):
    monkeypatch.setattr(views, "_require_talent_access", lambda request, key: None)
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )
    sub = Subscription.objects.get(billing_account=account, status=SubscriptionStatus.ACTIVE)
    (billing.suspend_subscription if how == "suspend" else billing.cancel_subscription)(
        sub, admin=admin, reason="x"
    )
    resp = _client(recruiter).get(
        ENDPOINTS[name](candidate)
    )  # the default plan carries no talent capability
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "entitlement_required"
    assert "professional_title" not in resp.content.decode()


@pytest.mark.parametrize("name", ENDPOINTS)
def test_a_read_that_completed_first_is_followed_by_the_revocation(
    employer, recruiter, candidate, name
):
    resp = _client(recruiter).get(ENDPOINTS[name](candidate))
    assert resp.status_code == 200
    _end(employer, recruiter)
    assert (
        EmployerMembership.objects.get(employer=employer, account=recruiter).status
        == MemberStatus.ENDED
    )
    assert _client(recruiter).get(ENDPOINTS[name](candidate)).status_code == 403


def test_privacy_rules_are_unchanged(employer, recruiter, seeker_factory, employer_factory):
    hidden = seeker_factory(discoverable=False)  # never applied, never saved
    assert _client(recruiter).get(f"/api/v1/talent/{hidden.pk}").status_code == 404
    other = employer_factory(plan_code="PROFESSIONAL")
    foreign = seeker_factory()
    services.save_candidate(other, foreign, actor=owner_of(other))
    body = _client(recruiter).get("/api/v1/talent/saved").json()
    assert str(foreign.pk) not in {row["candidate"]["id"] for row in body["results"]}


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_revocation_racing_a_detail_read_never_discloses_after_it(
    employer_factory, account_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    recruiter = account_factory(role="PROVIDER")
    services.add_member(employer, recruiter, MemberRole.RECRUITER, actor=owner_of(employer))
    profile = seeker_factory()
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def read():
        try:
            barrier.wait(timeout=10)
            resp = _client(recruiter).get(f"/api/v1/talent/{profile.pk}")
            outcomes["read"] = (resp.status_code, "professional_title" in resp.content.decode())
        finally:
            connection.close()

    def revoke():
        try:
            barrier.wait(timeout=10)
            _end(employer, recruiter)
            outcomes["revoke"] = "ok"
        finally:
            connection.close()

    threads = [threading.Thread(target=read), threading.Thread(target=revoke)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["revoke"] == "ok"
    assert outcomes["read"] in ((200, True), (403, False)), (
        outcomes
    )  # disclosed only under valid access
    assert (
        EmployerMembership.objects.get(employer=employer, account=recruiter).status
        == MemberStatus.ENDED
    )


def test_search_charging_is_unchanged(employer, recruiter, seeker_factory):
    seeker_factory()
    before = _events(employer)
    assert _client(recruiter).get("/api/v1/talent", {"profession": "NURSE"}).status_code == 200
    assert _events(employer) == before + 1
