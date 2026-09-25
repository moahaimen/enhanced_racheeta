"""Eighteenth Codex review of PR #4 (commit 1ef2e74), Phase 3 closure: the
staff subscription list normalises elapsed ACTIVE terms through the
authoritative expiry path before filtering and serialisation, and the direct
suspend/cancel paths expire an elapsed term instead of overriding it."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing import services
from apps.billing.models import Subscription, SubscriptionEvent
from apps.billing.types import Audience, SubjectType, SubscriptionStatus

pytestmark = pytest.mark.django_db
SUBS = "/api/v1/admin/billing/subscriptions"


def _elapse(sub, days=1):
    Subscription.objects.filter(pk=sub.pk).update(ends_at=timezone.now() - timedelta(days=days))


def _expired_events(sub):
    return SubscriptionEvent.objects.filter(
        subscription=sub, to_status=SubscriptionStatus.EXPIRED
    ).count()


def _statuses(admin_client, **params):
    resp = admin_client.get(SUBS, params)
    assert resp.status_code == 200
    body = resp.json()
    rows = body["results"] if isinstance(body, dict) else body
    return {row["id"]: row["status"] for row in rows}


@pytest.fixture
def other_active(plan, admin, account_factory):
    acc = services.get_or_create_billing_account(
        SubjectType.ORGANIZATION, uuid.uuid4(), Audience.EMPLOYER
    )
    sub = services.request_subscription(acc, plan, requested_by=account_factory())
    return services.activate_subscription(sub, admin=admin)


def test_elapsed_active_row_is_expired_before_the_list_responds(
    admin_client, active_basic, other_active
):
    _elapse(active_basic)
    statuses = _statuses(admin_client)
    assert statuses[str(active_basic.pk)] == "EXPIRED"
    assert statuses[str(other_active.pk)] == "ACTIVE"  # future term stays ACTIVE
    row = Subscription.objects.get(pk=active_basic.pk)
    assert row.status == SubscriptionStatus.EXPIRED  # persisted, not display-only
    assert _expired_events(active_basic) == 1


def test_repeated_lists_write_the_expiry_event_once(admin_client, active_basic):
    _elapse(active_basic)
    for _ in range(3):
        _statuses(admin_client)
    assert _expired_events(active_basic) == 1
    assert services.expire_all_elapsed_subscriptions() == 0


def test_status_filters_see_the_normalised_state(admin_client, active_basic, other_active):
    _elapse(active_basic)
    assert str(active_basic.pk) not in _statuses(admin_client, status="ACTIVE")
    assert str(other_active.pk) in _statuses(admin_client, status="ACTIVE")
    assert _statuses(admin_client, status="EXPIRED") == {str(active_basic.pk): "EXPIRED"}


@pytest.mark.parametrize("state", ["SUSPENDED", "CANCELLED", "EXPIRED"])
def test_non_active_rows_are_not_rewritten(admin_client, active_basic, admin, state):
    if state == "SUSPENDED":
        services.suspend_subscription(active_basic, admin=admin, reason="x")
    elif state == "CANCELLED":
        services.cancel_subscription(active_basic, admin=admin, reason="x")
    else:
        _elapse(active_basic)
        assert services.expire_subscription(active_basic)
    _elapse(active_basic, days=2)
    events_before = SubscriptionEvent.objects.filter(subscription=active_basic).count()
    assert _statuses(admin_client)[str(active_basic.pk)] == state
    assert SubscriptionEvent.objects.filter(subscription=active_basic).count() == events_before


@pytest.mark.parametrize("action", ["suspend", "cancel"])
def test_admin_actions_after_listing_reflect_the_normalised_status(
    admin_client, active_basic, action
):
    _elapse(active_basic)
    assert _statuses(admin_client)[str(active_basic.pk)] == "EXPIRED"
    resp = admin_client.post(f"{SUBS}/{active_basic.pk}/{action}", {"reason": "late"})
    assert resp.status_code == 400
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.EXPIRED
    assert _expired_events(active_basic) == 1


@pytest.mark.parametrize("action", ["suspend", "cancel"])
def test_direct_lifecycle_paths_expire_an_elapsed_term_instead_of_overriding_it(
    active_basic, admin, action
):
    """Nobody listed or resolved entitlements since the term ended: the direct
    service call still yields ACTIVE → EXPIRED, never ACTIVE → SUSPENDED/CANCELLED."""
    _elapse(active_basic)
    fn = services.suspend_subscription if action == "suspend" else services.cancel_subscription
    with pytest.raises(services.SubscriptionError, match="EXPIRED"):
        fn(active_basic, admin=admin, reason="late")
    row = Subscription.objects.get(pk=active_basic.pk)
    assert row.status == SubscriptionStatus.EXPIRED
    assert _expired_events(active_basic) == 1
    assert (
        not SubscriptionEvent.objects.filter(
            subscription=active_basic, to_status=action.upper().replace("SUSPEND", "SUSPENDED")
        )
        .exclude(to_status=SubscriptionStatus.EXPIRED)
        .exists()
    )


def test_live_terms_still_suspend_and_cancel(active_basic, admin):
    services.suspend_subscription(active_basic, admin=admin, reason="late")
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.SUSPENDED
    services.cancel_subscription(active_basic, admin=admin, reason="closed")
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.CANCELLED
    assert _expired_events(active_basic) == 0


def test_activation_expires_an_elapsed_row_instead_of_cancelling_it(
    employer_billing, plan, admin, account_factory, active_basic
):
    _elapse(active_basic)
    new = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    services.activate_subscription(new, admin=admin)
    assert Subscription.objects.get(pk=active_basic.pk).status == SubscriptionStatus.EXPIRED
    assert Subscription.objects.get(pk=new.pk).status == SubscriptionStatus.ACTIVE
