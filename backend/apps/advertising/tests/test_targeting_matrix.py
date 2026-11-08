"""Phase D: one positive/negative targeting matrix for sponsored products («إعلان ممول»).

Five categories, each with an audience rule set by the platform (never by the advertiser), one live
campaign per category. Every viewer must see exactly the campaigns of its own field, through the
real API, and nobody else may see any: dentists see dental supplies (not cardiology), pharmacies
see pharmacy stock, laboratories see lab supplies, therapists see rehabilitation equipment.
Unverified, suspended, consumer and anonymous viewers see nothing; expired or unpaid campaigns
never show; regulated products are never promotable at all."""

from datetime import timedelta

import pytest

from apps.advertising import services
from apps.advertising.models import AdvertisingCampaign
from apps.providers.types import ProviderType, VerificationStatus

from .conftest import SPONSORED, client_for, today

pytestmark = pytest.mark.django_db

FIELDS = ("dental", "cardiology", "pharmacy", "laboratory", "rehab")


@pytest.fixture
def market(
    company_factory, category_factory, product_factory, campaign_factory, make_live,
    dentistry, cardiology,
):  # fmt: skip
    rules = {
        "dental": [(ProviderType.DOCTOR, dentistry)],
        "cardiology": [(ProviderType.DOCTOR, cardiology)],
        "pharmacy": [(ProviderType.PHARMACY, None)],
        "laboratory": [(ProviderType.LABORATORY, None)],
        "rehab": [(ProviderType.THERAPIST, None)],
    }
    company = company_factory(name="Demo Supplies Co")
    campaigns = {}
    for field, rule in rules.items():
        category = category_factory(rules=rule, slug=f"{field}-supplies")
        product = product_factory(company, category, title=f"{field} product")
        campaigns[field] = make_live(campaign_factory(company, product, name=f"{field} campaign"))
    return {"company": company, "campaigns": campaigns}


@pytest.fixture
def viewers(provider_factory, dentistry, cardiology):
    return {
        "dentist": provider_factory(ProviderType.DOCTOR, specialties=[dentistry]),
        "cardiologist": provider_factory(ProviderType.DOCTOR, specialties=[cardiology]),
        "pharmacy": provider_factory(ProviderType.PHARMACY),
        "laboratory": provider_factory(ProviderType.LABORATORY),
        "therapist": provider_factory(ProviderType.THERAPIST),
    }


EXPECTED = {
    "dentist": {"dental"},
    "cardiologist": {"cardiology"},
    "pharmacy": {"pharmacy"},
    "laboratory": {"laboratory"},
    "therapist": {"rehab"},
}


def _seen_via_api(market, provider) -> set[str]:
    """Fields whose campaign the provider receives from GET /advertising/marketplace."""
    response = client_for(provider.account).get(SPONSORED)
    assert response.status_code == 200, response.json()
    by_id = {str(c.pk): field for field, c in market["campaigns"].items()}
    rows = response.json()["results"]
    assert all(row["sponsored"] is True for row in rows)  # the «إعلان ممول» label source
    return {by_id[row["id"]] for row in rows if row["id"] in by_id}


@pytest.mark.parametrize("viewer", sorted(EXPECTED))
def test_each_profession_sees_exactly_its_own_field(market, viewers, viewer):
    provider = viewers[viewer]
    assert _seen_via_api(market, provider) == EXPECTED[viewer]
    # The model rule agrees with the API.
    via_model = {
        field
        for field, campaign in market["campaigns"].items()
        if AdvertisingCampaign.objects.visible_to(provider).filter(pk=campaign.pk).exists()
    }
    assert via_model == EXPECTED[viewer]


def test_unverified_and_suspended_providers_see_nothing(market, provider_factory, dentistry):
    unverified = provider_factory(
        ProviderType.DOCTOR, specialties=[dentistry], verification_status=VerificationStatus.PENDING
    )
    suspended = provider_factory(ProviderType.DOCTOR, specialties=[dentistry])
    suspended.account.is_active = False
    suspended.account.save(update_fields=["is_active"])
    for provider in (unverified, suspended):
        assert not AdvertisingCampaign.objects.visible_to(provider).exists()
    assert client_for(unverified.account).get(SPONSORED).status_code in (403, 404)


def test_consumers_and_anonymous_never_reach_sponsored_b2b_products(
    market, account_factory, api_client
):
    patient = account_factory(role="PATIENT")
    assert client_for(patient).get(SPONSORED).status_code == 403
    assert api_client.get(SPONSORED).status_code in (401, 403)


def test_expired_and_future_campaigns_are_not_shown(market, viewers):
    dental = market["campaigns"]["dental"]
    AdvertisingCampaign.objects.filter(pk=dental.pk).update(
        starts_on=today() - timedelta(days=10), ends_on=today() - timedelta(days=1)
    )
    assert "dental" not in _seen_via_api(market, viewers["dentist"])
    AdvertisingCampaign.objects.filter(pk=dental.pk).update(
        starts_on=today() + timedelta(days=1), ends_on=today() + timedelta(days=5)
    )
    assert "dental" not in _seen_via_api(market, viewers["dentist"])


def test_an_unpaid_campaign_is_not_shown(market, viewers):
    dental = market["campaigns"]["dental"]
    from apps.advertising.models import CampaignPayment

    CampaignPayment.objects.filter(campaign=dental).update(status="PENDING", verified_at=None)
    assert "dental" not in _seen_via_api(market, viewers["dentist"])


def test_a_suspended_seller_stops_every_campaign(market, viewers):
    market["company"].verification_status = "SUSPENDED"
    market["company"].save(update_fields=["verification_status"])
    for viewer in viewers.values():
        assert _seen_via_api(market, viewer) == set()


@pytest.mark.parametrize("regulated", ["restricted_item", "prohibited_category"])
def test_regulated_products_are_never_promotable(
    company_factory, category_factory, product_factory, campaign_factory, rate, regulated
):
    company = company_factory()
    if regulated == "restricted_item":
        product = product_factory(
            company, category_factory(rules=[(ProviderType.PHARMACY, None)]), is_restricted=True
        )
    else:
        product = product_factory(
            company,
            category_factory(rules=[(ProviderType.PHARMACY, None)], compliance_class="PROHIBITED"),
        )
    campaign = campaign_factory(company, product)
    with pytest.raises(services.AdvertisingError):
        services.submit_campaign(company, campaign.pk)
    assert AdvertisingCampaign.objects.get(pk=campaign.pk).status == "DRAFT"
