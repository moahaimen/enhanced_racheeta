"""Who sees a sponsored campaign: ONE queryset, current database state, server
date, and a campaign that can only NARROW the Phase 6 product targeting."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.advertising.models import AdvertisingCampaign, CampaignPayment
from apps.marketplace.models import MedicalCompany, Product, ProductAudience
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus

from .conftest import SPONSORED, client_for, today

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(
    company_factory, category_factory, product_factory, provider_factory, campaign_factory,
    make_live, baghdad, dentistry,
):  # fmt: skip
    """A category open to doctors with dentistry; a live campaign narrowed to
    DOCTOR + dentistry + Baghdad; and the doctor it reaches."""
    category = category_factory(rules=[(ProviderType.DOCTOR, dentistry)])
    company = company_factory()
    product = product_factory(company, category)
    provider = provider_factory(ProviderType.DOCTOR, specialties=[dentistry], governorate=baghdad)
    campaign = campaign_factory(company, product)
    campaign.target_provider_types.create(provider_type=ProviderType.DOCTOR)
    campaign.target_specialties.create(specialty=dentistry)
    campaign.target_governorates.create(governorate=baghdad)
    campaign = make_live(campaign)
    return {
        "campaign": campaign, "company": company, "product": product,
        "category": category, "provider": provider,
    }  # fmt: skip


def visible(provider):
    return AdvertisingCampaign.objects.visible_to(provider)


def sees(w):
    return visible(w["provider"]).filter(pk=w["campaign"].pk).exists()


def test_a_matching_provider_sees_the_sponsored_campaign(world):
    assert sees(world)
    resp = client_for(world["provider"].account).get(SPONSORED)
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["results"]] == [str(world["campaign"].pk)]


# ---- exposure disappears the moment ANY current fact stops holding ----


def _provider_role(w):
    Account.objects.filter(pk=w["provider"].account_id).update(role=AccountRole.PATIENT)


def _provider_inactive(w):
    Account.objects.filter(pk=w["provider"].account_id).update(is_active=False)


def _provider_unverified(w):
    ProviderProfile.objects.filter(pk=w["provider"].pk).update(
        verification_status=VerificationStatus.SUSPENDED
    )


def _provider_pending(w):
    ProviderProfile.objects.filter(pk=w["provider"].pk).update(
        verification_status=VerificationStatus.PENDING
    )


def _provider_type(w):
    ProviderProfile.objects.filter(pk=w["provider"].pk).update(
        provider_type=ProviderType.LABORATORY
    )


def _provider_specialty(w):
    w["provider"].specialties.clear()


def _provider_geography(w):
    from apps.geography.models import Governorate

    ProviderProfile.objects.filter(pk=w["provider"].pk).update(
        governorate=Governorate.objects.get(slug="basra")
    )


def _company_role(w):
    Account.objects.filter(pk=w["company"].account_id).update(role=AccountRole.PATIENT)


def _company_inactive(w):
    Account.objects.filter(pk=w["company"].account_id).update(is_active=False)


def _company_suspended(w):
    MedicalCompany.objects.filter(pk=w["company"].pk).update(verification_status="SUSPENDED")


def _product_inactive(w):
    Product.objects.filter(pk=w["product"].pk).update(is_active=False)


def _category_inactive(w):
    w["category"].is_active = False
    w["category"].save()


def _audience_gone(w):
    ProductAudience.objects.filter(category=w["category"]).update(is_active=False)


def _payment_pending(w):
    CampaignPayment.objects.filter(campaign=w["campaign"]).update(
        status="PENDING", verified_at=None
    )


def _payment_rejected(w):
    CampaignPayment.objects.filter(campaign=w["campaign"]).update(
        status="REJECTED", verified_at=None
    )


def _status(status):
    def hide(w):
        AdvertisingCampaign.objects.filter(pk=w["campaign"].pk).update(status=status)

    hide.__name__ = f"_status_{status.lower()}"
    return hide


def _not_started(w):
    AdvertisingCampaign.objects.filter(pk=w["campaign"].pk).update(
        starts_on=today() + timedelta(days=1), ends_on=today() + timedelta(days=5)
    )


def _ended(w):
    AdvertisingCampaign.objects.filter(pk=w["campaign"].pk).update(
        starts_on=today() - timedelta(days=5), ends_on=today() - timedelta(days=1)
    )


def _targeted_governorate_deactivated(w):
    from apps.geography.models import Governorate

    Governorate.objects.filter(slug="baghdad").update(is_active=False)


def _narrowing_type_changed(w):
    w["campaign"].target_provider_types.all().delete()
    w["campaign"].target_provider_types.create(provider_type=ProviderType.PHARMACY)


def _narrowing_specialty_changed(w, cardiology=None):
    from apps.specialties.models import Specialty

    w["campaign"].target_specialties.all().delete()
    w["campaign"].target_specialties.create(specialty=Specialty.objects.get(slug="cardiology"))


def _narrowing_geography_changed(w):
    from apps.geography.models import Governorate

    w["campaign"].target_governorates.all().delete()
    w["campaign"].target_governorates.create(governorate=Governorate.objects.get(slug="basra"))


HIDERS = [
    _provider_role, _provider_inactive, _provider_unverified, _provider_pending, _provider_type,
    _provider_specialty, _provider_geography, _company_role, _company_inactive, _company_suspended,
    _product_inactive, _category_inactive, _audience_gone, _payment_pending, _payment_rejected,
    _status("CANCELLED"), _status("PENDING_PAYMENT"), _status("REJECTED"), _status("DRAFT"),
    _not_started, _ended, _targeted_governorate_deactivated, _narrowing_type_changed,
    _narrowing_specialty_changed, _narrowing_geography_changed,
]  # fmt: skip


@pytest.mark.parametrize("hide", HIDERS, ids=lambda f: f.__name__.lstrip("_"))
def test_exposure_disappears_immediately_from_current_state(world, hide):
    assert sees(world)
    hide(world)
    assert not sees(world)
    resp = client_for(world["provider"].account).get(SPONSORED)
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        assert resp.json()["results"] == []


def test_the_window_is_inclusive_on_both_ends(world):
    AdvertisingCampaign.objects.filter(pk=world["campaign"].pk).update(
        starts_on=today(), ends_on=today()
    )
    assert sees(world)  # a one-day campaign is live on that very day
    for day in (today() - timedelta(days=1), today() + timedelta(days=1)):
        hidden = AdvertisingCampaign.objects.visible_to(world["provider"], today=day)
        assert not hidden.filter(pk=world["campaign"].pk).exists()


def test_an_expired_campaign_needs_no_worker_to_disappear(world):
    assert sees(world)
    AdvertisingCampaign.objects.filter(pk=world["campaign"].pk).update(
        starts_on=today() - timedelta(days=5), ends_on=today() - timedelta(days=1)
    )
    stored = AdvertisingCampaign.objects.get(pk=world["campaign"].pk)
    assert stored.status == "ACTIVE"  # still stored ACTIVE …
    assert not sees(world)  # … but not exposed
    annotated = AdvertisingCampaign.objects.with_live_state().get(pk=world["campaign"].pk)
    assert annotated.is_live is False and annotated.is_ended is True


def test_restoring_the_state_restores_exposure(world):
    _company_role(world)
    assert not sees(world)
    Account.objects.filter(pk=world["company"].account_id).update(role=AccountRole.MEDICAL_COMPANY)
    assert sees(world)


# ---- the security invariant: a campaign only NARROWS product targeting ----


def test_campaign_targeting_can_only_narrow_never_broaden_product_targeting(
    category_factory,
    company_factory,
    product_factory,
    provider_factory,
    campaign_factory,
    make_live,
):
    """The category admits ONLY doctors (Phase 6 rule). A campaign that targets
    laboratories must not make the product visible to a laboratory: a paid campaign
    cannot widen access the product's own targeting denies."""
    category = category_factory(rules=[(ProviderType.DOCTOR, None)])
    company = company_factory()
    product = product_factory(company, category)
    doctor = provider_factory(ProviderType.DOCTOR)
    lab = provider_factory(ProviderType.LABORATORY)
    campaign = campaign_factory(company, product)
    campaign.target_provider_types.create(provider_type=ProviderType.LABORATORY)
    make_live(campaign)
    assert not visible(lab).exists()  # B targeted by the campaign, denied by the product rule
    assert not visible(doctor).exists()  # A admitted by the product, excluded by the narrowing
    # targeting both keeps the product rule as the outer boundary
    campaign.target_provider_types.create(provider_type=ProviderType.DOCTOR)
    assert visible(doctor).exists() and not visible(lab).exists()
    # and no targeting at all is exactly the organic audience — never more
    campaign.target_provider_types.all().delete()
    assert visible(doctor).exists() and not visible(lab).exists()
    # the organic catalogue agrees (a campaign never forces a product into it)
    assert not Product.objects.targeted_for(lab).filter(pk=product.pk).exists()
    assert client_for(lab.account).get(SPONSORED).json()["results"] == []


def test_a_campaign_never_forces_an_untargeted_product_into_view(
    category_factory,
    company_factory,
    product_factory,
    provider_factory,
    campaign_factory,
    make_live,
):
    category = category_factory()  # no audience rules at all
    company = company_factory()
    product = product_factory(company, category)
    provider = provider_factory(ProviderType.DOCTOR)
    make_live(campaign_factory(company, product))
    assert not visible(provider).exists()


def test_a_campaign_cannot_borrow_another_companys_product(
    world, company_factory, campaign_factory, make_live
):
    intruder = company_factory()
    stolen = campaign_factory(intruder, world["product"])  # crafted around the services
    make_live(stolen)
    assert not visible(world["provider"]).filter(pk=stolen.pk).exists()


@pytest.mark.parametrize(
    "narrowing,matches",
    [
        ("types_empty", True),
        ("types_match", True),
        ("types_other", False),
        ("specialties_empty", True),
        ("specialties_match", True),
        ("specialties_other", False),
        ("governorates_empty", True),
        ("governorates_match", True),
        ("governorates_other", False),
    ],
)
def test_each_narrowing_dimension(
    category_factory, company_factory, product_factory, provider_factory, campaign_factory,
    make_live, baghdad, basra, dentistry, cardiology, narrowing, matches,
):  # fmt: skip
    category = category_factory(rules=[(ProviderType.DOCTOR, None)])
    company = company_factory()
    product = product_factory(company, category)
    provider = provider_factory(ProviderType.DOCTOR, specialties=[dentistry], governorate=baghdad)
    campaign = campaign_factory(company, product)
    kind, how = narrowing.split("_")
    if how != "empty":
        if kind == "types":
            campaign.target_provider_types.create(
                provider_type=ProviderType.DOCTOR if how == "match" else ProviderType.NURSE
            )
        elif kind == "specialties":
            campaign.target_specialties.create(
                specialty=dentistry if how == "match" else cardiology
            )
        else:
            campaign.target_governorates.create(governorate=baghdad if how == "match" else basra)
    make_live(campaign)
    assert visible(provider).exists() is matches


def test_a_provider_matching_any_one_selected_specialty_is_enough(world, dentistry, cardiology):
    world["campaign"].target_specialties.create(specialty=cardiology)  # dentistry OR cardiology
    assert sees(world)


def test_a_multi_governorate_campaign_ignores_a_deactivated_one_the_provider_is_not_in(
    world, basra
):
    world["campaign"].target_governorates.create(governorate=basra)
    basra.is_active = False
    basra.save()
    assert sees(world)  # the provider's own targeted governorate (Baghdad) is still active


# ---- the provider API ----


def test_only_eligible_providers_reach_the_sponsored_api(world, account_factory, provider_factory):
    assert APIClient().get(SPONSORED).status_code == 401
    for role in (AccountRole.PATIENT, AccountRole.MEDICAL_COMPANY, AccountRole.REAL_ESTATE_SELLER):
        assert client_for(account_factory(role=role)).get(SPONSORED).status_code == 403
    unverified = provider_factory(verification_status=VerificationStatus.UNVERIFIED)
    assert client_for(unverified.account).get(SPONSORED).status_code == 403


def test_the_ad_payload_is_the_product_plus_the_window_and_nothing_commercial(world):
    row = client_for(world["provider"].account).get(SPONSORED).json()["results"][0]
    assert set(row) == {"id", "sponsored", "starts_on", "ends_on", "product"}
    assert row["sponsored"] is True
    assert row["product"]["id"] == str(world["product"].pk)
    assert set(row["product"]) >= {"id", "title", "price", "category", "company"}
    import json

    text = json.dumps(row)
    for key in (
        "quote", "quoted_amount", "payment", "amount", "admin_note", "reference",
        "verified_by", "status", "rate", "company_id",
    ):  # fmt: skip
        assert f'"{key}"' not in text, key
    assert "@example.com" not in text


def test_the_organic_marketplace_is_unchanged_by_a_campaign(world):
    organic = client_for(world["provider"].account).get("/api/v1/marketplace/products").json()
    assert [r["id"] for r in organic["results"]] == [str(world["product"].pk)]
    assert "sponsored" not in str(organic)


def test_ads_are_paginated_in_a_stable_order(
    company_factory,
    category_factory,
    product_factory,
    provider_factory,
    campaign_factory,
    make_live,
):
    category = category_factory(rules=[(ProviderType.DOCTOR, None)])
    company = company_factory()
    product = product_factory(company, category)
    provider = provider_factory(ProviderType.DOCTOR)
    for _ in range(23):
        make_live(campaign_factory(company, product, ends_on=today() + timedelta(days=5)))
    client = client_for(provider.account)
    first = client.get(SPONSORED).json()
    assert first["count"] == 23 and len(first["results"]) == 20 and first["next"]
    seen = [r["id"] for r in first["results"]] + [
        r["id"] for r in client.get(f"{SPONSORED}?page=2").json()["results"]
    ]
    assert len(seen) == 23 and len(set(seen)) == 23
    assert seen == [r["id"] for r in client.get(SPONSORED).json()["results"]] + seen[20:]


def _count_queries(client):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(SPONSORED).status_code == 200
    return len(ctx)


def test_the_sponsored_query_count_does_not_grow_with_the_number_of_campaigns(
    company_factory, category_factory, product_factory, provider_factory, campaign_factory,
    make_live, baghdad, dentistry, cardiology,
):  # fmt: skip
    category = category_factory(rules=[(ProviderType.DOCTOR, None)])
    provider = provider_factory(ProviderType.DOCTOR, specialties=[dentistry], governorate=baghdad)
    client = client_for(provider.account)

    def add():
        company = company_factory()
        campaign = campaign_factory(company, product_factory(company, category))
        campaign.target_provider_types.create(provider_type=ProviderType.DOCTOR)
        campaign.target_specialties.create(specialty=dentistry)
        campaign.target_specialties.create(specialty=cardiology)
        campaign.target_governorates.create(governorate=baghdad)
        make_live(campaign)

    add()
    few = _count_queries(client)
    for _ in range(12):
        add()
    many = _count_queries(client)
    assert few == many and many <= 8
