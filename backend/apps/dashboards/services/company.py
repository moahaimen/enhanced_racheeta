"""Medical-company dashboard: composes the EXISTING marketplace and advertising summaries
(same functions that back their own dashboards) and adds the one missing view, payment status.

No impressions, clicks, conversions or revenue exist, so none are reported.
"""

from __future__ import annotations

from apps.advertising import services as advertising_services
from apps.advertising.models import CampaignPayment
from apps.advertising.types import PaymentStatus
from apps.marketplace import services as marketplace_services

from .common import status_counts


def company_summary(company) -> dict:
    products = marketplace_services.dashboard_summary(company)  # 3 queries (existing)
    campaigns = advertising_services.dashboard_summary(company)  # 1 query (existing)
    payments = status_counts(
        CampaignPayment.objects.filter(campaign__company=company), "status", PaymentStatus.values
    )  # 1 query
    return {
        "verification_status": products["verification_status"],
        "can_publish": products["can_publish"],
        "products": {
            "total": products["products_total"],
            "active": products["products_active"],
            "inactive": products["products_inactive"],
            "exposable": products["products_exposable"],
        },
        "campaigns": {
            "total": campaigns["campaigns_total"],
            "draft": campaigns["campaigns_draft"],
            "pending_payment": campaigns["campaigns_pending_payment"],
            "active": campaigns["campaigns_active"],
            "live": campaigns["campaigns_live"],
            "ended": campaigns["campaigns_ended"],
            "rejected": campaigns["campaigns_rejected"],
            "cancelled": campaigns["campaigns_cancelled"],
        },
        "payments": payments["by_status"],
    }
