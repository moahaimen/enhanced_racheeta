"""Twentieth Codex review of PR #4 (commit bf5edf4): the default plan cannot be
deleted through any admin path, and the payment behind an activation is
recorded VERIFIED by the server."""

import pytest
from django.conf import settings
from django.db import transaction
from django.db.models import ProtectedError
from django.test import Client

from apps.billing import services
from apps.billing.models import PaymentRecord, Plan, PlanEntitlement, Subscription
from apps.billing.types import Audience, PaymentStatus, SubscriptionStatus

pytestmark = pytest.mark.django_db
PLANS = f"/{settings.ADMIN_URL_PATH}billing/plan/"
SUBS = "/api/v1/admin/billing/subscriptions"


# ---- 1. default plan deletion -----------------------------------------------------------


@pytest.fixture
def django_admin(admin):
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def default_plan():
    return Plan.objects.get(audience=Audience.EMPLOYER, is_default=True)


@pytest.fixture
def spare():
    return Plan.objects.create(code="spare", audience=Audience.EMPLOYER, name_ar="x", name_en="x")


def _bulk_delete(client, *plans):
    return client.post(
        PLANS,
        {
            "action": "delete_selected",
            "_selected_action": [str(p.pk) for p in plans],
            "post": "yes",
        },
    )


def test_unused_non_default_plan_can_still_be_deleted(django_admin, spare):
    resp = django_admin.post(f"{PLANS}{spare.pk}/delete/", {"post": "yes"})
    assert resp.status_code == 302 and not Plan.objects.filter(pk=spare.pk).exists()


def test_direct_deletes_of_the_default_plan_are_refused(django_admin, default_plan):
    assert (
        django_admin.post(f"{PLANS}{default_plan.pk}/delete/", {"post": "yes"}).status_code == 403
    )
    # ORM paths (shell, scripts, any future code) hit the model guard, not only the admin
    for delete in (default_plan.delete, Plan.objects.filter(pk=default_plan.pk).delete):
        with pytest.raises(ProtectedError), transaction.atomic():
            delete()
    assert Plan.objects.filter(pk=default_plan.pk).exists()


def test_bulk_delete_of_only_the_default_plan_is_refused(django_admin, default_plan):
    entitlements = PlanEntitlement.objects.filter(plan=default_plan).count()
    resp = _bulk_delete(django_admin, default_plan)
    assert resp.status_code == 200  # the "cannot delete" page, never the success redirect
    assert Plan.objects.filter(pk=default_plan.pk).exists()
    assert PlanEntitlement.objects.filter(plan=default_plan).count() == entitlements


def test_mixed_bulk_delete_deletes_nothing(django_admin, default_plan, spare):
    entitlements = PlanEntitlement.objects.count()
    resp = _bulk_delete(django_admin, default_plan, spare)
    assert resp.status_code == 200
    # and below the admin, a queryset delete of the mixed selection is atomic too
    with pytest.raises(ProtectedError), transaction.atomic():
        Plan.objects.filter(pk__in=[spare.pk, default_plan.pk]).delete()
    assert Plan.objects.filter(pk__in=[default_plan.pk, spare.pk]).count() == 2
    assert PlanEntitlement.objects.count() == entitlements


def test_bulk_delete_of_non_default_plans_still_works(django_admin, spare):
    other = Plan.objects.create(
        code="spare-2", audience=Audience.EMPLOYER, name_ar="y", name_en="y"
    )
    resp = _bulk_delete(django_admin, spare, other)
    assert resp.status_code == 302
    assert not Plan.objects.filter(pk__in=[spare.pk, other.pk]).exists()


# ---- 4. activation payment status ---------------------------------------------------------


@pytest.fixture
def pending(employer_billing, plan, account_factory):
    return services.request_subscription(employer_billing, plan, requested_by=account_factory())


def _activate(admin_client, sub, payload):
    return admin_client.post(f"{SUBS}/{sub.pk}/activate", payload, format="json")


@pytest.mark.parametrize("extra", [{}, {"currency": "IQD", "note": "bank slip"}])
def test_activation_with_a_payment_object_records_it_verified(admin_client, pending, extra):
    payment = {"amount": "150000", "method": "BANK_TRANSFER", "reference": "TRX-7", **extra}
    resp = _activate(admin_client, pending, {"term_days": 30, "payment": payment})
    assert resp.status_code == 200 and resp.json()["status"] == "ACTIVE"
    record = PaymentRecord.objects.get(subscription=pending)
    assert record.status == PaymentStatus.VERIFIED and record.reference == "TRX-7"


@pytest.mark.parametrize("status", ["REJECTED", "RECORDED", "VERIFIED"])
def test_a_client_cannot_choose_the_payment_status(admin_client, pending, status):
    payment = {"amount": "1", "method": "BANK_TRANSFER", "reference": "TRX-8", "status": status}
    resp = _activate(admin_client, pending, {"payment": payment})
    assert resp.status_code == 400
    # nested field errors live under `details` in the uniform envelope
    assert resp.json()["error"]["details"]["payment"]["status"] == [
        "This field cannot be set by a client."
    ]
    assert Subscription.objects.get(pk=pending.pk).status == SubscriptionStatus.PENDING
    assert not PaymentRecord.objects.filter(subscription=pending).exists()


def test_reference_only_activation_still_records_verified(admin_client, pending):
    assert _activate(admin_client, pending, {"reference": "TRX-9"}).status_code == 200
    assert PaymentRecord.objects.get(subscription=pending).status == PaymentStatus.VERIFIED


def test_failed_activation_records_no_payment(admin_client, pending, plan):
    Plan.objects.filter(pk=plan.pk).update(is_active=False)  # retired since the request
    resp = _activate(admin_client, pending, {"payment": {"amount": "1", "reference": "TRX-10"}})
    assert resp.status_code == 400
    assert Subscription.objects.get(pk=pending.pk).status == SubscriptionStatus.PENDING
    assert not PaymentRecord.objects.exists()


def test_payment_failure_rolls_the_activation_back(admin_client, pending, monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("storage down")

    monkeypatch.setattr(PaymentRecord.objects, "create", broken)
    with pytest.raises(RuntimeError):
        _activate(admin_client, pending, {"payment": {"amount": "1", "reference": "TRX-11"}})
    assert Subscription.objects.get(pk=pending.pk).status == SubscriptionStatus.PENDING
    assert not pending.events.filter(to_status=SubscriptionStatus.ACTIVE).exists()
