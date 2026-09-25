"""Eighteenth Codex review of PR #4 (commit 1ef2e74), Phase 3 closure: owner
identity edits decide on the LOCKED employer row, and every employer-side
recruitment mutation re-checks eligibility on the locked employer row first."""

import threading
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.billing.exceptions import EntitlementError
from apps.billing.models import PlanEntitlement
from apps.billing.types import Keys
from apps.jobs import services
from apps.jobs.models import (
    Employer,
    InterviewRequest,
    JobApplication,
    JobApplicationTransition,
    RecruitmentMessage,
)
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import ApplicationStatus, MessageSide, VerificationStatus

pytestmark = pytest.mark.django_db


# ---- 1. stale identity -------------------------------------------------------------------


def _verify(org, admin):
    services.set_employer_verification(org, VerificationStatus.VERIFIED, admin=admin)


def test_unverified_employer_updates_identity_fields(employer_factory, basra):
    org = employer_factory(verified=False)
    services.update_employer(
        org,
        {
            "name": "Renamed",
            "organization_type": "CLINIC",
            "governorate": basra,
            "is_recruitment_agency": True,
        },
        actor=owner_of(org),
    )
    row = Employer.objects.get(pk=org.pk)
    assert (row.name, row.organization_type, row.governorate_id, row.is_recruitment_agency) == (
        "Renamed",
        "CLINIC",
        basra.pk,
        True,
    )
    assert org.name == "Renamed"  # the caller's instance is synchronised


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "Other"),
        ("organization_type", "CLINIC"),
        ("governorate", "basra"),
        ("is_recruitment_agency", True),
        ("provider_profile", "provider"),
    ],
)
def test_verified_employer_cannot_change_frozen_identity(
    employer_factory, provider_factory, basra, field, value
):
    org = employer_factory()  # VERIFIED
    if value == "basra":
        value = basra
    elif value == "provider":
        value = provider_factory()
    with pytest.raises(services.IdentityLocked) as exc:
        services.update_employer(org, {field: value}, actor=owner_of(org))
    assert exc.value.fields == [field]
    assert getattr(Employer.objects.get(pk=org.pk), field) == getattr(org, field)


def test_non_identity_fields_still_update_after_verification(employer_factory):
    org = employer_factory()
    services.update_employer(org, {"description": "We hire nurses."}, actor=owner_of(org))
    assert Employer.objects.get(pk=org.pk).description == "We hire nurses."


@pytest.mark.parametrize(
    "field,old,new",
    [
        ("name", "Old name", "New name"),
        ("organization_type", "HOSPITAL", "CLINIC"),
        ("governorate", "baghdad", "basra"),
        ("is_recruitment_agency", False, True),
        ("provider_profile", None, "provider"),
    ],
)
def test_stale_instance_cannot_restore_the_pre_verification_identity(
    employer_factory, provider_factory, baghdad, basra, admin, field, old, new
):
    """The request read the identity before another edit + verification
    committed. Its submitted value equals its stale in-memory value, but the
    LOCKED row differs and is frozen: the edit must be refused."""
    lookup = {"baghdad": baghdad, "basra": basra, "provider": provider_factory()}
    old = lookup.get(old, old) if isinstance(old, str) else old
    new = lookup.get(new, new) if isinstance(new, str) else new
    org = employer_factory(verified=False, **({field: old} if field != "name" else {"name": old}))
    stale = Employer.objects.get(pk=org.pk)
    assert getattr(stale, field) == old

    services.update_employer(org, {field: new}, actor=owner_of(org))
    _verify(org, admin)

    with pytest.raises(services.IdentityLocked) as exc:
        services.update_employer(stale, {field: old}, actor=owner_of(org))
    assert exc.value.fields == [field]
    assert getattr(Employer.objects.get(pk=org.pk), field) == new


def test_agency_and_non_agency_verification_workflows_unchanged(employer_factory, admin):
    agency = employer_factory(verified=False, is_recruitment_agency=True)
    plain = employer_factory(verified=False)
    services.request_employer_verification(agency, actor=owner_of(agency))
    _verify(agency, admin)
    _verify(plain, admin)
    assert Employer.objects.get(pk=agency.pk).is_recruitment_agency is True
    assert Employer.objects.get(pk=plain.pk).verification_status == VerificationStatus.VERIFIED
    with pytest.raises(services.IdentityLocked):
        services.update_employer(agency, {"is_recruitment_agency": False}, actor=owner_of(agency))


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_stale_edit_races_edit_plus_verification(employer_factory, admin):
    org = employer_factory(verified=False, name="Old name")
    stale = Employer.objects.get(pk=org.pk)
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except services.IdentityLocked:
            outcomes[name] = "identity_locked"
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    def edit_and_verify():
        with transaction.atomic():
            fresh = Employer.objects.get(pk=org.pk)
            services.update_employer(fresh, {"name": "New name"}, actor=owner_of(org))
            _verify(fresh, admin)

    def stale_edit():
        services.update_employer(stale, {"name": "Old name"}, actor=owner_of(org))

    threads = [
        threading.Thread(target=run, args=("verify", edit_and_verify)),
        threading.Thread(target=run, args=("stale", stale_edit)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["verify"] == "ok" and outcomes["stale"] in ("ok", "identity_locked"), outcomes
    row = Employer.objects.get(pk=org.pk)
    # Whatever the interleaving, the verified identity is the one that was verified.
    assert row.verification_status == VerificationStatus.VERIFIED and row.name == "New name"


# ---- 2. recruitment mutations re-check the employer under lock ---------------------------


@pytest.fixture
def application(employer, job_factory, seeker_factory):
    job = job_factory(employer)
    return services.apply_to_job(job, seeker_factory(), cover_text="Hello")


def _suspend(employer, admin):
    services.set_employer_recruitment_status(employer, "SUSPENDED", admin=admin, reason="abuse")


def _stale(application):
    return JobApplication.objects.select_related("job__employer").get(pk=application.pk)


def test_eligible_employer_performs_every_action(employer, application, admin):
    owner = owner_of(employer)
    services.transition_application(application, ApplicationStatus.SHORTLISTED, actor=owner)
    services.request_interview(
        application, actor=owner, proposed_at=timezone.now() + timedelta(days=2), mode="ONLINE"
    )
    services.send_message(application, sender=owner, side=MessageSide.EMPLOYER, body="Welcome")
    application.refresh_from_db()
    assert application.status == ApplicationStatus.INTERVIEW
    assert InterviewRequest.objects.filter(application=application).count() == 1
    assert RecruitmentMessage.objects.filter(application=application).count() == 1


def _snapshot(application):
    return (
        JobApplicationTransition.objects.filter(application=application).count(),
        InterviewRequest.objects.filter(application=application).count(),
        RecruitmentMessage.objects.filter(application=application).count(),
        AuditEvent.objects.count(),
        JobApplication.objects.get(pk=application.pk).status,
    )


@pytest.mark.parametrize("action", ["transition", "interview", "message"])
def test_suspension_after_the_pre_check_refuses_the_mutation(employer, application, admin, action):
    """The application (and its employer) were loaded while the organisation
    could recruit; the suspension commits before the service takes its locks."""
    owner = owner_of(employer)
    services.transition_application(application, ApplicationStatus.SHORTLISTED, actor=owner)
    stale = _stale(application)
    assert stale.job.employer.can_recruit
    _suspend(employer, admin)
    before = _snapshot(application)
    with pytest.raises(services.OrganizationNotVerified):
        if action == "transition":
            services.transition_application(stale, ApplicationStatus.ACCEPTED, actor=owner)
        elif action == "interview":
            services.request_interview(
                stale, actor=owner, proposed_at=timezone.now() + timedelta(days=1), mode="ONLINE"
            )
        else:
            services.send_message(stale, sender=owner, side=MessageSide.EMPLOYER, body="Hi")
    assert _snapshot(application) == before


@pytest.mark.parametrize("action", ["transition", "interview", "message"])
def test_lost_entitlement_after_the_pre_check_refuses_the_mutation(
    employer, application, admin, action
):
    owner = owner_of(employer)
    services.transition_application(application, ApplicationStatus.SHORTLISTED, actor=owner)
    stale = _stale(application)
    key = Keys.RECRUITMENT_MESSAGING if action == "message" else Keys.JOBS_APPLICATION_REVIEW
    PlanEntitlement.objects.filter(plan__code="PROFESSIONAL", key=key).update(enabled=False)
    before = _snapshot(application)
    with pytest.raises(EntitlementError):
        if action == "transition":
            services.transition_application(stale, ApplicationStatus.ACCEPTED, actor=owner)
        elif action == "interview":
            services.request_interview(
                stale, actor=owner, proposed_at=timezone.now() + timedelta(days=1), mode="ONLINE"
            )
        else:
            services.send_message(stale, sender=owner, side=MessageSide.EMPLOYER, body="Hi")
    assert _snapshot(application) == before


def test_api_returns_typed_403_for_a_suspended_employer(
    employer_client, employer, application, admin
):
    _suspend(employer, admin)
    resp = employer_client.post(
        f"/api/v1/jobs/employer/applications/{application.pk}/transition",
        {"status": "REVIEWING"},
        format="json",
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "organization_not_verified"
    resp = employer_client.post(
        f"/api/v1/recruitment/applications/{application.pk}/messages", {"body": "Hi"}, format="json"
    )
    assert resp.status_code == 403


def test_candidate_actions_ignore_the_employer_recruitment_status(
    employer, application, admin, seeker_client
):
    owner = owner_of(employer)
    services.transition_application(application, ApplicationStatus.SHORTLISTED, actor=owner)
    interview = services.request_interview(
        application, actor=owner, proposed_at=timezone.now() + timedelta(days=1), mode="ONLINE"
    )
    _suspend(employer, admin)
    candidate = application.job_seeker.account
    services.respond_to_interview(interview, actor=candidate, accept=True)
    services.send_message(application, sender=candidate, side=MessageSide.CANDIDATE, body="Ok")
    services.withdraw_application(application, actor=candidate)
    assert JobApplication.objects.get(pk=application.pk).status == ApplicationStatus.WITHDRAWN


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_transition_races_suspension(employer_factory, job_factory, seeker_factory, admin):
    employer = employer_factory(plan_code="PROFESSIONAL")
    application = services.apply_to_job(job_factory(employer), seeker_factory())
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except services.JobsError as exc:
            outcomes[name] = exc.code
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    def suspend():
        _suspend(Employer.objects.get(pk=employer.pk), admin)

    def transition():
        services.transition_application(
            _stale(application), ApplicationStatus.REVIEWING, actor=owner_of(employer)
        )

    threads = [
        threading.Thread(target=run, args=("suspend", suspend)),
        threading.Thread(target=run, args=("transition", transition)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["suspend"] == "ok"
    assert outcomes["transition"] in ("ok", "organization_not_verified"), outcomes
    status = JobApplication.objects.get(pk=application.pk).status
    rows = JobApplicationTransition.objects.filter(
        application=application, to_status=ApplicationStatus.REVIEWING
    ).count()
    assert (status == ApplicationStatus.REVIEWING) == (outcomes["transition"] == "ok")
    assert rows == (1 if outcomes["transition"] == "ok" else 0)
