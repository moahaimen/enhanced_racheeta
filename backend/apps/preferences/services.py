"""Reading and writing marketing preferences. Absence of a row means the defaults."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from .models import DEFAULTS, FIELDS, MarketingPreference

# Topics an outreach notification can belong to -> the OUTREACH consent field that gates it.
# Display preferences (`show_sponsored_products`) never authorize a notification: a sponsored
# product alert needs the separate opt-in `offers_and_news` (off by default).
TOPIC_FIELD = {
    "sponsored_products": "offers_and_news",
    "real_estate": "real_estate_promotions",
    "jobs": "job_alerts",
    "offers": "offers_and_news",
}


def get(account) -> dict:
    row = MarketingPreference.objects.filter(account_id=account.pk).values(*FIELDS).first()
    return {**DEFAULTS, **(row or {})}


def wants_in_app(account_id, topic: str) -> bool:
    """May a marketing notification of this topic be created in-app for this account NOW?"""
    row = MarketingPreference.objects.filter(account_id=account_id).values(*FIELDS).first()
    prefs = {**DEFAULTS, **(row or {})}
    return bool(prefs["channel_in_app"] and prefs[TOPIC_FIELD[topic]])


@transaction.atomic
def update(account, changes: dict) -> dict:
    row, _ = MarketingPreference.objects.select_for_update().get_or_create(account=account)
    changed = sorted(k for k, v in changes.items() if k in FIELDS and getattr(row, k) != v)
    for key in changed:
        setattr(row, key, bool(changes[key]))
    if changed:
        row.consent_updated_at = timezone.now()
        row.save()
        audit.record(
            actor=account,
            action="preferences.marketing.updated",
            target=row,
            summary=", ".join(changed),
            data={k: getattr(row, k) for k in changed},
        )
    return get(account)
