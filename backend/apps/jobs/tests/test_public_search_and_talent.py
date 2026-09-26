import pytest

from apps.billing import services as billing
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import JobInvitation, TalentSearchQuery
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus

pytestmark = pytest.mark.django_db

LIST = "/api/v1/jobs"
TALENT = "/api/v1/talent"


def test_public_search_filters(
    api_client, employer, employer_factory, job_factory, baghdad, basra, cardiology
):
    a = job_factory(
        employer,
        title="Cardiology nurse",
        profession="NURSE",
        general_specialty=cardiology,
        employment_type="FULL_TIME",
        minimum_experience_years=2,
        salary_visible=True,
        salary_min="1000000",
    )
    b = job_factory(
        employer,
        title="Pharmacist",
        profession="PHARMACIST",
        governorate=basra,
        employment_type="PART_TIME",
        work_mode="REMOTE",
        shift_type="NIGHT",
        minimum_degree="MASTER",
    )
    job_factory(employer, status=JobStatus.DRAFT, title="Hidden draft")
    job_factory(employer_factory(verified=False), title="Unverified employer job")
    job_factory(employer, status=JobStatus.SUSPENDED, title="Suspended")

    def titles(**params):
        return sorted(r["title"] for r in api_client.get(LIST, params).json()["results"])

    assert titles() == ["Cardiology nurse", "Pharmacist"]
    assert titles(profession="NURSE") == ["Cardiology nurse"]
    assert titles(specialty="cardiology") == ["Cardiology nurse"]
    assert titles(governorate=str(basra.id)) == ["Pharmacist"]
    assert titles(employment_type="PART_TIME") == ["Pharmacist"]
    assert titles(work_mode="REMOTE") == ["Pharmacist"]
    assert titles(shift_type="NIGHT") == ["Pharmacist"]
    assert titles(degree="MASTER") == ["Pharmacist"]
    assert titles(min_experience=1) == ["Cardiology nurse"]
    assert titles(max_experience=0) == ["Pharmacist"]
    assert titles(salary_available="true") == ["Cardiology nurse"]
    assert titles(q="pharm") == ["Pharmacist"]
    assert titles(q=employer.name) == ["Cardiology nurse", "Pharmacist"]
    detail = api_client.get(f"{LIST}/{a.id}").json()
    assert detail["is_open"] is True and detail["employer"]["is_verified"] is True
    assert "email" not in str(detail) and "phone" not in str(detail)
    assert api_client.get(f"{LIST}/{b.id}").json()["salary_min"] is None  # hidden salary
    assert api_client.get(LIST, {"profession": "WIZARD"}).status_code == 400


def test_featured_first_then_newest_and_query_count(
    api_client, employer, job_factory, django_assert_max_num_queries
):
    for i in range(6):
        job_factory(employer, title=f"Job {i}")
    featured = job_factory(employer, title="Featured", is_featured=True)
    with django_assert_max_num_queries(4):
        body = api_client.get(LIST).json()
    assert body["results"][0]["id"] == str(featured.id)
    assert body["count"] == 7


def test_talent_search_requires_entitlement_and_charges_once_per_signature(
    api_client, employer_factory, seeker_factory, seeker, admin
):
    seeker_factory(discoverable=False)
    trial = employer_factory()
    api_client.force_authenticate(user=owner_of(trial))
    denied = api_client.get(TALENT)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "entitlement_required"
    basic = employer_factory(plan_code="BASIC")  # 20 searches / month
    api_client.force_authenticate(user=owner_of(basic))
    body = api_client.get(TALENT, {"profession": "NURSE"}).json()
    assert body["count"] == 1  # only discoverable
    card = body["results"][0]
    for hidden in ("email", "phone_number", "account", "full_name", "is_staff"):
        assert hidden not in card
    api_client.get(TALENT, {"profession": "NURSE", "page": 2})  # paging: same search
    api_client.get(TALENT, {"profession": "NURSE"})  # retry: same search
    api_client.get(TALENT, {"profession": "PHARMACIST"})  # new search
    used = services.employer_entitlements(basic).get(Keys.TALENT_SEARCH_LIMIT).used
    assert used == 2 and TalentSearchQuery.objects.filter(employer=basic).count() == 2


def test_talent_search_limit_blocks(api_client, employer_factory):
    basic = employer_factory(plan_code="BASIC")
    api_client.force_authenticate(user=owner_of(basic))
    from apps.billing.models import PlanEntitlement

    PlanEntitlement.objects.filter(plan__code="BASIC", key=Keys.TALENT_SEARCH_LIMIT).update(limit=1)
    assert api_client.get(TALENT, {"q": "a"}).status_code == 200
    blocked = api_client.get(TALENT, {"q": "b"})
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "usage_limit_reached"


def test_talent_filters(api_client, employer, seeker_factory, baghdad, basra, cardiology):
    nurse = seeker_factory(
        profession="NURSE",
        degree="BACHELOR",
        years_of_experience=5,
        governorate=baghdad,
        employment_preferences=["FULL_TIME"],
        availability="IMMEDIATE",
        general_specialty=cardiology,
    )
    nurse.skills.create(name="Ventilator care")
    nurse.languages.create(language="English", level="ADVANCED")
    pharm = seeker_factory(
        profession="PHARMACIST",
        degree="MASTER",
        years_of_experience=1,
        governorate=basra,
        employment_preferences=["PART_TIME"],
    )
    api_client.force_authenticate(user=owner_of(employer))

    def ids(**params):
        return {r["id"] for r in api_client.get(TALENT, params).json()["results"]}

    assert ids(profession="NURSE") == {str(nurse.id)}
    assert ids(specialty="cardiology") == {str(nurse.id)}
    assert ids(degree="MASTER") == {str(pharm.id)}
    assert ids(degree="BACHELOR") == {str(nurse.id), str(pharm.id)}
    assert ids(min_experience=3) == {str(nurse.id)}
    assert ids(governorate=str(basra.id)) == {str(pharm.id)}
    assert ids(skill="ventilator care") == {str(nurse.id)}
    assert ids(language="english", language_level="advanced") == {str(nurse.id)}
    assert ids(availability="IMMEDIATE") == {str(nurse.id)}
    assert ids(employment_type="PART_TIME") == {str(pharm.id)}


def test_talent_detail_saved_and_invite(api_client, employer, seeker, seeker_factory, job_factory):
    api_client.force_authenticate(user=owner_of(employer))
    detail = api_client.get(f"{TALENT}/{seeker.id}").json()
    assert detail["is_saved"] is False and "email" not in detail
    hidden = seeker_factory(discoverable=False)
    assert api_client.get(f"{TALENT}/{hidden.id}").status_code == 404
    saved = api_client.post(
        f"{TALENT}/saved", {"job_seeker": str(seeker.id), "note": "strong ICU background"}
    )
    assert saved.status_code == 201
    assert api_client.post(f"{TALENT}/saved", {"job_seeker": str(seeker.id)}).status_code == 409
    assert api_client.post(f"{TALENT}/saved", {"job_seeker": str(hidden.id)}).status_code == 404
    assert api_client.get(f"{TALENT}/{seeker.id}").json()["is_saved"] is True
    job = job_factory(employer)
    invite = api_client.post(
        f"{TALENT}/invitations",
        {
            "job": str(job.id),
            "job_seeker": str(seeker.id),
            "message": "We would like you to apply.",
        },
    )
    assert invite.status_code == 201, invite.content
    dup = api_client.post(
        f"{TALENT}/invitations", {"job": str(job.id), "job_seeker": str(seeker.id)}
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_invited"
    assert services.employer_entitlements(employer).get(Keys.TALENT_INVITE_LIMIT).used == 1
    leak = api_client.post(
        f"{TALENT}/invitations",
        {
            "job": str(job_factory(employer).id),
            "job_seeker": str(seeker.id),
            "message": "wa.me/9647701234567",
        },
    )
    assert leak.status_code == 400
    # candidate sees it, accepting does not auto-apply
    api_client.force_authenticate(user=seeker.account)
    mine = api_client.get("/api/v1/jobs/me/invitations").json()
    assert mine["count"] == 1 and mine["results"][0]["job"]["title"] == job.title
    accepted = api_client.post(
        f"/api/v1/jobs/me/invitations/{invite.json()['id']}/respond", {"accept": True}
    )
    assert accepted.json()["status"] == "ACCEPTED"
    assert not job.applications.exists()
    # saved list and cancel are org-scoped
    api_client.force_authenticate(user=owner_of(employer))
    assert api_client.get(f"{TALENT}/saved").json()["count"] == 1


def test_invite_quota_and_isolation(api_client, employer_factory, seeker, job_factory):
    basic = employer_factory(plan_code="BASIC")
    other = employer_factory(plan_code="BASIC")
    from apps.billing.models import PlanEntitlement

    PlanEntitlement.objects.filter(plan__code="BASIC", key=Keys.TALENT_INVITE_LIMIT).update(limit=1)
    api_client.force_authenticate(user=owner_of(basic))
    j1, j2 = job_factory(basic), job_factory(basic)
    assert (
        api_client.post(
            f"{TALENT}/invitations", {"job": str(j1.id), "job_seeker": str(seeker.id)}
        ).status_code
        == 201
    )
    blocked = api_client.post(
        f"{TALENT}/invitations", {"job": str(j2.id), "job_seeker": str(seeker.id)}
    )
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "usage_limit_reached"
    assert JobInvitation.objects.count() == 1
    other_job = job_factory(other)
    assert (
        api_client.post(
            f"{TALENT}/invitations", {"job": str(other_job.id), "job_seeker": str(seeker.id)}
        ).status_code
        == 404
    )
    api_client.force_authenticate(user=owner_of(other))
    assert api_client.get(f"{TALENT}/invitations").json()["results"] == []


def test_applied_candidate_visible_to_that_employer_only(
    api_client, employer, employer_factory, seeker_factory, job_factory
):
    private = seeker_factory(discoverable=False)
    job = job_factory(employer)
    services.apply_to_job(job, private)
    api_client.force_authenticate(user=owner_of(employer))
    assert api_client.get(f"{TALENT}/{private.id}").status_code == 200
    api_client.force_authenticate(user=owner_of(employer_factory(plan_code="BASIC")))
    assert api_client.get(f"{TALENT}/{private.id}").status_code == 404


def test_talent_search_query_count(
    api_client, employer, seeker_factory, django_assert_max_num_queries
):
    for i in range(8):
        s = seeker_factory()
        s.skills.create(name=f"skill {i}")
    api_client.force_authenticate(user=owner_of(employer))
    api_client.get(TALENT)  # first call records the search
    # Rounds twenty-six/seven: the charge is serialised like a write — employer
    # row, actor membership and billing account are each locked (three
    # SELECT ... FOR UPDATE) and the charge plus the listing run in one
    # transaction (savepoint pair), so authorisation and disclosure use
    # committed state.
    with django_assert_max_num_queries(17):
        assert api_client.get(TALENT).json()["count"] == 8


def test_billing_account_admin_view_reflects_usage(admin_client, employer):
    acc = billing.get_or_create_billing_account("organization", employer.pk, "EMPLOYER")
    services.employer_entitlements(employer).consume(Keys.TALENT_SEARCH_LIMIT, reference="x")
    body = admin_client.get(f"/api/v1/admin/billing/accounts/{acc.id}").json()
    assert (
        next(e for e in body["entitlements"] if e["key"] == Keys.TALENT_SEARCH_LIMIT)["used"] == 1
    )
