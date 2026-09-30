"""Company-side campaign management: access, ownership, drafts, targeting,
payload protection, editing rules, dashboard and cancellation."""

from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import AccountRole
from apps.advertising import services
from apps.advertising.models import (
    AdvertisingCampaign,
    CampaignGovernorate,
    CampaignProviderType,
    CampaignSpecialty,
)
from apps.audit.models import AuditEvent
from apps.providers.types import ProviderType

from .conftest import CAMPAIGNS, COMPANY, client_for, draft_payload, today

pytestmark = pytest.mark.django_db


def _codes(resp):
    return resp.json()["error"]["codes"]


# ---- access -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        f"{COMPANY}/dashboard",
        CAMPAIGNS,
        f"{COMPANY}/quote",
        f"{CAMPAIGNS}/{'0' * 8}-0000-0000-0000-{'0' * 12}",
    ],
)
def test_anonymous_cannot_use_company_apis(path):
    assert APIClient().get(path).status_code == 401


@pytest.mark.parametrize(
    "role", [AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.REAL_ESTATE_SELLER]
)
def test_other_roles_cannot_manage_campaigns(account_factory, role):
    client = client_for(account_factory(role=role))
    assert client.get(CAMPAIGNS).status_code == 403
    assert client.post(CAMPAIGNS, {}, format="json").status_code == 403
    assert client.get(f"{COMPANY}/dashboard").status_code == 403
    assert client.post(f"{COMPANY}/quote", {}, format="json").status_code == 403


def test_a_company_account_without_a_profile_cannot_manage_campaigns(account_factory):
    client = client_for(account_factory(role=AccountRole.MEDICAL_COMPANY))
    assert client.get(CAMPAIGNS).status_code == 403
    assert client.post(CAMPAIGNS, {}, format="json").status_code == 403


# ---- drafts ------------------------------------------------------------------------------


def test_creating_a_campaign_makes_a_draft_owned_by_the_caller(ready, rate):
    company, product = ready
    resp = client_for(company.account).post(CAMPAIGNS, draft_payload(product), format="json")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["status"] == "DRAFT" and body["quote"] is None and body["payment"] is None
    assert body["is_live"] is False and body["is_ended"] is False
    assert body["product"]["id"] == str(product.pk)
    campaign = AdvertisingCampaign.objects.get()
    assert campaign.company_id == company.pk
    assert AuditEvent.objects.filter(action="advertising.campaign.created").count() == 1


def test_an_incomplete_draft_is_allowed(ready):
    company, product = ready
    resp = client_for(company.account).post(
        CAMPAIGNS, {"name": "Later", "product": str(product.pk)}, format="json"
    )
    assert resp.status_code == 201 and resp.json()["starts_on"] is None


def test_drafts_work_before_the_company_is_verified(
    company_factory, open_category, product_factory
):
    company = company_factory(status="UNVERIFIED")
    product = product_factory(company, open_category)
    resp = client_for(company.account).post(CAMPAIGNS, draft_payload(product), format="json")
    assert resp.status_code == 201


def test_targeting_is_structured_and_round_trips(ready, baghdad, basra, dentistry, cardiology):
    company, product = ready
    payload = draft_payload(
        product,
        provider_types=["DOCTOR", "LABORATORY"],
        specialties=[str(dentistry.pk), str(cardiology.pk)],
        governorates=[str(baghdad.pk), str(basra.pk)],
    )
    resp = client_for(company.account).post(CAMPAIGNS, payload, format="json")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["provider_types"] == ["DOCTOR", "LABORATORY"]
    assert {s["slug"] for s in body["specialties"]} == {"dentistry", "cardiology"}
    assert {g["slug"] for g in body["governorates"]} == {"baghdad", "basra"}
    assert body["governorates"][0]["is_active"] is True
    campaign = AdvertisingCampaign.objects.get()
    assert campaign.target_provider_types.count() == 2
    assert campaign.target_specialties.count() == 2 and campaign.target_governorates.count() == 2


def test_target_replacement_and_omission(ready, baghdad, basra, dentistry):
    company, product = ready
    client = client_for(company.account)
    created = client.post(
        CAMPAIGNS,
        draft_payload(product, provider_types=["DOCTOR"], governorates=[str(baghdad.pk)]),
        format="json",
    ).json()
    url = f"{CAMPAIGNS}/{created['id']}"
    client.patch(
        url, {"governorates": [str(basra.pk)], "specialties": [str(dentistry.pk)]}, format="json"
    )
    campaign = AdvertisingCampaign.objects.get()
    assert list(campaign.target_governorates.values_list("governorate__slug", flat=True)) == [
        "basra"
    ]
    assert list(campaign.target_provider_types.values_list("provider_type", flat=True)) == [
        "DOCTOR"
    ]
    assert campaign.target_specialties.count() == 1
    client.patch(url, {"provider_types": [], "specialties": [], "governorates": []}, format="json")
    assert not CampaignProviderType.objects.exists()
    assert not CampaignSpecialty.objects.exists() and not CampaignGovernorate.objects.exists()


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"provider_types": ["WIZARD"]}, "provider_types"),
        ({"provider_types": ["DOCTOR", "DOCTOR"]}, "provider_types"),
        ({"specialties": ["00000000-0000-0000-0000-000000000000"]}, "specialties"),
        ({"governorates": ["00000000-0000-0000-0000-000000000000"]}, "governorates"),
        ({"starts_on": "2030-05-10", "ends_on": "2030-05-01"}, "ends_on"),
        ({"starts_on": "not-a-date"}, "starts_on"),
        ({"name": ""}, "name"),
    ],
)
def test_invalid_input_is_rejected(ready, overrides, field):
    company, product = ready
    resp = client_for(company.account).post(
        CAMPAIGNS, draft_payload(product, **overrides), format="json"
    )
    assert resp.status_code == 400 and field in resp.json()["error"]["details"], resp.json()


def test_an_inactive_governorate_or_specialty_cannot_be_targeted(ready, basra, dentistry):
    company, product = ready
    basra.is_active = False
    basra.save()
    dentistry.is_active = False
    dentistry.save()
    client = client_for(company.account)
    assert (
        "governorates"
        in client.post(
            CAMPAIGNS, draft_payload(product, governorates=[str(basra.pk)]), format="json"
        ).json()["error"]["details"]
    )
    assert (
        "specialties"
        in client.post(
            CAMPAIGNS, draft_payload(product, specialties=[str(dentistry.pk)]), format="json"
        ).json()["error"]["details"]
    )


# ---- ownership --------------------------------------------------------------------------


def test_a_company_cannot_advertise_another_companys_product(
    ready, company_factory, open_category, product_factory
):
    company, _ = ready
    theirs = product_factory(company_factory(), open_category, title="Theirs")
    resp = client_for(company.account).post(CAMPAIGNS, draft_payload(theirs), format="json")
    assert resp.status_code == 400 and "product" in resp.json()["error"]["details"]
    assert not AdvertisingCampaign.objects.exists()


def test_the_company_is_never_taken_from_the_payload(ready, company_factory, open_category):
    company, product = ready
    other = company_factory()
    for key in ("company", "company_id"):
        resp = client_for(company.account).post(
            CAMPAIGNS, draft_payload(product, **{key: str(other.pk)}), format="json"
        )
        assert resp.status_code == 400 and _codes(resp)[key] == ["field_not_allowed"]


def test_foreign_campaigns_are_invisible_and_untouchable(
    ready, company_factory, open_category, product_factory, campaign_factory, rate
):
    company, product = ready
    other = company_factory()
    theirs = campaign_factory(other, product_factory(other, open_category), name="Theirs")
    mine = campaign_factory(company, product, name="Mine")
    client = client_for(company.account)
    assert [r["name"] for r in client.get(CAMPAIGNS).json()["results"]] == ["Mine"]
    for method, suffix, body in (
        ("get", "", None),
        ("patch", "", {"name": "Hijacked"}),
        ("post", "/submit", None),
        ("post", "/cancel", None),
    ):
        resp = getattr(client, method)(f"{CAMPAIGNS}/{theirs.pk}{suffix}", body, format="json")
        assert resp.status_code == 404, (method, suffix)
    theirs.refresh_from_db()
    assert theirs.name == "Theirs" and theirs.status == "DRAFT" and mine.pk


def test_there_is_no_delete(ready, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    assert client_for(company.account).delete(f"{CAMPAIGNS}/{campaign.pk}").status_code == 405


# ---- payload protection -----------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "ACTIVE"),
        ("payment_status", "VERIFIED"),
        ("is_paid", True),
        ("paid", True),
        ("verified", True),
        ("verified_at", "2020-01-01T00:00:00Z"),
        ("verified_by", "x"),
        ("amount", "1"),
        ("quoted_amount", "1"),
        ("daily_rate", "1"),
        ("quoted_daily_rate", "1"),
        ("quoted_days", 1),
        ("quoted_currency", "IQD"),
        ("quoted_at", "2020-01-01T00:00:00Z"),
        ("currency", "IQD"),
        ("price", "1"),
        ("total", "1"),
        ("quote", {"amount": "1"}),
        ("payment", {"status": "VERIFIED"}),
        ("reference", "PAID-ALREADY"),
        ("payment_reference", "PAID-ALREADY"),
        ("is_live", True),
    ],
)
def test_lifecycle_money_and_verification_fields_are_refused_not_ignored(
    ready, campaign_factory, field, value
):
    company, product = ready
    client = client_for(company.account)
    created = client.post(CAMPAIGNS, draft_payload(product, **{field: value}), format="json")
    assert created.status_code == 400 and _codes(created)[field] == ["field_not_allowed"]
    campaign = campaign_factory(company, product)
    patched = client.patch(f"{CAMPAIGNS}/{campaign.pk}", {field: value}, format="json")
    assert patched.status_code == 400 and _codes(patched)[field] == ["field_not_allowed"]
    campaign.refresh_from_db()
    assert campaign.status == "DRAFT" and campaign.quoted_amount is None


# ---- editing ----------------------------------------------------------------------------


def test_a_draft_is_editable_and_nothing_else_is(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product, starts_on=today() + timedelta(days=1))
    client = client_for(company.account)
    url = f"{CAMPAIGNS}/{campaign.pk}"
    assert client.patch(url, {"name": "Renamed"}, format="json").json()["name"] == "Renamed"
    assert client.post(f"{url}/submit").status_code == 200
    resp = client.patch(url, {"name": "Too late"}, format="json")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "campaign_not_editable"
    campaign.refresh_from_db()
    assert campaign.name == "Renamed"
    for status in ("REJECTED", "CANCELLED", "ACTIVE"):
        AdvertisingCampaign.objects.filter(pk=campaign.pk).update(status=status)
        blocked = client.patch(url, {"name": "Nope"}, format="json")
        assert (
            blocked.status_code == 409
            and blocked.json()["error"]["code"] == "campaign_not_editable"
        )


def test_an_edit_can_move_the_product_to_another_own_product(
    ready, open_category, product_factory, campaign_factory
):
    company, product = ready
    other = product_factory(company, open_category, title="Second")
    campaign = campaign_factory(company, product)
    resp = client_for(company.account).patch(
        f"{CAMPAIGNS}/{campaign.pk}", {"product": str(other.pk)}, format="json"
    )
    assert resp.status_code == 200 and resp.json()["product"]["id"] == str(other.pk)


def test_the_model_refuses_to_move_a_submitted_campaigns_product_or_company(
    ready, rate, campaign_factory, company_factory, open_category, product_factory
):
    company, product = ready
    campaign = campaign_factory(company, product)
    services.submit_campaign(company, campaign.pk)
    loaded = AdvertisingCampaign.objects.get(pk=campaign.pk)
    loaded.product = product_factory(company, open_category)
    with pytest.raises(ValueError, match="product_id"):
        loaded.save()
    loaded = AdvertisingCampaign.objects.get(pk=campaign.pk)
    loaded.company = company_factory()
    with pytest.raises(ValueError, match="company_id"):
        loaded.save()
    loaded = AdvertisingCampaign.objects.get(pk=campaign.pk)
    loaded.quoted_amount = 1
    with pytest.raises(ValueError, match="quoted_amount"):
        loaded.save()


# ---- list / dashboard / cancel -----------------------------------------------------------


def test_the_list_is_paginated_newest_first_and_filterable(ready, campaign_factory):
    company, product = ready
    for i in range(23):
        campaign_factory(
            company, product, name=f"C{i:02d}", status="CANCELLED" if i == 5 else "DRAFT"
        )
    client = client_for(company.account)
    first = client.get(CAMPAIGNS).json()
    assert first["count"] == 23 and len(first["results"]) == 20 and first["next"]
    assert len(client.get(f"{CAMPAIGNS}?page=2").json()["results"]) == 3
    only = client.get(f"{CAMPAIGNS}?status=CANCELLED").json()
    assert [r["name"] for r in only["results"]] == ["C05"]
    assert client.get(f"{CAMPAIGNS}?status=BOGUS").status_code == 400


def test_the_dashboard_counts_are_backend_computed(ready, campaign_factory, live_campaign):
    company, product = ready
    campaign_factory(company, product)  # draft
    campaign_factory(company, product, status="REJECTED")
    campaign_factory(company, product, status="CANCELLED")
    campaign_factory(company, product, status="PENDING_PAYMENT")
    ended = campaign_factory(
        company,
        product,
        status="ACTIVE",
        starts_on=today() - timedelta(days=9),
        ends_on=today() - timedelta(days=1),
    )
    assert ended.pk and live_campaign.pk
    body = client_for(company.account).get(f"{COMPANY}/dashboard").json()
    assert body == {
        "campaigns_total": 6,
        "campaigns_draft": 1,
        "campaigns_pending_payment": 1,
        "campaigns_active": 2,
        "campaigns_live": 1,
        "campaigns_ended": 1,
        "campaigns_rejected": 1,
        "campaigns_cancelled": 1,
    }


def test_an_active_campaign_can_be_cancelled_and_only_that(live_campaign, ready, campaign_factory):
    company, product = ready
    client = client_for(company.account)
    resp = client.post(f"{CAMPAIGNS}/{live_campaign.pk}/cancel")
    assert resp.status_code == 200 and resp.json()["status"] == "CANCELLED"
    assert resp.json()["is_live"] is False
    assert resp.json()["payment"]["status"] == "VERIFIED"  # history: the payment is untouched
    assert AuditEvent.objects.filter(action="advertising.campaign.cancelled").count() == 1
    again = client.post(f"{CAMPAIGNS}/{live_campaign.pk}/cancel")
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_transition"
    draft = campaign_factory(company, product)
    assert client.post(f"{CAMPAIGNS}/{draft.pk}/cancel").status_code == 400


def test_the_owner_payment_summary_hides_admin_internals(live_campaign, ready):
    company, _ = ready
    body = client_for(company.account).get(f"{CAMPAIGNS}/{live_campaign.pk}").json()
    assert set(body["payment"]) == {
        "status", "amount", "currency", "method", "reference", "created_at", "verified_at",
    }  # fmt: skip
    text = str(body)
    assert "admin@example.com" not in text and "admin_note" not in text
    assert set(body["quote"]) == {"days", "daily_rate", "amount", "currency", "quoted_at"}


def test_a_company_can_always_cancel_even_after_losing_the_role(live_campaign, ready):
    from apps.accounts.models import Account

    company, _ = ready
    Account.objects.filter(pk=company.account_id).update(role=AccountRole.PATIENT)
    services.cancel_campaign(company, live_campaign.pk)  # withdrawal is always safe
    assert AdvertisingCampaign.objects.get(pk=live_campaign.pk).status == "CANCELLED"
    assert ProviderType.DOCTOR


def test_audit_events_are_recorded_without_request_bodies(ready, rate, admin_client):
    company, product = ready
    client = client_for(company.account)
    created = client.post(CAMPAIGNS, draft_payload(product), format="json").json()
    client.patch(f"{CAMPAIGNS}/{created['id']}", {"name": "Renamed"}, format="json")
    client.post(f"{CAMPAIGNS}/{created['id']}/submit")
    actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert {
        "advertising.campaign.created",
        "advertising.campaign.updated",
        "advertising.campaign.submitted",
        "advertising.payment.created",
    } <= actions
    updated = AuditEvent.objects.get(action="advertising.campaign.updated")
    assert updated.data == {"fields": ["name"]}  # which fields, never the body
