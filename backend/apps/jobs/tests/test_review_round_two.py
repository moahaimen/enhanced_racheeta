"""Regression tests for the second Codex review of PR #4 (commit 267fca0):
contact leaks through detailed_specialty and language names, bounded message
threads, the application-review entitlement on every employer applicant
endpoint, talent quota only after valid filters, and same-row language filters."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import PlanEntitlement, UsageEvent
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import RecruitmentMessage
from apps.jobs.tests.conftest import owner_of
from apps.jobs.tests.test_jobs_lifecycle import draft_payload
from apps.jobs.types import JobStatus, MessageSide

JOBS = "/api/v1/jobs/employer/jobs"
TALENT = "/api/v1/talent"
LEAKS = [
    "person@example.com",
    "07701234567",
    "+964 770 123 4567",
    "https://example.com/me",
    "whatsapp 0770 123 45 67",
    "telegram @nurse_sara",
]


def _disable(plan_code: str, key: str) -> None:
    PlanEntitlement.objects.filter(plan__code=plan_code, key=key).update(enabled=False)


# ---- 1. detailed_specialty ---------------------------------------------------


@pytest.mark.parametrize("leak", LEAKS)
def test_job_detailed_specialty_rejects_contact_info(employer_client, baghdad, leak):
    created = employer_client.post(JOBS, draft_payload(baghdad, detailed_specialty=leak))
    assert created.status_code == 400
    assert created.json()["error"]["codes"]["detailed_specialty"] == [
        "contact_information_not_allowed"
    ]


def test_job_detailed_specialty_accepts_normal_text_and_cannot_bypass_at_submit(
    employer_client, baghdad, employer, job_factory
):
    ok = employer_client.post(
        JOBS, draft_payload(baghdad, detailed_specialty="جراحة القلب المفتوح")
    )
    assert ok.status_code == 201, ok.content
    patched = employer_client.patch(f"{JOBS}/{ok.json()['id']}", {"detailed_specialty": "e@x.io"})
    assert patched.status_code == 400
    # Data that slipped in through another path is still caught by the submit re-scan.
    job = job_factory(employer, status=JobStatus.DRAFT, detailed_specialty="call +9647701234567")
    with pytest.raises(services.ContactLeak):
        services.submit_job_for_review(job, actor=owner_of(employer))
    job.refresh_from_db()
    assert [f["field"] for f in job.moderation_flags] == ["detailed_specialty"]


# ---- 9. language names ------------------------------------------------------


@pytest.mark.parametrize("leak", LEAKS)
def test_language_name_rejects_contact_info(seeker_client, leak):
    resp = seeker_client.post(
        "/api/v1/jobs/me/profile/languages", {"language": leak, "level": "BASIC"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["codes"]["language"] == ["contact_information_not_allowed"]


@pytest.mark.parametrize("name", ["العربية", "English", "Kurdish", "فارسی", "Persian"])
def test_language_name_accepts_legitimate_names(seeker_client, name):
    resp = seeker_client.post(
        "/api/v1/jobs/me/profile/languages", {"language": name, "level": "NATIVE"}
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["language"] == name


# ---- 2. message thread bound -------------------------------------------------


def test_thread_returns_newest_messages_in_chronological_order(
    seeker_client, seeker, employer, employer_client, job_factory, api_client, seeker_factory
):
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    url = f"/api/v1/recruitment/applications/{app_id}/messages"
    application = services.JobApplication.objects.get(pk=app_id)
    base = timezone.now() - timedelta(minutes=30)

    rows = [
        RecruitmentMessage(
            application=application,
            sender=seeker.account,
            sender_side=MessageSide.CANDIDATE,
            body=f"message {i}",
        )
        for i in range(205)
    ]
    created = RecruitmentMessage.objects.bulk_create(rows)
    for i, row in enumerate(created):
        RecruitmentMessage.objects.filter(pk=row.pk).update(created_at=base + timedelta(seconds=i))
    newest = seeker_client.post(url, {"body": "the newest one"})
    assert newest.status_code == 201
    bodies = [m["body"] for m in seeker_client.get(url).json()]
    assert len(bodies) == 200  # bounded
    assert bodies == [f"message {i}" for i in range(6, 205)] + ["the newest one"]  # chronological
    assert "message 0" not in bodies and "message 5" not in bodies  # oldest overflow dropped
    # authorisation is unchanged
    assert [m["body"] for m in employer_client.get(url).json()][-1] == "the newest one"
    api_client.force_authenticate(user=seeker_factory().account)
    assert api_client.get(url).status_code == 404


# ---- 4. application-review entitlement on every employer applicant route ------


@pytest.fixture
def applicant_setup(seeker_client, seeker, employer_factory, job_factory):
    employer = employer_factory()  # TRIAL: review enabled by default
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    return employer, job, app_id


def _routes(job, app_id):
    return {
        "list": ("get", f"{JOBS}/{job.id}/applications", None),
        "detail": ("get", f"/api/v1/jobs/employer/applications/{app_id}", None),
        "transition": (
            "post",
            f"/api/v1/jobs/employer/applications/{app_id}/transition",
            {"status": "SHORTLISTED"},
        ),
        "interview": (
            "post",
            f"/api/v1/jobs/employer/applications/{app_id}/interviews",
            {"proposed_at": "2030-01-01T10:00:00Z", "mode": "IN_PERSON"},
        ),
        "messages_get": ("get", f"/api/v1/recruitment/applications/{app_id}/messages", None),
        "messages_post": (
            "post",
            f"/api/v1/recruitment/applications/{app_id}/messages",
            {"body": "hello"},
        ),
    }


def test_authorised_plan_can_use_every_applicant_route(api_client, applicant_setup):
    employer, job, app_id = applicant_setup
    api_client.force_authenticate(user=owner_of(employer))
    for name, (method, url, body) in _routes(job, app_id).items():
        resp = getattr(api_client, method)(url, body, format="json")
        assert resp.status_code in (200, 201), (name, resp.status_code, resp.content)


def test_plan_without_application_review_is_denied_on_every_route(api_client, applicant_setup):
    employer, job, app_id = applicant_setup
    _disable("TRIAL", Keys.JOBS_APPLICATION_REVIEW)
    api_client.force_authenticate(user=owner_of(employer))
    for name, (method, url, body) in _routes(job, app_id).items():
        resp = getattr(api_client, method)(url, body, format="json")
        assert resp.status_code == 403, (name, resp.status_code, resp.content)
        assert resp.json()["error"]["code"] == "entitlement_required", name
        assert resp.json()["error"]["meta"]["key"] == Keys.JOBS_APPLICATION_REVIEW
    application = services.JobApplication.objects.get(pk=app_id)
    assert application.status == "SUBMITTED" and not application.interviews.exists()


def test_unrelated_organisation_stays_denied_regardless_of_plan(
    api_client, applicant_setup, employer_factory
):
    _, job, app_id = applicant_setup
    other = employer_factory(plan_code="PROFESSIONAL")
    api_client.force_authenticate(user=owner_of(other))
    for name, (method, url, body) in _routes(job, app_id).items():
        resp = getattr(api_client, method)(url, body, format="json")
        assert resp.status_code == 404, (name, resp.status_code)


def test_viewer_role_cannot_act_but_may_read_with_entitlement(
    api_client, seeker_client, employer_factory, job_factory, account_factory
):
    employer = employer_factory(plan_code="BASIC")  # two seats
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    viewer = account_factory()
    services.add_member(employer, viewer, "VIEWER", actor=owner_of(employer))
    api_client.force_authenticate(user=viewer)
    routes = _routes(job, app_id)
    assert api_client.get(routes["detail"][1]).status_code == 200
    assert (
        api_client.post(routes["transition"][1], routes["transition"][2], format="json").status_code
        == 403
    )
    assert (
        api_client.post(
            routes["messages_post"][1], routes["messages_post"][2], format="json"
        ).status_code
        == 404
    )


# ---- 5. talent quota only after valid filters ---------------------------------


def _searches(employer):
    return services.employer_entitlements(employer).get(Keys.TALENT_SEARCH_LIMIT).used


def test_invalid_talent_filters_are_rejected_without_charging(api_client, employer_factory):
    basic = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(basic))
    bad_profession = api_client.get(TALENT, {"profession": "WIZARD"})
    assert (
        bad_profession.status_code == 400
        and "profession" in bad_profession.json()["error"]["details"]
    )
    bad_level = api_client.get(TALENT, {"language": "english", "language_level": "FLUENT"})
    assert bad_level.status_code == 400
    bad_availability = api_client.get(TALENT, {"availability": "SOMETIME"})
    assert bad_availability.status_code == 400
    assert _searches(basic) == 0
    assert not UsageEvent.objects.filter(
        billing_account=services.employer_entitlements(basic).billing_account
    ).exists()
    assert api_client.get(TALENT, {"profession": "NURSE"}).status_code == 200
    assert api_client.get(TALENT, {"profession": "NURSE"}).status_code == 200  # retry, same search
    assert _searches(basic) == 1


# ---- 6. language + level on the same row -------------------------------------


def test_language_and_level_must_match_the_same_row(api_client, employer, seeker_factory):
    mixed = seeker_factory()
    mixed.languages.create(language="English", level="BASIC")
    mixed.languages.create(language="Arabic", level="ADVANCED")
    fluent = seeker_factory()
    fluent.languages.create(language="English", level="ADVANCED")
    fluent.languages.create(language="Arabic", level="NATIVE")
    api_client.force_authenticate(user=owner_of(employer))

    def search(**params):
        body = api_client.get(TALENT, params).json()
        return body["count"], [r["id"] for r in body["results"]]

    assert search(language="english", language_level="ADVANCED") == (1, [str(fluent.id)])
    assert search(language="arabic", language_level="ADVANCED") == (1, [str(mixed.id)])
    count, ids = search(language="english")
    assert count == 2 and set(ids) == {str(mixed.id), str(fluent.id)} and len(ids) == 2
    count, ids = search(language_level="ADVANCED")  # level only: any language at that level
    assert count == 2 and set(ids) == {str(mixed.id), str(fluent.id)} and len(ids) == 2
    assert search(language="kurdish", language_level="ADVANCED") == (0, [])
