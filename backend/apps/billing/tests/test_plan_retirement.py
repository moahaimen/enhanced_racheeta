"""Sixteenth Codex review of PR #4 (commit eca49d0): an ACTIVE subscription
never references a retired plan. Retirement is refused while ACTIVE rows exist,
on every write path, and serialises with activation on the plan row lock."""

import threading

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client

from apps.billing import services
from apps.billing.models import Plan, Subscription
from apps.billing.services import SubscriptionError
from apps.billing.types import SubscriptionStatus

pytestmark = pytest.mark.django_db


def _retire(plan):
    plan.is_active = False
    plan.save()


def _pending(billing_account, plan, account_factory):
    return services.request_subscription(billing_account, plan, requested_by=account_factory())


def test_plan_without_active_subscriptions_can_be_retired(plan):
    _retire(plan)
    assert Plan.objects.get(pk=plan.pk).is_active is False


def test_retirement_is_refused_while_an_active_subscription_references_it(plan, active_basic):
    with pytest.raises(ValidationError) as exc:
        _retire(plan)
    assert "is_active" in exc.value.message_dict
    assert "1 active subscription" in str(exc.value)
    assert Plan.objects.get(pk=plan.pk).is_active is True
    active_basic.refresh_from_db()
    assert active_basic.status == SubscriptionStatus.ACTIVE and active_basic.plan_id == plan.pk


def test_several_active_subscriptions_are_all_counted(plan, active_basic, admin, account_factory):
    import uuid

    from apps.billing.types import Audience, SubjectType

    for _ in range(2):
        acc = services.get_or_create_billing_account(
            SubjectType.ORGANIZATION, uuid.uuid4(), Audience.EMPLOYER
        )
        services.activate_subscription(_pending(acc, plan, account_factory), admin=admin)
    with pytest.raises(ValidationError) as exc:
        _retire(plan)
    assert "3 active subscription" in str(exc.value)
    assert Subscription.objects.filter(plan=plan, status=SubscriptionStatus.ACTIVE).count() == 3


@pytest.mark.parametrize("state", ["PENDING", "SUSPENDED", "EXPIRED", "CANCELLED", "REJECTED"])
def test_non_active_subscriptions_do_not_block_retirement(
    plan, employer_billing, admin, account_factory, state
):
    sub = _pending(employer_billing, plan, account_factory)
    if state in ("SUSPENDED", "EXPIRED", "CANCELLED"):
        services.activate_subscription(sub, admin=admin)
    if state == "SUSPENDED":
        services.suspend_subscription(sub, admin=admin, reason="unpaid")
    elif state == "CANCELLED":
        services.cancel_subscription(sub, admin=admin, reason="closed")
    elif state == "REJECTED":
        services.reject_subscription(sub, admin=admin, reason="no")
    elif state == "EXPIRED":
        from datetime import timedelta

        from django.utils import timezone

        Subscription.objects.filter(pk=sub.pk).update(ends_at=timezone.now() - timedelta(days=1))
        assert services.expire_subscription(sub)
    assert Subscription.objects.get(pk=sub.pk).status == state
    _retire(plan)
    assert Plan.objects.get(pk=plan.pk).is_active is False


def test_other_plan_edits_still_work_with_active_subscribers(plan, active_basic):
    plan.price_amount = 150000
    plan.name_en = "Basic (renamed)"
    plan.save()
    plan.refresh_from_db()
    assert plan.price_amount == 150000 and plan.name_en == "Basic (renamed)" and plan.is_active


def test_retirement_succeeds_once_the_subscription_leaves_active(plan, active_basic, admin):
    services.suspend_subscription(active_basic, admin=admin, reason="unpaid")
    _retire(plan)
    assert Plan.objects.get(pk=plan.pk).is_active is False
    # ...and the suspended subscription cannot be reactivated on the retired plan
    with pytest.raises(SubscriptionError):
        services.activate_subscription(active_basic, admin=admin)
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.SUSPENDED


def test_activation_against_a_retired_plan_is_still_refused(
    plan, employer_billing, admin, account_factory
):
    sub = _pending(employer_billing, plan, account_factory)
    _retire(plan)
    with pytest.raises(SubscriptionError):
        services.activate_subscription(sub, admin=admin)
    assert Subscription.objects.get(pk=sub.pk).status == SubscriptionStatus.PENDING


def test_a_new_plan_can_be_created_inactive(plan):
    p = Plan.objects.create(
        code="retired-from-birth", audience=plan.audience, name_ar="x", name_en="x", is_active=False
    )
    assert Plan.objects.get(pk=p.pk).is_active is False


# ---- Django admin renders the refusal as a field error ---------------------------------


@pytest.fixture
def django_admin(admin):
    client = Client()
    client.force_login(admin)
    return client


def _change_url(plan):
    return f"/{settings.ADMIN_URL_PATH}billing/plan/{plan.pk}/change/"


def _form_data(plan, **overrides):
    data = {
        "name_ar": plan.name_ar,
        "name_en": plan.name_en,
        "description_ar": plan.description_ar,
        "description_en": plan.description_en,
        "billing_period": plan.billing_period,
        "term_days": plan.term_days,
        "price_amount": plan.price_amount or "",
        "price_currency": plan.price_currency,
        "is_public": "on" if plan.is_public else "",
        "is_default": "on" if plan.is_default else "",
        "sort_order": plan.sort_order,
        "entitlements-TOTAL_FORMS": "0",
        "entitlements-INITIAL_FORMS": "0",
        "entitlements-MIN_NUM_FORMS": "0",
        "entitlements-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v != ""}


def test_admin_shows_a_validation_error_instead_of_a_500(django_admin, plan, active_basic):
    resp = django_admin.post(_change_url(plan), _form_data(plan))  # is_active unchecked
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "1 active subscription(s) still reference this plan" in html
    assert Plan.objects.get(pk=plan.pk).is_active is True


def test_admin_can_retire_an_unused_plan_and_edit_prices(django_admin, plan, active_basic, admin):
    resp = django_admin.post(_change_url(plan), _form_data(plan, is_active="on", price_amount="99"))
    assert resp.status_code == 302
    plan.refresh_from_db()
    assert plan.is_active and plan.price_amount == 99
    services.cancel_subscription(active_basic, admin=admin, reason="closed")
    resp = django_admin.post(_change_url(plan), _form_data(plan))
    assert resp.status_code == 302
    assert Plan.objects.get(pk=plan.pk).is_active is False


# ---- activation vs retirement race -----------------------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_activation_and_retirement_never_commit_active_plus_inactive(
    plan, employer_billing, admin, account_factory
):
    sub = _pending(employer_billing, plan, account_factory)
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except SubscriptionError:
            outcomes[name] = "plan_unavailable"
        except ValidationError:
            outcomes[name] = "plan_in_use"
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    def retire():
        row = Plan.objects.get(pk=plan.pk)
        row.is_active = False
        row.save()

    threads = [
        threading.Thread(
            target=run, args=("activate", lambda: services.activate_subscription(sub, admin=admin))
        ),
        threading.Thread(target=run, args=("retire", retire)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert outcomes in (
        {"activate": "ok", "retire": "plan_in_use"},
        {"activate": "plan_unavailable", "retire": "ok"},
    ), outcomes
    plan_active = Plan.objects.get(pk=plan.pk).is_active
    sub_status = Subscription.objects.get(pk=sub.pk).status
    assert not (sub_status == SubscriptionStatus.ACTIVE and not plan_active)
    if outcomes["activate"] == "ok":
        assert sub_status == SubscriptionStatus.ACTIVE and plan_active
    else:
        assert sub_status == SubscriptionStatus.PENDING and not plan_active
