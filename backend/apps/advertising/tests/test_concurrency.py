"""Race safety with real second database connections (Phase 6/7 style; no sleeps
decide correctness). Lock order: company/account -> campaign -> payment -> product
(and the active rate at submission)."""

import threading
from decimal import Decimal

import pytest
from django.db import connection, transaction
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.advertising import services, views
from apps.advertising.models import AdvertisingCampaign, AdvertisingRate, CampaignPayment
from apps.marketplace.models import Product

from .conftest import CAMPAIGNS

pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def _in_thread(fn):
    outcome: dict = {}

    def run():
        try:
            outcome["result"] = fn()
        except Exception as exc:  # noqa: BLE001 - reported to the test
            outcome["error"] = exc
        finally:
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    return thread, outcome


def _pending(ready, campaign_factory):
    company, product = ready
    campaign = campaign_factory(company, product)
    services.submit_campaign(company, campaign.pk)
    return AdvertisingCampaign.objects.get(pk=campaign.pk)


def _pair(campaign):
    state = AdvertisingCampaign.objects.select_related("payment").get(pk=campaign.pk)
    return state.status, state.payment.status


# ---- verify vs reject -------------------------------------------------------------------------


@pytest.mark.parametrize("round_", range(4))
def test_verify_racing_reject_commits_exactly_one_coherent_pair(
    ready, rate, campaign_factory, admin_user, round_
):
    campaign = _pending(ready, campaign_factory)
    barrier = threading.Barrier(2)

    def verify():
        barrier.wait(timeout=10)
        return services.verify_campaign_payment(
            campaign.pk, method="BANK_TRANSFER", reference="R", verified_by=admin_user
        )

    def reject():
        barrier.wait(timeout=10)
        return services.reject_campaign_payment(campaign.pk, reason="no", rejected_by=admin_user)

    t1, o1 = _in_thread(verify)
    t2, o2 = _in_thread(reject)
    t1.join(timeout=20)
    t2.join(timeout=20)
    assert not t1.is_alive() and not t2.is_alive()
    successes = [o for o in (o1, o2) if "error" not in o]
    assert len(successes) == 1, (o1, o2)  # exactly one transition committed
    loser = o1 if "error" in o1 else o2
    assert isinstance(loser["error"], (services.InvalidTransition, services.PaymentNotPending))
    assert _pair(campaign) in {("ACTIVE", "VERIFIED"), ("REJECTED", "REJECTED")}


def test_two_verifications_race_and_only_one_wins(ready, rate, campaign_factory, admin_user):
    campaign = _pending(ready, campaign_factory)
    barrier = threading.Barrier(2)

    def verify():
        barrier.wait(timeout=10)
        return services.verify_campaign_payment(campaign.pk, method="CASH", verified_by=admin_user)

    t1, o1 = _in_thread(verify)
    t2, o2 = _in_thread(verify)
    t1.join(timeout=20)
    t2.join(timeout=20)
    assert sum("error" not in o for o in (o1, o2)) == 1
    assert _pair(campaign) == ("ACTIVE", "VERIFIED")
    assert CampaignPayment.objects.filter(status="VERIFIED").count() == 1


# ---- company state ----------------------------------------------------------------------------


def test_submission_with_a_stale_company_role_fails_and_changes_nothing(
    ready, rate, campaign_factory, monkeypatch
):
    """The view loaded the company while it was a MEDICAL_COMPANY; another connection
    then changes the role; the service must decide on the current rows."""
    company, product = ready
    campaign = campaign_factory(company, product)
    account_id = company.account_id
    original = views._own_company

    def own_company_then_role_changes(request):
        snapshot = original(request)
        thread, _ = _in_thread(
            lambda: Account.objects.filter(pk=account_id).update(role=AccountRole.PATIENT)
        )
        thread.join(timeout=10)
        assert snapshot.account.role == AccountRole.MEDICAL_COMPANY  # stale, as a request holds it
        return snapshot

    monkeypatch.setattr(views, "_own_company", own_company_then_role_changes)
    client = APIClient()
    client.force_authenticate(user=Account.objects.get(pk=account_id))  # still a company here
    resp = client.post(f"{CAMPAIGNS}/{campaign.pk}/submit")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "company_not_eligible"
    assert AdvertisingCampaign.objects.get(pk=campaign.pk).status == "DRAFT"
    assert not CampaignPayment.objects.exists()


def test_verification_after_the_company_role_changed_elsewhere_fails_and_shows_no_ad(
    ready, rate, campaign_factory, provider_factory
):
    campaign = _pending(ready, campaign_factory)
    company, _ = ready
    thread, outcome = _in_thread(
        lambda: Account.objects.filter(pk=company.account_id).update(role=AccountRole.PATIENT)
    )
    thread.join(timeout=10)
    assert "error" not in outcome
    with pytest.raises(services.CompanyNotEligible):
        services.verify_campaign_payment(campaign.pk, method="CASH", verified_by=None)
    assert _pair(campaign) == ("PENDING_PAYMENT", "PENDING")
    provider = provider_factory()
    assert not AdvertisingCampaign.objects.visible_to(provider).exists()


# ---- product state -----------------------------------------------------------------------------


def test_verification_waits_for_a_concurrent_product_deactivation_and_then_refuses(
    ready, rate, campaign_factory, admin_user
):
    """Another transaction has deactivated the product but not committed yet.
    Verification must wait for the product row, re-read its CURRENT state and refuse:
    the payment stays PENDING and the campaign stays PENDING_PAYMENT."""
    campaign = _pending(ready, campaign_factory)
    _, product = ready
    holder_has_lock = threading.Event()
    release = threading.Event()

    def deactivate_then_commit():
        with transaction.atomic():
            Product.objects.select_for_update().get(pk=product.pk)
            Product.objects.filter(pk=product.pk).update(is_active=False)
            holder_has_lock.set()
            assert release.wait(timeout=15)

    holder, holder_outcome = _in_thread(deactivate_then_commit)
    assert holder_has_lock.wait(timeout=10)
    worker, outcome = _in_thread(
        lambda: services.verify_campaign_payment(campaign.pk, method="CASH", verified_by=admin_user)
    )
    worker.join(timeout=0.7)
    assert worker.is_alive(), "verification did not wait for the product row"
    release.set()
    worker.join(timeout=15)
    holder.join(timeout=15)
    assert "error" not in holder_outcome
    assert isinstance(outcome.get("error"), services.ProductUnavailable), outcome
    assert _pair(campaign) == ("PENDING_PAYMENT", "PENDING")


# ---- pricing ------------------------------------------------------------------------------------


def test_submission_waits_for_a_concurrent_rate_change_and_uses_the_committed_rate(
    ready, rate, campaign_factory
):
    """An administrator is changing the daily rate (not committed). A submission that
    starts meanwhile must wait for the rate row and price from the COMMITTED value —
    never from a rate a page loaded earlier."""
    company, product = ready
    campaign = campaign_factory(company, product)  # 10 days
    holder_has_lock = threading.Event()
    release = threading.Event()

    def change_rate_then_commit():
        with transaction.atomic():
            row = AdvertisingRate.objects.select_for_update().get(pk=rate.pk)
            row.price_per_day = Decimal("2500.00")
            row.save()
            holder_has_lock.set()
            assert release.wait(timeout=15)

    holder, holder_outcome = _in_thread(change_rate_then_commit)
    assert holder_has_lock.wait(timeout=10)
    worker, outcome = _in_thread(lambda: services.submit_campaign(company, campaign.pk))
    worker.join(timeout=0.7)
    assert worker.is_alive(), "submission did not wait for the rate row"
    release.set()
    worker.join(timeout=15)
    holder.join(timeout=15)
    assert "error" not in holder_outcome and "error" not in outcome, outcome
    stored = AdvertisingCampaign.objects.get(pk=campaign.pk)
    assert stored.quoted_amount == Decimal("25000.00") and stored.quoted_daily_rate == Decimal(
        "2500.00"
    )
    assert CampaignPayment.objects.get(campaign=campaign).amount == Decimal("25000.00")


def test_a_rate_swap_after_submission_leaves_the_snapshot_alone(ready, rate, campaign_factory):
    campaign = _pending(ready, campaign_factory)
    thread, outcome = _in_thread(
        lambda: AdvertisingRate.objects.filter(pk=rate.pk).update(price_per_day=Decimal("9999.00"))
    )
    thread.join(timeout=10)
    assert "error" not in outcome
    stored = AdvertisingCampaign.objects.get(pk=campaign.pk)
    assert stored.quoted_amount == Decimal("10000.00")


# ---- the campaign lock -------------------------------------------------------------------------


def test_a_cancellation_and_a_verification_serialize_on_the_campaign(
    ready, rate, campaign_factory, admin_user
):
    """Whichever wins the campaign lock, the pair stays coherent."""
    campaign = _pending(ready, campaign_factory)
    company, _ = ready
    barrier = threading.Barrier(2)

    def verify():
        barrier.wait(timeout=10)
        return services.verify_campaign_payment(campaign.pk, method="CASH", verified_by=admin_user)

    def cancel():
        barrier.wait(timeout=10)
        return services.cancel_campaign(company, campaign.pk)

    t1, o1 = _in_thread(verify)
    t2, o2 = _in_thread(cancel)
    t1.join(timeout=20)
    t2.join(timeout=20)
    status, payment = _pair(campaign)
    assert (status, payment) in {("ACTIVE", "VERIFIED"), ("CANCELLED", "VERIFIED")}
    if status == "CANCELLED":  # cancel only succeeds after activation
        assert "error" not in o1 and "error" not in o2


# ---- each row lock is really taken (state decided under the lock, not before it) -----------------


@pytest.mark.parametrize(
    "row,expected",
    [("campaign", services.InvalidTransition), ("payment", services.PaymentNotPending)],
)
def test_verification_decides_on_the_row_state_committed_under_its_lock(
    ready, rate, campaign_factory, admin_user, row, expected
):
    """Another transaction holds the row lock and has changed its state (not yet
    committed). Verification must wait for the lock and then decide on the committed
    state — refusing — instead of on the state it could see before the lock (which
    would activate a campaign that was already decided)."""
    campaign = _pending(ready, campaign_factory)
    holder_has_lock = threading.Event()
    release = threading.Event()

    def change_state_then_commit():
        with transaction.atomic():
            if row == "campaign":
                AdvertisingCampaign.objects.select_for_update().get(pk=campaign.pk)
                AdvertisingCampaign.objects.filter(pk=campaign.pk).update(status="REJECTED")
            else:
                CampaignPayment.objects.select_for_update().get(campaign=campaign)
                CampaignPayment.objects.filter(campaign=campaign).update(status="REJECTED")
            holder_has_lock.set()
            assert release.wait(timeout=15)

    holder, holder_outcome = _in_thread(change_state_then_commit)
    assert holder_has_lock.wait(timeout=10)
    worker, outcome = _in_thread(
        lambda: services.verify_campaign_payment(campaign.pk, method="CASH", verified_by=admin_user)
    )
    worker.join(timeout=0.7)
    assert worker.is_alive(), f"verification did not wait for the {row} lock"
    release.set()
    worker.join(timeout=15)
    holder.join(timeout=15)
    assert "error" not in holder_outcome
    assert isinstance(outcome.get("error"), expected), outcome
    assert not CampaignPayment.objects.filter(status="VERIFIED").exists()
    assert AdvertisingCampaign.objects.get(pk=campaign.pk).status != "ACTIVE"
