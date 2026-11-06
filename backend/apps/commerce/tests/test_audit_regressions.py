# ruff: noqa: F811  (pytest fixtures re-exported from test_marketplace_finance)
"""Regression tests for the independent financial/security audit of 2026-11-06
(docs/local-commerce-implementation-matrix.md §Audit). Each block names the finding it pins."""

import importlib
import threading
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.commerce import lifecycle
from apps.commerce.models import Checkout, Order
from apps.demo import cleaner
from apps.ledger import dbroles, posting, settlement
from apps.ledger.models import LedgerEntry, LedgerLine, SellerRecovery
from apps.ledger.settlement import SettlementError, reconciliation
from apps.ledger.types import Account
from apps.marketplace.models import Product, ProductCategory
from apps.marketplace.types import BusinessType, SaleChannel
from apps.providers.types import ProviderType
from apps.workspaces.models import OrganizationMember

from .conftest import client_for
from .test_marketplace_finance import (  # noqa: F401  (fixture re-export)
    ADMIN,
    CHECKOUTS,
    LEDGER,
    MERCHANT,
    ORDERS,
    _deliver_pay_complete,
    _order,
    _post,
    _reconciled,
    _return,
    hundred_k,
)

D = Decimal
pytestmark = pytest.mark.django_db


def _payable(store):
    return posting.balance(Account.SELLER_PAYABLE, company_id=store.pk)


def _receivable(store):
    return settlement.receivable(store.pk)


def _pay_out(finance, store):
    fin = client_for(finance)
    draft = _post(fin, f"{LEDGER}/settlements/prepare", {"company": str(store.pk)}, expect=201)
    return _post(fin, f"{LEDGER}/settlements/{draft['id']}/confirm", {"reference_note": "SIM-OUT"})


def _dispute_refund(buyer, finance, order_id):
    opened = _post(client_for(buyer), f"{ORDERS}/{order_id}/disputes", {"reason": "Broken (demo)"})
    dispute_id = next(d["id"] for d in opened["disputes"] if d["status"] == "OPEN")
    return _post(
        client_for(finance),
        f"{ADMIN}/disputes/{dispute_id}/resolve",
        {"refund": True, "note": "Refund approved"},
    )


# ---- Finding 1: refund after a confirmed payout -------------------------------------------------
# Before: the refund debited SELLER_PAYABLE below zero (-80,000) and reconciliation failed.


def test_full_refund_after_payout_creates_a_receivable_not_a_negative_payable(
    buyer, finance, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    _pay_out(finance, store)
    assert (_payable(store), _receivable(store)) == (0, 0)
    refunded = _dispute_refund(buyer, finance, order_id)
    assert refunded["payment_status"] == "REFUNDED"
    assert _payable(store) == 0  # never negative
    assert _receivable(store) == D("80000")  # the seller owes back what it was paid for this sale
    assert posting.balance(Account.COMMISSION_REVENUE) == 0  # Racheeta's fee is reversed too
    report = _reconciled()
    assert {c["name"] for c in report["checks"]} >= {
        "balance:SELLER_NET",
        "no_negative_seller_payable",
        "no_negative_seller_receivable",
        "payable_and_receivable_netted",
    }
    statement = client_for(store.account).get(f"{MERCHANT}/finance").json()
    assert D(statement["receivable"]) == D("80000") and D(statement["payable"]) == 0


def test_partial_refund_after_payout_is_offset_by_the_next_sales(
    buyer, finance, store, hundred_k, checkout
):
    first = _order(buyer, checkout, [(hundred_k, 2)])
    _deliver_pay_complete(buyer, finance, store, first)
    _pay_out(finance, store)  # 160,000 paid out
    _return(buyer, store, finance, first, 1)  # one unit back: seller part 80,000
    assert (_payable(store), _receivable(store)) == (0, D("80000"))
    _reconciled()

    second = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, second)  # seller part 80,000 settles the debt
    assert (_payable(store), _receivable(store)) == (0, 0)
    _post(
        client_for(finance),
        f"{LEDGER}/settlements/prepare",
        {"company": str(store.pk)},
        expect=400,
    )  # nothing owed: the sale paid back the receivable

    third = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, third)
    assert (_payable(store), _receivable(store)) == (D("80000"), 0)
    _reconciled()


def test_refund_takes_from_what_is_still_held_before_creating_a_receivable(
    buyer, finance, store, hundred_k, checkout
):
    paid_out = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, paid_out)
    _pay_out(finance, store)
    held = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, held)  # 80,000 held for the seller
    _return(buyer, store, finance, paid_out, 1)  # refund an ALREADY PAID-OUT sale
    assert (_payable(store), _receivable(store)) == (0, 0)  # netted against what is held
    _reconciled()


def test_finance_records_recovery_never_more_than_owed(
    buyer, finance, support_staff, store, hundred_k, checkout
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    _pay_out(finance, store)
    _dispute_refund(buyer, finance, order_id)
    url = f"{LEDGER}/recoveries"
    body = {"company": str(store.pk), "amount": "30000", "reference_note": "SIM-BACK-1"}
    for outsider in (support_staff, store.account, buyer):
        assert client_for(outsider).post(url, body, format="json").status_code == 403
    fin = client_for(finance)
    _post(fin, url, dict(body, amount="90000"), expect=400)  # more than owed
    _post(fin, url, dict(body, amount="0"), expect=400)
    _post(fin, url, body, expect=201)
    _post(fin, url, dict(body, amount="50000", reference_note="SIM-BACK-2"), expect=201)
    assert _receivable(store) == 0 and SellerRecovery.objects.count() == 2
    _post(fin, url, dict(body, amount="1"), expect=400)  # nothing left to recover
    assert (
        -posting.balance(Account.PLATFORM_CASH) == 0
    )  # in 100k, out 80k payout + 100k refund, back 80k
    _reconciled()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("round_", range(3))
def test_refund_racing_a_payout_confirmation_stays_consistent(
    buyer, finance, store, hundred_k, checkout, round_
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    draft = settlement.prepare(store.pk, actor=finance)
    dispute = lifecycle.open_dispute(order_id, buyer=buyer, reason="Broken")
    barrier = threading.Barrier(2)
    outcomes = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=5)
            fn()
            outcomes[name] = "ok"
        except Exception as exc:  # noqa: BLE001 — the outcome is asserted below
            outcomes[name] = getattr(exc, "code", type(exc).__name__)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=run,
            args=(
                "payout",
                lambda: settlement.confirm(draft.pk, actor=finance, reference_note="R"),
            ),
        ),
        threading.Thread(
            target=run,
            args=(
                "refund",
                lambda: lifecycle.resolve_dispute(
                    dispute.pk, actor=finance, refund=True, note="ok"
                ),
            ),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert outcomes["refund"] == "ok"
    assert _payable(store) == 0
    if outcomes["payout"] == "ok":  # payout first: the refund became a receivable
        assert _receivable(store) == D("80000")
    else:  # refund first: the draft no longer matched what is owed
        assert outcomes["payout"] == "stale" and _receivable(store) == 0
    assert reconciliation()["ok"]


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_refunds_after_payout_at_once_add_up(buyer, finance, store, hundred_k, checkout):
    orders = [_order(buyer, checkout, [(hundred_k, 1)]) for _ in range(2)]
    for order_id in orders:
        _deliver_pay_complete(buyer, finance, store, order_id)
    settlement.confirm(
        settlement.prepare(store.pk, actor=finance).pk, actor=finance, reference_note="x"
    )
    disputes = [lifecycle.open_dispute(o, buyer=buyer, reason="Broken") for o in orders]
    barrier = threading.Barrier(2)
    errors = []

    def refund(dispute):
        try:
            barrier.wait(timeout=5)
            lifecycle.resolve_dispute(dispute.pk, actor=finance, refund=True, note="ok")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=refund, args=(d,)) for d in disputes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert not errors
    assert (_payable(store), _receivable(store)) == (0, D("160000"))
    assert reconciliation()["ok"]


# ---- Finding 2: ledger immutability at the database level ---------------------------------------
# Before: any session could `set_config('racheeta.ledger_purge','on')` and delete history, and
# TRUNCATE bypassed the row triggers entirely.


def _completed_ledger(buyer, finance, store, hundred_k, checkout):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    return order_id


def test_the_session_purge_flag_no_longer_bypasses_immutability(
    buyer, finance, store, hundred_k, checkout
):
    _completed_ledger(buyer, finance, store, hundred_k, checkout)
    before = LedgerLine.objects.count()
    for statement in (
        "UPDATE ledger_line SET debit = debit + 1 WHERE debit > 0",
        "UPDATE ledger_entry SET memo = 'edited'",
        "DELETE FROM ledger_line",
        "DELETE FROM ledger_entry",
        "UPDATE ledger_commission_policy SET rate_percent = 0",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT set_config('racheeta.ledger_purge', 'on', true)")
            cursor.execute(statement)
    assert LedgerLine.objects.count() == before
    # an ORM re-save of identical values is not a change and stays possible
    line = LedgerLine.objects.first()
    with connection.cursor() as cursor:
        cursor.execute("UPDATE ledger_line SET debit = debit WHERE id = %s", [line.pk])


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_truncate_of_ledger_tables_is_refused(buyer, finance, store, hundred_k, checkout):
    _completed_ledger(buyer, finance, store, hundred_k, checkout)
    before = LedgerLine.objects.count()
    for table in ("ledger_line", "ledger_entry"):  # both hold rows
        with pytest.raises(DatabaseError, match="TRUNCATE refused"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"TRUNCATE {table} CASCADE")
    assert LedgerLine.objects.count() == before > 0
    # an EMPTY append-only table can be truncated: nothing is destroyed
    assert not SellerRecovery.objects.exists()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("TRUNCATE ledger_recovery")


def _can_create_roles():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user"
        )
        return cursor.fetchone()[0]


def test_a_restricted_runtime_role_cannot_change_history_even_with_tricks(
    buyer, finance, store, hundred_k, checkout
):
    """The production setup: the app connects with a role that does not own the tables and holds
    only SELECT/INSERT (dbroles.runtime_role_sql). Created inside this test's transaction, so the
    role never outlives the test."""
    if not _can_create_roles():
        pytest.skip("the test database user cannot create roles")
    _completed_ledger(buyer, finance, store, hundred_k, checkout)
    with connection.cursor() as cursor:
        cursor.execute("CREATE ROLE racheeta_audit_runtime NOLOGIN")
        for statement in dbroles.runtime_role_sql("racheeta_audit_runtime"):
            cursor.execute(statement)
        cursor.execute("SET LOCAL ROLE racheeta_audit_runtime")
        cursor.execute("SELECT count(*) FROM ledger_line")
        assert cursor.fetchone()[0] > 0  # it can read
        report = dbroles.audit()
        assert report["problems"] == [], report["problems"]
        for statement in (
            "UPDATE ledger_line SET debit = debit + 1",
            "DELETE FROM ledger_line",
            "TRUNCATE ledger_line",
            "ALTER TABLE ledger_line DISABLE TRIGGER ledger_line_immutable",
            "DROP TRIGGER ledger_line_immutable ON ledger_line",
        ):
            cursor.execute("SAVEPOINT probe")
            with pytest.raises(DatabaseError):
                cursor.execute("SELECT set_config('racheeta.ledger_purge', 'on', true)")
                cursor.execute(statement)
            cursor.execute("ROLLBACK TO SAVEPOINT probe")
        cursor.execute("RESET ROLE")


def test_ledger_db_audit_flags_an_owner_or_superuser_connection():
    report = dbroles.audit()
    assert any("owns ledger_line" in p or "superuser" in p for p in report["problems"])
    assert not any("bypass" in p or "missing" in p or "DISABLED" in p for p in report["problems"])
    with pytest.raises(CommandError):
        call_command("ledger_db_audit", "--strict")
    statements = dbroles.runtime_role_sql("app_runtime")
    assert 'GRANT SELECT, INSERT ON TABLE ledger_line TO "app_runtime";' in statements
    assert not any("UPDATE" in s and "ledger_line" in s and "GRANT" in s for s in statements)


def test_demo_cleaner_unlocks_the_ledger_only_on_the_guarded_local_demo_db(monkeypatch):
    assert cleaner._allow_ledger_cleanup({"accounts.Account": {"x"}}, "default") is False
    with pytest.raises(cleaner.ClearRefused, match="disposable local demo"):
        cleaner._allow_ledger_cleanup({"ledger.LedgerEntry": {"x"}}, "default")  # test DB: refused


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_demo_cleaner_triggers_come_back_after_its_transaction(
    monkeypatch, buyer, finance, store, hundred_k, checkout
):
    _completed_ledger(buyer, finance, store, hundred_k, checkout)
    monkeypatch.setattr("apps.demo.local_guard.check", lambda *a, **k: [])
    with transaction.atomic():
        assert cleaner._allow_ledger_cleanup({"ledger.LedgerLine": {"x"}}, "default") is True
        cleaner._restore_ledger_triggers("default")
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM ledger_line")


# ---- Finding 3: legacy compliance classification (marketplace 0004 -> 0005) ----------------------

migration_0004 = importlib.import_module(
    "apps.marketplace.migrations.0004_compliance_and_reservations"
)
migration_0005 = importlib.import_module(
    "apps.marketplace.migrations.0005_tighten_legacy_compliance"
)


def _legacy(category_factory, slug, *, consumer, active=True):
    category = category_factory(slug=slug, consumer_allowed=consumer, is_active=active)
    ProductCategory.objects.filter(pk=category.pk).update(
        compliance_class="RESTRICTED_PENDING_REVIEW"
    )
    return category


def test_legacy_migration_never_authorizes_more_than_before(
    category_factory, store, product_factory
):
    clean = _legacy(category_factory, "legacy-clean", consumer=True)
    inactive = _legacy(category_factory, "legacy-inactive", consumer=True, active=False)
    mixed = _legacy(category_factory, "legacy-mixed", consumer=True)
    pro = _legacy(category_factory, "legacy-pro", consumer=False)
    product_factory(store, mixed, price=D("10"), sale_channel=SaleChannel.B2B, is_restricted=True)
    migration_0004.classify_existing(django_apps, None)
    migration_0005.tighten(django_apps, None)
    migration_0005.tighten(django_apps, None)  # idempotent
    result = dict(
        ProductCategory.objects.filter(
            pk__in=[clean.pk, inactive.pk, mixed.pk, pro.pk]
        ).values_list("slug", "compliance_class")
    )
    assert result == {
        "legacy-clean": "B2C_ALLOWED",
        "legacy-inactive": "RESTRICTED_PENDING_REVIEW",
        "legacy-mixed": "RESTRICTED_PENDING_REVIEW",
        "legacy-pro": "QUOTE_ONLY",
    }


def test_previously_published_products_keep_only_their_old_purchase_paths(
    store, category_factory, product_factory, provider_factory, buyer, checkout
):
    consumer = _legacy(category_factory, "legacy-consumer", consumer=True)
    ProductCategory.objects.filter(pk=consumer.pk).update(compliance_class="B2C_ALLOWED")
    from apps.marketplace.models import ProductAudience

    ProductAudience.objects.create(category=consumer, provider_type=ProviderType.DOCTOR)
    store_item = product_factory(
        store, consumer, price=D("20000"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    pro_item = product_factory(
        store, consumer, price=D("90000"), sale_channel=SaleChannel.B2B, stock_quantity=5
    )
    doctor = provider_factory(provider_type=ProviderType.DOCTOR)
    type(doctor.account).objects.filter(pk=doctor.account_id).update(
        email_verified_at=timezone.now()
    )
    doctor.account.refresh_from_db()
    # the public store item still sells (it did before)
    assert (
        client_for(buyer).post(CHECKOUTS, checkout([(store_item, 1)]), format="json").status_code
        == 201
    )
    # the B2B item in a legacy consumer category was only ever quotable: no direct purchase now
    refused = client_for(doctor.account).post(CHECKOUTS, checkout([(pro_item, 1)]), format="json")
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "quote_only"
    quote = client_for(doctor.account).post(
        "/api/v1/quotes", {"product": str(pro_item.pk), "quantity": 1}, format="json"
    )
    assert quote.status_code == 201  # the quotation path is unchanged


def test_regulated_and_unreviewed_products_never_reach_the_store(
    api_client, store, category_factory, product_factory, buyer, checkout
):
    unreviewed = category_factory(slug="brand-new", consumer_allowed=True)
    ProductCategory.objects.filter(pk=unreviewed.pk).update(
        compliance_class="RESTRICTED_PENDING_REVIEW"
    )
    new_item = product_factory(
        store, unreviewed, price=D("5000"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    mixed = _legacy(category_factory, "mixed-store", consumer=True)
    ProductCategory.objects.filter(pk=mixed.pk).update(compliance_class="B2C_ALLOWED")
    was_public = product_factory(
        store, mixed, price=D("5000"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    product_factory(store, mixed, price=D("5000"), sale_channel=SaleChannel.B2B, is_restricted=True)
    listed = {r["id"] for r in api_client.get("/api/v1/store/products").json()["results"]}
    assert str(was_public.pk) in listed  # before the tightening migration it was public
    migration_0005.tighten(django_apps, None)
    listed = {r["id"] for r in api_client.get("/api/v1/store/products").json()["results"]}
    assert str(was_public.pk) not in listed and str(new_item.pk) not in listed
    for item in (new_item, was_public):
        response = client_for(buyer).post(CHECKOUTS, checkout([(item, 1)]), format="json")
        assert response.status_code == 403 and response.json()["error"]["code"] == "not_purchasable"
    assert not Order.objects.exists()


# ---- Finding 4: idempotency-key reuse with a different request ----------------------------------
# Before: the second request silently returned the FIRST checkout (quantity 5 ignored, 200).


@pytest.mark.parametrize(
    "change",
    [
        {"items": "qty"},
        {"coupons": ["SOMECODE"]},
        {"address": "Another street 9"},
        {"payment_method": "MANUAL_TRANSFER"},
        {"phone": "07701112222"},
    ],
)
def test_reusing_a_key_for_a_different_request_is_refused(buyer, hundred_k, checkout, change):
    body = checkout([(hundred_k, 1)])
    client = client_for(buyer)
    assert client.post(CHECKOUTS, body, format="json").status_code == 201
    other = dict(body)
    if change.get("items"):
        other["items"] = [{"product": str(hundred_k.pk), "quantity": 5}]
    else:
        other.update(change)
    response = client.post(CHECKOUTS, other, format="json")
    assert response.status_code == 409, response.json()
    assert response.json()["error"]["code"] == "idempotency_conflict"
    assert Checkout.objects.count() == 1 and Order.objects.count() == 1
    hundred_k.refresh_from_db()
    assert hundred_k.stock_reserved == 1


def test_the_same_request_again_is_a_replay_whatever_the_line_order(
    buyer, hundred_k, store, store_category, product_factory, checkout, account_factory
):
    cane = product_factory(
        store, store_category, price=D("5000"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    body = checkout([(hundred_k, 1), (cane, 2)])
    client = client_for(buyer)
    first = client.post(CHECKOUTS, body, format="json")
    reordered = dict(body, items=list(reversed(body["items"])))
    again = client.post(CHECKOUTS, reordered, format="json")
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    someone_else = account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())
    assert client_for(someone_else).post(CHECKOUTS, body, format="json").status_code == 201


# ---- Organization scoping of every seller-facing endpoint ---------------------------------------


@pytest.fixture
def two_sellers(buyer, finance, store, hundred_k, checkout, company_factory, account_factory):
    """`store` with a completed order, a return, a coupon and a sale; a rival business and a rival
    MANAGER who has every capability — but only in the rival business."""
    from apps.commerce.models import Coupon, ProductOffer

    order_id = _order(buyer, checkout, [(hundred_k, 2)])
    _deliver_pay_complete(buyer, finance, store, order_id)
    item = Order.objects.get(pk=order_id).items.get()
    returned = _post(
        client_for(buyer),
        f"{ORDERS}/{order_id}/returns",
        {"lines": [{"item": str(item.pk), "quantity": 1}], "reason": "demo"},
    )
    now = timezone.now()
    coupon = Coupon.objects.create(
        code="MINE",
        funded_by="SELLER",
        company=store,
        kind="FIXED",
        value=D("1000"),
        starts_at=now,
        ends_at=now + timezone.timedelta(days=1),
    )
    offer = ProductOffer.objects.create(
        company=store,
        product=hundred_k,
        percent=D("5"),
        starts_at=now,
        ends_at=now + timezone.timedelta(days=1),
    )
    rival = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    manager = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=manager, company=rival, role="MANAGER", added_by=rival.account
    )
    return {
        "order": order_id,
        "return": returned["returns"][0]["id"],
        "coupon": str(coupon.pk),
        "offer": str(offer.pk),
        "product": str(hundred_k.pk),
        "rival": rival,
        "manager": manager,
    }


READS = [
    "merchant/orders",
    "merchant/orders/{order}",
    "merchant/returns",
    "merchant/inventory",
    "merchant/inventory/{product}/movements",
    "merchant/coupons",
    "merchant/offers",
    "merchant/finance",
    "merchant/quotes",
]
WRITES = [
    ("merchant/orders/{order}/transition", {"status": "CANCELLED"}),
    ("merchant/returns/{return}/decide", {"approve": True}),
    ("merchant/returns/{return}/received", {}),
    ("merchant/inventory/{product}/adjust", {"delta": -1, "reason": "x"}),
    ("merchant/inventory/{product}/threshold", {"threshold": 1}),
    ("merchant/coupons/{coupon}/deactivate", {}),
    ("merchant/offers/{offer}/deactivate", {}),
    (
        "merchant/offers",
        {"product": "{product}", "percent": "10", "ends_at": "2099-01-01T00:00:00Z"},
    ),
]


def _fill(text, ids):
    return text.format(**ids) if isinstance(text, str) else text


def test_seller_endpoints_never_cross_organizations(two_sellers, store):
    ids = {k: v for k, v in two_sellers.items() if isinstance(v, str)}
    rival_owner = client_for(two_sellers["rival"].account)
    rival_manager = client_for(two_sellers["manager"])
    foreign = f"?company={store.pk}"
    for client in (rival_owner, rival_manager):
        for path in READS:
            url = f"/api/v1/{_fill(path, ids)}"
            # asking for the other business explicitly: refused
            assert client.get(url + foreign).status_code == 403, url
            # within its own business: the other business's records simply do not exist
            own = client.get(
                url + ("" if client is rival_owner else f"?company={two_sellers['rival'].pk}")
            )
            # 403 = its own role lacks that tool (e.g. a MANAGER has no finance view): no leak
            assert own.status_code in (200, 403, 404), (url, own.status_code)
            if own.status_code == 200:
                text = own.content.decode()
                for secret in (ids["order"], ids["return"], ids["coupon"], ids["offer"], "MINE"):
                    assert secret not in text, (url, secret)
        for path, body in WRITES:
            url = f"/api/v1/{_fill(path, ids)}"
            payload = {k: _fill(v, ids) for k, v in body.items()}
            assert client.post(url + foreign, payload, format="json").status_code == 403, url
            own_q = "" if client is rival_owner else f"?company={two_sellers['rival'].pk}"
            response = client.post(url + own_q, payload, format="json")
            assert response.status_code in (400, 403, 404), (url, response.status_code)
    # nothing changed for the real seller
    assert Order.objects.get(pk=two_sellers["order"]).status == "COMPLETED"
    assert Product.objects.get(pk=two_sellers["product"]).stock_quantity == 8


def test_an_ended_membership_loses_every_seller_tool_at_once(two_sellers, store, account_factory):
    member = account_factory(role=AccountRole.PATIENT)
    membership = OrganizationMember.objects.create(
        account=member, company=store, role="MANAGER", added_by=store.account
    )
    client = client_for(member)
    assert client.get(f"/api/v1/merchant/orders?company={store.pk}").status_code == 200
    membership.status = "ENDED"
    membership.ended_at = timezone.now()
    membership.save()
    for path in READS:
        url = (
            f"/api/v1/{path.format(**{k: v for k, v in two_sellers.items() if isinstance(v, str)})}"
        )
        assert client.get(f"{url}?company={store.pk}").status_code == 403, url


def test_a_seller_never_sees_the_other_sellers_order_of_the_same_checkout(
    buyer, store, hundred_k, store_category, company_factory, product_factory, checkout
):
    other = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    cane = product_factory(
        other, store_category, price=D("5000"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    placed = _post(client_for(buyer), CHECKOUTS, checkout([(hundred_k, 1), (cane, 1)]), expect=201)
    theirs = next(o["id"] for o in placed["orders"] if o["merchant"]["id"] == str(other.pk))
    mine = client_for(store.account)
    assert mine.get(f"{MERCHANT}/orders/{theirs}").status_code == 404
    listed = mine.get(f"{MERCHANT}/orders").json()["results"]
    assert {o["merchant"]["id"] for o in listed} == {str(store.pk)}
    assert all("checkout" not in key or key == "checkout_number" for key in listed[0])


def test_receivable_lines_require_a_seller_and_payable_cannot_be_posted_negative():
    from apps.ledger.posting import LedgerError, Line

    with pytest.raises(LedgerError):
        posting.post(
            "audit-r1",
            kind="REFUND",
            lines=[
                Line(Account.SELLER_RECEIVABLE, debit=D("5")),
                Line(Account.PLATFORM_CASH, credit=D("5")),
            ],
        )
    assert not LedgerEntry.objects.filter(reference="audit-r1").exists()
    with pytest.raises(SettlementError):
        settlement.record_recovery(
            "00000000-0000-0000-0000-000000000000", actor=None, amount=1, reference_note="x"
        )


# ---- Demo cleaner: ownership is proven transitively, never by absence of references --------------


def test_cleaner_proves_walkthrough_rows_demo_owned_but_never_real_users(
    buyer, store, hundred_k, checkout, account_factory
):
    order_id = _order(buyer, checkout, [(hundred_k, 1)])  # created through the API, unregistered
    order = Order.objects.get(pk=order_id)
    registered = {
        ("accounts.Account", str(buyer.pk)),
        ("accounts.Account", str(store.account_id)),
        ("marketplace.MedicalCompany", str(store.pk)),
    }
    assert cleaner._is_internal(order, registered)  # order → checkout → demo buyer: owned
    real = account_factory(role=AccountRole.PATIENT, email_verified_at=timezone.now())
    real_order = Order.objects.get(pk=_order(real, checkout, [(hundred_k, 1)]))
    assert not cleaner._is_internal(real_order, registered)  # reaches a real (unregistered) user
    # a row with no path into demo data is never inferred as demo data
    assert not cleaner._is_internal(real_order.checkout, registered)


def test_cleaner_removes_a_demo_operators_entry_that_has_no_order(monkeypatch, finance, store):
    """A recovery-style entry references no order or payout; before the fix the clear removed its
    lines and left the entry behind."""
    from apps.demo.models import DemoRecord
    from apps.ledger.posting import Line

    for obj in (finance, store.account, store):
        DemoRecord.objects.create(model_label=obj._meta.label, object_pk=str(obj.pk))
    posting.post(
        "audit-orphan-1",
        kind="RECOVERY",
        actor=finance,
        lines=[
            Line(Account.PLATFORM_CASH, debit=D("100")),
            Line(Account.SELLER_RECEIVABLE, credit=D("100"), company_id=store.pk),
        ],
    )
    # the registry owns one of the lines (as the seed's registry would); the ENTRY is unregistered
    one_line = LedgerLine.objects.filter(entry__reference="audit-orphan-1").first()
    DemoRecord.objects.create(model_label="ledger.LedgerLine", object_pk=str(one_line.pk))
    monkeypatch.setattr("apps.demo.local_guard.check", lambda *a, **k: [])
    plan = cleaner.execute()
    assert not LedgerEntry.objects.filter(reference="audit-orphan-1").exists()
    assert not LedgerLine.objects.exists()
    assert plan.internal["ledger.LedgerEntry"] == 1  # found through its demo operator, counted once
    assert plan.registered["ledger.LedgerLine"] == 1 and plan.internal["ledger.LedgerLine"] == 1
