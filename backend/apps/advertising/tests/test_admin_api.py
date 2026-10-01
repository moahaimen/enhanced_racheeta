"""The administrator control plane: only staff can list, inspect, verify or reject;
a company can never touch a payment or activate its own campaign."""

from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.advertising import services
from apps.advertising.models import AdvertisingCampaign, CampaignPayment

from .conftest import ADMIN, CAMPAIGNS, client_for, today

pytestmark = pytest.mark.django_db


@pytest.fixture
def pending(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    services.submit_campaign(company, campaign.pk)
    return AdvertisingCampaign.objects.get(pk=campaign.pk)


def _paths(campaign):
    return [
        ("get", ADMIN),
        ("get", f"{ADMIN}/{campaign.pk}"),
        ("post", f"{ADMIN}/{campaign.pk}/verify-payment"),
        ("post", f"{ADMIN}/{campaign.pk}/reject-payment"),
    ]


def test_anonymous_gets_401_on_every_admin_route(pending):
    for method, path in _paths(pending):
        assert getattr(APIClient(), method)(path, {}, format="json").status_code == 401, path


@pytest.mark.parametrize(
    "role",
    [AccountRole.MEDICAL_COMPANY, AccountRole.PROVIDER, AccountRole.PATIENT, AccountRole.ADMIN],
)
def test_non_staff_accounts_get_403_on_every_admin_route(pending, account_factory, role):
    # ADMIN role without the staff flag is not enough: the staff flag is the authority
    account = account_factory(role=role) if role != AccountRole.ADMIN else account_factory()
    client = client_for(account)
    for method, path in _paths(pending):
        body = {"method": "CASH", "reason": "x"}
        assert getattr(client, method)(path, body, format="json").status_code == 403, path
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("PENDING_PAYMENT", "PENDING")


def test_the_owning_company_cannot_verify_or_reject_its_own_payment(pending, ready):
    company, _ = ready
    client = client_for(company.account)
    assert (
        client.post(
            f"{ADMIN}/{pending.pk}/verify-payment", {"method": "CASH"}, format="json"
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{ADMIN}/{pending.pk}/reject-payment", {"reason": "x"}, format="json"
        ).status_code
        == 403
    )


def test_a_company_has_no_route_to_change_a_payment_or_activate(pending, ready):
    company, _ = ready
    client = client_for(company.account)
    url = f"{CAMPAIGNS}/{pending.pk}"
    for body in ({"payment": {"status": "VERIFIED"}}, {"status": "ACTIVE"}, {"is_paid": True}):
        assert client.patch(url, body, format="json").status_code == 400
    assert client.patch(url, {"name": "x"}, format="json").status_code == 409  # frozen anyway
    assert client.delete(url).status_code == 405
    for suffix in ("/payment", "/verify", "/verify-payment", "/activate", "/pay"):
        assert client.post(f"{url}{suffix}", {}, format="json").status_code == 404
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("PENDING_PAYMENT", "PENDING")
    assert not CampaignPayment.objects.exclude(campaign=pending).exists()


def test_the_admin_list_shows_review_data_and_filters(
    ready, rate, campaign_factory, admin_client, company_factory, open_category, product_factory
):
    company, product = ready
    a = campaign_factory(company, product, name="A")
    services.submit_campaign(company, a.pk)
    campaign_factory(company, product, name="Draft")
    other = company_factory()
    b = campaign_factory(other, product_factory(other, open_category), name="B")
    services.submit_campaign(other, b.pk)
    services.reject_campaign_payment(b.pk, reason="no", rejected_by=None)
    rows = admin_client.get(ADMIN).json()
    assert rows["count"] == 3
    only_pending = admin_client.get(f"{ADMIN}?status=PENDING_PAYMENT").json()["results"]
    assert [r["name"] for r in only_pending] == ["A"]
    row = only_pending[0]
    assert row["company"]["name"] == company.name and row["company"]["account_email"]
    assert row["quote"]["amount"] == "10000.00" and row["payment"]["status"] == "PENDING"
    assert row["product"]["title"] and row["payment"]["admin_note"] == ""
    assert [
        r["name"] for r in admin_client.get(f"{ADMIN}?payment_status=REJECTED").json()["results"]
    ] == ["B"]
    assert {
        r["name"] for r in admin_client.get(f"{ADMIN}?company={other.pk}").json()["results"]
    } == {"B"}
    assert admin_client.get(f"{ADMIN}?status=BOGUS").status_code == 400
    assert admin_client.get(f"{ADMIN}/{a.pk}").json()["id"] == str(a.pk)


def test_the_admin_payload_shows_the_targeting_summary(
    ready, rate, campaign_factory, admin_client, baghdad, dentistry
):
    company, product = ready
    campaign = campaign_factory(company, product)
    campaign.target_provider_types.create(provider_type="DOCTOR")
    campaign.target_specialties.create(specialty=dentistry)
    campaign.target_governorates.create(governorate=baghdad)
    body = admin_client.get(f"{ADMIN}/{campaign.pk}").json()
    assert body["provider_types"] == ["DOCTOR"]
    assert (
        body["specialties"][0]["slug"] == "dentistry"
        and body["governorates"][0]["slug"] == "baghdad"
    )


def test_verification_ends_the_pending_state_only_once_through_the_api(pending, admin_client):
    ok = {"method": "EXCHANGE_OFFICE", "reference": "EX-77"}
    assert (
        admin_client.post(f"{ADMIN}/{pending.pk}/verify-payment", ok, format="json").status_code
        == 200
    )
    resp = admin_client.post(f"{ADMIN}/{pending.pk}/verify-payment", ok, format="json")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_transition"
    assert CampaignPayment.objects.filter(status="VERIFIED").count() == 1


def test_an_ended_campaign_cannot_be_verified_through_the_api(pending, admin_client):
    AdvertisingCampaign.objects.filter(pk=pending.pk).update(
        starts_on=today() - timedelta(days=10), ends_on=today() - timedelta(days=1)
    )
    resp = admin_client.post(
        f"{ADMIN}/{pending.pk}/verify-payment", {"method": "CASH"}, format="json"
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "campaign_ended"


def _count_admin_queries(client):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        assert client.get(ADMIN).status_code == 200
    return len(ctx)


def test_the_admin_list_does_not_query_a_verifier_account_per_campaign(
    ready, campaign_factory, make_live, admin_client, account_factory
):
    """`verified_by_email` is serialized for every verified payment: the verifier must be
    loaded with the payment, not once per campaign (mixed with pending and rejected ones)."""
    from decimal import Decimal

    company, product = ready

    def add(kind):
        campaign = campaign_factory(company, product)
        if kind == "verified":
            make_live(campaign, verified_by=account_factory())  # a different verifier each time
        else:
            AdvertisingCampaign.objects.filter(pk=campaign.pk).update(
                status="PENDING_PAYMENT" if kind == "pending" else "REJECTED",
                quoted_days=10,
                quoted_daily_rate=Decimal("1000.00"),
                quoted_amount=Decimal("10000.00"),
                quoted_currency="IQD",
                quoted_at=campaign.created_at,
            )
            CampaignPayment.objects.create(
                campaign=campaign,
                amount=Decimal("10000.00"),
                currency="IQD",
                status="PENDING" if kind == "pending" else "REJECTED",
            )

    add("verified")
    add("pending")
    few = _count_admin_queries(admin_client)
    for kind in ("verified", "pending", "rejected") * 4:
        add(kind)
    many = _count_admin_queries(admin_client)
    assert many <= few + 1, (few, many)  # no growth per verified campaign
    rows = admin_client.get(ADMIN).json()["results"]
    verified = [r for r in rows if r["payment"]["status"] == "VERIFIED"]
    assert len(verified) == 5 and all(r["payment"]["verified_by_email"] for r in verified)
    assert {r["payment"]["status"] for r in rows} == {"PENDING", "VERIFIED", "REJECTED"}
