from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.billing import services as billing
from apps.billing.models import Plan
from apps.billing.types import Audience, SubjectType
from apps.geography.models import Governorate
from apps.jobs import services
from apps.jobs.models import Employer, EmployerMembership, JobPost, JobSeekerProfile
from apps.jobs.types import JobStatus, MemberRole, VerificationStatus
from apps.specialties.models import Specialty

PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture
def baghdad(db):
    return Governorate.objects.get(slug="baghdad")


@pytest.fixture
def basra(db):
    return Governorate.objects.get(slug="basra")


@pytest.fixture
def admin(db):
    return Account.objects.create_superuser(
        email="admin@example.com", password=PASSWORD, full_name="Admin"
    )


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def employer_factory(account_factory, baghdad, admin):
    counter = {"n": 0}

    def _make(verified=True, name=None, plan_code=None, **fields) -> Employer:
        counter["n"] += 1
        owner = account_factory(role="PROVIDER")
        fields.setdefault("organization_type", "HOSPITAL")
        fields.setdefault("governorate", baghdad)
        employer = services.create_employer(
            owner, name=name or f"Hospital {counter['n']}", **fields
        )
        if verified:
            services.set_employer_verification(employer, VerificationStatus.VERIFIED, admin=admin)
        if plan_code:
            acc = billing.get_or_create_billing_account(
                SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
            )
            sub = billing.request_subscription(
                acc, Plan.objects.get(code=plan_code), requested_by=owner
            )
            billing.activate_subscription(sub, admin=admin)
        employer.refresh_from_db()
        return employer

    return _make


@pytest.fixture
def employer(employer_factory) -> Employer:
    return employer_factory(plan_code="PROFESSIONAL")


def owner_of(employer: Employer) -> Account:
    return EmployerMembership.objects.get(employer=employer, role=MemberRole.OWNER).account


@pytest.fixture
def employer_client(employer):
    client = APIClient()
    client.force_authenticate(user=owner_of(employer))
    return client


@pytest.fixture
def provider_factory(account_factory, baghdad):
    from apps.providers.models import ProviderProfile

    def _make(provider_type="DOCTOR", **fields) -> ProviderProfile:
        account = account_factory(role="PROVIDER")
        return ProviderProfile.objects.create(
            account=account,
            provider_type=provider_type,
            display_name=fields.pop("display_name", f"Provider {account.email}"),
            governorate=baghdad,
            verification_status="VERIFIED",
            **fields,
        )

    return _make


@pytest.fixture
def job_factory(baghdad):
    counter = {"n": 0}

    def _make(employer: Employer, status=JobStatus.PUBLISHED, **fields) -> JobPost:
        counter["n"] += 1
        fields.setdefault("title", f"Registered nurse {counter['n']}")
        fields.setdefault("profession", "NURSE")
        fields.setdefault("description", "ICU nursing role, day and night shifts.")
        fields.setdefault("governorate", baghdad)
        fields.setdefault("employment_type", "FULL_TIME")
        job = JobPost.objects.create(
            employer=employer, created_by=owner_of(employer), status=status, **fields
        )
        if status == JobStatus.PUBLISHED and not job.published_at:
            job.published_at = timezone.now()
            job.save(update_fields=["published_at"])
        return job

    return _make


@pytest.fixture
def seeker_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(discoverable=True, **fields) -> JobSeekerProfile:
        counter["n"] += 1
        account = fields.pop("account", None) or account_factory(role="PATIENT")
        fields.setdefault("professional_title", f"Nurse {counter['n']}")
        fields.setdefault("profession", "NURSE")
        fields.setdefault("degree", "BACHELOR")
        fields.setdefault("governorate", baghdad)
        fields.setdefault("years_of_experience", 3)
        return JobSeekerProfile.objects.create(
            account=account, discoverable_by_employers=discoverable, **fields
        )

    return _make


@pytest.fixture
def seeker(seeker_factory) -> JobSeekerProfile:
    return seeker_factory()


@pytest.fixture
def seeker_client(seeker):
    client = APIClient()
    client.force_authenticate(user=seeker.account)
    return client


@pytest.fixture
def cardiology(db):
    return Specialty.objects.get(slug="cardiology")


@pytest.fixture
def tomorrow():
    return timezone.localdate() + timedelta(days=1)
