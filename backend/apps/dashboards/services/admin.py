"""Administrator operational summary: COUNTS ONLY.

No row, e-mail, name or other personal field is selected anywhere in this module, so the payload
cannot expose sensitive user data. Each block is one conditional-aggregate query. The caller must
already be a staff account (enforced by the view); this module trusts that and has no mutation.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.advertising.models import AdvertisingCampaign, CampaignPayment
from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.audit.models import AuditEvent
from apps.billing.models import Subscription
from apps.billing.types import SubscriptionStatus
from apps.jobs.models import Employer, JobPost
from apps.jobs.types import JobStatus, RecruitmentStatus
from apps.jobs.types import VerificationStatus as EmployerVerification
from apps.marketplace.models import MedicalCompany, Product
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus as ProviderVerification
from apps.real_estate.models import PropertyListing
from apps.real_estate.types import PublicationStatus
from apps.reservations.models import Reservation
from apps.reservations.types import ReservationStatus

from .common import status_counts


def admin_summary(*, now=None) -> dict:
    now = now or timezone.now()

    accounts = status_counts(
        Account.objects.all(),
        "role",
        AccountRole.values,
        active=Count("pk", filter=Q(is_active=True)),
    )
    employers = status_counts(
        Employer.objects.all(),
        "verification_status",
        EmployerVerification.values,
        recruitment_suspended=Count("pk", filter=Q(recruitment_status=RecruitmentStatus.SUSPENDED)),
    )
    products = Product.objects.order_by().aggregate(
        total=Count("pk"), active=Count("pk", filter=Q(is_active=True))
    )
    audit = AuditEvent.objects.order_by().aggregate(
        last_24_hours=Count("pk", filter=Q(created_at__gte=now - timedelta(hours=24))),
        last_7_days=Count("pk", filter=Q(created_at__gte=now - timedelta(days=7))),
    )

    return {
        "accounts": {
            "total": accounts["total"],
            "active": accounts["active"],
            "inactive": accounts["total"] - accounts["active"],
            "by_role": accounts["by_status"],
        },
        "providers": {
            "by_verification": status_counts(
                ProviderProfile.objects.all(), "verification_status", ProviderVerification.values
            )["by_status"],
        },
        "medical_companies": {
            "by_verification": status_counts(
                MedicalCompany.objects.all(),
                "verification_status",
                CompanyVerificationStatus.values,
            )["by_status"],
        },
        "employers": {
            "by_verification": employers["by_status"],
            "recruitment_suspended": employers["recruitment_suspended"],
        },
        "jobs": {
            "by_status": status_counts(JobPost.objects.all(), "status", JobStatus.values)[
                "by_status"
            ],
        },
        "reservations": {
            "by_status": status_counts(
                Reservation.objects.all(), "status", ReservationStatus.values
            )["by_status"],
        },
        "marketplace": {"products": products},
        "real_estate": {
            "listings_by_status": status_counts(
                PropertyListing.objects.all(), "publication_status", PublicationStatus.values
            )["by_status"],
        },
        "advertising": {
            "campaigns_by_status": status_counts(
                AdvertisingCampaign.objects.all(), "status", CampaignStatus.values
            )["by_status"],
            "payments_by_status": status_counts(
                CampaignPayment.objects.all(), "status", PaymentStatus.values
            )["by_status"],
        },
        "billing": {
            "subscriptions_by_status": status_counts(
                Subscription.objects.all(), "status", SubscriptionStatus.values
            )["by_status"],
        },
        "audit": audit,
    }
