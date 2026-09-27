"""Regression tests for the fourteenth Codex review of PR #4 (commit 1daeec7):
exact experience bounds in the billing signature, sent invitations honouring
the shared candidate visibility rule, and paginated sent invitations."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import JobInvitation
from apps.jobs.services import search_signature
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import InvitationStatus

TALENT = "/api/v1/talent"
pytestmark = pytest.mark.django_db


# ---- 1. experience bounds ----------------------------------------------------------


def test_fractional_experience_is_rejected_and_never_billed(api_client, employer_factory):
    basic = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(basic))
    for value in ("5.9", "5.5", "abc"):
        resp = api_client.get(TALENT, {"min_experience": value})
        assert resp.status_code == 400, value
        assert "min_experience" in resp.json()["error"]["details"], value
    assert api_client.get(TALENT, {"max_experience": "2.5"}).status_code == 400
    assert services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used == 0
    assert api_client.get(TALENT, {"min_experience": "5"}).status_code == 200
    assert api_client.get(TALENT, {"min_experience": "05"}).status_code == 200  # same search
    assert api_client.get(TALENT, {"min_experience": "5.0"}).status_code == 200  # parsed as 5
    assert services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used == 1
    assert api_client.get(TALENT, {"min_experience": "6"}).status_code == 200  # a different one
    assert services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used == 2


def test_public_job_search_rejects_fractional_experience_too(api_client):
    assert api_client.get("/api/v1/jobs", {"min_experience": "1.5"}).status_code == 400
    assert api_client.get("/api/v1/jobs", {"min_experience": "1"}).status_code == 200


def test_signature_is_exact_for_experience_and_order_independent():
    assert search_signature({"min_experience": "5"}) == search_signature({"min_experience": "05"})
    assert search_signature({"min_experience": "5"}) == search_signature({"min_experience": "5.0"})
    assert search_signature({"min_experience": "5"}) != search_signature({"min_experience": "5.9"})
    assert search_signature({"min_experience": "5"}) != search_signature({"min_experience": "6"})
    assert search_signature({"min_experience": "5"}) != search_signature({"max_experience": "5"})
    assert search_signature({"min_experience": "5", "skill": "icu"}) == search_signature(
        {"skill": "ICU ", "min_experience": " 5"}
    )
    assert search_signature({"min_experience": "5", "max_experience": ""}) == search_signature(
        {"min_experience": "5"}
    )


# ---- 2 + 3. sent invitations: visibility and pagination --------------------------------


@pytest.fixture
def basic(employer_factory):
    return employer_factory(plan_code="BASIC")


def _sent(api_client, page=1):
    body = api_client.get(f"{TALENT}/invitations", {"page": page}).json()
    return body, [r["candidate"]["id"] for r in body["results"]]


def _invite(employer, job, candidate):
    return services.invite_candidate(employer, job, candidate, actor=owner_of(employer))


def test_hidden_invited_candidate_disappears_and_reappears(
    api_client, basic, job_factory, seeker_factory
):
    job, candidate = job_factory(basic), seeker_factory()
    inv = _invite(basic, job, candidate)
    api_client.force_authenticate(user=owner_of(basic))
    assert _sent(api_client)[1] == [str(candidate.id)]
    candidate.discoverable_by_employers = False
    candidate.save(update_fields=["discoverable_by_employers"])
    body, ids = _sent(api_client)
    assert ids == [] and body["count"] == 0
    inv.refresh_from_db()
    assert inv.status == InvitationStatus.PENDING  # stored, untouched
    candidate.discoverable_by_employers = True
    candidate.save(update_fields=["discoverable_by_employers"])
    assert _sent(api_client)[1] == [str(candidate.id)]


def test_hidden_candidate_with_application_here_stays_but_elsewhere_does_not(
    api_client, basic, employer_factory, job_factory, seeker_factory
):
    ours, theirs = seeker_factory(), seeker_factory()
    job = job_factory(basic)
    _invite(basic, job, ours)
    _invite(basic, job, theirs)
    services.apply_to_job(job_factory(basic), ours)
    other = employer_factory(plan_code="BASIC")
    services.apply_to_job(job_factory(other), theirs)
    for c in (ours, theirs):
        c.discoverable_by_employers = False
        c.save(update_fields=["discoverable_by_employers"])
    api_client.force_authenticate(user=owner_of(basic))
    assert _sent(api_client)[1] == [str(ours.id)]
    # The other organisation gains nothing through our invitation.
    api_client.force_authenticate(user=owner_of(other))
    assert _sent(api_client)[0]["count"] == 0


def test_inactive_candidate_hidden_and_gates_enforced(
    api_client, basic, job_factory, seeker_factory, admin
):
    candidate = seeker_factory()
    _invite(basic, job_factory(basic), candidate)
    candidate.account.is_active = False
    candidate.account.save(update_fields=["is_active"])
    api_client.force_authenticate(user=owner_of(basic))
    assert _sent(api_client)[0]["count"] == 0
    services.set_employer_recruitment_status(basic, "SUSPENDED", admin=admin, reason="x")
    assert api_client.get(f"{TALENT}/invitations").status_code == 403


def test_sent_invitations_are_paginated_newest_first(
    api_client, basic, job_factory, seeker_factory
):
    job = job_factory(basic)
    owner = owner_of(basic)
    now = timezone.now()
    rows = JobInvitation.objects.bulk_create(
        [
            JobInvitation(
                employer=basic,
                job=job,
                job_seeker=seeker_factory(),
                created_by=owner,
                expires_at=now + timedelta(days=14),
            )
            for _ in range(205)
        ]
    )
    for i, row in enumerate(rows):  # deterministic creation order
        JobInvitation.objects.filter(pk=row.pk).update(created_at=now - timedelta(minutes=205 - i))
    api_client.force_authenticate(user=owner)
    first, ids1 = _sent(api_client, 1)
    assert first["count"] == 205 and first["next"] and first["previous"] is None
    assert len(ids1) == 20 and ids1[0] == str(rows[-1].job_seeker_id)  # newest first
    page2, ids2 = _sent(api_client, 2)
    assert page2["previous"] and not set(ids1) & set(ids2)
    assert page2["results"][0]["id"] == str(rows[-21].pk)  # older invitation ids reachable
    last, ids_last = _sent(api_client, 11)
    assert last["next"] is None and len(ids_last) == 5
    assert ids_last[-1] == str(rows[0].job_seeker_id)  # beyond the old 200 limit
    hidden = rows[0].job_seeker
    hidden.discoverable_by_employers = False
    hidden.save(update_fields=["discoverable_by_employers"])
    body, _ = _sent(api_client, 11)
    assert body["count"] == 204 and len(body["results"]) == 4
    assert all(r["candidate"]["id"] != str(hidden.id) for r in body["results"])
