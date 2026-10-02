"""Medical-company dashboard: composes the existing summaries + payment status."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.advertising import services as advertising_services
from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.marketplace import services as marketplace_services
from apps.marketplace.types import CompanyVerificationStatus

from .conftest import DASH, client_for

COMPANY = f"{DASH}/company"


@pytest.mark.django_db
def test_only_company_accounts_with_a_profile_open_it(
    patient, provider_factory, seller_factory, admin, account_factory
):
    assert client_for(patient).get(COMPANY).status_code == 403
    assert client_for(provider_factory().account).get(COMPANY).status_code == 403
    assert client_for(seller_factory().account).get(COMPANY).status_code == 403
    assert client_for(admin).get(COMPANY).status_code == 403
    no_profile = account_factory(role="MEDICAL_COMPANY")
    assert client_for(no_profile).get(COMPANY).status_code == 403


@pytest.mark.django_db
def test_empty_company_dashboard(company_factory):
    company = company_factory()
    body = client_for(company.account).get(COMPANY).json()
    assert body["verification_status"] == "VERIFIED" and body["can_publish"] is True
    assert body["products"] == {"total": 0, "active": 0, "inactive": 0, "exposable": 0}
    assert body["campaigns"] == dict.fromkeys(
        ("total", "draft", "pending_payment", "active", "live", "ended", "rejected", "cancelled"), 0
    )
    assert body["payments"] == {"PENDING": 0, "VERIFIED": 0, "REJECTED": 0}


@pytest.mark.django_db
def test_it_reuses_the_existing_summaries_without_drifting_from_them(
    company_factory, product_factory, campaign_factory
):
    company = company_factory()
    products = [product_factory(company, is_active=i < 3) for i in range(5)]
    today = timezone.localdate()
    campaign_factory(company, products[0], CampaignStatus.DRAFT)
    campaign_factory(company, products[0], CampaignStatus.PENDING_PAYMENT, PaymentStatus.PENDING)
    campaign_factory(
        company,
        products[1],
        CampaignStatus.ACTIVE,
        PaymentStatus.VERIFIED,
        starts_on=today - timedelta(days=1),
        ends_on=today + timedelta(days=5),
    )
    campaign_factory(
        company,
        products[1],
        CampaignStatus.ACTIVE,
        PaymentStatus.VERIFIED,
        starts_on=today - timedelta(days=9),
        ends_on=today - timedelta(days=2),
    )
    campaign_factory(company, products[2], CampaignStatus.REJECTED, PaymentStatus.REJECTED)
    campaign_factory(company, products[2], CampaignStatus.CANCELLED)

    body = client_for(company.account).get(COMPANY).json()
    existing_products = marketplace_services.dashboard_summary(company)
    existing_campaigns = advertising_services.dashboard_summary(company)
    assert body["products"]["total"] == existing_products["products_total"] == 5
    assert body["products"]["active"] == existing_products["products_active"] == 3
    assert body["products"]["inactive"] == 2
    assert body["products"]["exposable"] == existing_products["products_exposable"]
    assert body["campaigns"] == {
        "total": 6,
        "draft": 1,
        "pending_payment": 1,
        "active": 2,
        "live": 1,
        "ended": 1,
        "rejected": 1,
        "cancelled": 1,
    }
    assert {k.removeprefix("campaigns_"): v for k, v in existing_campaigns.items()} == body[
        "campaigns"
    ]
    assert body["payments"] == {"PENDING": 1, "VERIFIED": 2, "REJECTED": 1}


@pytest.mark.django_db
def test_company_data_is_isolated_between_companies(
    company_factory, product_factory, campaign_factory
):
    mine, other = company_factory(), company_factory()
    for _ in range(3):
        campaign_factory(
            other, product_factory(other), CampaignStatus.PENDING_PAYMENT, PaymentStatus.PENDING
        )
    body = client_for(mine.account).get(COMPANY).json()
    assert body["products"]["total"] == 0 and body["campaigns"]["total"] == 0
    assert body["payments"]["PENDING"] == 0


@pytest.mark.django_db
def test_an_unverified_company_cannot_publish_and_shows_no_exposable_products(
    company_factory, product_factory
):
    company = company_factory(status=CompanyVerificationStatus.PENDING)
    product_factory(company, is_active=True)
    body = client_for(company.account).get(COMPANY).json()
    assert body["verification_status"] == "PENDING"
    assert body["can_publish"] is False and body["products"]["exposable"] == 0


@pytest.mark.django_db
def test_no_fabricated_advertising_statistics(company_factory):
    body = client_for(company_factory().account).get(COMPANY).json()
    text = str(body).lower()
    for word in ("impression", "click", "conversion", "revenue", "roi", "spend", "ctr"):
        assert word not in text


@pytest.mark.django_db
def test_company_dashboard_query_count_is_constant(
    company_factory, product_factory, campaign_factory
):
    company = company_factory()
    client = client_for(company.account)

    def queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(COMPANY).status_code == 200
        return len(ctx)

    baseline = queries()
    for _ in range(15):
        campaign_factory(
            company, product_factory(company), CampaignStatus.PENDING_PAYMENT, PaymentStatus.PENDING
        )
    assert queries() == baseline
    assert baseline <= 9
