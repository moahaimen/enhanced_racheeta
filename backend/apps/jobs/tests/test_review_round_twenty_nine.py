"""Twenty-ninth Codex review of PR #4 (commit 4ca9e8c): closure of the
candidate-data disclosure family. Every employer endpoint that returns
candidate professional data decides on committed state (employer →
membership → billing account → locked candidate rows) and builds its
response before releasing those locks."""

import threading
import time

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.billing import services as billing
from apps.billing.models import Subscription, UsageEvent
from apps.billing.types import Audience, Keys, SubjectType, SubscriptionStatus
from apps.jobs import permissions, serializers, services, views
from apps.jobs.models import EmployerMembership, JobInvitation, JobSeekerProfile, SavedCandidate
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import ApplicationStatus, MemberRole, MemberStatus

pytestmark = pytest.mark.django_db
PROFILE = "/api/v1/jobs/me/profile"


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


class Setup:
    """One organisation (PROFESSIONAL plan) with a recruiter and a viewer, one
    discoverable candidate that is saved and invited, one applicant."""

    def __init__(self, employer, account_factory, job_factory, seeker_factory):
        self.employer = employer
        self.owner = owner_of(employer)
        self.recruiter = account_factory(role="PROVIDER")
        self.viewer = account_factory(role="PROVIDER")
        services.add_member(employer, self.recruiter, MemberRole.RECRUITER, actor=self.owner)
        services.add_member(employer, self.viewer, MemberRole.VIEWER, actor=self.owner)
        self.job = job_factory(employer)
        self.candidate = seeker_factory()
        self.saved = services.save_candidate(employer, self.candidate, actor=self.owner)
        self.invitation = services.invite_candidate(
            employer, self.job, self.candidate, actor=self.owner
        )
        self.applicant = seeker_factory()
        self.application = services.apply_to_job(self.job, self.applicant, cover_text="Cover")
        self.fresh = seeker_factory()  # for save/invite responses

    def actors(self):
        return {"OWNER": self.owner, "RECRUITER": self.recruiter, "VIEWER": self.viewer}


@pytest.fixture
def s(employer, account_factory, job_factory, seeker_factory):
    return Setup(employer, account_factory, job_factory, seeker_factory)


# name: (method, url builder, allowed roles, whose card the response must carry,
# whether disclosure depends on the candidate's current discoverability)
ENDPOINTS = {
    "search": (
        "get",
        lambda s: ("/api/v1/talent", {"profession": "NURSE"}),
        ("OWNER", "RECRUITER"),
        "candidate",
        True,
    ),
    "detail": (
        "get",
        lambda s: (f"/api/v1/talent/{s.candidate.pk}", None),
        ("OWNER", "RECRUITER"),
        "candidate",
        True,
    ),
    "saved_list": (
        "get",
        lambda s: ("/api/v1/talent/saved", None),
        ("OWNER", "RECRUITER"),
        "candidate",
        True,
    ),
    "invitation_list": (
        "get",
        lambda s: ("/api/v1/talent/invitations", None),
        ("OWNER", "RECRUITER"),
        "candidate",
        True,
    ),
    "applicant_list": (
        "get",
        lambda s: (f"/api/v1/jobs/employer/jobs/{s.job.pk}/applications", None),
        ("OWNER", "RECRUITER", "VIEWER"),
        "applicant",
        False,
    ),
    "applicant_detail": (
        "get",
        lambda s: (f"/api/v1/jobs/employer/applications/{s.application.pk}", None),
        ("OWNER", "RECRUITER", "VIEWER"),
        "applicant",
        False,
    ),
    "transition": (
        "post",
        lambda s: (
            f"/api/v1/jobs/employer/applications/{s.application.pk}/transition",
            {"status": "REVIEWING"},
        ),
        ("OWNER", "RECRUITER"),
        "applicant",
        False,
    ),
    "save": (
        "post",
        lambda s: ("/api/v1/talent/saved", {"job_seeker": str(s.fresh.pk)}),
        ("OWNER", "RECRUITER"),
        "fresh",
        True,
    ),
    "invite": (
        "post",
        lambda s: (
            "/api/v1/talent/invitations",
            {"job": str(s.job.pk), "job_seeker": str(s.fresh.pk)},
        ),
        ("OWNER", "RECRUITER"),
        "fresh",
        True,
    ),
    "cancel": (
        "post",
        lambda s: (f"/api/v1/talent/invitations/{s.invitation.pk}/cancel", None),
        ("OWNER", "RECRUITER"),
        "candidate",
        True,
    ),
}
TALENT_ENTITLED = {"search", "detail", "saved_list", "invitation_list", "save", "invite", "cancel"}


def _call(s, name, actor):
    method, build, *_ = ENDPOINTS[name]
    url, payload = build(s)
    client = _client(actor)
    return client.get(url, payload) if method == "get" else client.post(url, payload, format="json")


def _cards(body):
    """Every candidate professional card in a response body (any shape)."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "professional_title" in node and "id" in node and "skills" in node:
                found.append(node["id"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(body)
    return found


def _leaks(body) -> bool:
    """True when any protected candidate data (card, snapshot, cover text) is present."""
    text = str(body)
    return "professional_title" in text or "snapshot" in text or "cover_text" in text


def _expected_card(s, name):
    who = ENDPOINTS[name][3]
    return str({"candidate": s.candidate, "applicant": s.applicant, "fresh": s.fresh}[who].pk)


def _bypass_prechecks(monkeypatch):
    monkeypatch.setattr(views, "_require_talent_access", lambda request, key: None)
    monkeypatch.setattr(views, "_require_application_review", lambda request: None)


def _stale_permission(monkeypatch, employer, account):
    stale = EmployerMembership.objects.select_related("employer").get(
        employer=employer, account=account
    )
    fake = lambda acc: stale if acc == account else None  # noqa: E731
    monkeypatch.setattr(permissions, "membership_for", fake)
    monkeypatch.setattr(services, "membership_for", fake)


def _end(employer, account):
    m = EmployerMembership.objects.get(
        employer=employer, account=account, status=MemberStatus.ACTIVE
    )
    services.end_membership(m, actor=owner_of(employer))


def _employer_sub(employer):
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )
    return Subscription.objects.get(billing_account=account, status=SubscriptionStatus.ACTIVE)


# ---- policy regression: every endpoint, every legitimate role ------------------------------


@pytest.mark.parametrize("name", ENDPOINTS)
def test_every_endpoint_returns_the_candidate_to_its_legitimate_roles(s, name):
    for role, actor in s.actors().items():
        resp = _call(s, name, actor)
        if role in ENDPOINTS[name][2]:
            assert resp.status_code in (200, 201), (name, role, resp.content)
            assert _expected_card(s, name) in _cards(resp.json()), (name, role)
            if name in ("transition", "save", "invite", "cancel"):
                break  # a mutation: once is enough
        else:
            assert resp.status_code == 403, (name, role)
            assert not _leaks(resp.json())


# ---- revocation classes, committed before the authoritative locks --------------------------


@pytest.mark.parametrize("name", ENDPOINTS)
def test_membership_revocation_discloses_nothing(s, name, monkeypatch):
    _stale_permission(monkeypatch, s.employer, s.recruiter)
    _end(s.employer, s.recruiter)
    resp = _call(s, name, s.recruiter)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "membership_inactive", name
    assert not _leaks(resp.json())


@pytest.mark.parametrize("name", ENDPOINTS)
def test_employer_suspension_discloses_nothing(s, name, admin, monkeypatch):
    _bypass_prechecks(monkeypatch)
    services.set_employer_recruitment_status(s.employer, "SUSPENDED", admin=admin, reason="x")
    resp = _call(s, name, s.recruiter)
    if (
        name == "invite"
    ):  # a suspended organisation's jobs are not open: the existing typed conflict
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "job_not_open"
    else:
        assert resp.status_code == 403, name
        assert resp.json()["error"]["code"] == "organization_not_verified", name
    assert not _leaks(resp.json())


@pytest.mark.parametrize("name", ENDPOINTS)
def test_subscription_revocation_applies_the_current_entitlement(s, name, admin, monkeypatch):
    _bypass_prechecks(monkeypatch)
    billing.cancel_subscription(_employer_sub(s.employer), admin=admin, reason="x")
    resp = _call(s, name, s.recruiter)
    if name in TALENT_ENTITLED:  # the default plan carries no talent capability
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "entitlement_required", (
            name
        )
        assert not _leaks(resp.json())
    else:  # applicant review is part of the default plan: still allowed, on the current plan
        assert resp.status_code == 200, name
        assert services.employer_entitlements(s.employer).plan.is_default


@pytest.mark.parametrize("name", ENDPOINTS)
def test_candidate_opt_out_follows_each_endpoint_policy(s, name):
    for profile in (s.candidate, s.fresh):
        JobSeekerProfile.objects.filter(pk=profile.pk).update(discoverable_by_employers=False)
    resp = _call(s, name, s.recruiter)
    cards = _cards(resp.json()) if resp.content else []
    if name == "search":
        assert resp.status_code == 200 and str(s.candidate.pk) not in cards
    elif name == "detail":
        assert resp.status_code == 404 and not cards
    elif name in ("saved_list", "invitation_list"):
        assert resp.status_code == 200 and cards == []  # the rows are kept, the cards are not shown
    elif name in ("save", "invite"):
        assert resp.status_code == 404 and not cards
    elif name == "cancel":
        assert resp.status_code == 200 and resp.json()["candidate"] is None and not cards
    else:  # applicants stay visible through their application (snapshot policy)
        assert resp.status_code == 200 and str(s.applicant.pk) in cards


# ---- serialisation: a competing writer waits until the response is built -------------------


def _blocked_writer(fn, hold_seconds=1.0):
    """Runs `fn` on its own connection; reports whether it was still blocked
    after `hold_seconds` (i.e. it waited on a lock the caller holds)."""
    done = threading.Event()
    errors = []

    def run():
        try:
            fn()
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))
        finally:
            done.set()
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    blocked = not done.wait(hold_seconds)
    return thread, blocked, errors


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("name", ["detail", "save", "invite", "applicant_detail", "transition"])
def test_a_writer_waits_while_the_response_is_built(
    employer_factory, account_factory, job_factory, seeker_factory, name, monkeypatch
):
    """The competing write (privacy opt-out for candidate endpoints, membership
    revocation for applicant endpoints) starts while the serializer runs; it
    must block until the response exists, then complete."""
    employer = employer_factory(plan_code="PROFESSIONAL")
    s = Setup(employer, account_factory, job_factory, seeker_factory)
    state: dict[str, object] = {}
    real = serializers.TalentCardSerializer.to_representation

    def competing():
        if name in ("detail", "save", "invite"):
            target = s.fresh if name in ("save", "invite") else s.candidate
            _client(target.account).patch(
                PROFILE, {"discoverable_by_employers": False}, format="json"
            )
        else:
            _end(employer, s.recruiter)

    def hooked(self, instance):
        if "thread" not in state:
            state["thread"], state["blocked"], state["errors"] = _blocked_writer(competing)
        return real(self, instance)

    monkeypatch.setattr(serializers.TalentCardSerializer, "to_representation", hooked)
    resp = _call(s, name, s.recruiter)
    state["thread"].join(timeout=30)
    assert resp.status_code in (200, 201), resp.content
    assert _expected_card(s, name) in _cards(resp.json())  # disclosed under valid, locked state
    assert state["blocked"] is True and not state["errors"], state  # the writer waited for us
    if name in ("detail", "save", "invite"):
        target = s.fresh if name in ("save", "invite") else s.candidate
        assert JobSeekerProfile.objects.get(pk=target.pk).discoverable_by_employers is False
    else:
        assert (
            EmployerMembership.objects.get(employer=employer, account=s.recruiter).status
            == MemberStatus.ENDED
        )


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_opt_out_racing_a_detail_read_never_discloses_after_it(
    employer_factory, account_factory, job_factory, seeker_factory
):
    employer = employer_factory(plan_code="PROFESSIONAL")
    s = Setup(employer, account_factory, job_factory, seeker_factory)
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def read():
        try:
            barrier.wait(timeout=10)
            resp = _client(s.recruiter).get(f"/api/v1/talent/{s.fresh.pk}")
            outcomes["read"] = (resp.status_code, bool(_cards(resp.json())))
        finally:
            connection.close()

    def opt_out():
        try:
            barrier.wait(timeout=10)
            outcomes["opt_out"] = (
                _client(s.fresh.account)
                .patch(PROFILE, {"discoverable_by_employers": False}, format="json")
                .status_code
            )
        finally:
            connection.close()

    threads = [threading.Thread(target=read), threading.Thread(target=opt_out)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["opt_out"] == 200
    assert outcomes["read"] in ((200, True), (404, False)), outcomes
    assert JobSeekerProfile.objects.get(pk=s.fresh.pk).discoverable_by_employers is False


# ---- unchanged semantics -----------------------------------------------------------------


def test_search_charges_once_even_when_privacy_filtering_drops_rows(s, seeker_factory):
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, s.employer.pk, Audience.EMPLOYER
    )
    before = UsageEvent.objects.filter(
        billing_account=account, key=Keys.TALENT_SEARCH_LIMIT
    ).count()
    for _ in range(3):
        seeker_factory()
    assert _call(s, "search", s.recruiter).status_code == 200
    assert _call(s, "search", s.recruiter).status_code == 200
    assert (
        UsageEvent.objects.filter(billing_account=account, key=Keys.TALENT_SEARCH_LIMIT).count()
        == before + 1
    )


def test_interview_and_message_responses_carry_no_candidate_profile(s):
    services.transition_application(s.application, ApplicationStatus.SHORTLISTED, actor=s.owner)
    from datetime import timedelta

    from django.utils import timezone

    client = _client(s.recruiter)
    iv = client.post(
        f"/api/v1/jobs/employer/applications/{s.application.pk}/interviews",
        {"proposed_at": (timezone.now() + timedelta(days=2)).isoformat(), "mode": "ONLINE"},
        format="json",
    )
    assert iv.status_code == 201 and not _cards(iv.json())
    msg = client.post(
        f"/api/v1/recruitment/applications/{s.application.pk}/messages",
        {"body": "Hi"},
        format="json",
    )
    assert msg.status_code == 201 and not _cards(msg.json())
    assert client.delete(f"/api/v1/talent/saved/{s.saved.pk}").status_code == 204


def test_lifecycles_are_unchanged(s):
    assert _call(s, "transition", s.recruiter).json()["status"] == "REVIEWING"
    assert _call(s, "cancel", s.recruiter).json()["status"] == "CANCELLED"
    assert JobInvitation.objects.get(pk=s.invitation.pk).status == "CANCELLED"
    assert _call(s, "save", s.recruiter).status_code == 201
    assert SavedCandidate.objects.filter(employer=s.employer, job_seeker=s.fresh).exists()
    assert _call(s, "save", s.recruiter).status_code == 409  # already_saved
    assert _call(s, "invite", s.recruiter).status_code == 201
    assert _call(s, "invite", s.recruiter).status_code == 409  # already_invited
    time.sleep(0)  # keep the import used on platforms where the writer helper is skipped


# ---- round thirty: complete locked card state + account activity ----------------------------


def _find_card(body, candidate_id):
    if isinstance(body, dict):
        if (
            body.get("id") == str(candidate_id)
            and "professional_title" in body
            and "skills" in body
        ):
            return body
        for value in body.values():
            found = _find_card(value, candidate_id)
            if found is not None:
                return found
    elif isinstance(body, list):
        for value in body:
            found = _find_card(value, candidate_id)
            if found is not None:
                return found
    return None


@pytest.mark.parametrize("name", ["search", "saved_list", "invitation_list"])
def test_list_rows_serialize_the_complete_locked_candidate_state(s, name, monkeypatch):
    """A profile edit committed after page evaluation but before the candidate
    lock must be reflected in every serialized card field, not only the
    discoverability flag."""
    real = services.lock_candidates
    changed = {"done": False}
    new_title = "Updated after pagination"

    def update_then_lock(ids):
        ids = list(ids)
        if not changed["done"] and s.candidate.pk in ids:
            JobSeekerProfile.objects.filter(pk=s.candidate.pk).update(professional_title=new_title)
            changed["done"] = True
        return real(ids)

    monkeypatch.setattr(services, "lock_candidates", update_then_lock)
    resp = _call(s, name, s.recruiter)
    assert resp.status_code == 200, resp.content
    card = _find_card(resp.json(), s.candidate.pk)
    assert card is not None
    assert card["professional_title"] == new_title


def test_invitation_history_refreshes_every_candidate_instance(s, monkeypatch):
    """Two historical invitation rows for the same candidate carry distinct
    select_related profile objects.  Every instance must be synchronized from
    the one authoritative locked profile before the list is serialized."""
    services.cancel_invitation(s.invitation, actor=s.owner)
    services.invite_candidate(s.employer, s.job, s.candidate, actor=s.owner)

    real = services.lock_candidates
    changed = {"done": False}
    new_title = "Updated across invitation history"

    def update_then_lock(ids):
        ids = list(ids)
        if not changed["done"] and s.candidate.pk in ids:
            JobSeekerProfile.objects.filter(pk=s.candidate.pk).update(professional_title=new_title)
            changed["done"] = True
        return real(ids)

    monkeypatch.setattr(services, "lock_candidates", update_then_lock)
    resp = _call(s, "invitation_list", s.recruiter)

    assert resp.status_code == 200, resp.content
    cards = []

    def collect(node):
        if isinstance(node, dict):
            if (
                node.get("id") == str(s.candidate.pk)
                and "professional_title" in node
                and "skills" in node
            ):
                cards.append(node)
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(resp.json())
    assert len(cards) == 2
    assert {card["professional_title"] for card in cards} == {new_title}


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("name", ["search", "detail", "saved_list", "invitation_list", "cancel"])
def test_account_deactivation_waits_until_candidate_response_is_materialized(
    employer_factory, account_factory, job_factory, seeker_factory, name, monkeypatch
):
    """Account.is_active participates in candidate visibility, so an admin-like
    deactivation UPDATE must wait on the Account row lock until serializer.data
    has been fully materialized."""
    employer = employer_factory(plan_code="PROFESSIONAL")
    s = Setup(employer, account_factory, job_factory, seeker_factory)
    state: dict[str, object] = {}
    real = serializers.TalentCardSerializer.to_representation

    def deactivate():
        from apps.accounts.models import Account

        Account.objects.filter(pk=s.candidate.account_id).update(is_active=False)

    def hooked(self, instance):
        if instance.pk == s.candidate.pk and "thread" not in state:
            state["thread"], state["blocked"], state["errors"] = _blocked_writer(deactivate)
        return real(self, instance)

    monkeypatch.setattr(serializers.TalentCardSerializer, "to_representation", hooked)
    resp = _call(s, name, s.recruiter)
    state["thread"].join(timeout=30)

    assert resp.status_code == 200, resp.content
    assert str(s.candidate.pk) in _cards(resp.json())
    assert state["blocked"] is True and not state["errors"], state
    assert s.candidate.account.__class__.objects.get(pk=s.candidate.account_id).is_active is False
