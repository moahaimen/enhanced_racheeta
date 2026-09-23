"""Controlled provider classification. The backend is authoritative.

Adding a provider type: add it here, to the right kind set, to the web
translations (`providerTypes.*`) and to docs/PERMISSIONS.md. A migration is
needed because the field choices change.
"""

from django.db import models


class ProviderType(models.TextChoices):
    # Practitioners (people)
    DOCTOR = "DOCTOR", "Doctor"
    NURSE = "NURSE", "Nurse"
    THERAPIST = "THERAPIST", "Therapist"
    # Facilities (organisations)
    HOSPITAL = "HOSPITAL", "Hospital"
    MEDICAL_CENTER = "MEDICAL_CENTER", "Medical center"
    PHARMACY = "PHARMACY", "Pharmacy"
    LABORATORY = "LABORATORY", "Laboratory"
    BEAUTY_CENTER = "BEAUTY_CENTER", "Beauty center"


class ProviderKind(models.TextChoices):
    PRACTITIONER = "PRACTITIONER", "Practitioner"
    FACILITY = "FACILITY", "Facility"


PRACTITIONER_TYPES = frozenset({ProviderType.DOCTOR, ProviderType.NURSE, ProviderType.THERAPIST})
FACILITY_TYPES = frozenset(
    {
        ProviderType.HOSPITAL,
        ProviderType.MEDICAL_CENTER,
        ProviderType.PHARMACY,
        ProviderType.LABORATORY,
        ProviderType.BEAUTY_CENTER,
    }
)
assert PRACTITIONER_TYPES | FACILITY_TYPES == frozenset(ProviderType.values)  # noqa: S101


def kind_of(provider_type: str) -> str:
    return (
        ProviderKind.PRACTITIONER if provider_type in PRACTITIONER_TYPES else ProviderKind.FACILITY
    )


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    PENDING = "PENDING", "Pending review"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"
    SUSPENDED = "SUSPENDED", "Suspended"


# Provider-initiated transition: request review.
VERIFICATION_REQUESTABLE_FROM = frozenset(
    {VerificationStatus.UNVERIFIED, VerificationStatus.REJECTED}
)
# Admin-settable targets (from any state).
ADMIN_VERIFICATION_TARGETS = frozenset(
    {
        VerificationStatus.VERIFIED,
        VerificationStatus.REJECTED,
        VerificationStatus.SUSPENDED,
        VerificationStatus.UNVERIFIED,
    }
)


class MembershipStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    REJECTED = "REJECTED", "Rejected"
    ENDED = "ENDED", "Ended"


class MembershipSide(models.TextChoices):
    PRACTITIONER = "PRACTITIONER", "Practitioner"
    FACILITY = "FACILITY", "Facility"
