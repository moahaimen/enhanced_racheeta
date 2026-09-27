"""Regression tests for the thirteenth Codex review of PR #4 (commit 5c1bb4b):
Django admin cannot drive the subscription lifecycle, saved candidates honour
the shared visibility rule and are paginated, and talent detail exposes the
employer's own saved-record id for unsaving."""

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from apps.billing import services as billing
from apps.billing.models import Plan, Subscription
from apps.billing.types import Audience, SubjectType, SubscriptionStatus
from apps.jobs import services
from apps.jobs.models import SavedCandidate
from apps.jobs.tests.conftest import owner_of

TALENT = "/api/v1/talent"


# ---- 1. Django admin is inspection only ------------------------------------------


@pytest.fixture
def pending_sub(employer_factory):
    org = employer_factory()
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, org.pk, Audience.EMPLOYER
    )
    return billing.request_subscription(
        account, Plan.objects.get(code="BASIC"), requested_by=owner_of(org)
    )


@pytest.fixture
def django_admin(admin):
    client = Client()
    client.force_login(admin)
    return client


def _change_url(sub):
    return f"/{settings.ADMIN_URL_PATH}billing/subscription/{sub.pk}/change/"


def test_subscription_change_form_has_no_editable_lifecycle_fields(django_admin, pending_sub):
    resp = django_admin.get(_change_url(pending_sub))
    assert resp.status_code == 200
    html = resp.content.decode()
    for field in ("status", "plan", "billing_account", "starts_at_0", "ends_at_0", "requested_by"):
        assert f'name="{field}"' not in html, field
    assert "PENDING" in html and "BASIC" in html  # still inspectable
    assert 'name="admin_note"' in html  # legitimate note stays editable


def test_subscription_cannot_be_activated_or_re_planned_through_django_admin(
    django_admin, pending_sub, admin
):
    pro = Plan.objects.get(code="PROFESSIONAL")
    resp = django_admin.post(
        _change_url(pending_sub),
        {
            "status": SubscriptionStatus.ACTIVE,
            "plan": str(pro.pk),
            "billing_account": str(pending_sub.billing_account_id),
            "starts_at_0": "2020-01-01",
            "starts_at_1": "00:00:00",
            "ends_at_0": "2099-01-01",
            "ends_at_1": "00:00:00",
            "admin_note": "via django admin",
            "events-TOTAL_FORMS": "0",
            "events-INITIAL_FORMS": "0",
            "payments-TOTAL_FORMS": "0",
            "payments-INITIAL_FORMS": "0",
            "_save": "Save",
        },
    )
    assert resp.status_code in (200, 302)
    pending_sub.refresh_from_db()
    assert pending_sub.status == SubscriptionStatus.PENDING
    assert pending_sub.plan.code == "BASIC" and pending_sub.ends_at is None
    assert not pending_sub.events.filter(to_status=SubscriptionStatus.ACTIVE).exists()
    # The service-backed path still works and stays audited.
    billing.activate_subscription(pending_sub, admin=admin, term_days=30)
    pending_sub.refresh_from_db()
    assert pending_sub.status == SubscriptionStatus.ACTIVE


def test_django_admin_cannot_add_or_delete_subscriptions(django_admin, pending_sub):
    add = django_admin.get(f"/{settings.ADMIN_URL_PATH}billing/subscription/add/")
    assert add.status_code == 403
    delete = django_admin.get(
        f"/{settings.ADMIN_URL_PATH}billing/subscription/{pending_sub.pk}/delete/"
    )
    assert delete.status_code == 403
    assert Subscription.objects.filter(pk=pending_sub.pk).exists()


def test_plan_identity_is_frozen_but_prices_stay_editable(django_admin):
    plan = Plan.objects.get(code="BASIC")
    html = django_admin.get(
        f"/{settings.ADMIN_URL_PATH}billing/plan/{plan.pk}/change/"
    ).content.decode()
    assert 'name="code"' not in html and 'name="audience"' not in html
    assert 'name="price_amount"' in html and 'name="is_active"' in html


def test_admin_api_lifecycle_actions_are_unaffected(admin_client, pending_sub):
    resp = admin_client.post(
        f"/api/v1/admin/billing/subscriptions/{pending_sub.id}/activate",
        {"term_days": 30},
        format="json",
    )
    assert resp.status_code == 200 and resp.json()["status"] == "ACTIVE"


# ---- 2 + 3. saved candidates: visibility and pagination --------------------------------


@pytest.fixture
def basic(employer_factory):
    return employer_factory(plan_code="BASIC")


def _saved_ids(api_client, page=1):
    body = api_client.get(f"{TALENT}/saved", {"page": page}).json()
    return body, [r["candidate"]["id"] for r in body["results"]]


def test_hidden_candidate_disappears_and_reappears(api_client, basic, seeker_factory):
    candidate = seeker_factory()
    services.save_candidate(basic, candidate, actor=owner_of(basic))
    api_client.force_authenticate(user=owner_of(basic))
    assert _saved_ids(api_client)[1] == [str(candidate.id)]
    candidate.discoverable_by_employers = False
    candidate.save(update_fields=["discoverable_by_employers"])
    body, ids = _saved_ids(api_client)
    assert ids == [] and body["count"] == 0
    assert SavedCandidate.objects.filter(employer=basic, job_seeker=candidate).exists()  # kept
    candidate.discoverable_by_employers = True
    candidate.save(update_fields=["discoverable_by_employers"])
    assert _saved_ids(api_client)[1] == [str(candidate.id)]


def test_hidden_candidate_who_applied_here_stays_visible_but_not_elsewhere(
    api_client, basic, employer_factory, job_factory, seeker_factory
):
    applicant, other_applicant = seeker_factory(), seeker_factory()
    owner = owner_of(basic)
    services.save_candidate(basic, applicant, actor=owner)
    services.save_candidate(basic, other_applicant, actor=owner)
    services.apply_to_job(job_factory(basic), applicant)
    other = employer_factory(plan_code="BASIC")
    services.apply_to_job(job_factory(other), other_applicant)
    for c in (applicant, other_applicant):
        c.discoverable_by_employers = False
        c.save(update_fields=["discoverable_by_employers"])
    api_client.force_authenticate(user=owner)
    assert _saved_ids(api_client)[1] == [
        str(applicant.id)
    ]  # applied to us → visible; other → hidden


def test_inactive_account_is_hidden_and_other_employers_see_nothing(
    api_client, basic, employer_factory, seeker_factory
):
    candidate = seeker_factory()
    services.save_candidate(basic, candidate, actor=owner_of(basic))
    candidate.account.is_active = False
    candidate.account.save(update_fields=["is_active"])
    api_client.force_authenticate(user=owner_of(basic))
    assert _saved_ids(api_client)[1] == []
    other = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(other))
    assert _saved_ids(api_client)[0]["count"] == 0


def test_saved_candidates_are_paginated_newest_first(api_client, basic, seeker_factory):
    owner = owner_of(basic)
    saved = [services.save_candidate(basic, seeker_factory(), actor=owner) for _ in range(205)]
    for i, row in enumerate(saved):  # deterministic creation order
        SavedCandidate.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timezone.timedelta(minutes=205 - i)
        )
    api_client.force_authenticate(user=owner)
    first, ids1 = _saved_ids(api_client, 1)
    assert first["count"] == 205 and first["next"] and first["previous"] is None
    assert len(ids1) == 20 and ids1[0] == str(saved[-1].job_seeker_id)  # newest first
    page2, ids2 = _saved_ids(api_client, 2)
    assert page2["previous"] and not set(ids1) & set(ids2)
    assert page2["results"][0]["id"] == str(saved[-21].pk)  # older SavedCandidate ids reachable
    last, ids_last = _saved_ids(api_client, 11)
    assert last["next"] is None and len(ids_last) == 5
    assert ids_last[-1] == str(saved[0].job_seeker_id)
    # Privacy and pagination interact: hide five, the count drops accordingly.
    for row in saved[:5]:
        row.job_seeker.discoverable_by_employers = False
        row.job_seeker.save(update_fields=["discoverable_by_employers"])
    assert _saved_ids(api_client)[0]["count"] == 200
    # Older records remain deletable through their ids.
    assert api_client.delete(f"{TALENT}/saved/{saved[0].pk}").status_code == 204


# ---- 4. own saved-record id on talent detail ------------------------------------------


def test_talent_detail_exposes_only_the_callers_saved_record(
    api_client, basic, employer_factory, seeker_factory
):
    candidate = seeker_factory()
    mine = services.save_candidate(basic, candidate, actor=owner_of(basic))
    other = employer_factory(plan_code="BASIC")
    theirs = services.save_candidate(other, candidate, actor=owner_of(other))
    api_client.force_authenticate(user=owner_of(basic))
    detail = api_client.get(f"{TALENT}/{candidate.id}").json()
    assert detail["is_saved"] is True and detail["saved_candidate_id"] == str(mine.pk)
    assert detail["saved_candidate_id"] != str(theirs.pk)
    # DELETE removes only the caller's record; the other organisation's stays.
    assert api_client.delete(f"{TALENT}/saved/{theirs.pk}").status_code == 404
    assert api_client.delete(f"{TALENT}/saved/{mine.pk}").status_code == 204
    detail = api_client.get(f"{TALENT}/{candidate.id}").json()
    assert detail["is_saved"] is False and detail["saved_candidate_id"] is None
    assert SavedCandidate.objects.filter(pk=theirs.pk).exists()


def test_talent_detail_saved_fields_respect_recruiting_and_entitlement_gates(
    api_client, basic, seeker_factory, admin
):
    candidate = seeker_factory()
    services.save_candidate(basic, candidate, actor=owner_of(basic))
    services.set_employer_recruitment_status(basic, "SUSPENDED", admin=admin, reason="x")
    api_client.force_authenticate(user=owner_of(basic))
    assert api_client.get(f"{TALENT}/{candidate.id}").status_code == 403
    assert api_client.get(f"{TALENT}/saved").status_code == 403
