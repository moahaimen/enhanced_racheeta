"""Controlled vocabularies of advertising (Phase 8)."""

from django.db import models


class CampaignStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_PAYMENT = "PENDING_PAYMENT", "Pending payment verification"
    ACTIVE = "ACTIVE", "Active"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class PaymentMethod(models.TextChoices):
    """Off-platform payment channels an administrator can record. Same documented
    meaning as billing.PaymentMethod; defined here so advertising does not depend
    on the subscription payment model."""

    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
    CASH = "CASH", "Cash"
    EXCHANGE_OFFICE = "EXCHANGE_OFFICE", "Exchange office"
    OTHER = "OTHER", "Other"


# Only a DRAFT is editable; everything after submission is frozen.
EDITABLE_STATUSES = frozenset({CampaignStatus.DRAFT})
PENDING_PAYMENT_STATES = frozenset({CampaignStatus.PENDING_PAYMENT})
