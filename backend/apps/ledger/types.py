"""Marketplace accounting vocabulary (docs/MARKETPLACE_COMMERCE.md §Ledger).

This domain is ONLY for merchandise sales. Advertising payments (advertising.CampaignPayment) and
subscriptions (billing) are separate and never posted here.

Accounts (double entry; every entry balances):
  PLATFORM_CASH          asset      simulated money Racheeta holds (demo: no real money)
  CUSTOMER_FUNDS_HELD    liability  paid by buyers, not yet earned (until the order completes)
  SELLER_PAYABLE         liability  owed to one seller (per company)
  COMMISSION_REVENUE     revenue    Racheeta's 20% commission
  PLATFORM_PROMO_EXPENSE expense    platform-funded coupons (never charged to sellers)
"""

from django.db import models


class Account(models.TextChoices):
    PLATFORM_CASH = "PLATFORM_CASH", "Platform cash (simulated)"
    CUSTOMER_FUNDS_HELD = "CUSTOMER_FUNDS_HELD", "Customer funds held"
    SELLER_PAYABLE = "SELLER_PAYABLE", "Seller payable"
    COMMISSION_REVENUE = "COMMISSION_REVENUE", "Commission revenue"
    PLATFORM_PROMO_EXPENSE = "PLATFORM_PROMO_EXPENSE", "Platform promotion expense"


class EntryKind(models.TextChoices):
    PAYMENT = "PAYMENT", "Payment verified (simulated)"
    ACCRUAL = "ACCRUAL", "Sale completed: commission and seller payable accrued"
    REFUND = "REFUND", "Refund (compensating)"
    PAYOUT = "PAYOUT", "Seller payout (simulated)"


class SettlementStatus(models.TextChoices):
    DRAFT = "DRAFT", "Prepared, awaiting finance confirmation"
    PAID = "PAID", "Marked paid (simulated)"
    CANCELLED = "CANCELLED", "Cancelled"


# Iraqi dinar has no minor unit in practice: every amount is a whole dinar (ROUND_HALF_UP).
SUPPORTED_CURRENCY = "IQD"
DEFAULT_COMMISSION_RATE = "20.00"
