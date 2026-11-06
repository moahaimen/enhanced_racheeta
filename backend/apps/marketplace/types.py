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
# Verified identity (ADR-045): frozen for the company while review is pending
# or granted; description, phone and public email stay editable.
COMPANY_IDENTITY_FIELDS = ("name", "business_type", "governorate", "city", "address", "website")
IDENTITY_LOCKED_STATUSES = frozenset(
    {CompanyVerificationStatus.PENDING, CompanyVerificationStatus.VERIFIED}
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


class BusinessType(models.TextChoices):
    """Normalized classification of a MedicalCompany (the business behind the account).

    Existing companies are MEDICAL_COMPANY (data migration), which behaves exactly as before.
    """

    MEDICAL_COMPANY = "MEDICAL_COMPANY", "Medical company"
    PHARMACEUTICAL_COMPANY = "PHARMACEUTICAL_COMPANY", "Pharmaceutical company"
    SCIENTIFIC_OFFICE = "SCIENTIFIC_OFFICE", "Scientific office"
    MEDICAL_SUPPLIES_OFFICE = "MEDICAL_SUPPLIES_OFFICE", "Medical supplies office"
    EQUIPMENT_SUPPLIER = "EQUIPMENT_SUPPLIER", "Medical equipment supplier"
    ASSISTIVE_DEVICE_STORE = "ASSISTIVE_DEVICE_STORE", "Assistive devices store"
    PHARMA_DISTRIBUTOR = "PHARMA_DISTRIBUTOR", "Pharmaceutical distributor"


# Businesses that may sell allowed products directly to the public (B2C). Pharmaceutical
# companies, scientific offices and distributors are B2B only.
RETAIL_BUSINESS_TYPES = frozenset(
    {
        BusinessType.ASSISTIVE_DEVICE_STORE,
        BusinessType.EQUIPMENT_SUPPLIER,
        BusinessType.MEDICAL_SUPPLIES_OFFICE,
    }
)


class SaleChannel(models.TextChoices):
    B2B = "B2B", "Professionals only (targeted)"
    B2C = "B2C", "Public store only"
    BOTH = "BOTH", "Professionals and public store"


CONSUMER_CHANNELS = frozenset({SaleChannel.B2C, SaleChannel.BOTH})
PROFESSIONAL_CHANNELS = frozenset({SaleChannel.B2B, SaleChannel.BOTH})


class ComplianceClass(models.TextChoices):
    """Server-controlled sale eligibility of a CATEGORY (fail closed: unknown = not purchasable).
    A seller's own title, category choice or description can never grant more than this."""

    B2C_ALLOWED = "B2C_ALLOWED", "Public store allowed"
    B2B_VERIFIED_ONLY = "B2B_VERIFIED_ONLY", "Verified professional buyers only"
    QUOTE_ONLY = "QUOTE_ONLY", "Quotation only"
    RESTRICTED_PENDING_REVIEW = "RESTRICTED_PENDING_REVIEW", "Restricted - legal review required"
    PROHIBITED = "PROHIBITED", "Prohibited"


NOT_PURCHASABLE_CLASSES = frozenset(
    {ComplianceClass.RESTRICTED_PENDING_REVIEW, ComplianceClass.PROHIBITED}
)
