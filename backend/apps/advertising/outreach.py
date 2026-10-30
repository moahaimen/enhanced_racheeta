"""Targeted in-app notifications when a sponsored campaign goes live.

Recipients are exactly the providers the visibility rule
(`AdvertisingCampaign.objects.visible_to`) admits at send time, filtered by their
marketing consent and the daily cap in `apps.preferences.outreach`.
"""

from __future__ import annotations

from apps.accounts.roles import AccountRole
from apps.notifications.types import NotificationEventType, NotificationResourceType
from apps.preferences import outreach
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus

from .models import AdvertisingCampaign


def _audience(campaign: AdvertisingCampaign):
    candidates = ProviderProfile.objects.filter(
        verification_status=VerificationStatus.VERIFIED,
        account__is_active=True,
        account__role=AccountRole.PROVIDER,
    )
    wanted_types = list(campaign.target_provider_types.values_list("provider_type", flat=True))
    if wanted_types:
        candidates = candidates.filter(provider_type__in=wanted_types)
    for provider in candidates.order_by("pk").iterator(chunk_size=200):
        if AdvertisingCampaign.objects.visible_to(provider).filter(pk=campaign.pk).exists():
            yield provider.account_id


def notify_campaign_audience(campaign_id) -> int:
    campaign = (
        AdvertisingCampaign.objects.select_related("product", "company")
        .filter(pk=campaign_id)
        .first()
    )
    if campaign is None:
        return 0
    return outreach.deliver(
        account_ids=_audience(campaign),
        topic="sponsored_products",
        event_type=NotificationEventType.SPONSORED_PRODUCT,
        dedupe_prefix=f"sponsored:{campaign.pk}",
        resource_type=NotificationResourceType.PRODUCT,
        resource_id=campaign.product_id,
        payload={
            "product_title": campaign.product.title,
            "company_name": campaign.company.name,
        },
    )
