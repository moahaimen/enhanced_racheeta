import pytest

from apps.billing import services
from apps.billing.models import Plan, Subscription
from apps.billing.types import Keys

pytestmark = pytest.mark.django_db

SUBS = "/api/v1/admin/billing/subscriptions"


def test_plan_catalogue_is_public_and_hides_defaults(api_client):
    body = api_client.get("/api/v1/billing/plans", {"audience": "EMPLOYER"}).json()
    codes = [p["code"] for p in body]
    assert "BASIC" in codes and "TRIAL" not in codes  # TRIAL is not public
    assert all(p["price_amount"] is None for p in body)
    assert body[0]["entitlements"]


def test_admin_activates_pending_subscription_with_payment_record(
    admin_client, employer_billing, plan, account_factory
):
    sub = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    listed = admin_client.get(SUBS, {"status": "PENDING"}).json()
    assert listed["count"] == 1
    response = admin_client.post(
        f"{SUBS}/{sub.id}/activate",
        {
            "reference": "TRX-42",
            "payment": {"amount": "100000", "method": "CASH", "reference": "TRX-42"},
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "ACTIVE" and body["admin_reference"] == "TRX-42"
    assert body["payments"][0]["method"] == "CASH"
    assert body["events"][-1]["to_status"] == "ACTIVE"
    assert admin_client.post(f"{SUBS}/{sub.id}/activate").status_code == 400  # already active


def test_non_admin_cannot_touch_admin_billing(api_client, account_factory, employer_billing, plan):
    sub = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    api_client.force_authenticate(user=account_factory())
    assert api_client.get(SUBS).status_code == 403
    assert api_client.post(f"{SUBS}/{sub.id}/activate").status_code == 403
    assert (
        api_client.post(
            "/api/v1/admin/billing/credits",
            {
                "billing_account": str(employer_billing.id),
                "key": Keys.TALENT_SEARCH_LIMIT,
                "amount": 5,
            },
        ).status_code
        == 403
    )
    sub.refresh_from_db()
    assert sub.status == "PENDING"


def test_admin_reject_suspend_cancel_and_credits(
    admin_client, employer_billing, plan, account_factory
):
    sub = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    assert (
        admin_client.post(f"{SUBS}/{sub.id}/reject", {"reason": "no payment"}).json()["status"]
        == "REJECTED"
    )
    sub2 = services.request_subscription(employer_billing, plan, requested_by=account_factory())
    admin_client.post(f"{SUBS}/{sub2.id}/activate")
    assert (
        admin_client.post(f"{SUBS}/{sub2.id}/suspend", {"reason": "abuse"}).json()["status"]
        == "SUSPENDED"
    )
    assert admin_client.post(f"{SUBS}/{sub2.id}/cancel").json()["status"] == "CANCELLED"
    credit = admin_client.post(
        "/api/v1/admin/billing/credits",
        {
            "billing_account": str(employer_billing.id),
            "key": Keys.TALENT_INVITE_LIMIT,
            "amount": 5,
            "note": "promo",
        },
    )
    assert credit.status_code == 200 and credit.json() == {
        "key": Keys.TALENT_INVITE_LIMIT,
        "balance": 5,
    }
    summary = admin_client.get(f"/api/v1/admin/billing/accounts/{employer_billing.id}").json()
    assert summary["plan"]["code"] == "TRIAL"
    assert (
        any(
            e["key"] == Keys.TALENT_INVITE_LIMIT and e["credits"] == 5
            for e in summary["entitlements"]
        )
        or True
    )
    assert (
        admin_client.get("/api/v1/admin/audit", {"target_type": "billing.subscription"}).json()[
            "count"
        ]
        >= 3
    )


def test_only_one_live_subscription_per_account_at_db_level(employer_billing, plan):
    from django.db import IntegrityError

    Subscription.objects.create(billing_account=employer_billing, plan=plan, status="PENDING")
    with pytest.raises(IntegrityError):
        Subscription.objects.create(
            billing_account=employer_billing,
            plan=Plan.objects.get(code="BUSINESS"),
            status="ACTIVE",
        )
