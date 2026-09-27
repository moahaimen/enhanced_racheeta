"""Seventeenth Codex review of PR #4 (commit 153493f): employer creation
serialises on the owner account before the one-active-membership check, with
the same policy as add_member; a refused creation leaves no orphan Employer."""

import threading

import pytest
from django.db import IntegrityError, connection
from rest_framework.test import APIClient

from apps.jobs import services
from apps.jobs.models import Employer, EmployerMembership
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import MemberRole, MemberStatus

pytestmark = pytest.mark.django_db
EMPLOYER = "/api/v1/jobs/employer"


def _post(account, name, baghdad):
    client = APIClient()
    client.force_authenticate(user=account)
    return client.post(
        EMPLOYER,
        {"name": name, "organization_type": "HOSPITAL", "governorate": str(baghdad.pk)},
        format="json",
    )


def test_normal_creation_succeeds(account_factory, baghdad):
    acct = account_factory(role="PROVIDER")
    resp = _post(acct, "New clinic", baghdad)
    assert resp.status_code == 201 and resp.json()["my_role"] == "OWNER"
    m = EmployerMembership.objects.get(account=acct, status=MemberStatus.ACTIVE)
    assert m.role == MemberRole.OWNER and m.employer.name == "New clinic"


def test_account_already_in_an_organisation_gets_a_typed_error(employer, baghdad):
    resp = _post(owner_of(employer), "Second clinic", baghdad)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "already_member"
    assert Employer.objects.filter(name="Second clinic").count() == 0


def test_member_of_another_organisation_cannot_create_one(employer, account_factory, baghdad):
    acct = account_factory()
    services.add_member(employer, acct, MemberRole.VIEWER, actor=owner_of(employer))
    resp = _post(acct, "Side clinic", baghdad)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "already_member"
    assert not Employer.objects.filter(name="Side clinic").exists()


def test_refused_membership_rolls_the_employer_back(
    employer, account_factory, baghdad, monkeypatch
):
    """The DB constraint is the last line: when it fires, the Employer row that
    was inserted in the same transaction disappears with it, and no audit row
    is written."""
    acct = account_factory()
    real_membership_for = services.membership_for
    monkeypatch.setattr(services, "membership_for", lambda a: None)  # blind the pre-check
    services.add_member(employer, acct, MemberRole.VIEWER, actor=owner_of(employer))
    with pytest.raises(services.JobsError) as exc:
        services.create_employer(
            acct, name="Ghost", organization_type="HOSPITAL", governorate=baghdad
        )
    assert exc.value.code == "already_member"
    monkeypatch.setattr(services, "membership_for", real_membership_for)
    assert not Employer.objects.filter(name="Ghost").exists()
    assert EmployerMembership.objects.filter(account=acct).count() == 1
    from apps.audit.models import AuditEvent

    assert not AuditEvent.objects.filter(action="jobs.employer.created", summary="Ghost").exists()


def test_other_integrity_errors_propagate(account_factory, baghdad, monkeypatch):
    def broken(*args, **kwargs):
        raise IntegrityError("something else")

    monkeypatch.setattr(services.EmployerMembership.objects, "create", broken)
    with pytest.raises(IntegrityError):
        services.create_employer(
            account_factory(), name="X", organization_type="HOSPITAL", governorate=baghdad
        )
    assert not Employer.objects.filter(name="X").exists()


def test_account_freed_by_an_ended_membership_can_create(employer, account_factory, baghdad):
    acct = account_factory()
    m = services.add_member(employer, acct, MemberRole.RECRUITER, actor=owner_of(employer))
    services.end_membership(m, actor=owner_of(employer))
    resp = _post(acct, "Own clinic", baghdad)
    assert resp.status_code == 201
    assert EmployerMembership.objects.filter(account=acct, status=MemberStatus.ACTIVE).count() == 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_creations_by_the_same_account(account_factory, baghdad):
    acct = account_factory(role="PROVIDER")
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def run(name):
        try:
            barrier.wait(timeout=10)
            resp = _post(acct, name, baghdad)
            outcomes[name] = (resp.status_code, resp.json().get("error", {}).get("code"))
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(n,)) for n in ("Clinic A", "Clinic B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(outcomes.values(), key=str) == [(201, None), (409, "already_member")], outcomes
    assert Employer.objects.filter(name__in=["Clinic A", "Clinic B"]).count() == 1
    live = EmployerMembership.objects.filter(account=acct, status=MemberStatus.ACTIVE)
    assert live.count() == 1 and live.get().role == MemberRole.OWNER
    # and the account keeps working afterwards
    client = APIClient()
    client.force_authenticate(user=acct)
    assert client.get(EMPLOYER).json()["my_role"] == "OWNER"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_creation_races_add_member_on_the_same_account(employer_factory, account_factory, baghdad):
    """Both assignment paths serialise on the account row: one wins, the other
    gets the typed error, one active membership exists."""
    org = employer_factory(plan_code="PROFESSIONAL")
    acct = account_factory(role="PROVIDER")
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

    threads = [
        threading.Thread(
            target=run,
            args=(
                "create",
                lambda: services.create_employer(
                    acct, name="Mine", organization_type="HOSPITAL", governorate=baghdad
                ),
            ),
        ),
        threading.Thread(
            target=run,
            args=(
                "add",
                lambda: services.add_member(org, acct, MemberRole.VIEWER, actor=owner_of(org)),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes.values()) == ["already_member", "ok"], outcomes
    assert EmployerMembership.objects.filter(account=acct, status=MemberStatus.ACTIVE).count() == 1
    assert Employer.objects.filter(name="Mine").exists() == (outcomes["create"] == "ok")
