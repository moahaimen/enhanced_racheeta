"""Django admin: only the advertising RATE is editable; campaigns, payments and
targets are inspection-only, so the admin cannot activate a campaign, verify a
payment, rewrite a status or change an amount."""

from decimal import Decimal

import pytest
from django.conf import settings
from django.test import Client

from apps.advertising import services
from apps.advertising.models import AdvertisingCampaign, AdvertisingRate, CampaignPayment
from apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db
BASE = f"/{settings.ADMIN_URL_PATH}advertising/"


@pytest.fixture
def staff(admin_user):
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.fixture
def pending(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    services.submit_campaign(company, campaign.pk)
    return AdvertisingCampaign.objects.get(pk=campaign.pk)


def _rate_form(**overrides):
    data = {
        "code": "premium",
        "name_ar": "متميز",
        "name_en": "Premium",
        "price_per_day": "2000.00",
        "currency": "IQD",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v != ""}


def test_a_rate_can_be_created_and_activating_it_retires_the_previous_one(staff, rate):
    resp = staff.post(f"{BASE}advertisingrate/add/", _rate_form(is_active="on"))
    assert resp.status_code == 302, resp.content.decode()[:400]
    assert AdvertisingRate.objects.filter(is_active=True).count() == 1
    assert AdvertisingRate.objects.get(is_active=True).code == "premium"
    assert AdvertisingRate.objects.get(pk=rate.pk).is_active is False
    assert AuditEvent.objects.filter(action="advertising.rate.created").count() == 1
    staff.post(
        f"{BASE}advertisingrate/{rate.pk}/change/",
        _rate_form(code="standard", price_per_day="1500.00", is_active="on"),
    )
    assert AdvertisingRate.objects.get(is_active=True).code == "standard"
    assert AuditEvent.objects.filter(action="advertising.rate.updated").count() == 1


@pytest.mark.parametrize(
    "overrides,field",
    [({"price_per_day": "0"}, "price_per_day"), ({"price_per_day": "-5"}, "price_per_day"),
     ({"currency": "EUR"}, "currency")],
)  # fmt: skip
def test_a_rate_form_refuses_a_bad_price_or_currency(staff, overrides, field):
    resp = staff.post(f"{BASE}advertisingrate/add/", _rate_form(**overrides))
    assert resp.status_code == 200 and field in resp.context["adminform"].form.errors
    assert not AdvertisingRate.objects.exists()


def test_a_rate_cannot_be_deleted_from_the_admin(staff, rate):
    url = f"{BASE}advertisingrate/{rate.pk}/delete/"
    assert staff.post(url, {"post": "yes"}).status_code == 403
    assert AdvertisingRate.objects.filter(pk=rate.pk).exists()


@pytest.mark.parametrize(
    "model", ["advertisingcampaign", "campaignpayment", "campaignprovidertype",
              "campaignspecialty", "campaigngovernorate"],
)  # fmt: skip
def test_lifecycle_models_are_inspectable_but_not_addable(staff, pending, model):
    assert staff.get(f"{BASE}{model}/").status_code == 200
    assert staff.get(f"{BASE}{model}/add/").status_code == 403


def test_the_admin_cannot_activate_verify_or_change_amounts(staff, pending):
    campaign_url = f"{BASE}advertisingcampaign/{pending.pk}/change/"
    html = staff.get(campaign_url).content.decode()
    for field in ("status", "name", "quoted_amount", "product", "company"):
        assert f'name="{field}"' not in html, field
    assert staff.post(campaign_url, {"status": "ACTIVE", "name": "x"}).status_code == 403
    payment = CampaignPayment.objects.get(campaign=pending)
    payment_url = f"{BASE}campaignpayment/{payment.pk}/change/"
    assert 'name="status"' not in staff.get(payment_url).content.decode()
    assert (
        staff.post(payment_url, {"status": "VERIFIED", "amount": "1", "method": "CASH"}).status_code
        == 403
    )
    assert (
        staff.post(f"{BASE}campaignpayment/{payment.pk}/delete/", {"post": "yes"}).status_code
        == 403
    )
    assert (
        staff.post(f"{BASE}advertisingcampaign/{pending.pk}/delete/", {"post": "yes"}).status_code
        == 403
    )
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status, state.payment.amount) == (
        "PENDING_PAYMENT", "PENDING", Decimal("10000.00"),
    )  # fmt: skip


def test_a_rate_activation_conflict_is_a_message_not_a_500(staff, rate, monkeypatch):
    from apps.advertising import services

    def conflict(*args, **kwargs):
        raise services.RateActivationConflict("simultaneous")

    monkeypatch.setattr(services, "save_rate", conflict)
    resp = staff.post(f"{BASE}advertisingrate/add/", _rate_form(is_active="on"), follow=True)
    assert resp.status_code == 200
    assert "Another rate was activated at the same time" in resp.content.decode()
    assert AdvertisingRate.objects.filter(is_active=True).count() == 1  # untouched
    assert AdvertisingRate.objects.get(is_active=True).pk == rate.pk
