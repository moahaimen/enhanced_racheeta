"""Billing accounts are linked to their employer or account by id, not by a foreign key.

Opening an employer page or applying as a seeker creates one lazily, so a demo walkthrough leaves
one behind for each demo employer and seeker. Before this, `clear_demo_data` deleted the employer
and left an orphan billing account per cycle. These tests pin the rule: a billing account goes
only with an owner that is itself demo data, its subscriptions and payments are checked like any
other cascade, and everything else (a real employer's account, an orphan whose owner is unknown)
is kept and reported.
"""

import uuid

import pytest
from django.core.management.base import CommandError

from apps.accounts.models import Account
from apps.billing import services as billing
from apps.billing.models import BillingAccount, Plan, Subscription
from apps.billing.types import Audience, SubjectType
from apps.demo.content import common
from apps.demo.models import DemoRecord
from apps.demo.tests.conftest import clear, seed
from apps.geography.models import Governorate
from apps.jobs import services as jobs_services
from apps.jobs.models import Employer, JobSeekerProfile

pytestmark = pytest.mark.django_db


def _demo_employer() -> Employer:
    pk = DemoRecord.objects.get(key="employer:dijla-hospital").object_pk
    return Employer.objects.get(pk=pk)


def _demo_seeker() -> JobSeekerProfile:
    return JobSeekerProfile.objects.get(account__email=common.email("seeker-ahmad"))


def _browse_as_demo():
    """What a walkthrough does: read entitlements on an employer page and as a job seeker."""
    jobs_services.employer_entitlements(_demo_employer())
    jobs_services.seeker_entitlements(_demo_seeker())


@pytest.fixture
def real_employer(account_factory):
    owner = account_factory(role="PROVIDER", full_name="Real Owner")
    employer = jobs_services.create_employer(
        owner, name="Real Clinic", organization_type="CLINIC",
        governorate=Governorate.objects.get(slug="baghdad"),
    )  # fmt: skip
    jobs_services.employer_entitlements(employer)  # its billing account exists too
    return employer


@pytest.fixture
def orphan():
    """A billing account whose owner is gone and was never registered (ownership unknown)."""
    return billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, uuid.uuid4(), Audience.EMPLOYER
    )


def test_lazily_created_billing_accounts_go_with_their_demo_owner(db):
    before = BillingAccount.objects.count()
    seed()
    _browse_as_demo()
    assert BillingAccount.objects.count() == before + 2
    assert not DemoRecord.objects.filter(model_label="billing.BillingAccount").exists()

    clear(yes=True)

    assert BillingAccount.objects.count() == before


def test_real_and_unproven_billing_accounts_are_kept(real_employer, orphan, capsys):
    real_account = BillingAccount.objects.get(subject_id=real_employer.pk)
    seed()
    _browse_as_demo()
    clear(yes=True)

    assert BillingAccount.objects.filter(pk=real_account.pk).exists()
    assert BillingAccount.objects.filter(pk=orphan.pk).exists()
    out = capsys.readouterr().out
    assert "Kept (not deleted): billing.BillingAccount: 1 whose owner no longer exists" in out


def test_dry_run_lists_the_billing_accounts_and_deletes_nothing(db, capsys):
    seed()
    _browse_as_demo()
    count = BillingAccount.objects.count()
    clear(dry_run=True)
    assert BillingAccount.objects.count() == count
    assert "billing.BillingAccount: 2" in capsys.readouterr().out


def test_repeated_cycles_leave_no_orphans(real_employer, orphan):
    baseline = set(BillingAccount.objects.values_list("pk", flat=True))
    for _ in range(3):
        seed()
        _browse_as_demo()
        clear(yes=True)
        assert set(BillingAccount.objects.values_list("pk", flat=True)) == baseline


def test_a_demo_subscription_and_its_history_go_with_the_billing_account(db):
    seed()
    employer = _demo_employer()
    owner = Account.objects.get(pk=employer.created_by_id)
    demo_admin = Account.objects.filter(email__endswith=common.EMAIL_DOMAIN, is_staff=True).first()
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )
    sub = billing.request_subscription(
        account, Plan.objects.get(code="PROFESSIONAL"), requested_by=owner
    )
    if demo_admin is not None:  # activated by a demo admin: still entirely demo data
        billing.activate_subscription(sub, admin=demo_admin, reference="DEMO")

    clear(yes=True)

    assert not BillingAccount.objects.filter(pk=account.pk).exists()
    assert not Subscription.objects.filter(pk=sub.pk).exists()


def test_refuses_when_a_real_admin_activated_a_demo_subscription(db):
    seed()
    employer = _demo_employer()
    real_admin = Account.objects.create_superuser(
        email="real-admin@example.com", password="Str0ng-Passw0rd!", full_name="Real Admin"
    )
    account = billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )
    sub = billing.request_subscription(
        account, Plan.objects.get(code="PROFESSIONAL"), requested_by=real_admin
    )
    billing.activate_subscription(sub, admin=real_admin, reference="REAL-123")
    registry = DemoRecord.objects.count()
    employers = Employer.objects.count()

    with pytest.raises(CommandError, match="not demo data"):
        clear(yes=True)

    # one transaction: nothing at all was deleted
    assert DemoRecord.objects.count() == registry
    assert Employer.objects.count() == employers
    assert Subscription.objects.filter(pk=sub.pk, status="ACTIVE").exists()
    assert BillingAccount.objects.filter(pk=account.pk).exists()


def test_a_real_employer_sharing_nothing_with_the_demo_never_loses_its_subscription(
    real_employer,
):
    real_admin = Account.objects.create_superuser(
        email="owner-admin@example.com", password="Str0ng-Passw0rd!", full_name="Real Admin"
    )
    account = BillingAccount.objects.get(subject_id=real_employer.pk)
    sub = billing.request_subscription(
        account, Plan.objects.get(code="PROFESSIONAL"), requested_by=real_admin
    )
    billing.activate_subscription(sub, admin=real_admin, reference="REAL-1")
    seed()
    _browse_as_demo()
    clear(yes=True)
    assert Subscription.objects.filter(pk=sub.pk, status="ACTIVE").exists()
