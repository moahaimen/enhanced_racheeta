"""Nineteenth Codex review of PR #4 (commit 5c3ebcb): one public-presence rule
for organisations, canonical entitlement shapes, and typed conflicts for
concurrent job-seeker child-row updates."""

import threading

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import Client
from rest_framework.test import APIClient

from apps.billing import services as billing
from apps.billing.models import Plan, PlanEntitlement
from apps.billing.types import Audience, EntitlementKind, Keys, SubjectType, UsagePeriod
from apps.jobs import services
from apps.jobs.models import Employer, LanguageSkill, Skill
from apps.jobs.tests.conftest import owner_of

pytestmark = pytest.mark.django_db


# ---- 1. hiring employer: the public employer rule -------------------------------------


def _states():
    return [
        ("VERIFIED", "ACTIVE", True, True),
        ("VERIFIED", "SUSPENDED", True, False),
        ("UNVERIFIED", "ACTIVE", True, False),
        ("PENDING", "ACTIVE", True, False),
        ("VERIFIED", "ACTIVE", False, False),
    ]


@pytest.mark.parametrize("verification,recruitment,discoverable,visible", _states())
def test_public_page_and_hiring_employer_share_one_rule(
    api_client, employer_factory, job_factory, verification, recruitment, discoverable, visible
):
    agency = employer_factory(is_recruitment_agency=True, name="Agency")
    hiring = employer_factory(name="Hiring org")
    job = job_factory(agency, hiring_employer=hiring)
    Employer.objects.filter(pk=hiring.pk).update(
        verification_status=verification,
        recruitment_status=recruitment,
        is_discoverable=discoverable,
    )
    page = api_client.get(f"/api/v1/employers/{hiring.pk}").status_code
    detail = api_client.get(f"/api/v1/jobs/{job.pk}").json()["hiring_employer"]
    cards = {r["id"]: r for r in api_client.get("/api/v1/jobs").json()["results"]}
    card = cards[str(job.pk)]["hiring_employer"]
    assert (page == 200) is visible
    assert (detail is not None) is visible and (card is not None) is visible
    if visible:
        assert detail["id"] == card["id"] == str(hiring.pk)
    assert Employer.objects.get(pk=hiring.pk).is_public is visible
    assert Employer.objects.public().filter(pk=hiring.pk).exists() is visible


def test_internal_representations_keep_the_hiring_employer(
    admin_client, employer_factory, job_factory, seeker_factory
):
    agency = employer_factory(is_recruitment_agency=True, name="Agency", plan_code="PROFESSIONAL")
    hiring = employer_factory(name="Hiring org")
    job = job_factory(agency, hiring_employer=hiring)
    candidate = seeker_factory()
    inv = services.invite_candidate(agency, job, candidate, actor=owner_of(agency))
    Employer.objects.filter(pk=hiring.pk).update(recruitment_status="SUSPENDED")
    agency_client = APIClient()
    agency_client.force_authenticate(user=owner_of(agency))
    hid = str(hiring.pk)
    assert (
        agency_client.get(f"/api/v1/jobs/employer/jobs/{job.pk}").json()["hiring_employer"]["id"]
        == hid
    )
    assert (
        agency_client.get("/api/v1/talent/invitations").json()["results"][0]["job"][
            "hiring_employer"
        ]["id"]
        == hid
    )
    assert (
        admin_client.get(f"/api/v1/admin/recruitment/jobs/{job.pk}").json()["hiring_employer"]["id"]
        == hid
    )
    # the candidate's own views are public representations
    seeker = APIClient()
    seeker.force_authenticate(user=candidate.account)
    assert (
        seeker.get("/api/v1/jobs/me/invitations").json()["results"][0]["job"]["hiring_employer"]
        is None
    )
    assert (
        agency_client.post(f"/api/v1/talent/invitations/{inv.pk}/cancel").json()["job"][
            "hiring_employer"
        ]["id"]
        == hid
    )


def test_only_public_organisations_can_be_named(employer_factory, job_factory):
    agency = employer_factory(is_recruitment_agency=True, name="Agency")
    suspended = employer_factory(name="Suspended org")
    Employer.objects.filter(pk=suspended.pk).update(recruitment_status="SUSPENDED")
    client = APIClient()
    client.force_authenticate(user=owner_of(agency))
    resp = client.post(
        "/api/v1/jobs/employer/jobs",
        {
            "title": "Nurse",
            "profession": "NURSE",
            "description": "Role",
            "governorate": str(agency.governorate_id),
            "employment_type": "FULL_TIME",
            "hiring_employer": str(suspended.pk),
        },
        format="json",
    )
    assert resp.status_code == 400 and "hiring_employer" in resp.json()["error"]["codes"]


# ---- 2. entitlement shapes ---------------------------------------------------------------


@pytest.fixture
def pro():
    return Plan.objects.get(code="PROFESSIONAL")


def _row(plan, key):
    return PlanEntitlement.objects.get(plan=plan, key=key)


@pytest.mark.parametrize(
    "key,kind,period",
    [
        (Keys.TALENT_SEARCH, EntitlementKind.BOOLEAN, UsagePeriod.NONE),
        (Keys.APPLICATIONS_LIMIT, EntitlementKind.LIMIT, UsagePeriod.MONTHLY),
        (Keys.JOBS_ACTIVE_LIMIT, EntitlementKind.LIMIT, UsagePeriod.NONE),
    ],
)
def test_canonical_shapes_save(pro, key, kind, period):
    plan = (
        pro
        if key != Keys.APPLICATIONS_LIMIT
        else Plan.objects.get(audience=Audience.JOB_SEEKER, is_default=True)
    )
    row = _row(plan, key)
    assert (row.kind, row.period) == (kind, period)
    row.limit = 7 if kind == EntitlementKind.LIMIT else None
    row.enabled = True
    row.save()  # values stay editable
    assert _row(plan, key).enabled is True


@pytest.mark.parametrize(
    "key,change",
    [
        (Keys.APPLICATIONS_LIMIT, {"kind": EntitlementKind.BOOLEAN}),
        (Keys.APPLICATIONS_LIMIT, {"period": UsagePeriod.NONE}),
        (Keys.TALENT_SEARCH, {"kind": EntitlementKind.LIMIT}),
        (Keys.JOBS_ACTIVE_LIMIT, {"period": UsagePeriod.MONTHLY}),
    ],
)
def test_non_canonical_shapes_are_refused_on_save(key, change):
    plan = Plan.objects.filter(entitlements__key=key).first()
    row = _row(plan, key)
    before = (row.kind, row.period)
    for field, value in change.items():
        setattr(row, field, value)
    with pytest.raises(ValidationError) as exc:
        row.save()
    assert set(exc.value.message_dict) == set(change)
    row = _row(plan, key)
    assert (row.kind, row.period) == before
    with pytest.raises(ValidationError):
        PlanEntitlement(
            plan=plan, key=key, **{**dict(zip(("kind", "period"), before, strict=True)), **change}
        ).full_clean()


def test_unknown_keys_keep_a_free_shape(pro):
    PlanEntitlement.objects.create(
        plan=pro, key="custom.flag", kind=EntitlementKind.LIMIT, period=UsagePeriod.DAILY, limit=3
    )


def test_admin_shows_a_validation_error_for_a_wrong_shape(admin, pro):
    client = Client()
    client.force_login(admin)
    row = _row(pro, Keys.TALENT_INVITE_LIMIT)
    rows = list(pro.entitlements.order_by("pk"))
    data = {
        "name_ar": pro.name_ar,
        "name_en": pro.name_en,
        "billing_period": pro.billing_period,
        "term_days": pro.term_days,
        "price_amount": pro.price_amount or "",
        "price_currency": pro.price_currency,
        "is_active": "on",
        "is_public": "on" if pro.is_public else "",
        "sort_order": pro.sort_order,
        "entitlements-TOTAL_FORMS": str(len(rows)),
        "entitlements-INITIAL_FORMS": str(len(rows)),
        "entitlements-MIN_NUM_FORMS": "0",
        "entitlements-MAX_NUM_FORMS": "1000",
    }
    for i, r in enumerate(rows):
        data.update(
            {
                f"entitlements-{i}-id": str(r.pk),
                f"entitlements-{i}-plan": str(pro.pk),
                f"entitlements-{i}-key": r.key,
                f"entitlements-{i}-kind": r.kind,
                f"entitlements-{i}-enabled": "on" if r.enabled else "",
                f"entitlements-{i}-limit": "" if r.limit is None else str(r.limit),
                f"entitlements-{i}-period": r.period,
            }
        )
        if r.pk == row.pk:
            data[f"entitlements-{i}-kind"] = EntitlementKind.BOOLEAN  # the finding's example
    resp = client.post(
        f"/{settings.ADMIN_URL_PATH}billing/plan/{pro.pk}/change/",
        {k: v for k, v in data.items() if v != ""},
    )
    assert resp.status_code == 200 and "LIMIT entitlement" in resp.content.decode()
    assert _row(pro, Keys.TALENT_INVITE_LIMIT).kind == EntitlementKind.LIMIT


def test_quota_cannot_be_bypassed_by_reshaping_a_limit(employer_factory, pro):
    org = employer_factory(plan_code="PROFESSIONAL")
    row = _row(pro, Keys.TALENT_INVITE_LIMIT)
    row.kind = EntitlementKind.BOOLEAN
    with pytest.raises(ValidationError):
        row.save()
    PlanEntitlement.objects.filter(pk=row.pk).update(limit=1)
    ent = billing.entitlements_for(SubjectType.ORGANIZATION, org.pk, Audience.EMPLOYER)
    ent.consume(Keys.TALENT_INVITE_LIMIT, reference="a")
    from apps.billing.exceptions import UsageLimitReached

    with pytest.raises(UsageLimitReached):
        ent.consume(Keys.TALENT_INVITE_LIMIT, reference="b")


def test_every_known_key_row_matches_the_registry():
    from apps.billing.types import KNOWN_KEYS

    for row in PlanEntitlement.objects.all():
        expected = KNOWN_KEYS.get(row.key)
        assert expected is None or (row.kind, row.period) == expected, (row.plan.code, row.key)


# ---- 3. child-row updates: typed conflicts ------------------------------------------------


def _level():
    return LanguageSkill._meta.get_field("level").choices[0][0]


def _client(seeker):
    client = APIClient()
    client.force_authenticate(user=seeker.account)
    return client


def test_skill_patch_succeeds_and_obvious_duplicates_are_refused(seeker):
    client = _client(seeker)
    a = client.post("/api/v1/jobs/me/profile/skills", {"name": "Cardiology"}, format="json").json()
    client.post("/api/v1/jobs/me/profile/skills", {"name": "Surgery"}, format="json")
    assert (
        client.patch(
            f"/api/v1/jobs/me/profile/skills/{a['id']}", {"name": "Echo"}, format="json"
        ).status_code
        == 200
    )
    resp = client.patch(
        f"/api/v1/jobs/me/profile/skills/{a['id']}", {"name": " surgery "}, format="json"
    )
    assert resp.status_code == 400 and resp.json()["error"]["codes"]["name"] == ["duplicate"]


@pytest.mark.parametrize("kind", ["skills", "languages"])
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_renames_to_one_value_never_500(seeker_factory, kind):
    seeker = seeker_factory()
    client = _client(seeker)
    if kind == "skills":
        base, payloads, target = (
            "/api/v1/jobs/me/profile/skills",
            [{"name": "Cardiology"}, {"name": "Surgery"}],
            {"name": "Emergency Medicine"},
        )
    else:
        base, payloads, target = (
            "/api/v1/jobs/me/profile/languages",
            [{"language": "Arabic", "level": _level()}, {"language": "English", "level": _level()}],
            {"language": "Kurdish"},
        )
    ids = [client.post(base, p, format="json").json()["id"] for p in payloads]
    barrier = threading.Barrier(2)
    outcomes: list[int] = []

    def run(pk):
        try:
            barrier.wait(timeout=10)
            c = APIClient()
            c.force_authenticate(user=seeker.account)
            outcomes.append(c.patch(f"{base}/{pk}", target, format="json").status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(pk,)) for pk in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == [200, 400], outcomes
    model = Skill if kind == "skills" else LanguageSkill
    field = "name_normalized" if kind == "skills" else "language_normalized"
    values = list(model.objects.filter(profile=seeker).values_list(field, flat=True))
    assert len(values) == 2 and len(set(values)) == 2


def test_unrelated_integrity_errors_still_propagate(seeker, monkeypatch):
    client = _client(seeker)
    sid = client.post(
        "/api/v1/jobs/me/profile/skills", {"name": "Cardiology"}, format="json"
    ).json()["id"]
    from apps.jobs import serializers as ser

    def broken(self, *args, **kwargs):
        raise IntegrityError("some other constraint")

    monkeypatch.setattr(ser.SkillSerializer, "save", broken)
    with pytest.raises(IntegrityError):
        client.patch(f"/api/v1/jobs/me/profile/skills/{sid}", {"name": "X"}, format="json")
    with pytest.raises(IntegrityError):
        client.post("/api/v1/jobs/me/profile/skills", {"name": "Y"}, format="json")
