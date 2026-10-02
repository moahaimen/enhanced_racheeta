"""Factories for the dashboard tests. Rows are created directly through the ORM (explicit,
fast); the dashboards read them back through the real services and endpoints."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.advertising.models import AdvertisingCampaign, CampaignPayment
from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.billing import services as billing
from apps.billing.models import Plan
from apps.billing.types import Audience, SubjectType
from apps.geography.models import Governorate
from apps.jobs import services as jobs_services
from apps.jobs.models import (
    EmployerMembership,
    InterviewRequest,
    JobApplication,
    JobPost,
    JobSeekerProfile,
)
from apps.jobs.types import JobStatus, MemberRole
from apps.jobs.types import VerificationStatus as EmployerVerification
from apps.marketplace.models import MedicalCompany, Product, ProductCategory
from apps.marketplace.types import CompanyVerificationStatus
from apps.offers.models import Offer
from apps.providers.models import ProviderMembership, ProviderProfile, ServiceOffering
from apps.providers.types import MembershipSide, MembershipStatus, ProviderType, VerificationStatus
from apps.real_estate.models import PropertyListing, RealEstateSeller
from apps.real_estate.types import (
    ContactMethod,
    PropertyType,
    PublicationStatus,
    SellerType,
    TransactionType,
)
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus
from apps.reviews.models import Review

PASSWORD = "Str0ng-Passw0rd!"
DASH = "/api/v1/dashboards"


def client_for(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.fixture
def baghdad(db):
    return Governorate.objects.get(slug="baghdad")


@pytest.fixture
def admin(db):
    return Account.objects.create_superuser(
        email="admin@example.com", password=PASSWORD, full_name="Admin"
    )


@pytest.fixture
def patient(account_factory):
    return account_factory(role=AccountRole.PATIENT, full_name="Patient One")


@pytest.fixture
def provider_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(provider_type=ProviderType.DOCTOR, **fields) -> ProviderProfile:
        counter["n"] += 1
        fields.setdefault("verification_status", VerificationStatus.VERIFIED)
        return ProviderProfile.objects.create(
            account=fields.pop("account", None) or account_factory(role=AccountRole.PROVIDER),
            provider_type=provider_type,
            display_name=fields.pop("display_name", f"Provider {counter['n']}"),
            governorate=baghdad,
            **fields,
        )

    return _make


@pytest.fixture
def reservation_factory():
    def _make(patient, provider, status=ReservationStatus.PENDING, starts_in=None, **fields):
        starts_at = fields.pop("starts_at", None) or (
            timezone.now() + (starts_in if starts_in is not None else timedelta(days=2))
        )
        return Reservation.objects.create(
            patient=patient,
            provider=provider,
            provider_name_snapshot=provider.display_name,
            service_title_snapshot=fields.pop("service_title_snapshot", "Consultation"),
            price_snapshot=Decimal("25000"),
            currency_snapshot="IQD",
            duration_minutes_snapshot=30,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            status=status,
            **fields,
        )

    return _make


@pytest.fixture
def review_factory():
    def _make(reservation, rating):
        return Review.objects.create(
            reservation=reservation,
            patient=reservation.patient,
            provider=reservation.provider,
            provider_name_snapshot=reservation.provider_name_snapshot,
            service_title_snapshot=reservation.service_title_snapshot,
            rating=rating,
        )

    return _make


@pytest.fixture
def offer_factory():
    counter = {"n": 0}

    def _make(provider, *, starts=timedelta(hours=-1), ends=timedelta(days=1), **fields):
        counter["n"] += 1
        service = fields.pop("service", None) or ServiceOffering.objects.create(
            provider=provider,
            title=f"Checkup {counter['n']}",
            price=Decimal("30000"),
            currency="IQD",
        )
        now = timezone.now()
        return Offer.objects.create(
            provider=provider,
            service=service,
            service_title_snapshot=service.title,
            title=fields.pop("title", "Offer"),
            original_price_snapshot=Decimal("30000"),
            offer_price=Decimal("20000"),
            currency_snapshot="IQD",
            starts_at=now + starts,
            ends_at=now + ends,
            **fields,
        )

    return _make


@pytest.fixture
def membership_factory():
    def _make(practitioner, facility, status=MembershipStatus.ACTIVE, by=MembershipSide.FACILITY):
        return ProviderMembership.objects.create(
            practitioner=practitioner, facility=facility, status=status, initiated_by=by
        )

    return _make


@pytest.fixture
def company_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(status=CompanyVerificationStatus.VERIFIED, **fields) -> MedicalCompany:
        counter["n"] += 1
        return MedicalCompany.objects.create(
            account=fields.pop("account", None)
            or account_factory(role=AccountRole.MEDICAL_COMPANY),
            name=f"Company {counter['n']}",
            governorate=baghdad,
            verification_status=status,
            **fields,
        )

    return _make


@pytest.fixture
def product_factory(db):
    counter = {"n": 0}
    category = {}

    def _make(company, is_active=True) -> Product:
        counter["n"] += 1
        if "c" not in category:
            category["c"] = ProductCategory.objects.create(
                slug="dash-cat", name_ar="فئة", name_en="Category"
            )
        return Product.objects.create(
            company=company,
            category=category["c"],
            title=f"Product {counter['n']}",
            is_active=is_active,
        )

    return _make


@pytest.fixture
def campaign_factory():
    counter = {"n": 0}

    def _make(company, product, status=CampaignStatus.DRAFT, payment=None, **fields):
        counter["n"] += 1
        if status != CampaignStatus.DRAFT:  # the DB requires a complete quote once submitted
            today = timezone.localdate()
            fields.setdefault("starts_on", today)
            fields.setdefault("ends_on", today + timedelta(days=10))
            fields.setdefault("quoted_days", 10)
            fields.setdefault("quoted_daily_rate", Decimal("10"))
            fields.setdefault("quoted_amount", Decimal("100"))
            fields.setdefault("quoted_currency", "IQD")
            fields.setdefault("quoted_at", timezone.now())
        campaign = AdvertisingCampaign.objects.create(
            company=company,
            product=product,
            name=f"Campaign {counter['n']}",
            status=status,
            **fields,
        )
        if payment is not None:
            verified = (
                {"method": "BANK_TRANSFER", "verified_at": timezone.now()}
                if payment == PaymentStatus.VERIFIED
                else {}
            )
            CampaignPayment.objects.create(
                campaign=campaign, amount=Decimal("100"), currency="IQD", status=payment, **verified
            )
        return campaign

    return _make


@pytest.fixture
def seller_factory(account_factory):
    counter = {"n": 0}

    def _make(**fields) -> RealEstateSeller:
        counter["n"] += 1
        return RealEstateSeller.objects.create(
            account=fields.pop("account", None)
            or account_factory(role=AccountRole.REAL_ESTATE_SELLER),
            seller_type=SellerType.OWNER,
            display_name=f"Seller {counter['n']}",
        )

    return _make


@pytest.fixture
def listing_factory(baghdad):
    def _make(seller, status=PublicationStatus.DRAFT, **fields) -> PropertyListing:
        defaults = {
            "title": "Listing",
            "property_type": PropertyType.CLINIC,
            "transaction_type": TransactionType.RENT,
            "governorate": baghdad,
            "district": "Karrada",
            "area_sqm": Decimal("120.00"),
            "price": Decimal("1500000.00"),
            "currency": "IQD",
            "facilities": "Parking",
            "contact_method": ContactMethod.PHONE,
            "contact_phone": "07700000000",
            "expires_at": timezone.now() + timedelta(days=30),
        }
        defaults.update(fields)
        if status == PublicationStatus.PUBLISHED:
            defaults.setdefault("published_at", timezone.now())
        return PropertyListing.objects.create(seller=seller, publication_status=status, **defaults)

    return _make


@pytest.fixture
def employer_factory(account_factory, baghdad, admin):
    counter = {"n": 0}

    def _make(verified=True, plan_code="PROFESSIONAL", **fields):
        counter["n"] += 1
        owner = account_factory(role=AccountRole.PROVIDER)
        employer = jobs_services.create_employer(
            owner,
            name=f"Hospital {counter['n']}",
            organization_type="HOSPITAL",
            governorate=baghdad,
            **fields,
        )
        if verified:
            jobs_services.set_employer_verification(
                employer, EmployerVerification.VERIFIED, admin=admin
            )
        if plan_code:
            acc = billing.get_or_create_billing_account(
                SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
            )
            sub = billing.request_subscription(
                acc, Plan.objects.get(code=plan_code), requested_by=owner
            )
            billing.activate_subscription(sub, admin=admin)
        employer.refresh_from_db()
        return employer, owner

    return _make


@pytest.fixture
def member_factory(account_factory):
    def _make(employer, role=MemberRole.VIEWER) -> Account:
        account = account_factory(role=AccountRole.PROVIDER)
        EmployerMembership.objects.create(employer=employer, account=account, role=role)
        return account

    return _make


@pytest.fixture
def job_factory(baghdad):
    counter = {"n": 0}

    def _make(employer, owner, status=JobStatus.PUBLISHED, **fields) -> JobPost:
        counter["n"] += 1
        return JobPost.objects.create(
            employer=employer,
            created_by=owner,
            status=status,
            title=f"Nurse {counter['n']}",
            profession="NURSE",
            description="ICU nursing role.",
            governorate=baghdad,
            employment_type="FULL_TIME",
            **fields,
        )

    return _make


@pytest.fixture
def application_factory(account_factory, baghdad):
    counter = {"n": 0}

    def _make(job, status="SUBMITTED", submitted_at=None) -> JobApplication:
        counter["n"] += 1
        seeker = JobSeekerProfile.objects.create(
            account=account_factory(role=AccountRole.PATIENT),
            professional_title=f"Nurse {counter['n']}",
            profession="NURSE",
            degree="BACHELOR",
            governorate=baghdad,
            years_of_experience=3,
        )
        application = JobApplication.objects.create(job=job, job_seeker=seeker, status=status)
        if submitted_at is not None:
            JobApplication.objects.filter(pk=application.pk).update(submitted_at=submitted_at)
        return application

    return _make


@pytest.fixture
def interview_factory():
    def _make(application, creator, status="PROPOSED") -> InterviewRequest:
        return InterviewRequest.objects.create(
            application=application,
            proposed_at=timezone.now() + timedelta(days=3),
            mode="IN_PERSON",
            created_by=creator,
            status=status,
        )

    return _make
