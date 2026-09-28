"""Controlled vocabularies of the medical marketplace (Phase 6)."""

from django.db import models


class CompanyVerificationStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    PENDING = "PENDING", "Pending review"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"
    SUSPENDED = "SUSPENDED", "Suspended"


# Company-initiated: ask for review.
VERIFICATION_REQUESTABLE_FROM = frozenset(
    {CompanyVerificationStatus.UNVERIFIED, CompanyVerificationStatus.REJECTED}
)
# Administrator-settable outcomes.
ADMIN_VERIFICATION_TARGETS = frozenset(
    {
        CompanyVerificationStatus.VERIFIED,
        CompanyVerificationStatus.REJECTED,
        CompanyVerificationStatus.SUSPENDED,
        CompanyVerificationStatus.UNVERIFIED,
    }
)
VERIFICATION_DECISION_CHOICES = [
    (s.value, s.label)
    for s in (
        CompanyVerificationStatus.VERIFIED,
        CompanyVerificationStatus.REJECTED,
        CompanyVerificationStatus.SUSPENDED,
        CompanyVerificationStatus.UNVERIFIED,
    )
]
