"""A laboratory-targeted sponsored campaign, shaped like the local demo one
(`apps/demo/content/local_extras.CAMPAIGNS` "lab-live"): a lab-equipment product whose category
reaches laboratories AND hospitals, narrowed by the campaign to laboratories only.

A qualified laboratory sees it («إعلان ممول») and is notified once; every other profession,
including a hospital that may buy the same category, does not. Opting out (display or marketing)
and any suspension (the lab, the seller, the campaign) suppress it at once."""

import pytest

from apps.advertising.models import AdvertisingCampaign, CampaignProviderType
from apps.advertising.outreach import notify_campaign_audience
from apps.notifications.models import Notification
from apps.preferences import services as preferences
from apps.providers.types import ProviderType, VerificationStatus

from .conftest import SPONSORED, client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def lab_campaign(company_factory, category_factory, product_factory, campaign_factory, make_live):
    company = company_factory(name="Rafidain LabTech (demo)")
    category = category_factory(
        rules=[(ProviderType.LABORATORY, None), (ProviderType.HOSPITAL, None)],
        slug="laboratory-equipment",
    )
    product = product_factory(company, category, title="Automated hematology analyzer")
    campaign = make_live(campaign_factory(company, product, name="Lab analyzer launch"))
    CampaignProviderType.objects.create(campaign=campaign, provider_type=ProviderType.LABORATORY)
    return campaign


@pytest.fixture
def audience(provider_factory, dentistry, cardiology):
    """Every viewer opted in to product alerts (off by default), so only targeting decides."""
    viewers = {
        "laboratory": provider_factory(ProviderType.LABORATORY),
        "hospital": provider_factory(ProviderType.HOSPITAL),
        "medical_center": provider_factory(ProviderType.MEDICAL_CENTER),
        "dentist": provider_factory(ProviderType.DOCTOR, specialties=[dentistry]),
        "cardiologist": provider_factory(ProviderType.DOCTOR, specialties=[cardiology]),
        "pharmacy": provider_factory(ProviderType.PHARMACY),
        "therapist": provider_factory(ProviderType.THERAPIST),
        "nurse": provider_factory(ProviderType.NURSE),
        "beauty_center": provider_factory(ProviderType.BEAUTY_CENTER),
    }
    for provider in viewers.values():
        preferences.update(provider.account, {"offers_and_news": True})
    return viewers


def _sees(provider, campaign) -> bool:
    response = client_for(provider.account).get(SPONSORED)
    assert response.status_code == 200, response.json()
    rows = [row for row in response.json()["results"] if row["id"] == str(campaign.pk)]
    assert all(row["sponsored"] is True for row in rows)
    return bool(rows)


def test_only_the_laboratory_sees_the_lab_campaign(lab_campaign, audience):
    seen = {name for name, provider in audience.items() if _sees(provider, lab_campaign)}
    assert seen == {"laboratory"}


def test_the_hospital_could_buy_the_category_but_the_campaign_narrows_it_out(
    lab_campaign, audience
):
    # Without the campaign's narrowing the hospital is in the category audience...
    CampaignProviderType.objects.filter(campaign=lab_campaign).delete()
    assert _sees(audience["hospital"], lab_campaign)
    # ...the advertiser can only narrow, never widen: back to laboratories only.
    CampaignProviderType.objects.create(
        campaign=lab_campaign, provider_type=ProviderType.LABORATORY
    )
    assert not _sees(audience["hospital"], lab_campaign)


def test_going_live_notifies_only_the_laboratory(lab_campaign, audience):
    sent = notify_campaign_audience(lab_campaign.pk)
    recipients = set(
        Notification.objects.filter(event_type="SPONSORED_PRODUCT").values_list(
            "recipient_id", flat=True
        )
    )
    assert sent == 1 and recipients == {audience["laboratory"].account_id}
    assert notify_campaign_audience(lab_campaign.pk) == 0  # deduplicated


def test_the_display_opt_out_hides_it_at_once(lab_campaign, audience):
    lab = audience["laboratory"]
    preferences.update(lab.account, {"show_sponsored_products": False})
    assert not _sees(lab, lab_campaign)
    preferences.update(lab.account, {"show_sponsored_products": True})
    assert _sees(lab, lab_campaign)


def test_the_marketing_opt_out_stops_the_notification_but_not_the_label(lab_campaign, audience):
    lab = audience["laboratory"]
    preferences.update(lab.account, {"offers_and_news": False})
    assert notify_campaign_audience(lab_campaign.pk) == 0
    assert not Notification.objects.filter(recipient=lab.account).exists()
    assert _sees(lab, lab_campaign)  # a display preference, not a consent, governs the feed


@pytest.mark.parametrize("how", ["verification", "account"])
def test_a_suspended_laboratory_sees_nothing(lab_campaign, audience, how):
    lab = audience["laboratory"]
    if how == "verification":
        lab.verification_status = VerificationStatus.SUSPENDED
        lab.save(update_fields=["verification_status"])
        assert client_for(lab.account).get(SPONSORED).status_code in (403, 404)
    else:
        lab.account.is_active = False
        lab.account.save(update_fields=["is_active"])
    assert not AdvertisingCampaign.objects.visible_to(lab).filter(pk=lab_campaign.pk).exists()
    assert notify_campaign_audience(lab_campaign.pk) == 0


def test_a_suspended_seller_or_a_cancelled_campaign_is_suppressed(lab_campaign, audience):
    lab = audience["laboratory"]
    company = lab_campaign.company
    company.verification_status = "SUSPENDED"
    company.save(update_fields=["verification_status"])
    assert not _sees(lab, lab_campaign)
    company.verification_status = "VERIFIED"
    company.save(update_fields=["verification_status"])
    assert _sees(lab, lab_campaign)
    AdvertisingCampaign.objects.filter(pk=lab_campaign.pk).update(status="CANCELLED")
    assert not _sees(lab, lab_campaign)
