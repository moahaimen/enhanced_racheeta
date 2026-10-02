"""Response contracts. Views serialize every payload through these, so a field that is not
declared here can never leave the server (a service accidentally returning an extra column
would not leak). They are output-only: dashboards accept no client input."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.accounts.roles import AccountRole
from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.billing.types import SubscriptionStatus
from apps.jobs.types import ApplicationStatus, InterviewStatus, JobStatus
from apps.jobs.types import VerificationStatus as EmployerVerification
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.types import ProviderType, VerificationStatus
from apps.real_estate.types import PublicationStatus
from apps.reservations.types import ReservationStatus

from . import access


def counts_serializer(name: str, values) -> type[serializers.Serializer]:
    """`{value: int}` for every value of a controlled list (zero-filled by the services)."""
    fields = {str(value): serializers.IntegerField(min_value=0) for value in values}
    cls = type(name, (serializers.Serializer,), fields)
    return extend_schema_serializer(component_name=name)(cls)


ReservationStatusCounts = counts_serializer(
    "DashboardReservationStatusCounts", ReservationStatus.values
)
JobStatusCounts = counts_serializer("DashboardJobStatusCounts", JobStatus.values)
ApplicationStatusCounts = counts_serializer(
    "DashboardApplicationStatusCounts", ApplicationStatus.values
)
InterviewStatusCounts = counts_serializer("DashboardInterviewStatusCounts", InterviewStatus.values)
PaymentStatusCounts = counts_serializer("DashboardPaymentStatusCounts", PaymentStatus.values)
RatingDistribution = counts_serializer("DashboardRatingDistribution", ["1", "2", "3", "4", "5"])


# ---- shared blocks ---------------------------------------------------------------------------


@extend_schema_serializer(component_name="DashboardReservationCounts")
class ReservationCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = ReservationStatusCounts()
    upcoming = serializers.IntegerField(
        help_text="PENDING or CONFIRMED reservations that have not started yet."
    )


@extend_schema_serializer(component_name="DashboardReservationBrief")
class ReservationBriefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    provider_name_snapshot = serializers.CharField()
    service_title_snapshot = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=ReservationStatus.choices)


@extend_schema_serializer(component_name="DashboardProviderAppointment")
class ProviderAppointmentSerializer(ReservationBriefSerializer):
    patient_name = serializers.CharField(
        help_text="The patient's name, as the provider's own reservation API already shows it."
    )


@extend_schema_serializer(component_name="DashboardUnread")
class UnreadSerializer(serializers.Serializer):
    notifications = serializers.IntegerField()
    messages = serializers.IntegerField()


# ---- patient ----------------------------------------------------------------------------------


@extend_schema_serializer(component_name="PatientDashboard")
class PatientDashboardSerializer(serializers.Serializer):
    reservations = ReservationCountsSerializer()
    upcoming = ReservationBriefSerializer(many=True)
    recent = ReservationBriefSerializer(many=True)
    unread = UnreadSerializer()


# ---- doctor / facility ----------------------------------------------------------------------


@extend_schema_serializer(component_name="DashboardProviderProfile")
class ProviderProfileBlockSerializer(serializers.Serializer):
    display_name = serializers.CharField()
    provider_type = serializers.ChoiceField(choices=ProviderType.choices)
    verification_status = serializers.ChoiceField(choices=VerificationStatus.choices)
    is_visible = serializers.BooleanField()


@extend_schema_serializer(component_name="DashboardReviewSummary")
class ReviewSummarySerializer(serializers.Serializer):
    average_rating = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()
    distribution = RatingDistribution()


@extend_schema_serializer(component_name="DashboardOfferSummary")
class OfferSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    running_now = serializers.IntegerField()
    scheduled = serializers.IntegerField()


@extend_schema_serializer(component_name="DashboardFacilityMemberships")
class FacilityMembershipSerializer(serializers.Serializer):
    active = serializers.IntegerField()
    incoming_requests = serializers.IntegerField()
    outgoing_invitations = serializers.IntegerField()


@extend_schema_serializer(component_name="DoctorDashboard")
class DoctorDashboardSerializer(serializers.Serializer):
    profile = ProviderProfileBlockSerializer()
    reservations = ReservationCountsSerializer()
    upcoming = ProviderAppointmentSerializer(many=True)
    reviews = ReviewSummarySerializer()
    offers = OfferSummarySerializer()
    unread = UnreadSerializer()


@extend_schema_serializer(component_name="FacilityDashboard")
class FacilityDashboardSerializer(DoctorDashboardSerializer):
    practitioners = FacilityMembershipSerializer()


# ---- medical company -------------------------------------------------------------------------


@extend_schema_serializer(component_name="DashboardCompanyProducts")
class CompanyProductsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()
    exposable = serializers.IntegerField()


@extend_schema_serializer(component_name="DashboardCompanyCampaigns")
class CompanyCampaignsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    draft = serializers.IntegerField()
    pending_payment = serializers.IntegerField()
    active = serializers.IntegerField()
    live = serializers.IntegerField()
    ended = serializers.IntegerField()
    rejected = serializers.IntegerField()
    cancelled = serializers.IntegerField()


@extend_schema_serializer(component_name="MedicalCompanyDashboard")
class CompanyDashboardSerializer(serializers.Serializer):
    verification_status = serializers.ChoiceField(choices=CompanyVerificationStatus.choices)
    can_publish = serializers.BooleanField()
    products = CompanyProductsSerializer()
    campaigns = CompanyCampaignsSerializer()
    payments = PaymentStatusCounts()


# ---- recruiter ---------------------------------------------------------------------------------


@extend_schema_serializer(component_name="DashboardOrganization")
class OrganizationBlockSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    verification_status = serializers.ChoiceField(choices=EmployerVerification.choices)
    recruitment_status = serializers.CharField()
    can_recruit = serializers.BooleanField()
    my_role = serializers.CharField()


@extend_schema_serializer(component_name="DashboardRecruiterJobs")
class RecruiterJobsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = JobStatusCounts()
    open_now = serializers.IntegerField()


@extend_schema_serializer(component_name="DashboardRecruiterApplications")
class RecruiterApplicationsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = ApplicationStatusCounts()
    awaiting_review = serializers.IntegerField()
    last_7_days = serializers.IntegerField()


@extend_schema_serializer(component_name="DashboardRecruiterInterviews")
class RecruiterInterviewsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = InterviewStatusCounts()


@extend_schema_serializer(component_name="DashboardSeats")
class SeatsSerializer(serializers.Serializer):
    active_members = serializers.IntegerField()
    enabled = serializers.BooleanField()
    limit = serializers.IntegerField(allow_null=True, help_text="Null means unlimited.")


@extend_schema_serializer(component_name="RecruiterDashboard")
class RecruiterDashboardSerializer(serializers.Serializer):
    organization = OrganizationBlockSerializer()
    jobs = RecruiterJobsSerializer()
    applications_access = serializers.CharField(
        allow_null=True,
        help_text=(
            "Null when applicant aggregates are included; otherwise why they are not: "
            "`organization_not_verified` or `plan_required`."
        ),
    )
    applications = RecruiterApplicationsSerializer(allow_null=True)
    interviews = RecruiterInterviewsSerializer(allow_null=True)
    seats = SeatsSerializer()


# ---- administrator -------------------------------------------------------------------------------
# Counts only; every block is declared so the contract is explicit (no personal data).

VerificationCounts = counts_serializer("DashboardVerificationCounts", VerificationStatus.values)
CompanyVerificationCounts = counts_serializer(
    "DashboardCompanyVerificationCounts", CompanyVerificationStatus.values
)
EmployerVerificationCounts = counts_serializer(
    "DashboardEmployerVerificationCounts", EmployerVerification.values
)
AccountRoleCounts = counts_serializer("DashboardAccountRoleCounts", AccountRole.values)
PublicationCounts = counts_serializer("DashboardPublicationCounts", PublicationStatus.values)
CampaignStatusCounts = counts_serializer("DashboardCampaignStatusCounts", CampaignStatus.values)
SubscriptionStatusCounts = counts_serializer(
    "DashboardSubscriptionStatusCounts", SubscriptionStatus.values
)


@extend_schema_serializer(component_name="DashboardAdminAccounts")
class AdminAccountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()
    by_role = AccountRoleCounts()


@extend_schema_serializer(component_name="DashboardAdminProviders")
class AdminProvidersSerializer(serializers.Serializer):
    by_verification = VerificationCounts()


@extend_schema_serializer(component_name="DashboardAdminCompanies")
class AdminCompaniesSerializer(serializers.Serializer):
    by_verification = CompanyVerificationCounts()


@extend_schema_serializer(component_name="DashboardAdminEmployers")
class AdminEmployersSerializer(serializers.Serializer):
    by_verification = EmployerVerificationCounts()
    recruitment_suspended = serializers.IntegerField()


@extend_schema_serializer(component_name="DashboardAdminJobs")
class AdminJobsSerializer(serializers.Serializer):
    by_status = JobStatusCounts()


@extend_schema_serializer(component_name="DashboardAdminReservations")
class AdminReservationsSerializer(serializers.Serializer):
    by_status = ReservationStatusCounts()


@extend_schema_serializer(component_name="DashboardAdminProducts")
class AdminProductsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()


@extend_schema_serializer(component_name="DashboardAdminMarketplace")
class AdminMarketplaceSerializer(serializers.Serializer):
    products = AdminProductsSerializer()


@extend_schema_serializer(component_name="DashboardAdminRealEstate")
class AdminRealEstateSerializer(serializers.Serializer):
    listings_by_status = PublicationCounts()


@extend_schema_serializer(component_name="DashboardAdminAdvertising")
class AdminAdvertisingSerializer(serializers.Serializer):
    campaigns_by_status = CampaignStatusCounts()
    payments_by_status = PaymentStatusCounts()


@extend_schema_serializer(component_name="DashboardAdminBilling")
class AdminBillingSerializer(serializers.Serializer):
    subscriptions_by_status = SubscriptionStatusCounts()


@extend_schema_serializer(component_name="DashboardAdminAudit")
class AdminAuditSerializer(serializers.Serializer):
    last_24_hours = serializers.IntegerField()
    last_7_days = serializers.IntegerField()


@extend_schema_serializer(component_name="AdminDashboard")
class AdminDashboardSerializer(serializers.Serializer):
    accounts = AdminAccountsSerializer()
    providers = AdminProvidersSerializer()
    medical_companies = AdminCompaniesSerializer()
    employers = AdminEmployersSerializer()
    jobs = AdminJobsSerializer()
    reservations = AdminReservationsSerializer()
    marketplace = AdminMarketplaceSerializer()
    real_estate = AdminRealEstateSerializer()
    advertising = AdminAdvertisingSerializer()
    billing = AdminBillingSerializer()
    audit = AdminAuditSerializer()


# ---- index --------------------------------------------------------------------------------------


@extend_schema_serializer(component_name="DashboardIndex")
class DashboardIndexSerializer(serializers.Serializer):
    dashboards = serializers.ListField(child=serializers.ChoiceField(choices=access.ALL))
