"""Controlled vocabularies of medical real estate (Phase 7). Codes derive from
Master Plan section 15; clients can never invent values."""

from django.db import models


class SellerType(models.TextChoices):
    OWNER = "OWNER", "Owner"
    AGENT = "AGENT", "Agent"


class PropertyType(models.TextChoices):
    CLINIC = "CLINIC", "Clinic"
    APARTMENT_FOR_CLINIC = "APARTMENT_FOR_CLINIC", "Apartment suitable for a clinic"
    MEDICAL_BUILDING = "MEDICAL_BUILDING", "Medical building"
    PHARMACY_LOCATION = "PHARMACY_LOCATION", "Pharmacy location"
    LABORATORY_LOCATION = "LABORATORY_LOCATION", "Laboratory location"
    MEDICAL_CENTER = "MEDICAL_CENTER", "Medical center"
    HOSPITAL_BUILDING = "HOSPITAL_BUILDING", "Hospital building"
    COMMERCIAL_MEDICAL_PROPERTY = (
        "COMMERCIAL_MEDICAL_PROPERTY",
        "Commercial property suitable for medical use",
    )
    MEDICAL_INVESTMENT_LAND = "MEDICAL_INVESTMENT_LAND", "Land for medical investment"


class TransactionType(models.TextChoices):
    SALE = "SALE", "Sale"
    RENT = "RENT", "Rent"


class SuitableUse(models.TextChoices):
    CLINIC = "CLINIC", "Clinic"
    PHARMACY = "PHARMACY", "Pharmacy"
    LABORATORY = "LABORATORY", "Laboratory"
    MEDICAL_CENTER = "MEDICAL_CENTER", "Medical center"
    HOSPITAL = "HOSPITAL", "Hospital"
    GENERAL_MEDICAL_USE = "GENERAL_MEDICAL_USE", "General medical use"
    MEDICAL_INVESTMENT = "MEDICAL_INVESTMENT", "Medical investment"


class ContactMethod(models.TextChoices):
    PHONE = "PHONE", "Phone"
    EMAIL = "EMAIL", "Email"
    BOTH = "BOTH", "Phone and email"


class PublicationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"


# Which stored contact values a contact method makes public.
PHONE_METHODS = frozenset({ContactMethod.PHONE, ContactMethod.BOTH})
EMAIL_METHODS = frozenset({ContactMethod.EMAIL, ContactMethod.BOTH})

# Fixed display order of suitable uses (stable API output).
SUITABLE_USE_ORDER = {use.value: index for index, use in enumerate(SuitableUse)}
