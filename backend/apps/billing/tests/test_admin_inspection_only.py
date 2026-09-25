"""Seventeenth Codex review of PR #4 (commit 153493f): billing accounts,
credit balances and every ledger/history model are inspection-only in the
Django admin. Lifecycle and credits move only through apps.billing.services."""

import uuid

import pytest
from django.conf import settings
from django.test import Client

from apps.billing import services
from apps.billing.models import (
    BillingAccount,
    CreditBalance,
    CreditTransaction,
    PaymentRecord,
    Subscription,
    SubscriptionEvent,
    UsageCounter,
    UsageEvent,
)
from apps.billing.types import Audience, SubjectType

pytestmark = pytest.mark.django_db
A = f"/{settings.ADMIN_URL_PATH}billing/"


@pytest.fixture
def django_admin(admin):
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def credits(employer_billing, admin):
    return services.grant_credits(employer_billing, "talent.search", 5, admin=admin, note="seed")


def _change(model, pk):
    return f"{A}{model}/{pk}/change/"


# ---- BillingAccount --------------------------------------------------------------------


def test_billing_account_change_page_is_read_only(django_admin, employer_billing, active_basic):
    resp = django_admin.get(_change("billingaccount", employer_billing.pk))
    assert resp.status_code == 200
    html = resp.content.decode()
    for field in ("subject_type", "subject_id", "audience"):
        assert f'name="{field}"' not in html  # rendered as text, not as an input
    assert str(employer_billing.subject_id) in html
    assert "BASIC" in html  # subscriptions stay inspectable inline
    assert (
        'name="_save"' not in html or "Save" not in html or True
    )  # no save controls asserted below
    assert 'name="_save"' not in html


@pytest.mark.parametrize("field", ["subject_type", "subject_id", "audience"])
def test_posting_a_new_identity_does_not_rebind_the_account(
    django_admin, employer_billing, active_basic, field
):
    before = BillingAccount.objects.get(pk=employer_billing.pk)
    payload = {
        "subject_type": before.subject_type,
        "subject_id": str(before.subject_id),
        "audience": before.audience,
    }
    payload[field] = {
        "subject_type": SubjectType.ACCOUNT,
        "subject_id": str(uuid.uuid4()),
        "audience": Audience.JOB_SEEKER,
    }[field]
    resp = django_admin.post(_change("billingaccount", employer_billing.pk), payload)
    assert resp.status_code == 403
    after = BillingAccount.objects.get(pk=employer_billing.pk)
    assert (after.subject_type, after.subject_id, after.audience) == (
        before.subject_type,
        before.subject_id,
        before.audience,
    )
    assert Subscription.objects.get(pk=active_basic.pk).billing_account_id == before.pk


def test_billing_account_add_and_delete_are_forbidden(django_admin, employer_billing, active_basic):
    assert django_admin.get(f"{A}billingaccount/add/").status_code == 403
    assert (
        django_admin.post(
            f"{A}billingaccount/{employer_billing.pk}/delete/", {"post": "yes"}
        ).status_code
        == 403
    )
    # bulk delete action is not offered either
    resp = django_admin.post(
        f"{A}billingaccount/",
        {"action": "delete_selected", "_selected_action": [str(employer_billing.pk)]},
    )
    assert resp.status_code in (200, 302)
    assert BillingAccount.objects.filter(pk=employer_billing.pk).exists()
    assert Subscription.objects.filter(pk=active_basic.pk).exists()


def test_service_created_accounts_still_work(admin, account_factory, plan):
    acc = services.get_or_create_billing_account(
        SubjectType.ORGANIZATION, uuid.uuid4(), Audience.EMPLOYER
    )
    sub = services.request_subscription(acc, plan, requested_by=account_factory())
    services.activate_subscription(sub, admin=admin)
    assert services.entitlements_for(acc.subject_type, acc.subject_id, acc.audience).plan == plan


# ---- CreditBalance and the ledger ------------------------------------------------------


def test_credit_balance_form_has_no_editable_fields(django_admin, credits):
    html = django_admin.get(_change("creditbalance", credits.pk)).content.decode()
    for field in ("billing_account", "key", "balance"):
        assert f'name="{field}"' not in html
    assert "talent.search" in html and ">5<" in html
    assert 'name="_save"' not in html


def test_credit_balance_cannot_be_moved_changed_or_deleted(
    django_admin, credits, employer_billing, seeker_billing
):
    resp = django_admin.post(
        _change("creditbalance", credits.pk),
        {"billing_account": str(seeker_billing.pk), "key": "other", "balance": "999"},
    )
    assert resp.status_code == 403
    row = CreditBalance.objects.get(pk=credits.pk)
    assert (row.billing_account_id, row.key, row.balance) == (
        employer_billing.pk,
        "talent.search",
        5,
    )
    assert django_admin.get(f"{A}creditbalance/add/").status_code == 403
    assert (
        django_admin.post(f"{A}creditbalance/{credits.pk}/delete/", {"post": "yes"}).status_code
        == 403
    )
    assert CreditBalance.objects.filter(pk=credits.pk).exists()
    assert CreditTransaction.objects.filter(billing_account=employer_billing).count() == 1


def test_grant_credits_is_unaffected(credits, employer_billing, admin):
    services.grant_credits(employer_billing, "talent.search", -2, admin=admin, note="adjust")
    assert CreditBalance.objects.get(pk=credits.pk).balance == 3
    deltas = list(
        CreditTransaction.objects.filter(billing_account=employer_billing)
        .order_by("created_at")
        .values_list("delta", flat=True)
    )
    assert deltas == [5, -2]


@pytest.mark.parametrize(
    "model",
    ["credittransaction", "usagecounter", "usageevent", "subscriptionevent", "paymentrecord"],
)
def test_ledger_and_history_models_are_append_only(django_admin, model, employer_billing, admin):
    assert django_admin.get(f"{A}{model}/add/").status_code == 403
    assert django_admin.get(f"{A}{model}/").status_code == 200


def test_history_rows_cannot_be_edited_or_deleted(
    django_admin, employer_billing, active_basic, admin, credits
):
    from datetime import date

    UsageCounter.objects.create(
        billing_account=employer_billing, key="talent.search", period_start=date.today(), used=1
    )
    UsageEvent.objects.create(billing_account=employer_billing, key="talent.search", reference="r1")
    rows = {
        "credittransaction": CreditTransaction.objects.get(billing_account=employer_billing),
        "usagecounter": UsageCounter.objects.get(billing_account=employer_billing),
        "usageevent": UsageEvent.objects.get(billing_account=employer_billing),
        "subscriptionevent": SubscriptionEvent.objects.filter(subscription=active_basic).first(),
        "paymentrecord": PaymentRecord.objects.create(
            subscription=active_basic, amount=1000, reference="TRX-9", recorded_by=admin
        ),
    }
    for model, row in rows.items():
        html = django_admin.get(_change(model, row.pk)).content.decode()
        assert 'name="_save"' not in html, model
        assert (
            django_admin.post(f"{A}{model}/{row.pk}/delete/", {"post": "yes"}).status_code == 403
        ), model
        assert type(row).objects.filter(pk=row.pk).exists(), model
