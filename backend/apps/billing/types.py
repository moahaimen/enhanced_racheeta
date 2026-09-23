from django.db import models


class Audience(models.TextChoices):
    EMPLOYER = "EMPLOYER", "Employer organisation"
    JOB_SEEKER = "JOB_SEEKER", "Job seeker"


class BillingPeriod(models.TextChoices):
    NONE = "NONE", "No renewal (default / trial)"
    MONTHLY = "MONTHLY", "Monthly"
    QUARTERLY = "QUARTERLY", "Quarterly"
    YEARLY = "YEARLY", "Yearly"


class EntitlementKind(models.TextChoices):
    BOOLEAN = "BOOLEAN", "Capability on/off"
    LIMIT = "LIMIT", "Numeric limit"


class UsagePeriod(models.TextChoices):
    NONE = "NONE", "Concurrent count (not consumed)"
    DAILY = "DAILY", "Per day"
    MONTHLY = "MONTHLY", "Per calendar month"
    SUBSCRIPTION = "SUBSCRIPTION", "Per subscription term"


class SubscriptionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending administrator approval"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"
    REJECTED = "REJECTED", "Rejected"


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
    CASH = "CASH", "Cash"
    EXCHANGE_OFFICE = "EXCHANGE_OFFICE", "Exchange office"
    OTHER = "OTHER", "Other"


class PaymentStatus(models.TextChoices):
    RECORDED = "RECORDED", "Recorded"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class CreditReason(models.TextChoices):
    GRANT = "GRANT", "Administrator grant"
    REVOKE = "REVOKE", "Administrator revoke"
    CONSUME = "CONSUME", "Consumed by usage"
    REFUND = "REFUND", "Refund"


class SubjectType(models.TextChoices):
    ORGANIZATION = "organization", "Organisation"
    ACCOUNT = "account", "Account"


# Entitlement keys. Business modules reference these constants; plans decide values.
class Keys:
    JOBS_POST = "jobs.post"
    JOBS_ACTIVE_LIMIT = "jobs.active_limit"
    JOBS_FEATURED = "jobs.featured"
    JOBS_FEATURED_LIMIT = "jobs.featured_limit"
    JOBS_APPLICATION_REVIEW = "jobs.application_review"
    TALENT_SEARCH = "talent.search"
    TALENT_SEARCH_LIMIT = "talent.search_limit"
    TALENT_INVITE = "talent.invite"
    TALENT_INVITE_LIMIT = "talent.invite_limit"
    TALENT_SAVE = "talent.save_candidate"
    RECRUITER_SEATS = "recruiter.seats"
    RECRUITMENT_MESSAGING = "recruitment.messaging"
    APPLICATIONS_LIMIT = "applications.limit"


KNOWN_KEYS: dict[str, tuple[str, str]] = {
    # key: (kind, usage period)
    Keys.JOBS_POST: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.JOBS_ACTIVE_LIMIT: (EntitlementKind.LIMIT, UsagePeriod.NONE),
    Keys.JOBS_FEATURED: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.JOBS_FEATURED_LIMIT: (EntitlementKind.LIMIT, UsagePeriod.NONE),
    Keys.JOBS_APPLICATION_REVIEW: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.TALENT_SEARCH: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.TALENT_SEARCH_LIMIT: (EntitlementKind.LIMIT, UsagePeriod.MONTHLY),
    Keys.TALENT_INVITE: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.TALENT_INVITE_LIMIT: (EntitlementKind.LIMIT, UsagePeriod.MONTHLY),
    Keys.TALENT_SAVE: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.RECRUITER_SEATS: (EntitlementKind.LIMIT, UsagePeriod.NONE),
    Keys.RECRUITMENT_MESSAGING: (EntitlementKind.BOOLEAN, UsagePeriod.NONE),
    Keys.APPLICATIONS_LIMIT: (EntitlementKind.LIMIT, UsagePeriod.MONTHLY),
}
