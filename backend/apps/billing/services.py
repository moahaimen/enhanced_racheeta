"""Entitlement service — the only way business modules ask commercial questions.

    ent = entitlements_for(subject_type, subject_id)
    ent.require(Keys.JOBS_POST)                    # boolean capability
    ent.check_concurrent(Keys.JOBS_ACTIVE_LIMIT, current=3)
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference=...)  # atomic, idempotent

Resolution order: ACTIVE subscription plan → default plan of the audience →
nothing (every capability denied). Extra credits cover usage beyond a limit.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.audit import services as audit

from .exceptions import EntitlementError, SubscriptionRequired, UsageLimitReached
from .models import (
    BillingAccount,
    CreditBalance,
    CreditTransaction,
    Plan,
    PlanEntitlement,
    Subscription,
    SubscriptionEvent,
    UsageCounter,
    UsageEvent,
)
from .types import CreditReason, EntitlementKind, SubscriptionStatus, UsagePeriod


@dataclass(frozen=True)
class Entitlement:
    key: str
    kind: str
    enabled: bool
    limit: int | None  # None = unlimited (LIMIT kind) / n.a. (BOOLEAN)
    period: str
    used: int
    credits: int

    @property
    def remaining(self) -> int | None:
        if self.kind != EntitlementKind.LIMIT or self.limit is None:
            return None
        return max(self.limit - self.used, 0) + self.credits

    @property
    def unlimited(self) -> bool:
        return self.kind == EntitlementKind.LIMIT and self.limit is None


def period_start_for(
    period: str, subscription: Subscription | None, today: date | None = None
) -> date:
    today = today or timezone.localdate()
    if period == UsagePeriod.DAILY:
        return today
    if period == UsagePeriod.MONTHLY:
        return today.replace(day=1)
    if period == UsagePeriod.SUBSCRIPTION and subscription is not None and subscription.starts_at:
        return timezone.localdate(subscription.starts_at)
    return date(1970, 1, 1)  # NONE / no term: one perpetual bucket


def period_end_for(period: str, start: date) -> date | None:
    if period == UsagePeriod.DAILY:
        return start + timedelta(days=1)
    if period == UsagePeriod.MONTHLY:
        return start.replace(day=calendar.monthrange(start.year, start.month)[1]) + timedelta(
            days=1
        )
    return None


def get_or_create_billing_account(subject_type: str, subject_id, audience: str) -> BillingAccount:
    account, _ = BillingAccount.objects.get_or_create(
        subject_type=subject_type, subject_id=subject_id, defaults={"audience": audience}
    )
    return account


class EntitlementService:
    def __init__(self, billing_account: BillingAccount):
        self.billing_account = billing_account
        self._subscription: Subscription | None | bool = False
        self._pending: Subscription | None | bool = False
        self._plan: Plan | None | bool = False

    # ---- resolution ---------------------------------------------------------

    @property
    def subscription(self) -> Subscription | None:
        if self._subscription is False:
            sub = (
                Subscription.objects.filter(
                    billing_account=self.billing_account, status=SubscriptionStatus.ACTIVE
                )
                .select_related("plan")
                .first()
            )
            if sub is not None and _has_elapsed(sub):
                expire_subscription(sub)
                sub = None
            self._subscription = sub
        return self._subscription  # type: ignore[return-value]

    @property
    def pending_subscription(self) -> Subscription | None:
        """The request waiting for an administrator, if any.

        This is billing *UI* state, never entitlement state: a PENDING request
        grants nothing, so `plan`, `get()` and every capability check keep
        resolving through the ACTIVE subscription (or the audience default).
        Only PENDING counts — a SUSPENDED, CANCELLED, REJECTED or EXPIRED row
        is finished business and must never be shown as a live request."""
        if self._pending is False:
            self._pending = (
                Subscription.objects.filter(
                    billing_account=self.billing_account, status=SubscriptionStatus.PENDING
                )
                .select_related("plan")
                .order_by("-created_at")
                .first()
            )
        return self._pending  # type: ignore[return-value]

    @property
    def plan(self) -> Plan | None:
        if self._plan is False:
            sub = self.subscription
            if sub is not None and sub.plan.is_active:
                self._plan = sub.plan
            else:
                self._plan = Plan.objects.filter(
                    audience=self.billing_account.audience, is_default=True, is_active=True
                ).first()
        return self._plan  # type: ignore[return-value]

    def _entitlement_row(self, key: str) -> PlanEntitlement | None:
        plan = self.plan
        if plan is None:
            return None
        return PlanEntitlement.objects.filter(plan=plan, key=key).first()

    def get(self, key: str) -> Entitlement:
        row = self._entitlement_row(key)
        credits = (
            CreditBalance.objects.filter(billing_account=self.billing_account, key=key)
            .values_list("balance", flat=True)
            .first()
            or 0
        )
        if row is None:
            return Entitlement(
                key=key,
                kind=EntitlementKind.BOOLEAN,
                enabled=False,
                limit=0,
                period=UsagePeriod.NONE,
                used=0,
                credits=credits,
            )
        used = 0
        if row.kind == EntitlementKind.LIMIT:
            # Same bucket `consume()` increments (the perpetual one for NONE), so
            # what is reported always equals what is enforced.
            start = period_start_for(row.period, self.subscription)
            used = (
                UsageCounter.objects.filter(
                    billing_account=self.billing_account, key=key, period_start=start
                )
                .values_list("used", flat=True)
                .first()
                or 0
            )
        return Entitlement(
            key=key,
            kind=row.kind,
            enabled=row.enabled,
            limit=row.limit,
            period=row.period,
            used=used,
            credits=credits,
        )

    def all(self) -> list[Entitlement]:
        plan = self.plan
        if plan is None:
            return []
        return [self.get(row.key) for row in plan.entitlements.all()]

    # ---- checks -------------------------------------------------------------

    def can(self, key: str) -> bool:
        ent = self.get(key)
        return bool(ent.enabled)

    def require(self, key: str) -> Entitlement:
        ent = self.get(key)
        if not ent.enabled:
            if self.plan is None:
                raise SubscriptionRequired(key=key)
            raise EntitlementError(key=key)
        return ent

    def check_concurrent(self, key: str, current: int) -> Entitlement:
        """For LIMIT keys that count live objects (e.g. active jobs)."""
        ent = self.require(key)
        if ent.limit is not None and current >= ent.limit + ent.credits:
            raise UsageLimitReached(key=key, limit=ent.limit, used=current)
        return ent

    @transaction.atomic
    def consume(self, key: str, amount: int = 1, reference: str = "") -> Entitlement:
        """Consume usage atomically. Credits cover usage beyond the plan limit.
        A repeated `reference` is a no-op (idempotent retries, concurrent
        identical requests): the usage event is inserted first as the claim,
        and a unique-constraint failure means another transaction already
        consumed this reference."""
        ent = self.require(key)
        if ent.kind != EntitlementKind.LIMIT:
            return ent
        try:
            with transaction.atomic():
                event = UsageEvent.objects.create(
                    billing_account=self.billing_account,
                    key=key,
                    amount=amount,
                    reference=reference,
                )
        except IntegrityError:
            return self.get(key)
        if ent.unlimited:
            return ent
        start = period_start_for(ent.period, self.subscription)
        counter, _ = UsageCounter.objects.select_for_update().get_or_create(
            billing_account=self.billing_account, key=key, period_start=start
        )
        if counter.used + amount > (ent.limit or 0):
            # Only the part of *this* consumption above the limit needs credit.
            overflow = min(amount, counter.used + amount - (ent.limit or 0))
            credit = (
                CreditBalance.objects.select_for_update()
                .filter(billing_account=self.billing_account, key=key)
                .first()
            )
            if credit is None or credit.balance < overflow:
                raise UsageLimitReached(key=key, limit=ent.limit, used=counter.used)
            credit.balance = F("balance") - overflow
            credit.save(update_fields=["balance", "updated_at"])
            CreditTransaction.objects.create(
                billing_account=self.billing_account,
                key=key,
                delta=-overflow,
                reason=CreditReason.CONSUME,
                reference=reference,
            )
            event.covered_by_credit = True
            event.save(update_fields=["covered_by_credit"])
        counter.used = F("used") + amount
        counter.save(update_fields=["used", "updated_at"])
        return self.get(key)


def entitlements_for(subject_type: str, subject_id, audience: str) -> EntitlementService:
    return EntitlementService(get_or_create_billing_account(subject_type, subject_id, audience))


# ---- subscription lifecycle (administrator-controlled) ---------------------


class SubscriptionError(Exception):
    pass


def _event(sub: Subscription, from_status: str, to_status: str, actor, reason: str = "") -> None:
    SubscriptionEvent.objects.create(
        subscription=sub,
        from_status=from_status,
        to_status=to_status,
        actor=actor if getattr(actor, "pk", None) else None,
        reason=reason,
    )


@transaction.atomic
@transaction.atomic
def request_subscription(
    billing_account: BillingAccount, plan: Plan, *, requested_by, note: str = ""
) -> Subscription:
    if not plan.is_active or not plan.is_public or plan.audience != billing_account.audience:
        raise SubscriptionError("This plan cannot be requested.")
    # Serialise requests per account and normalise elapsed terms *before* the
    # live-subscription check, so a renewal never depends on some other
    # entitlement lookup having expired the old row first.
    BillingAccount.objects.select_for_update().get(pk=billing_account.pk)
    expire_elapsed_subscriptions(billing_account)
    if Subscription.objects.filter(
        billing_account=billing_account,
        status__in=[SubscriptionStatus.PENDING, SubscriptionStatus.ACTIVE],
    ).exists():
        raise SubscriptionError("A pending or active subscription already exists.")
    try:
        with transaction.atomic():
            sub = Subscription.objects.create(
                billing_account=billing_account,
                plan=plan,
                requested_by=requested_by,
                requester_note=note,
            )
    except IntegrityError as exc:  # one live subscription per account (DB constraint)
        raise SubscriptionError("A pending or active subscription already exists.") from exc
    _event(sub, "", SubscriptionStatus.PENDING, requested_by, note)
    audit.record(
        actor=requested_by,
        action="billing.subscription.requested",
        target=sub,
        summary=f"requested {plan.code}",
    )
    return sub


@transaction.atomic
def activate_subscription(
    sub: Subscription,
    *,
    admin,
    starts_at: datetime | None = None,
    term_days: int | None = None,
    reference: str = "",
    note: str = "",
) -> Subscription:
    # Serialise admin decisions per account and re-read the row under the lock.
    BillingAccount.objects.select_for_update().get(pk=sub.billing_account_id)
    sub.status = (
        Subscription.objects.select_for_update()
        .filter(pk=sub.pk)
        .values_list("status", flat=True)
        .get()
    )
    if sub.status not in (SubscriptionStatus.PENDING, SubscriptionStatus.SUSPENDED):
        raise SubscriptionError(f"Cannot activate a subscription in status {sub.status}.")
    # The plan is re-read under lock in the same transaction: a plan retired
    # between the request and the decision must not become an ACTIVE row that
    # entitlements would then ignore (they fall back to the default plan).
    plan_row = Plan.objects.select_for_update().filter(pk=sub.plan_id).first()
    if plan_row is None or not plan_row.is_active:
        raise SubscriptionError(
            "The requested plan is no longer available; reject this request and ask the "
            "organisation to choose a current plan."
        )
    sub.plan = plan_row
    # Elapsed ACTIVE rows of this account are EXPIRED first (same helper as
    # every entitlement read), so only a genuinely live row gets superseded.
    expire_elapsed_subscriptions(sub.billing_account)
    # One live subscription per account (DB constraint): the administrator's
    # decision supersedes any other ACTIVE row *and* any newer PENDING request
    # (policy: reactivating a suspended subscription cancels the pending
    # request; the cancellation is its own audited event).
    # A SUSPENDED row is superseded too: left alone it could be "reactivated"
    # later and cancel the subscription that replaced it.
    for other in Subscription.objects.filter(
        billing_account=sub.billing_account,
        status__in=[
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PENDING,
            SubscriptionStatus.SUSPENDED,
        ],
    ).exclude(pk=sub.pk):
        cancel_subscription(
            other, admin=admin, reason=f"superseded by activation of {sub.plan.code} ({sub.pk})"
        )
    starts = starts_at or timezone.now()
    days = term_days or sub.plan.term_days
    previous = sub.status
    sub.status = SubscriptionStatus.ACTIVE
    sub.starts_at = starts
    sub.ends_at = starts + timedelta(days=days) if days else None
    sub.activated_by = admin
    sub.admin_reference = reference or sub.admin_reference
    sub.admin_note = note or sub.admin_note
    try:
        with transaction.atomic():
            sub.save(
                update_fields=[
                    "status",
                    "starts_at",
                    "ends_at",
                    "activated_by",
                    "admin_reference",
                    "admin_note",
                    "updated_at",
                ]
            )
    except IntegrityError as exc:  # never a 500: another live row won a race
        raise SubscriptionError("Another live subscription exists for this account.") from exc
    _event(sub, previous, SubscriptionStatus.ACTIVE, admin, note)
    audit.record(
        actor=admin,
        action="billing.subscription.activated",
        target=sub,
        summary=f"{sub.plan.code} until {sub.ends_at}",
        data={"reference": reference},
    )
    return sub


@transaction.atomic
def _transition(
    sub: Subscription,
    to_status: str,
    *,
    admin,
    reason: str,
    action: str,
    allowed_from: tuple[str, ...],
) -> Subscription:
    sub.status = (
        Subscription.objects.select_for_update()
        .filter(pk=sub.pk)
        .values_list("status", flat=True)
        .get()
    )
    if sub.status not in allowed_from:
        raise SubscriptionError(f"Cannot move a subscription from {sub.status} to {to_status}.")
    previous = sub.status
    sub.status = to_status
    sub.admin_note = reason or sub.admin_note
    sub.save(update_fields=["status", "admin_note", "updated_at"])
    _event(sub, previous, to_status, admin, reason)
    audit.record(actor=admin, action=action, target=sub, summary=reason)
    return sub


def reject_subscription(sub, *, admin, reason=""):
    return _transition(
        sub,
        SubscriptionStatus.REJECTED,
        admin=admin,
        reason=reason,
        action="billing.subscription.rejected",
        allowed_from=(SubscriptionStatus.PENDING,),
    )


def suspend_subscription(sub, *, admin, reason=""):
    # An elapsed term is EXPIRED, never SUSPENDED: normalise first (locked,
    # evented, committed on its own), then the transition sees EXPIRED and
    # refuses with the typed error.
    expire_subscription(sub)
    return _transition(
        sub,
        SubscriptionStatus.SUSPENDED,
        admin=admin,
        reason=reason,
        action="billing.subscription.suspended",
        allowed_from=(SubscriptionStatus.ACTIVE,),
    )


def cancel_subscription(sub, *, admin, reason=""):
    expire_subscription(sub)  # same rule as suspend: ACTIVE + elapsed → EXPIRED, not CANCELLED
    return _transition(
        sub,
        SubscriptionStatus.CANCELLED,
        admin=admin,
        reason=reason,
        action="billing.subscription.cancelled",
        allowed_from=(
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.SUSPENDED,
            SubscriptionStatus.PENDING,
        ),
    )


@transaction.atomic
def expire_subscription(sub) -> bool:
    """Read-time expiry under the subscription row lock: only a row that is
    STILL ACTIVE with an elapsed term becomes EXPIRED, so a concurrent admin
    suspension/cancellation is never overwritten and two concurrent lookups
    produce exactly one ACTIVE → EXPIRED event. Lock order is unchanged
    (billing account, when held, before the subscription row)."""
    sub.status, sub.ends_at = (
        Subscription.objects.select_for_update()
        .filter(pk=sub.pk)
        .values_list("status", "ends_at")
        .get()
    )
    if sub.status != SubscriptionStatus.ACTIVE or not _has_elapsed(sub):
        return False
    previous = sub.status
    sub.status = SubscriptionStatus.EXPIRED
    sub.save(update_fields=["status", "updated_at"])
    _event(sub, previous, SubscriptionStatus.EXPIRED, None, "term ended")
    return True


def _has_elapsed(sub: Subscription) -> bool:
    return bool(sub.ends_at and sub.ends_at < timezone.now())


def expire_elapsed_subscriptions(billing_account: BillingAccount) -> int:
    """Read-time normalisation: ACTIVE rows whose term ended become EXPIRED.
    Called by every entitlement resolution and by subscription requests."""
    count = 0
    for sub in Subscription.objects.filter(
        billing_account=billing_account,
        status=SubscriptionStatus.ACTIVE,
        ends_at__lt=timezone.now(),
    ):
        expire_subscription(sub)
        count += 1
    return count


def expire_all_elapsed_subscriptions() -> int:
    """Read-time normalisation for staff listings: every ACTIVE row whose term
    ended becomes EXPIRED through the same locked, evented path
    (`expire_subscription`). Only rows that are actually elapsed are touched,
    one short transaction each, so the work is bounded by the number of
    not-yet-normalised rows and a repeated call finds nothing to do."""
    count = 0
    for sub in Subscription.objects.filter(
        status=SubscriptionStatus.ACTIVE, ends_at__lt=timezone.now()
    ).order_by("pk"):
        if expire_subscription(sub):
            count += 1
    return count


@transaction.atomic
def grant_credits(
    billing_account: BillingAccount, key: str, amount: int, *, admin, note: str = ""
) -> CreditBalance:
    if amount == 0:
        raise SubscriptionError("Amount must not be zero.")
    balance, _ = CreditBalance.objects.select_for_update().get_or_create(
        billing_account=billing_account, key=key
    )
    if balance.balance + amount < 0:
        raise SubscriptionError("Cannot revoke more credits than the balance.")
    balance.balance = balance.balance + amount
    balance.save(update_fields=["balance", "updated_at"])
    CreditTransaction.objects.create(
        billing_account=billing_account,
        key=key,
        delta=amount,
        reason=CreditReason.GRANT if amount > 0 else CreditReason.REVOKE,
        actor=admin,
        note=note,
    )
    audit.record(
        actor=admin,
        action="billing.credits.granted" if amount > 0 else "billing.credits.revoked",
        target=balance,
        summary=f"{key} {amount:+d}",
        data={"note": note},
    )
    return balance
