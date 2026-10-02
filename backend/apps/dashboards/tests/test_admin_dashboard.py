"""Administrator dashboard: counts only, staff only, read only."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.audit.models import AuditEvent
from apps.dashboards.services import admin as admin_services
from apps.jobs.types import JobStatus
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.types import ProviderType, VerificationStatus
from apps.real_estate.types import PublicationStatus
from apps.reservations.types import ReservationStatus

from .conftest import DASH, client_for

ADMIN = f"{DASH}/admin"


@pytest.mark.django_db
def test_only_staff_accounts_open_it(
    api_client, patient, provider_factory, company_factory, seller_factory, employer_factory, admin
):
    assert api_client.get(ADMIN).status_code == 401
    employer_owner = employer_factory()[1]
    for account in (
        patient,
        provider_factory().account,
        company_factory().account,
        seller_factory().account,
        employer_owner,
    ):
        assert client_for(account).get(ADMIN).status_code == 403
    assert client_for(admin).get(ADMIN).status_code == 200


@pytest.mark.django_db
def test_it_exposes_no_mutation_capability(admin):
    client = client_for(admin)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(ADMIN, {}, format="json").status_code == 405


@pytest.mark.django_db
def test_empty_platform_reports_zeros(admin):
    body = client_for(admin).get(ADMIN).json()
    assert body["accounts"]["total"] == 1 and body["accounts"]["by_role"]["ADMIN"] == 1
    assert body["jobs"]["by_status"]["PUBLISHED"] == 0
    assert body["reservations"]["by_status"]["PENDING"] == 0
    assert body["marketplace"]["products"] == {"total": 0, "active": 0}
    assert body["advertising"]["payments_by_status"] == {"PENDING": 0, "VERIFIED": 0, "REJECTED": 0}


@pytest.mark.django_db
def test_counts_match_the_stored_rows(
    admin,
    account_factory,
    provider_factory,
    company_factory,
    product_factory,
    campaign_factory,
    seller_factory,
    listing_factory,
    employer_factory,
    job_factory,
    reservation_factory,
):
    for _ in range(3):
        account_factory(role=AccountRole.PATIENT)
    inactive = account_factory(role=AccountRole.PATIENT)
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])

    provider_factory(verification_status=VerificationStatus.PENDING)
    provider_factory(ProviderType.HOSPITAL, verification_status=VerificationStatus.PENDING)
    provider_factory(verification_status=VerificationStatus.VERIFIED)

    pending_company = company_factory(status=CompanyVerificationStatus.PENDING)
    company = company_factory()
    product_factory(company, True)
    product = product_factory(company, False)
    campaign_factory(company, product, CampaignStatus.PENDING_PAYMENT, PaymentStatus.PENDING)

    seller = seller_factory()
    listing_factory(seller, PublicationStatus.PUBLISHED)
    listing_factory(seller, PublicationStatus.DRAFT)
    listing_factory(seller, PublicationStatus.DRAFT)

    employer, owner = employer_factory(verified=False)
    job_factory(employer, owner, JobStatus.PENDING_ADMIN_REVIEW)
    job_factory(employer, owner, JobStatus.PUBLISHED)

    patient = account_factory(role=AccountRole.PATIENT)
    doctor = provider_factory()
    reservation_factory(patient, doctor, ReservationStatus.PENDING)
    reservation_factory(patient, doctor, ReservationStatus.COMPLETED)

    body = client_for(admin).get(ADMIN).json()
    assert body["accounts"]["by_role"]["PATIENT"] == 5  # 3 + inactive + 1
    assert body["accounts"]["inactive"] == 1
    assert body["accounts"]["total"] == body["accounts"]["active"] + body["accounts"]["inactive"]
    assert body["providers"]["by_verification"]["PENDING"] == 2
    assert body["medical_companies"]["by_verification"]["PENDING"] == 1 and pending_company.pk
    assert body["employers"]["by_verification"]["UNVERIFIED"] == 1
    assert body["jobs"]["by_status"]["PENDING_ADMIN_REVIEW"] == 1
    assert body["reservations"]["by_status"] == {
        "PENDING": 1,
        "CONFIRMED": 0,
        "COMPLETED": 1,
        "REJECTED": 0,
        "CANCELLED": 0,
        "NO_SHOW": 0,
    }
    assert body["marketplace"]["products"] == {"total": 2, "active": 1}
    assert body["real_estate"]["listings_by_status"] == {"DRAFT": 2, "PUBLISHED": 1}
    assert body["advertising"]["campaigns_by_status"]["PENDING_PAYMENT"] == 1
    assert body["advertising"]["payments_by_status"]["PENDING"] == 1


@pytest.mark.django_db
def test_audit_windows_use_24_hour_and_7_day_boundaries(admin):
    now = timezone.now()
    for hours in (1, 23, 25, 24 * 6, 24 * 8):
        event = AuditEvent.objects.create(action="x.y", target_type="t", target_id="1")
        AuditEvent.objects.filter(pk=event.pk).update(created_at=now - timedelta(hours=hours))
    summary = admin_services.admin_summary(now=now)["audit"]
    assert summary == {"last_24_hours": 2, "last_7_days": 4}


@pytest.mark.django_db
def test_no_personal_data_can_appear(
    admin, patient, provider_factory, company_factory, employer_factory, account_factory
):
    provider_factory()
    company_factory()
    employer_factory()
    account_factory(role=AccountRole.PATIENT, full_name="Secret Person")
    text = str(client_for(admin).get(ADMIN).json())
    for forbidden in (
        "@example.com",
        "Secret Person",
        "Patient One",
        "Company 1",
        "Hospital 1",
        "email",
        "full_name",
        "phone",
        "token",
        "password",
        "note",
    ):
        assert forbidden not in text, forbidden


@pytest.mark.django_db
def test_admin_dashboard_query_count_is_constant(
    admin, account_factory, provider_factory, reservation_factory
):
    client = client_for(admin)

    def queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(ADMIN).status_code == 200
        return len(ctx)

    baseline = queries()
    patient = account_factory(role=AccountRole.PATIENT)
    doctor = provider_factory()
    for _ in range(25):
        reservation_factory(patient, doctor, ReservationStatus.PENDING)
    for _ in range(10):
        account_factory(role=AccountRole.PATIENT)
    assert queries() == baseline
    assert baseline <= 12  # one aggregate per domain block
