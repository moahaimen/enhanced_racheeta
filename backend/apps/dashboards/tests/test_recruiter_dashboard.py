"""Recruiter dashboard: organisation membership, verification, seats and entitlements."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboards.services import recruiter as recruiter_services
from apps.jobs.models import EmployerMembership
from apps.jobs.types import JobStatus, MemberRole, MemberStatus, RecruitmentStatus
from apps.jobs.types import VerificationStatus as EmployerVerification

from .conftest import DASH, client_for

RECRUITER = f"{DASH}/recruiter"


@pytest.mark.django_db
def test_requires_an_active_membership(patient, provider_factory, company_factory, admin):
    for account in (patient, provider_factory().account, company_factory().account, admin):
        assert client_for(account).get(RECRUITER).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", [MemberRole.OWNER, MemberRole.RECRUITER, MemberRole.VIEWER])
def test_every_member_role_can_read_its_own_organisations_dashboard(
    employer_factory, member_factory, role
):
    employer, owner = employer_factory()
    account = owner if role == MemberRole.OWNER else member_factory(employer, role)
    body = client_for(account).get(RECRUITER).json()
    assert body["organization"]["id"] == str(employer.pk)
    assert body["organization"]["my_role"] == role


@pytest.mark.django_db
def test_an_ended_membership_loses_access_immediately(employer_factory, member_factory):
    employer, _ = employer_factory()
    member = member_factory(employer, MemberRole.RECRUITER)
    client = client_for(member)
    assert client.get(RECRUITER).status_code == 200
    EmployerMembership.objects.filter(account=member).update(status=MemberStatus.ENDED)
    assert client.get(RECRUITER).status_code == 403


@pytest.mark.django_db
def test_jobs_and_applications_are_counted_per_status_and_isolated_per_organisation(
    employer_factory, job_factory, application_factory
):
    employer, owner = employer_factory()
    other, other_owner = employer_factory()
    today = timezone.localdate()
    open_job = job_factory(employer, owner, JobStatus.PUBLISHED)
    job_factory(employer, owner, JobStatus.PUBLISHED, application_deadline=today)  # last open day
    job_factory(
        employer, owner, JobStatus.PUBLISHED, application_deadline=today - timedelta(days=1)
    )  # published but past deadline
    job_factory(employer, owner, JobStatus.DRAFT)
    job_factory(employer, owner, JobStatus.PENDING_ADMIN_REVIEW)
    job_factory(employer, owner, JobStatus.CLOSED)
    foreign = job_factory(other, other_owner, JobStatus.PUBLISHED)
    for _ in range(4):
        application_factory(foreign, "SUBMITTED")  # another organisation's applicants

    for status in (
        "SUBMITTED",
        "SUBMITTED",
        "REVIEWING",
        "SHORTLISTED",
        "INTERVIEW",
        "ACCEPTED",
        "REJECTED",
        "WITHDRAWN",
    ):
        application_factory(open_job, status)

    body = client_for(owner).get(RECRUITER).json()
    assert body["jobs"]["total"] == 6
    assert body["jobs"]["by_status"]["PUBLISHED"] == 3
    assert body["jobs"]["by_status"]["DRAFT"] == 1
    assert body["jobs"]["by_status"]["PENDING_ADMIN_REVIEW"] == 1
    assert body["jobs"]["open_now"] == 2  # past-deadline job is published but not open
    assert body["applications_access"] is None
    apps = body["applications"]
    assert apps["total"] == 8
    assert apps["awaiting_review"] == 2 == apps["by_status"]["SUBMITTED"]
    assert apps["by_status"]["REVIEWING"] == 1 and apps["by_status"]["WITHDRAWN"] == 1


@pytest.mark.django_db
def test_recent_applications_use_a_seven_day_boundary(
    employer_factory, job_factory, application_factory
):
    employer, owner = employer_factory()
    job = job_factory(employer, owner)
    now = timezone.now()
    application_factory(job, submitted_at=now - timedelta(days=6, hours=23))  # inside
    application_factory(job, submitted_at=now - timedelta(days=7, hours=1))  # outside
    application_factory(job, submitted_at=now - timedelta(hours=1))
    membership = EmployerMembership.objects.get(employer=employer, account=owner)
    summary = recruiter_services.recruiter_summary(membership, now=now)
    assert summary["applications"]["last_7_days"] == 2
    assert summary["applications"]["total"] == 3


@pytest.mark.django_db
def test_interviews_are_counted_for_the_organisation_only(
    employer_factory, job_factory, application_factory, interview_factory
):
    employer, owner = employer_factory()
    other, other_owner = employer_factory()
    mine = application_factory(job_factory(employer, owner), "INTERVIEW")
    theirs = application_factory(job_factory(other, other_owner), "INTERVIEW")
    interview_factory(mine, owner, "PROPOSED")
    interview_factory(mine, owner, "ACCEPTED")
    interview_factory(theirs, other_owner, "PROPOSED")
    body = client_for(owner).get(RECRUITER).json()
    assert body["interviews"]["total"] == 2
    assert body["interviews"]["by_status"] == {
        "PROPOSED": 1,
        "ACCEPTED": 1,
        "DECLINED": 0,
        "CANCELLED": 0,
    }


@pytest.mark.django_db
def test_applicant_aggregates_are_withheld_not_zeroed_for_an_unverified_organisation(
    employer_factory, job_factory, application_factory
):
    employer, owner = employer_factory(verified=False)
    job_factory(employer, owner, JobStatus.DRAFT)
    body = client_for(owner).get(RECRUITER).json()
    assert body["organization"]["can_recruit"] is False
    assert body["applications_access"] == "organization_not_verified"
    assert body["applications"] is None and body["interviews"] is None
    assert body["jobs"]["total"] == 1 and body["jobs"]["open_now"] == 0


@pytest.mark.django_db
def test_a_suspended_organisation_has_no_open_jobs_and_no_applicant_data(
    employer_factory, job_factory
):
    employer, owner = employer_factory()
    job_factory(employer, owner, JobStatus.PUBLISHED)
    employer.recruitment_status = RecruitmentStatus.SUSPENDED
    employer.save(update_fields=["recruitment_status"])
    body = client_for(owner).get(RECRUITER).json()
    assert body["organization"]["recruitment_status"] == "SUSPENDED"
    assert body["jobs"]["open_now"] == 0
    assert body["applications_access"] == "organization_not_verified"


@pytest.mark.django_db
def test_applicant_aggregates_need_the_application_review_entitlement(
    employer_factory, job_factory, application_factory
):
    from apps.billing.models import PlanEntitlement
    from apps.billing.types import Audience, Keys

    employer, owner = employer_factory(plan_code=None)  # runs on the audience default plan
    application_factory(job_factory(employer, owner))
    assert client_for(owner).get(RECRUITER).json()["applications_access"] is None

    # An administrator edits the plan: the very next read reflects it (no cached entitlement).
    PlanEntitlement.objects.filter(
        plan__audience=Audience.EMPLOYER, plan__is_default=True, key=Keys.JOBS_APPLICATION_REVIEW
    ).update(enabled=False)
    body = client_for(owner).get(RECRUITER).json()
    assert body["applications_access"] == "plan_required"
    assert body["applications"] is None and body["interviews"] is None
    assert body["jobs"]["total"] == 1  # the organisation's own jobs stay visible


@pytest.mark.django_db
def test_seats_report_active_members_and_the_enforced_limit(employer_factory, member_factory):
    employer, owner = employer_factory(plan_code="PROFESSIONAL")
    member_factory(employer, MemberRole.RECRUITER)
    ended = member_factory(employer, MemberRole.VIEWER)
    EmployerMembership.objects.filter(account=ended).update(status=MemberStatus.ENDED)
    body = client_for(owner).get(RECRUITER).json()["seats"]
    assert body["active_members"] == 2  # owner + recruiter; the ended one does not count
    assert body["enabled"] is True and body["limit"] == 5  # PROFESSIONAL seat limit (seed)


@pytest.mark.django_db
def test_no_candidate_personal_data_in_the_payload(
    employer_factory, job_factory, application_factory
):
    employer, owner = employer_factory()
    application_factory(job_factory(employer, owner))
    text = str(client_for(owner).get(RECRUITER).json()).lower()
    for word in ("email", "phone", "cover_text", "snapshot", "professional_title", "message"):
        assert word not in text


@pytest.mark.django_db
def test_recruiter_dashboard_query_count_is_constant(
    employer_factory, job_factory, application_factory
):
    employer, owner = employer_factory()
    job = job_factory(employer, owner)
    client = client_for(owner)

    def queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(RECRUITER).status_code == 200
        return len(ctx)

    baseline = queries()
    for _ in range(15):
        application_factory(job)
    job_factory(employer, owner, JobStatus.DRAFT)
    assert queries() == baseline
    assert baseline <= 12  # entitlement resolution dominates; independent of data volume


def test_verification_status_enum_is_the_jobs_one():
    assert EmployerVerification.VERIFIED == "VERIFIED"
