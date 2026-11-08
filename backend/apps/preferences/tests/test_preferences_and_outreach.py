from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.advertising import services as ads
from apps.advertising.models import AdvertisingCampaign
from apps.audit.models import AuditEvent
from apps.notifications.models import Notification
from apps.preferences import outreach
from apps.preferences import services as prefs
from apps.providers.types import ProviderType

from .conftest import client_for

pytestmark = pytest.mark.django_db

PREFS = "/api/v1/me/preferences"
SPONSORED = "/api/v1/advertising/marketplace"


# ---- preferences API ----------------------------------------------------------------------------


def test_defaults_are_privacy_friendly(account_factory):
    data = client_for(account_factory()).get(PREFS).json()
    assert data["show_sponsored_products"] is True
    for outreach_field in ("real_estate_promotions", "job_alerts", "offers_and_news"):
        assert data[outreach_field] is False
    assert data["channel_in_app"] is True
    assert data["channel_email"] is False and data["channel_push"] is False


def test_patch_updates_and_audits_and_rejects_unknown_fields(account_factory):
    account = account_factory()
    client = client_for(account)
    response = client.patch(PREFS, {"real_estate_promotions": True}, format="json")
    assert response.status_code == 200 and response.json()["real_estate_promotions"] is True
    assert AuditEvent.objects.filter(action="preferences.marketing.updated").count() == 1
    assert client.patch(PREFS, {"account": "x", "is_staff": True}, format="json").status_code == 400
    assert client.patch(PREFS, {}, format="json").status_code == 200
    assert AuditEvent.objects.filter(action="preferences.marketing.updated").count() == 1


def test_anonymous_cannot_read_preferences(api_client):
    assert api_client.get(PREFS).status_code == 401


# ---- display preference gates the sponsored feed ------------------------------------------------


def _feed_ids(account):
    response = client_for(account).get(SPONSORED)
    assert response.status_code == 200
    return {row["id"] for row in response.json()["results"]}


def test_sponsored_feed_respects_display_preference(
    ready, campaign_factory, make_live, provider_factory
):
    company, product = ready
    campaign = campaign_factory(company, product)
    make_live(campaign)
    doctor = provider_factory()
    assert str(campaign.pk) in _feed_ids(doctor.account)
    prefs.update(doctor.account, {"show_sponsored_products": False})
    assert _feed_ids(doctor.account) == set()


# ---- bounded outreach on activation -------------------------------------------------------------


@pytest.fixture
def dental(company_factory, category_factory, product_factory, dentistry):
    company = company_factory()
    category = category_factory(rules=[(ProviderType.DOCTOR, dentistry)])
    return company, product_factory(company, category, title="Demo dental scaler")


def _activate(company, product, campaign_factory, admin_user, capture):
    campaign = campaign_factory(company, product)
    ads.submit_campaign(company, campaign.pk)
    with capture(execute=True):
        ads.verify_campaign_payment(
            campaign.pk, method="BANK_TRANSFER", reference="DEMO-REF", verified_by=admin_user
        )
    return AdvertisingCampaign.objects.get(pk=campaign.pk)


def test_activation_notifies_only_opted_in_targeted_providers(
    dental,
    rate,
    campaign_factory,
    admin_user,
    provider_factory,
    dentistry,
    cardiology,
    django_capture_on_commit_callbacks,
):
    company, product = dental
    opted_in_dentist = provider_factory(specialties=[dentistry])
    prefs.update(opted_in_dentist.account, {"offers_and_news": True})
    provider_factory(specialties=[dentistry])  # display on, outreach consent off: not notified
    cardiologist = provider_factory(specialties=[cardiology])
    prefs.update(cardiologist.account, {"offers_and_news": True})
    in_app_off = provider_factory(specialties=[dentistry])
    prefs.update(in_app_off.account, {"offers_and_news": True, "channel_in_app": False})

    campaign = _activate(
        company, product, campaign_factory, admin_user, django_capture_on_commit_callbacks
    )
    recipients = set(
        Notification.objects.filter(event_type="SPONSORED_PRODUCT").values_list(
            "recipient_id", flat=True
        )
    )
    assert recipients == {opted_in_dentist.account_id}
    note = Notification.objects.get(recipient=opted_in_dentist.account)
    assert (
        note.category == "MARKETING"
        and note.dedupe_key == f"sponsored:{campaign.pk}:{opted_in_dentist.account_id}"
    )
    assert set(note.payload) <= {"product_title", "company_name"}
    # the company never learns who was notified
    company_view = client_for(company.account).get(
        f"/api/v1/advertising/company/campaigns/{campaign.pk}"
    )
    assert str(opted_in_dentist.account_id) not in company_view.content.decode()
    # replay is idempotent
    assert (
        outreach.deliver(
            account_ids=[opted_in_dentist.account_id],
            topic="sponsored_products",
            event_type="SPONSORED_PRODUCT",
            dedupe_prefix=f"sponsored:{campaign.pk}",
            resource_type="PRODUCT",
            resource_id=product.pk,
            payload={},
        )
        == 0
    )


def test_daily_cap_and_send_cap(account_factory, provider_factory):
    doctor = provider_factory()
    prefs.update(doctor.account, {"offers_and_news": True})
    sent = 0
    for i in range(outreach.DAILY_CAP + 2):
        sent += outreach.deliver(
            account_ids=[doctor.account_id],
            topic="sponsored_products",
            event_type="SPONSORED_PRODUCT",
            dedupe_prefix=f"test:{i}",
            resource_type="PRODUCT",
            resource_id=doctor.pk,
            payload={},
        )
    assert sent == outreach.DAILY_CAP
    # yesterday's notifications do not count toward today's cap
    Notification.objects.filter(recipient=doctor.account).update(
        created_at=timezone.now() - timedelta(days=1)
    )
    assert (
        outreach.deliver(
            account_ids=[doctor.account_id],
            topic="sponsored_products",
            event_type="SPONSORED_PRODUCT",
            dedupe_prefix="test:next-day",
            resource_type="PRODUCT",
            resource_id=doctor.pk,
            payload={},
        )
        == 1
    )

    many = [provider_factory().account for _ in range(3)]
    for other in many:
        prefs.update(other, {"offers_and_news": True})
    many = [other.pk for other in many]
    assert (
        outreach.deliver(
            account_ids=many,
            topic="sponsored_products",
            event_type="SPONSORED_PRODUCT",
            dedupe_prefix="test:bounded",
            resource_type="PRODUCT",
            resource_id=doctor.pk,
            payload={},
            limit=2,
        )
        == 2
    )


def test_deactivated_accounts_are_never_notified(account_factory):
    account = account_factory(role=AccountRole.PROVIDER, is_active=False)
    prefs.update(account, {"offers_and_news": True})
    assert (
        outreach.deliver(
            account_ids=[account.pk],
            topic="sponsored_products",
            event_type="SPONSORED_PRODUCT",
            dedupe_prefix="test:inactive",
            resource_type="PRODUCT",
            resource_id=account.pk,
            payload={},
        )
        == 0
    )


def test_transactional_notifications_ignore_marketing_opt_out(account_factory):
    from apps.notifications.services import create_notification

    account = account_factory()
    prefs.update(account, {"channel_in_app": False})
    _, created = create_notification(
        recipient_id=account.pk,
        category="ORDER",
        event_type="ORDER_PLACED",
        dedupe_key="order:test",
        payload={"order_number": "RX-1"},
    )
    assert created
