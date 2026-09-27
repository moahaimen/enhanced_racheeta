"""Phase 3 production-closure audit (2026-09-25): billing regressions found
while preparing the launch review."""

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client

from apps.billing import services
from apps.billing.models import Plan, PlanEntitlement, Subscription
from apps.billing.types import Audience, Keys, SubscriptionStatus, UsagePeriod

pytestmark = pytest.mark.django_db


# ---- a superseded SUSPENDED row can never cancel the paid subscription that replaced it ----


def test_activation_supersedes_a_suspended_row(
    employer_billing, active_basic, admin, account_factory
):
    services.suspend_subscription(active_basic, admin=admin, reason="late")
    pro = services.request_subscription(
        employer_billing, Plan.objects.get(code="PROFESSIONAL"), requested_by=account_factory()
    )
    services.activate_subscription(pro, admin=admin)
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.CANCELLED
    assert Subscription.objects.get(pk=pro.pk).status == SubscriptionStatus.ACTIVE
    # the old row is terminal: "reactivating" it is refused and the paid plan survives
    with pytest.raises(services.SubscriptionError):
        services.activate_subscription(active_basic, admin=admin)
    assert Subscription.objects.get(pk=pro.pk).status == SubscriptionStatus.ACTIVE
    ent = services.entitlements_for(
        employer_billing.subject_type, employer_billing.subject_id, employer_billing.audience
    )
    assert ent.plan.code == "PROFESSIONAL"


def test_reactivating_a_suspended_row_still_works_when_nothing_replaced_it(active_basic, admin):
    services.suspend_subscription(active_basic, admin=admin, reason="late")
    services.activate_subscription(active_basic, admin=admin)
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.ACTIVE


# ---- the default plan cannot be retired or deleted --------------------------------------


@pytest.fixture
def default_plan():
    return Plan.objects.get(audience=Audience.EMPLOYER, is_default=True)


def test_default_plan_cannot_be_retired(default_plan):
    default_plan.is_active = False
    with pytest.raises(ValidationError) as exc:
        default_plan.save()
    assert "default" in str(exc.value)
    assert Plan.objects.get(pk=default_plan.pk).is_active is True


def test_admin_refuses_to_retire_or_delete_the_default_plan(admin, default_plan):
    client = Client()
    client.force_login(admin)
    base = f"/{settings.ADMIN_URL_PATH}billing/plan/{default_plan.pk}/"
    assert client.post(f"{base}delete/", {"post": "yes"}).status_code == 403
    assert Plan.objects.filter(pk=default_plan.pk).exists()
    data = {
        "name_ar": default_plan.name_ar,
        "name_en": default_plan.name_en,
        "billing_period": default_plan.billing_period,
        "term_days": default_plan.term_days,
        "price_currency": default_plan.price_currency,
        "is_public": "on" if default_plan.is_public else "",
        "is_default": "on",
        "sort_order": default_plan.sort_order,
        "entitlements-TOTAL_FORMS": "0",
        "entitlements-INITIAL_FORMS": "0",
        "entitlements-MIN_NUM_FORMS": "0",
        "entitlements-MAX_NUM_FORMS": "1000",
    }
    resp = client.post(f"{base}change/", {k: v for k, v in data.items() if v != ""})
    assert resp.status_code == 200 and "default plan" in resp.content.decode()
    assert Plan.objects.get(pk=default_plan.pk).is_active is True


# ---- reported usage equals enforced usage for every LIMIT period ---------------------------


def test_reported_usage_matches_enforcement_for_a_perpetual_limit(
    employer_billing, active_basic, plan
):
    PlanEntitlement.objects.filter(plan=plan, key=Keys.TALENT_INVITE_LIMIT).update(
        period=UsagePeriod.NONE, limit=2
    )
    ent = services.entitlements_for(
        employer_billing.subject_type, employer_billing.subject_id, employer_billing.audience
    )
    ent.consume(Keys.TALENT_INVITE_LIMIT, reference="a")
    ent.consume(Keys.TALENT_INVITE_LIMIT, reference="b")
    reported = services.entitlements_for(
        employer_billing.subject_type, employer_billing.subject_id, employer_billing.audience
    ).get(Keys.TALENT_INVITE_LIMIT)
    assert (reported.used, reported.remaining) == (2, 0)
