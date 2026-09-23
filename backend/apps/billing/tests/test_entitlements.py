from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing import services
from apps.billing.exceptions import EntitlementError, SubscriptionRequired, UsageLimitReached
from apps.billing.models import Plan, Subscription, UsageEvent
from apps.billing.types import Keys, SubscriptionStatus

pytestmark = pytest.mark.django_db


def test_plans_are_seeded_without_prices():
    codes = set(Plan.objects.values_list("code", flat=True))
    assert {
        "TRIAL",
        "BASIC",
        "PROFESSIONAL",
        "BUSINESS",
        "ENTERPRISE",
        "SEEKER_FREE",
        "SEEKER_PLUS",
    } <= codes
    assert Plan.objects.filter(price_amount__isnull=False).count() == 0
    assert (
        Plan.objects.get(code="TRIAL").is_default
        and Plan.objects.get(code="SEEKER_FREE").is_default
    )


def test_default_plan_applies_without_subscription(employer_billing):
    ent = services.EntitlementService(employer_billing)
    assert ent.subscription is None
    assert ent.plan.code == "TRIAL"
    assert ent.can(Keys.JOBS_POST)
    assert not ent.can(Keys.TALENT_SEARCH)
    with pytest.raises(EntitlementError) as excinfo:
        ent.require(Keys.TALENT_SEARCH)
    assert excinfo.value.default_code == "entitlement_required"
    assert excinfo.value.key == Keys.TALENT_SEARCH


def test_no_default_plan_means_subscription_required(employer_billing):
    Plan.objects.filter(code="TRIAL").update(is_active=False)
    ent = services.EntitlementService(employer_billing)
    with pytest.raises(SubscriptionRequired):
        ent.require(Keys.JOBS_POST)


def test_concurrent_limit(employer_billing):
    ent = services.EntitlementService(employer_billing)  # TRIAL: 1 active job
    ent.check_concurrent(Keys.JOBS_ACTIVE_LIMIT, current=0)
    with pytest.raises(UsageLimitReached) as excinfo:
        ent.check_concurrent(Keys.JOBS_ACTIVE_LIMIT, current=1)
    assert excinfo.value.limit == 1 and excinfo.value.used == 1


def test_active_subscription_replaces_default(active_basic, employer_billing):
    ent = services.EntitlementService(employer_billing)
    assert ent.plan.code == "BASIC"
    assert ent.can(Keys.TALENT_SEARCH)
    e = ent.get(Keys.TALENT_SEARCH_LIMIT)
    assert (e.limit, e.used, e.remaining) == (20, 0, 20)


def test_consume_counts_and_blocks_at_limit(active_basic, employer_billing):
    ent = services.EntitlementService(employer_billing)
    for i in range(20):
        ent.consume(Keys.TALENT_SEARCH_LIMIT, reference=f"s{i}")
    assert ent.get(Keys.TALENT_SEARCH_LIMIT).remaining == 0
    with pytest.raises(UsageLimitReached):
        ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="s21")
    assert UsageEvent.objects.filter(billing_account=employer_billing).count() == 20


def test_consume_is_idempotent_by_reference(active_basic, employer_billing):
    ent = services.EntitlementService(employer_billing)
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="same")
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="same")
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="same")
    assert ent.get(Keys.TALENT_SEARCH_LIMIT).used == 1


def test_credits_cover_overflow_and_are_consumed_atomically(active_basic, employer_billing, admin):
    ent = services.EntitlementService(employer_billing)
    for i in range(20):
        ent.consume(Keys.TALENT_SEARCH_LIMIT, reference=f"s{i}")
    services.grant_credits(
        employer_billing, Keys.TALENT_SEARCH_LIMIT, 2, admin=admin, note="goodwill"
    )
    assert ent.get(Keys.TALENT_SEARCH_LIMIT).remaining == 2
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="c1")
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="c2")
    assert ent.get(Keys.TALENT_SEARCH_LIMIT).credits == 0
    with pytest.raises(UsageLimitReached):
        ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="c3")
    # a failed consume must not touch the counter or credits
    assert ent.get(Keys.TALENT_SEARCH_LIMIT).used == 22


def test_revoking_more_than_balance_is_refused(employer_billing, admin):
    services.grant_credits(employer_billing, Keys.TALENT_INVITE_LIMIT, 3, admin=admin)
    with pytest.raises(services.SubscriptionError):
        services.grant_credits(employer_billing, Keys.TALENT_INVITE_LIMIT, -5, admin=admin)


def test_monthly_usage_resets_with_period(active_basic, employer_billing):
    ent = services.EntitlementService(employer_billing)
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference="x")
    assert ent.get(Keys.TALENT_SEARCH_LIMIT).used == 1
    next_month = timezone.localdate().replace(day=1) + timedelta(days=32)
    assert services.period_start_for("MONTHLY", None, next_month) != services.period_start_for(
        "MONTHLY", None
    )


def test_expired_subscription_falls_back_to_default(employer_billing, plan, admin, account_factory):
    sub = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    services.activate_subscription(
        sub, admin=admin, starts_at=timezone.now() - timedelta(days=40), term_days=30
    )
    ent = services.EntitlementService(employer_billing)
    assert ent.subscription is None
    assert ent.plan.code == "TRIAL"
    sub.refresh_from_db()
    assert sub.status == SubscriptionStatus.EXPIRED


def test_seeker_default_plan(seeker_billing):
    ent = services.EntitlementService(seeker_billing)
    assert ent.plan.code == "SEEKER_FREE"
    assert ent.get(Keys.APPLICATIONS_LIMIT).limit == 15


def test_unlimited_limit(employer_billing, admin, account_factory):
    sub = services.request_subscription(
        employer_billing, Plan.objects.get(code="ENTERPRISE"), requested_by=account_factory()
    )
    services.activate_subscription(sub, admin=admin)
    ent = services.EntitlementService(employer_billing)
    e = ent.get(Keys.TALENT_SEARCH_LIMIT)
    assert e.unlimited and e.remaining is None
    for i in range(3):
        ent.consume(Keys.TALENT_SEARCH_LIMIT, reference=f"u{i}")


def test_subscription_lifecycle_and_audit(employer_billing, plan, admin, account_factory):
    from apps.audit.models import AuditEvent

    requester = account_factory()
    sub = services.request_subscription(
        employer_billing, plan, requested_by=requester, note="paid by transfer"
    )
    assert sub.status == SubscriptionStatus.PENDING
    with pytest.raises(services.SubscriptionError):
        services.request_subscription(
            employer_billing, plan, requested_by=requester
        )  # one live at a time
    services.activate_subscription(sub, admin=admin, reference="TRX-9")
    services.suspend_subscription(sub, admin=admin, reason="abuse")
    assert services.EntitlementService(employer_billing).plan.code == "TRIAL"
    services.activate_subscription(sub, admin=admin)
    services.cancel_subscription(sub, admin=admin, reason="requested")
    with pytest.raises(services.SubscriptionError):
        services.reject_subscription(sub, admin=admin)
    actions = list(
        AuditEvent.objects.filter(
            target_type="billing.subscription", target_id=str(sub.pk)
        ).values_list("action", flat=True)
    )
    assert (
        "billing.subscription.activated" in actions and "billing.subscription.cancelled" in actions
    )
    assert sub.events.count() >= 5
    assert Subscription.objects.filter(billing_account=employer_billing).count() == 1
