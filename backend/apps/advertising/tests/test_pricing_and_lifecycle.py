"""Backend pricing (no seeded price), the quote preview, the submission snapshot,
the CampaignPayment, and the manual verification / rejection state machine."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.advertising import services
from apps.advertising.models import AdvertisingCampaign, AdvertisingRate, CampaignPayment
from apps.audit.models import AuditEvent
from apps.marketplace.models import Product

from .conftest import ADMIN, CAMPAIGNS, COMPANY, client_for, today

pytestmark = pytest.mark.django_db


def _err(resp):
    return resp.json()["error"]


def _decide(admin_client, campaign, action, body):
    return admin_client.post(f"{ADMIN}/{campaign.pk}/{action}", body, format="json")


# ---- pricing ----


def test_no_price_is_seeded_by_any_migration(db):
    assert AdvertisingRate.objects.count() == 0


def test_without_an_active_rate_quote_and_submission_are_typed_unavailable(ready, campaign_factory):
    company, product = ready
    client = client_for(company.account)
    quote = client.post(
        f"{COMPANY}/quote",
        {"starts_on": str(today()), "ends_on": str(today() + timedelta(days=3))},
        format="json",
    )
    assert quote.status_code == 409 and _err(quote)["code"] == "pricing_unavailable"
    campaign = campaign_factory(company, product)
    resp = client.post(f"{CAMPAIGNS}/{campaign.pk}/submit")
    assert resp.status_code == 409 and _err(resp)["code"] == "pricing_unavailable"
    campaign.refresh_from_db()
    assert (
        campaign.status == "DRAFT" and not CampaignPayment.objects.exists()
    )  # nothing half-written


def test_the_quote_is_days_times_the_active_rate_using_decimals(ready, rate):
    company, _ = ready
    AdvertisingRate.objects.filter(pk=rate.pk).update(price_per_day=Decimal("1234.56"))
    resp = client_for(company.account).post(
        f"{COMPANY}/quote",
        {"starts_on": "2030-01-01", "ends_on": "2030-01-10"},  # inclusive: 10 days
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "days": 10,
        "daily_rate": "1234.56",
        "total": "12345.60",
        "currency": "IQD",
    }
    one = client_for(company.account).post(
        f"{COMPANY}/quote", {"starts_on": "2030-01-01", "ends_on": "2030-01-01"}, format="json"
    )
    assert one.json()["days"] == 1


def test_the_quote_validates_its_dates(ready, rate):
    company, _ = ready
    client = client_for(company.account)
    bad = client.post(
        f"{COMPANY}/quote", {"starts_on": "2030-01-10", "ends_on": "2030-01-01"}, format="json"
    )
    assert bad.status_code == 400 and "ends_on" in _err(bad)["details"]
    assert (
        client.post(f"{COMPANY}/quote", {"starts_on": "2030-01-10"}, format="json").status_code
        == 400
    )


def test_the_rate_is_positive_single_and_supported(rate, db):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        AdvertisingRate.objects.create(
            code="second", name_ar="a", name_en="b", price_per_day=5, is_active=True
        )
    AdvertisingRate.objects.create(
        code="off", name_ar="a", name_en="b", price_per_day=5
    )  # inactive ok
    with pytest.raises(IntegrityError), transaction.atomic():
        AdvertisingRate.objects.filter(pk=rate.pk).update(price_per_day=0)
    with pytest.raises(Exception, match="currency"):
        AdvertisingRate.objects.create(
            code="eur", name_ar="a", name_en="b", price_per_day=5, currency="EUR"
        )


# ---- submission ----


def test_submission_snapshots_the_price_and_creates_exactly_one_pending_payment(
    ready, rate, campaign_factory
):
    company, product = ready
    campaign = campaign_factory(company, product)  # today .. today+9 => 10 days
    resp = client_for(company.account).post(f"{CAMPAIGNS}/{campaign.pk}/submit")
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["status"] == "PENDING_PAYMENT"
    assert body["quote"]["days"] == 10 and body["quote"]["amount"] == "10000.00"
    assert body["quote"]["daily_rate"] == "1000.00" and body["quote"]["currency"] == "IQD"
    assert body["payment"]["status"] == "PENDING" and body["payment"]["amount"] == "10000.00"
    payment = CampaignPayment.objects.get(campaign=campaign)
    assert (payment.amount, payment.currency, payment.status) == (
        Decimal("10000.00"),
        "IQD",
        "PENDING",
    )
    stored = AdvertisingCampaign.objects.get(pk=campaign.pk)
    assert stored.rate_id == rate.pk and stored.quoted_at is not None
    assert AuditEvent.objects.filter(action="advertising.campaign.submitted").count() == 1
    assert AuditEvent.objects.filter(action="advertising.payment.created").count() == 1


def test_a_rate_change_never_touches_a_snapshot_and_submit_uses_the_current_rate(
    ready, rate, campaign_factory
):
    company, product = ready
    first = campaign_factory(company, product, name="First")
    services.submit_campaign(company, first.pk)
    # the browser previewed 10,000; the admin then changes the rate before submit #2
    preview = (
        client_for(company.account)
        .post(
            f"{COMPANY}/quote",
            {"starts_on": str(today()), "ends_on": str(today() + timedelta(days=9))},
            format="json",
        )
        .json()
    )
    assert preview["total"] == "10000.00"
    AdvertisingRate.objects.filter(pk=rate.pk).update(price_per_day=Decimal("2500.00"))
    second = campaign_factory(company, product, name="Second")
    resp = client_for(company.account).post(f"{CAMPAIGNS}/{second.pk}/submit")
    assert resp.json()["quote"]["amount"] == "25000.00"  # the CURRENT backend rate, not the preview
    first_after = AdvertisingCampaign.objects.get(pk=first.pk)
    assert first_after.quoted_amount == Decimal("10000.00")  # the earlier snapshot is untouched
    assert CampaignPayment.objects.get(campaign=first).amount == Decimal("10000.00")


FORBIDDEN_ACTION_KEYS = [
    "amount", "quoted_amount", "quoted_daily_rate", "quoted_days", "quoted_currency",
    "payment_status", "status", "is_paid", "paid", "verified", "company", "company_id",
    "product", "product_id", "payment", "rate", "reference", "currency", "anything_else",
]  # fmt: skip


def test_submit_takes_no_body_empty_and_empty_object_both_work(ready, rate, campaign_factory):
    company, product = ready
    client = client_for(company.account)
    first = campaign_factory(company, product)
    assert client.post(f"{CAMPAIGNS}/{first.pk}/submit").status_code == 200  # no body at all
    second = campaign_factory(company, product)
    assert client.post(f"{CAMPAIGNS}/{second.pk}/submit", {}, format="json").status_code == 200
    for campaign in (first, second):
        campaign.refresh_from_db()
        assert (
            campaign.quoted_amount == Decimal("10000.00") and campaign.status == "PENDING_PAYMENT"
        )


@pytest.mark.parametrize("key", FORBIDDEN_ACTION_KEYS)
def test_submit_rejects_any_client_field_instead_of_ignoring_it(ready, rate, campaign_factory, key):
    company, product = ready
    campaign = campaign_factory(company, product)
    resp = client_for(company.account).post(
        f"{CAMPAIGNS}/{campaign.pk}/submit", {key: "1"}, format="json"
    )
    assert resp.status_code == 400, key
    assert _err(resp)["codes"][key] == ["field_not_allowed"]
    campaign.refresh_from_db()
    assert campaign.status == "DRAFT" and campaign.quoted_amount is None
    assert not CampaignPayment.objects.exists()  # nothing was created by the rejected attempt


# Bodies that are not a mapping are request bodies too, falsey or not.
NON_OBJECT_BODIES = [
    pytest.param([], id="empty-array"),
    pytest.param([{"amount": 1}], id="array-with-object"),
    pytest.param("", id="empty-string"),
    pytest.param("hello", id="string"),
    pytest.param(0, id="zero"),
    pytest.param(1, id="one"),
    pytest.param(False, id="false"),
    pytest.param(True, id="true"),
]


def _assert_refused(resp):
    assert resp.status_code == 400
    assert _err(resp)["code"] == "validation_error"
    assert _err(resp)["codes"]["non_field_errors"] == ["field_not_allowed"]


@pytest.mark.parametrize("body", NON_OBJECT_BODIES)
def test_submit_rejects_any_non_object_body_even_a_falsey_one(ready, rate, campaign_factory, body):
    company, product = ready
    campaign = campaign_factory(company, product)
    resp = client_for(company.account).post(
        f"{CAMPAIGNS}/{campaign.pk}/submit", body, format="json"
    )
    _assert_refused(resp)
    campaign.refresh_from_db()
    assert campaign.status == "DRAFT" and campaign.quoted_amount is None
    assert not CampaignPayment.objects.exists()


def test_submit_rejects_an_explicit_json_null(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    resp = client_for(company.account).generic(
        "POST", f"{CAMPAIGNS}/{campaign.pk}/submit", "null", content_type="application/json"
    )
    _assert_refused(resp)
    assert AdvertisingCampaign.objects.get(pk=campaign.pk).status == "DRAFT"
    assert not CampaignPayment.objects.exists()


@pytest.mark.parametrize("body", NON_OBJECT_BODIES)
def test_cancel_rejects_any_non_object_body_even_a_falsey_one(live_campaign, ready, body):
    company, _ = ready
    resp = client_for(company.account).post(
        f"{CAMPAIGNS}/{live_campaign.pk}/cancel", body, format="json"
    )
    _assert_refused(resp)
    assert AdvertisingCampaign.objects.get(pk=live_campaign.pk).status == "ACTIVE"


def test_cancel_rejects_an_explicit_json_null(live_campaign, ready):
    company, _ = ready
    resp = client_for(company.account).generic(
        "POST", f"{CAMPAIGNS}/{live_campaign.pk}/cancel", "null", content_type="application/json"
    )
    _assert_refused(resp)
    assert AdvertisingCampaign.objects.get(pk=live_campaign.pk).status == "ACTIVE"


def test_an_empty_form_is_still_no_data(ready, rate, campaign_factory):
    """An empty multipart/form mapping is what a body-less POST can look like to DRF."""
    company, product = ready
    campaign = campaign_factory(company, product)
    resp = client_for(company.account).post(
        f"{CAMPAIGNS}/{campaign.pk}/submit", {}, format="multipart"
    )
    assert resp.status_code == 200


def test_cancel_takes_no_body_and_rejects_tampering(live_campaign, ready):
    company, _ = ready
    client = client_for(company.account)
    url = f"{CAMPAIGNS}/{live_campaign.pk}/cancel"
    for key in ("status", "amount", "payment_status", "is_paid", "reference", "company"):
        resp = client.post(url, {key: "x"}, format="json")
        assert resp.status_code == 400 and _err(resp)["codes"][key] == ["field_not_allowed"], key
        assert AdvertisingCampaign.objects.get(pk=live_campaign.pk).status == "ACTIVE"
    assert client.post(url, {}, format="json").status_code == 200  # empty object is fine
    assert AdvertisingCampaign.objects.get(pk=live_campaign.pk).status == "CANCELLED"


def test_cancel_with_no_body_at_all_works(live_campaign, ready):
    company, _ = ready
    resp = client_for(company.account).post(f"{CAMPAIGNS}/{live_campaign.pk}/cancel")
    assert resp.status_code == 200 and resp.json()["status"] == "CANCELLED"


def test_create_and_patch_keep_their_forbidden_field_protection(ready, campaign_factory):
    from .conftest import draft_payload

    company, product = ready
    client = client_for(company.account)
    created = client.post(CAMPAIGNS, draft_payload(product, amount="1"), format="json")
    assert created.status_code == 400 and _err(created)["codes"]["amount"] == ["field_not_allowed"]
    campaign = campaign_factory(company, product)
    patched = client.patch(f"{CAMPAIGNS}/{campaign.pk}", {"status": "ACTIVE"}, format="json")
    assert patched.status_code == 400 and _err(patched)["codes"]["status"] == ["field_not_allowed"]


def test_submission_needs_dates_a_name_a_future_window_and_active_targets(
    ready, rate, campaign_factory, baghdad
):
    company, product = ready
    client = client_for(company.account)

    def submit(campaign):
        return client.post(f"{CAMPAIGNS}/{campaign.pk}/submit")

    no_dates = campaign_factory(company, product, starts_on=None, ends_on=None)
    resp = submit(no_dates)
    assert resp.status_code == 400 and {"starts_on", "ends_on"} <= set(_err(resp)["details"])
    past_end = campaign_factory(
        company, product, starts_on=today() - timedelta(days=5), ends_on=today() - timedelta(days=1)
    )
    assert "ends_on" in _err(submit(past_end))["details"]
    past_start = campaign_factory(company, product, starts_on=today() - timedelta(days=1))
    assert _err(submit(past_start))["codes"]["starts_on"] == ["start_in_past"]
    blank = campaign_factory(company, product, name="  ")
    assert "name" in _err(submit(blank))["details"]
    targeted = campaign_factory(company, product)
    targeted.target_governorates.create(governorate=baghdad)
    baghdad.is_active = False
    baghdad.save()
    assert _err(submit(targeted))["codes"]["governorates"] == ["governorate_inactive"]
    for campaign in (no_dates, past_end, past_start, blank, targeted):
        assert AdvertisingCampaign.objects.get(pk=campaign.pk).status == "DRAFT"
    assert not CampaignPayment.objects.exists()


def test_a_campaign_can_only_be_submitted_from_draft(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    client = client_for(company.account)
    assert client.post(f"{CAMPAIGNS}/{campaign.pk}/submit").status_code == 200
    again = client.post(f"{CAMPAIGNS}/{campaign.pk}/submit")
    assert again.status_code == 409 and _err(again)["code"] == "campaign_not_submittable"
    assert CampaignPayment.objects.filter(campaign=campaign).count() == 1


# ---- submission needs the CURRENT company / product state ----


def test_submission_fails_when_the_company_role_was_lost(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    Account.objects.filter(pk=company.account_id).update(role=AccountRole.PATIENT)
    with pytest.raises(services.CompanyNotEligible):
        services.submit_campaign(company, campaign.pk)
    assert AdvertisingCampaign.objects.get(pk=campaign.pk).status == "DRAFT"
    assert not CampaignPayment.objects.exists()


@pytest.mark.parametrize("break_it", ["inactive_account", "unverified", "suspended"])
def test_submission_fails_when_the_company_is_no_longer_eligible(
    ready, rate, campaign_factory, break_it
):
    company, product = ready
    campaign = campaign_factory(company, product)
    if break_it == "inactive_account":
        Account.objects.filter(pk=company.account_id).update(is_active=False)
    else:
        type(company).objects.filter(pk=company.pk).update(verification_status=break_it.upper())
    with pytest.raises(services.CompanyNotEligible):
        services.submit_campaign(company, campaign.pk)
    assert not CampaignPayment.objects.exists()


@pytest.mark.parametrize("break_it", ["product_inactive", "category_inactive", "no_audience"])
def test_submission_fails_when_the_product_is_no_longer_exposable(
    ready, rate, campaign_factory, open_category, break_it
):
    company, product = ready
    campaign = campaign_factory(company, product)
    if break_it == "product_inactive":
        Product.objects.filter(pk=product.pk).update(is_active=False)
    elif break_it == "category_inactive":
        open_category.is_active = False
        open_category.save()
    else:
        open_category.audiences.update(is_active=False)
    resp = client_for(company.account).post(f"{CAMPAIGNS}/{campaign.pk}/submit")
    assert resp.status_code == 409 and _err(resp)["code"] == "product_unavailable"
    assert not CampaignPayment.objects.exists()


# ---- manual verification ----


@pytest.fixture
def pending(ready, rate, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    services.submit_campaign(company, campaign.pk)
    return AdvertisingCampaign.objects.get(pk=campaign.pk)


def test_verifying_activates_the_campaign_and_the_payment_together(
    pending, admin_client, admin_user
):
    resp = _decide(
        admin_client, pending, "verify-payment",
        {"method": "BANK_TRANSFER", "reference": "TX-991", "note": "Seen in statement"},
    )  # fmt: skip
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["status"] == "ACTIVE" and body["payment"]["status"] == "VERIFIED"
    assert body["payment"]["method"] == "BANK_TRANSFER" and body["payment"]["reference"] == "TX-991"
    assert body["payment"]["amount"] == "10000.00"  # the campaign's own quote
    assert body["payment"]["verified_by_email"] == admin_user.email
    assert body["payment"]["admin_note"] == "Seen in statement" and body["is_live"] is True
    payment = CampaignPayment.objects.get(campaign=pending)
    assert payment.verified_at is not None and payment.verified_by_id == admin_user.pk
    assert AuditEvent.objects.filter(action="advertising.payment.verified").count() == 1
    assert AuditEvent.objects.filter(action="advertising.campaign.activated").count() == 1


def test_rejecting_rejects_the_payment_and_the_campaign_together(pending, admin_client):
    resp = _decide(admin_client, pending, "reject-payment", {"reason": "No transfer found"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"
    assert resp.json()["payment"]["status"] == "REJECTED"
    assert resp.json()["payment"]["admin_note"] == "No transfer found"
    assert AuditEvent.objects.filter(action="advertising.payment.rejected").count() == 1
    assert not AuditEvent.objects.filter(action="advertising.campaign.activated").exists()


def test_a_reason_is_required_to_reject(pending, admin_client):
    resp = _decide(admin_client, pending, "reject-payment", {"reason": "  "})
    assert resp.status_code == 400
    assert AdvertisingCampaign.objects.get(pk=pending.pk).status == "PENDING_PAYMENT"


def test_decisions_are_final_no_double_verify_no_flip_no_resurrection(pending, admin_client):
    ok = {"method": "CASH"}
    assert _decide(admin_client, pending, "verify-payment", ok).status_code == 200
    again = _decide(admin_client, pending, "verify-payment", ok)
    assert again.status_code == 400 and _err(again)["code"] == "invalid_transition"
    flip = _decide(admin_client, pending, "reject-payment", {"reason": "changed mind"})
    assert flip.status_code == 400 and _err(flip)["code"] == "invalid_transition"
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("ACTIVE", "VERIFIED")


def test_a_rejected_campaign_can_never_be_verified(pending, admin_client):
    assert _decide(admin_client, pending, "reject-payment", {"reason": "no"}).status_code == 200
    resp = _decide(admin_client, pending, "verify-payment", {"method": "CASH"})
    assert resp.status_code == 400 and _err(resp)["code"] == "invalid_transition"
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("REJECTED", "REJECTED")


def test_a_draft_or_unknown_campaign_cannot_be_verified(ready, campaign_factory, admin_client):
    import uuid

    company, product = ready
    draft = campaign_factory(company, product)
    resp = _decide(admin_client, draft, "verify-payment", {"method": "CASH"})
    assert resp.status_code == 400 and _err(resp)["code"] == "invalid_transition"
    unknown = admin_client.post(
        f"{ADMIN}/{uuid.uuid4()}/verify-payment", {"method": "CASH"}, format="json"
    )
    assert unknown.status_code == 404


def test_verification_needs_a_valid_method_and_never_takes_money_or_state(pending, admin_client):
    assert _decide(admin_client, pending, "verify-payment", {}).status_code == 400
    assert (
        _decide(admin_client, pending, "verify-payment", {"method": "BITCOIN"}).status_code == 400
    )
    for key, value in (
        ("amount", "1"),
        ("currency", "USD"),
        ("status", "ACTIVE"),
        ("payment_status", "VERIFIED"),
        ("quoted_amount", "1"),
        ("company", "x"),
        ("product", "x"),
        ("verified_by", "x"),
    ):
        resp = _decide(admin_client, pending, "verify-payment", {"method": "CASH", key: value})
        assert resp.status_code == 400 and _err(resp)["codes"][key] == ["field_not_allowed"], key
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("PENDING_PAYMENT", "PENDING")


# ---- verification re-checks CURRENT state; payment never overrides safety ----


def test_verification_fails_when_the_company_role_was_lost(pending, ready):
    company, _ = ready
    Account.objects.filter(pk=company.account_id).update(role=AccountRole.PATIENT)
    with pytest.raises(services.CompanyNotEligible):
        services.verify_campaign_payment(pending.pk, method="CASH", verified_by=None)
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("PENDING_PAYMENT", "PENDING")


@pytest.mark.parametrize("break_it", ["inactive_account", "suspended", "unverified"])
def test_verification_fails_when_the_company_lost_eligibility(pending, ready, break_it):
    company, _ = ready
    if break_it == "inactive_account":
        Account.objects.filter(pk=company.account_id).update(is_active=False)
    else:
        type(company).objects.filter(pk=company.pk).update(verification_status=break_it.upper())
    with pytest.raises(services.CompanyNotEligible):
        services.verify_campaign_payment(pending.pk, method="CASH", verified_by=None)
    assert CampaignPayment.objects.get(campaign=pending).status == "PENDING"


@pytest.mark.parametrize("break_it", ["product_inactive", "category_inactive", "no_audience"])
def test_verification_fails_when_the_product_is_no_longer_exposable(
    pending, ready, open_category, break_it
):
    _, product = ready
    if break_it == "product_inactive":
        Product.objects.filter(pk=product.pk).update(is_active=False)
    elif break_it == "category_inactive":
        open_category.is_active = False
        open_category.save()
    else:
        open_category.audiences.update(is_active=False)
    with pytest.raises(services.ProductUnavailable):
        services.verify_campaign_payment(pending.pk, method="CASH", verified_by=None)
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("PENDING_PAYMENT", "PENDING")


def test_verification_fails_for_a_campaign_whose_end_date_has_passed(pending):
    AdvertisingCampaign.objects.filter(pk=pending.pk).update(
        starts_on=today() - timedelta(days=10), ends_on=today() - timedelta(days=1)
    )
    with pytest.raises(services.CampaignEnded):
        services.verify_campaign_payment(pending.pk, method="CASH", verified_by=None)
    assert CampaignPayment.objects.get(campaign=pending).status == "PENDING"


def test_verification_fails_when_a_targeted_reference_was_deactivated(pending, baghdad):
    pending.target_governorates.create(governorate=baghdad)
    baghdad.is_active = False
    baghdad.save()
    with pytest.raises(services.CampaignProblems) as exc:
        services.verify_campaign_payment(pending.pk, method="CASH", verified_by=None)
    assert exc.value.problems == {"governorates": "governorate_inactive"}
    assert CampaignPayment.objects.get(campaign=pending).status == "PENDING"


def test_the_payment_amount_and_the_campaign_snapshot_are_immutable_in_the_model(pending):
    payment = CampaignPayment.objects.get(campaign=pending)
    payment.amount = Decimal("1.00")
    with pytest.raises(ValueError, match="amount"):
        payment.save()
    payment = CampaignPayment.objects.get(campaign=pending)
    payment.currency = "USD"
    with pytest.raises(ValueError, match="currency"):
        payment.save()
    payment = CampaignPayment.objects.get(campaign=pending)
    payment.campaign = AdvertisingCampaign.objects.exclude(pk=pending.pk).first() or pending
    payment.campaign_id = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError, match="campaign_id"):
        payment.save()


def test_a_verified_payment_row_must_be_coherent_in_the_database(pending):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        CampaignPayment.objects.filter(campaign=pending).update(
            status="VERIFIED"
        )  # no time, no method


# ---- verification proves payment <-> quote coherence on the LOCKED snapshot ----


def _corrupt(pending, what):
    if what == "payment_amount":
        CampaignPayment.objects.filter(campaign=pending).update(amount=Decimal("9999.00"))
    elif what == "payment_currency":
        CampaignPayment.objects.filter(campaign=pending).update(currency="USD")
    elif what == "quoted_amount":
        AdvertisingCampaign.objects.filter(pk=pending.pk).update(quoted_amount=Decimal("1.00"))
    elif what == "arithmetic":
        AdvertisingCampaign.objects.filter(pk=pending.pk).update(quoted_daily_rate=Decimal("5.00"))
    elif what == "quoted_days":
        AdvertisingCampaign.objects.filter(pk=pending.pk).update(quoted_days=3)
    elif what == "quoted_currency":
        AdvertisingCampaign.objects.filter(pk=pending.pk).update(quoted_currency="EUR")
    elif what == "no_rate_reference":
        AdvertisingCampaign.objects.filter(pk=pending.pk).update(rate=None)


@pytest.mark.parametrize(
    "what",
    ["payment_amount", "payment_currency", "quoted_amount", "arithmetic", "quoted_days",
     "quoted_currency", "no_rate_reference"],
)  # fmt: skip
def test_verification_refuses_a_payment_that_no_longer_matches_the_quote(
    pending, admin_client, what
):
    _corrupt(pending, what)  # bypasses the model guards, as SQL / update() / a bug could
    resp = _decide(admin_client, pending, "verify-payment", {"method": "CASH", "reference": "R"})
    assert resp.status_code == 409 and _err(resp)["code"] == "payment_quote_mismatch"
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=pending.pk)
    assert (state.status, state.payment.status) == ("PENDING_PAYMENT", "PENDING")
    assert (
        state.payment.verified_at is None
        and not AuditEvent.objects.filter(action="advertising.campaign.activated").exists()
    )
    # rejecting stays possible: the administrator is never stuck with a corrupt record
    assert (
        _decide(admin_client, pending, "reject-payment", {"reason": "corrupt"}).status_code == 200
    )


def test_an_off_by_one_payment_amount_is_enough_to_refuse(pending, admin_client):
    CampaignPayment.objects.filter(campaign=pending).update(amount=Decimal("10001.00"))
    with pytest.raises(services.PaymentQuoteMismatch):
        services.verify_campaign_payment(pending.pk, method="CASH", verified_by=None)
    assert CampaignPayment.objects.get(campaign=pending).status == "PENDING"


def test_a_historical_rate_change_does_not_affect_verification(pending, rate, admin_client):
    """The snapshot is history: the CURRENT rate may differ and verification still works."""
    AdvertisingRate.objects.filter(pk=rate.pk).update(price_per_day=Decimal("7777.00"))
    resp = _decide(admin_client, pending, "verify-payment", {"method": "CASH"})
    assert resp.status_code == 200 and resp.json()["payment"]["amount"] == "10000.00"
    AdvertisingRate.objects.filter(pk=rate.pk).update(is_active=False)  # even with no active rate
    assert AdvertisingCampaign.objects.get(pk=pending.pk).status == "ACTIVE"
