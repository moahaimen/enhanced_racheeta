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
    # A licensed pharmacy (a PROVIDER facility) that also runs a store. It keeps its healthcare
    # provider account and profile; the store is linked to that facility (MedicalCompany.facility).
    PHARMACY = "PHARMACY", "Pharmacy"


# Businesses that may sell allowed products directly to the public (B2C). Pharmaceutical
# companies, scientific offices and distributors are B2B only. What a store may sell is still
# decided per category (compliance class): a pharmacy never sells prescription medicine online.
RETAIL_BUSINESS_TYPES = frozenset(
    {
        BusinessType.ASSISTIVE_DEVICE_STORE,
        BusinessType.EQUIPMENT_SUPPLIER,
        BusinessType.MEDICAL_SUPPLIES_OFFICE,
        BusinessType.PHARMACY,
    }
)
# Business types a MEDICAL_COMPANY account may choose itself. PHARMACY is reserved for stores
# opened from a pharmacy provider profile (the facility link proves it).
COMPANY_SELECTABLE_TYPES = frozenset(BusinessType.values) - {BusinessType.PHARMACY}


class StoreStatus(models.TextChoices):
    """The seller's own switch, separate from Racheeta's verification. A store sells only when it
    is ACTIVE *and* verified. New stores start INACTIVE; activation needs verification and every
    required document approved."""

    INACTIVE = "INACTIVE", "Not activated"
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused by the seller"


class TaxMode(models.TextChoices):
    """How the SELLER says its prices treat tax. Racheeta does not decide tax obligations: the
    default is NONE (no tax line). INCLUSIVE only shows the included part on invoices; EXCLUSIVE
    adds a tax line the seller declared, passed through to the seller (no commission on it)."""

    NONE = "NONE", "No tax shown"
    INCLUSIVE = "INCLUSIVE", "Prices include tax"
    EXCLUSIVE = "EXCLUSIVE", "Tax added at checkout"


MAX_TAX_RATE = 30  # percent; a sanity bound on what a seller can declare


class SellerDocumentKind(models.TextChoices):
    COMMERCIAL_REGISTRATION = "COMMERCIAL_REGISTRATION", "Commercial registration"
    PHARMACY_LICENSE = "PHARMACY_LICENSE", "Pharmacy practice licence"
    MOH_IMPORT_LICENSE = "MOH_IMPORT_LICENSE", "Ministry of Health import / trade licence"
    SCIENTIFIC_OFFICE_LICENSE = "SCIENTIFIC_OFFICE_LICENSE", "Scientific office licence"
    DEVICE_REGISTRATION = "DEVICE_REGISTRATION", "Medical device registration"
    OWNER_ID = "OWNER_ID", "Owner identity document"
    OTHER = "OTHER", "Other supporting document"


class DocumentStatus(models.TextChoices):
    PENDING = "PENDING", "Waiting for review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


_D = SellerDocumentKind
# What Racheeta needs to see before a store can be verified and activated (per business type).
# Fictional, conservative local rule set — not a statement of Iraqi licensing law.
REQUIRED_DOCUMENTS: dict[str, tuple[str, ...]] = {
    BusinessType.MEDICAL_COMPANY: (_D.COMMERCIAL_REGISTRATION,),
    BusinessType.PHARMACEUTICAL_COMPANY: (_D.COMMERCIAL_REGISTRATION, _D.MOH_IMPORT_LICENSE),
    BusinessType.SCIENTIFIC_OFFICE: (_D.COMMERCIAL_REGISTRATION, _D.SCIENTIFIC_OFFICE_LICENSE),
    BusinessType.MEDICAL_SUPPLIES_OFFICE: (_D.COMMERCIAL_REGISTRATION,),
    BusinessType.EQUIPMENT_SUPPLIER: (_D.COMMERCIAL_REGISTRATION, _D.DEVICE_REGISTRATION),
    BusinessType.ASSISTIVE_DEVICE_STORE: (_D.COMMERCIAL_REGISTRATION,),
    BusinessType.PHARMA_DISTRIBUTOR: (_D.COMMERCIAL_REGISTRATION, _D.MOH_IMPORT_LICENSE),
    BusinessType.PHARMACY: (_D.PHARMACY_LICENSE, _D.OWNER_ID),
}
assert set(REQUIRED_DOCUMENTS) == set(BusinessType.values)  # noqa: S101


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
