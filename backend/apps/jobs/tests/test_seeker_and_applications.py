from datetime import timedelta

import pytest
from django.utils import timezone

from apps.jobs.models import JobApplication
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus

pytestmark = pytest.mark.django_db

PROFILE = "/api/v1/jobs/me/profile"
APPS = "/api/v1/jobs/me/applications"


def profile_payload(baghdad, **over):
    return {
        "professional_title": "Registered Nurse",
        "profession": "NURSE",
        "degree": "BACHELOR",
        "governorate": str(baghdad.id),
        "years_of_experience": 4,
        "professional_summary": "ICU experience.",
        "employment_preferences": ["FULL_TIME", "PART_TIME"],
        "availability": "IMMEDIATE",
        **over,
    }


def test_create_profile_and_children(api_client, account_factory, baghdad, cardiology):
    api_client.force_authenticate(user=account_factory())
    assert api_client.get(PROFILE).status_code == 404
    created = api_client.post(
        PROFILE, profile_payload(baghdad, general_specialty=str(cardiology.id))
    )
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["discoverable_by_employers"] is False  # privacy-first default
    assert body["general_specialty"]["slug"] == "cardiology"
    for hidden in ("email", "phone_number", "account", "firebase_uid"):
        assert hidden not in body
    assert api_client.post(PROFILE, profile_payload(baghdad)).status_code == 400
    exp = api_client.post(
        f"{PROFILE}/experiences",
        {
            "title": "Staff nurse",
            "organization_name": "Medical City",
            "start_date": "2020-01-01",
            "end_date": "2023-06-30",
        },
    )
    assert exp.status_code == 201
    assert (
        api_client.post(
            f"{PROFILE}/experiences",
            {
                "title": "x",
                "organization_name": "y",
                "start_date": "2022-01-01",
                "end_date": "2021-01-01",
            },
        ).status_code
        == 400
    )
    assert api_client.post(f"{PROFILE}/skills", {"name": "Ventilator care"}).status_code == 201
    assert (
        api_client.post(f"{PROFILE}/skills", {"name": "ventilator  CARE"}).status_code == 400
    )  # duplicate after normalisation
    assert (
        api_client.post(
            f"{PROFILE}/languages", {"language": "English", "level": "ADVANCED"}
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            f"{PROFILE}/credentials",
            {
                "kind": "LICENSE",
                "name": "Nursing licence",
                "issuer": "Ministry of Health",
                "year": 2019,
            },
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            f"{PROFILE}/education",
            {
                "degree": "BACHELOR",
                "field_of_study": "Nursing",
                "institution_name": "University of Baghdad",
                "end_year": 2019,
            },
        ).status_code
        == 201
    )
    me = api_client.get(PROFILE).json()
    assert (
        len(me["experiences"]) == 1
        and me["skills"][0]["name"] == "Ventilator care"
        and me["languages"][0]["level"] == "ADVANCED"
    )
    exp_id = exp.json()["id"]
    assert (
        api_client.patch(
            f"{PROFILE}/experiences/{exp_id}", {"is_current": True, "end_date": None}
        ).status_code
        == 200
    )
    assert api_client.delete(f"{PROFILE}/experiences/{exp_id}").status_code == 204


def test_profile_text_fields_reject_contact_info(api_client, account_factory, baghdad):
    api_client.force_authenticate(user=account_factory())
    bad = api_client.post(
        PROFILE,
        profile_payload(
            baghdad, professional_summary="Reach me on telegram @nurse_ali or t.me/nurse"
        ),
    )
    assert bad.status_code == 400 and bad.json()["error"]["codes"]["professional_summary"] == [
        "contact_information_not_allowed"
    ]


def test_children_are_owner_scoped(api_client, seeker_factory):
    mine = seeker_factory()
    other = seeker_factory()
    api_client.force_authenticate(user=mine.account)
    api_client.post(f"{PROFILE}/skills", {"name": "Suturing"})
    api_client.force_authenticate(user=other.account)
    assert api_client.get(f"{PROFILE}/skills").json() == []
    skill_id = str(mine.skills.first().id)
    assert api_client.delete(f"{PROFILE}/skills/{skill_id}").status_code == 404


def test_no_file_fields_exist():
    from django.db import models

    from apps.jobs import models as jobs_models

    for model in [
        jobs_models.JobSeekerProfile,
        jobs_models.JobPost,
        jobs_models.JobApplication,
        jobs_models.Employer,
        jobs_models.Credential,
    ]:
        assert not any(
            isinstance(f, models.FileField)
            for f in model._meta.get_fields()
            if hasattr(f, "get_internal_type")
        ), model


# ---- applications ---------------------------------------------------------


def test_apply_snapshot_and_my_applications(seeker_client, seeker, employer, job_factory):
    job = job_factory(employer)
    seeker.skills.create(name="Triage")
    response = seeker_client.post(
        f"/api/v1/jobs/{job.id}/apply", {"cover_text": "Available immediately."}
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert (
        body["status"] == "SUBMITTED"
        and body["snapshot"]["skills"] == ["Triage"]
        and body["snapshot"]["professional_title"] == seeker.professional_title
    )
    assert "email" not in body["snapshot"]
    # profile changes after applying do not rewrite the snapshot
    seeker.professional_title = "Head Nurse"
    seeker.save()
    listed = seeker_client.get(APPS).json()
    assert (
        listed["count"] == 1
        and listed["results"][0]["snapshot"]["professional_title"] != "Head Nurse"
    )
    assert listed["results"][0]["job"]["employer"]["name"] == employer.name
    assert listed["results"][0]["transitions"][0]["to_status"] == "SUBMITTED"


def test_duplicate_application_blocked_and_allowed_after_withdraw(
    seeker_client, employer, job_factory
):
    job = job_factory(employer)
    first = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()
    dup = seeker_client.post(f"/api/v1/jobs/{job.id}/apply")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_applied"
    withdrawn = seeker_client.post(
        f"{APPS}/{first['id']}/withdraw", {"reason": "found another job"}
    )
    assert withdrawn.json()["status"] == "WITHDRAWN"
    assert seeker_client.post(f"{APPS}/{first['id']}/withdraw").status_code == 400
    assert seeker_client.post(f"/api/v1/jobs/{job.id}/apply").status_code == 201


def test_apply_requires_open_job_and_profile(
    api_client, account_factory, seeker_client, employer, job_factory, employer_factory
):
    closed = job_factory(employer, status=JobStatus.CLOSED)
    assert seeker_client.post(f"/api/v1/jobs/{closed.id}/apply").status_code == 404
    overdue = job_factory(employer, application_deadline=timezone.localdate() - timedelta(days=1))
    assert seeker_client.post(f"/api/v1/jobs/{overdue.id}/apply").status_code in (404, 409)
    suspended_employer = employer_factory()
    from apps.jobs import services

    job = job_factory(suspended_employer)
    services.set_employer_recruitment_status(
        suspended_employer, "SUSPENDED", admin=owner_of(employer)
    )
    assert seeker_client.post(f"/api/v1/jobs/{job.id}/apply").status_code == 404
    api_client.force_authenticate(user=account_factory())
    assert api_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply").status_code == 403


def test_application_limit_for_seekers(seeker_client, seeker, employer, job_factory):
    from apps.billing.models import PlanEntitlement

    PlanEntitlement.objects.filter(plan__code="SEEKER_FREE", key="applications.limit").update(
        limit=2
    )
    for _ in range(2):
        assert (
            seeker_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply").status_code == 201
        )
    blocked = seeker_client.post(f"/api/v1/jobs/{job_factory(employer).id}/apply")
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "usage_limit_reached"
    assert JobApplication.objects.filter(job_seeker=seeker).count() == 2


def test_cover_text_contact_leak(seeker_client, employer, job_factory):
    bad = seeker_client.post(
        f"/api/v1/jobs/{job_factory(employer).id}/apply", {"cover_text": "my number 0770 123 4567"}
    )
    assert bad.status_code == 400 and bad.json()["error"]["codes"]["cover_text"] == [
        "contact_information_not_allowed"
    ]


def test_employer_reviews_applicants_and_transitions(
    seeker_client, seeker, employer, employer_client, job_factory, api_client, employer_factory
):
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    listed = employer_client.get(f"/api/v1/jobs/employer/jobs/{job.id}/applications").json()
    assert listed["count"] == 1
    candidate = listed["results"][0]["candidate"]
    assert candidate["professional_title"] == seeker.professional_title
    for hidden in ("email", "phone_number", "account", "full_name"):
        assert hidden not in candidate and hidden not in listed["results"][0]
    assert (
        employer_client.get(f"/api/v1/jobs/employer/jobs/{job.id}").json()["applications_count"]
        == 1
    )
    url = f"/api/v1/jobs/employer/applications/{app_id}/transition"
    assert (
        employer_client.post(url, {"status": "ACCEPTED"}).status_code == 400
    )  # SUBMITTED -> ACCEPTED not allowed
    assert employer_client.post(url, {"status": "REVIEWING"}).json()["status"] == "REVIEWING"
    assert employer_client.post(url, {"status": "SHORTLISTED"}).json()["status"] == "SHORTLISTED"
    interview = employer_client.post(
        f"/api/v1/jobs/employer/applications/{app_id}/interviews",
        {
            "proposed_at": (timezone.now() + timedelta(days=2)).isoformat(),
            "mode": "IN_PERSON",
            "location_text": "HR office, 2nd floor",
            "note": "Bring your licence",
        },
    )
    assert interview.status_code == 201, interview.content
    assert (
        employer_client.get(f"/api/v1/jobs/employer/applications/{app_id}").json()["status"]
        == "INTERVIEW"
    )
    # candidate answers
    reply = seeker_client.post(
        f"/api/v1/jobs/me/interviews/{interview.json()['id']}/respond",
        {"accept": True, "response": "See you then"},
    )
    assert reply.status_code == 200 and reply.json()["status"] == "ACCEPTED"
    assert (
        employer_client.post(url, {"status": "ACCEPTED", "reason": "welcome"}).json()["status"]
        == "ACCEPTED"
    )
    history = [t["to_status"] for t in seeker_client.get(f"{APPS}/{app_id}").json()["transitions"]]
    assert history == ["SUBMITTED", "REVIEWING", "SHORTLISTED", "INTERVIEW", "ACCEPTED"]
    # accepted applications cannot be withdrawn; other employers cannot see it
    assert seeker_client.post(f"{APPS}/{app_id}/withdraw").status_code == 400
    other = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(other))
    assert api_client.get(f"/api/v1/jobs/employer/applications/{app_id}").status_code == 404
    assert api_client.post(url, {"status": "REJECTED"}).status_code == 404


def test_interview_location_and_reason_reject_contact_info(
    seeker_client, employer, employer_client, job_factory
):
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    employer_client.post(
        f"/api/v1/jobs/employer/applications/{app_id}/transition", {"status": "SHORTLISTED"}
    )
    bad = employer_client.post(
        f"/api/v1/jobs/employer/applications/{app_id}/interviews",
        {
            "proposed_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "mode": "ONLINE",
            "location_text": "https://meet.example.com/abc",
        },
    )
    assert bad.status_code == 400 and bad.json()["error"]["codes"]["location_text"] == [
        "contact_information_not_allowed"
    ]


def test_recruitment_messages_scoped_to_parties(
    seeker_client,
    seeker,
    employer,
    employer_client,
    job_factory,
    api_client,
    seeker_factory,
    employer_factory,
):
    job = job_factory(employer)
    app_id = seeker_client.post(f"/api/v1/jobs/{job.id}/apply").json()["id"]
    url = f"/api/v1/recruitment/applications/{app_id}/messages"
    sent = employer_client.post(
        url, {"body": "Thanks for applying. Are you available for a night shift?"}
    )
    assert sent.status_code == 201 and sent.json()["sender_side"] == "EMPLOYER"
    reply = seeker_client.post(url, {"body": "Yes, from next week."})
    assert reply.json()["sender_side"] == "CANDIDATE"
    assert [m["sender_side"] for m in seeker_client.get(url).json()] == ["EMPLOYER", "CANDIDATE"]
    leak = seeker_client.post(url, {"body": "call me 07701234567"})
    assert leak.status_code == 400 and leak.json()["error"]["codes"]["body"] == [
        "contact_information_not_allowed"
    ]
    # strangers: another seeker and another employer
    api_client.force_authenticate(user=seeker_factory().account)
    assert (
        api_client.get(url).status_code == 404
        and api_client.post(url, {"body": "hi"}).status_code == 404
    )
    api_client.force_authenticate(user=owner_of(employer_factory(plan_code="BASIC")))
    assert api_client.get(url).status_code == 404
    # no edit/delete endpoints exist for messages
    assert api_client.patch(url, {}).status_code in (404, 405)
